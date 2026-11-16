"""
BOT PC agent: listens for the BOT phone app on your Wi-Fi (and on Tailscale when you're outside).

    python bot_agent.py

It prints this PC's IP address and a PIN; type the PIN into the phone app once.
The phone finds the PC by itself (UDP discovery on port 8766).
"""
from __future__ import annotations

import win_input  # first: makes the process DPI-aware so all coordinates are real pixels

import asyncio
import ctypes
import hmac
import json
import logging
import os
import secrets
import socket
import subprocess
import sys
import time
import uuid
from datetime import datetime
from logging.handlers import RotatingFileHandler
from pathlib import Path

import websockets

import actions
import matcher
import screen
from overlay import BUBBLE

HERE = Path(__file__).resolve().parent
CONFIG_PATH = HERE / "config.json"
UNMATCHED_PATH = HERE / "unmatched.txt"
LOG_PATH = HERE / "bot.log"
PID_PATH = HERE / "bot.pid"
DEFAULT_PORT = 8765
DISCOVERY_PORT = 8766
DISCOVERY_MAGIC = b"BOT_DISCOVER_V1"
CONFIRM_TIMEOUT = 30          # seconds the phone has to answer "are you sure?"
MAX_BAD_PINS = 5              # per IP, per 5 minutes
TAP_LABELS = {"left": "Clicking", "right": "Right-clicking", "double": "Double-clicking"}

log = logging.getLogger("bot")
_bad_pins: dict[str, list[float]] = {}
_tailscale_ip = ""  # refreshed in the background; shared with the phone for outside access
_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)


def load_config() -> dict:
    cfg = {}
    if CONFIG_PATH.exists():
        cfg = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    changed = False
    if not cfg.get("pin"):
        cfg["pin"] = f"{secrets.randbelow(10**6):06d}"
        changed = True
    if not cfg.get("port"):
        cfg["port"] = DEFAULT_PORT
        changed = True
    for key, default in (("bubble_cursor", True), ("keep_awake_when_charging", True)):
        if key not in cfg:
            cfg[key] = default
            changed = True
    if changed:
        CONFIG_PATH.write_text(json.dumps(cfg, indent=2), encoding="utf-8")
    return cfg


def local_ip() -> str:
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("10.255.255.255", 1))  # no packet is sent; just picks the Wi-Fi interface
        return s.getsockname()[0]
    except OSError:
        return "127.0.0.1"
    finally:
        s.close()


def find_tailscale_ip() -> str:
    for exe in ("tailscale", r"C:\Program Files\Tailscale\tailscale.exe"):
        try:
            out = subprocess.run([exe, "ip", "-4"], capture_output=True, text=True, timeout=5,
                                 creationflags=_NO_WINDOW)
        except (OSError, subprocess.TimeoutExpired):
            continue
        lines = out.stdout.strip().splitlines()
        if out.returncode == 0 and lines:
            return lines[0].strip()
    return ""


CFG: dict = {}


def set_bubble(on: bool) -> None:
    """Switch BOT's bubble cursor on/off and remember it."""
    BUBBLE.set_wanted(on)
    if CFG.get("bubble_cursor") != on:
        CFG["bubble_cursor"] = on
        CONFIG_PATH.write_text(json.dumps(CFG, indent=2), encoding="utf-8")
    log.info("Bubble cursor %s", "on" if on else "off")


def record_unmatched(text: str, lang: str) -> None:
    with UNMATCHED_PATH.open("a", encoding="utf-8") as f:
        f.write(f"{datetime.now():%Y-%m-%d %H:%M:%S}\t{lang}\t{text}\n")


def too_many_bad_pins(ip: str) -> bool:
    now = time.time()
    recent = [t for t in _bad_pins.get(ip, []) if now - t < 300]
    _bad_pins[ip] = recent
    return len(recent) >= MAX_BAD_PINS


def _num(value, default: float, lo: float, hi: float) -> float:
    try:
        v = float(value)
    except (TypeError, ValueError):
        return default
    return max(lo, min(hi, v))


# ---- background jobs ---------------------------------------------------------------

class Discovery(asyncio.DatagramProtocol):
    """The phone broadcasts BOT_DISCOVER_V1 on the Wi-Fi; we answer with our name and port."""

    def __init__(self, port: int):
        self.port = port
        self.transport = None

    def connection_made(self, transport):
        self.transport = transport

    def datagram_received(self, data: bytes, addr):
        if data.strip() != DISCOVERY_MAGIC:
            return
        reply = {"bot": "BOT", "v": 2, "name": socket.gethostname(), "port": self.port,
                 "tailscale": _tailscale_ip}
        self.transport.sendto(json.dumps(reply).encode(), addr)

    def error_received(self, exc):  # e.g. ICMP "port unreachable" on Windows; harmless
        log.debug("Discovery socket error: %s", exc)


async def refresh_tailscale_forever() -> None:
    global _tailscale_ip
    while True:
        ip = await asyncio.to_thread(find_tailscale_ip)
        if ip != _tailscale_ip:
            _tailscale_ip = ip
            if ip:
                log.info("Tailscale address: %s (the phone can reach this PC from outside)", ip)
        await asyncio.sleep(60)


async def keep_awake_forever() -> None:
    """While charging, stop Windows from sleeping so the phone can always reach the PC."""
    es_continuous, es_system_required = 0x80000000, 0x00000001
    set_state = ctypes.windll.kernel32.SetThreadExecutionState
    set_state.restype = ctypes.c_uint
    while True:
        charging = actions.power_status().ACLineStatus == 1
        set_state(ctypes.c_uint(es_continuous | (es_system_required if charging else 0)))
        await asyncio.sleep(60)


# ---- one connected phone -------------------------------------------------------------

class Session:
    def __init__(self, ws):
        self.ws = ws
        self.pending: dict = {}
        self.cursor_hz = 0                      # 0 = not tracking
        self.cursor_task: asyncio.Task | None = None
        self.screen_quality: str | None = None  # None = screen view off
        self.screen_task: asyncio.Task | None = None
        self.ack = asyncio.Event()
        self.geom = win_input.primary_screen()  # area shown in the screen view
        self.buttons_down: set[str] = set()

    def close(self) -> None:
        self.cursor_hz = 0
        self.screen_quality = None
        for task in (self.cursor_task, self.screen_task):
            if task and not task.done():
                task.cancel()
        for name in self.buttons_down:  # never leave a mouse button stuck down
            win_input.button(name, False)
        self.buttons_down.clear()


async def send(ws, **msg) -> None:
    await ws.send(json.dumps(msg, ensure_ascii=False))


async def track_cursor(sess: Session) -> None:
    """Stream the mouse (or BOT's bubble) position so the phone's eyes can follow it."""
    last = None
    try:
        while True:
            hz = sess.cursor_hz
            if not hz:
                break
            bx, by, bot = BUBBLE.position()
            x, y = (bx, by) if bot else win_input.cursor_pos()
            vl, vt, vw, vh = win_input.virtual_screen()
            gl, gt, gw, gh = sess.geom
            data = (round((x - vl) / vw, 3), round((y - vt) / vh, 3),
                    round((x - gl) / gw, 4), round((y - gt) / gh, 4), bot)
            if data != last:
                last = data
                await send(sess.ws, type="cursor", vx=data[0], vy=data[1], mx=data[2], my=data[3], bot=bot)
            await asyncio.sleep(1 / hz)
    except websockets.ConnectionClosed:
        pass


async def stream_screen(sess: Session) -> None:
    """Send JPEG frames of the main monitor. Waits for the phone's ack (no lag pile-up)
    and skips frames that didn't change (saves mobile data)."""
    last_digest, last_sent, last_geom = None, 0.0, None
    try:
        while sess.screen_quality:
            quality = sess.screen_quality
            started = time.monotonic()
            keepalive = started - last_sent > 3
            try:
                jpeg, geom, digest = await asyncio.to_thread(
                    screen.grab, quality, None if keepalive else last_digest)
            except Exception as exc:
                log.warning("Screen capture failed: %s", exc)
                await send(sess.ws, type="screen_error",
                           message="Can't capture the screen right now (is the PC locked?)")
                await asyncio.sleep(2)
                continue
            if geom != last_geom:
                sess.geom = last_geom = geom
                await send(sess.ws, type="screen_info", left=geom[0], top=geom[1],
                           width=geom[2], height=geom[3])
            if jpeg is not None:
                sess.ack.clear()
                await sess.ws.send(jpeg)
                last_digest, last_sent = digest, time.monotonic()
                try:
                    await asyncio.wait_for(sess.ack.wait(), timeout=4)
                except asyncio.TimeoutError:
                    pass
            fps = screen.QUALITY.get(quality, screen.QUALITY["medium"])[2]
            await asyncio.sleep(max(0.0, 1 / fps - (time.monotonic() - started)))
    except websockets.ConnectionClosed:
        pass


def do_tap(u: float, v: float, kind: str, geom) -> None:
    """A tap on the phone's screen view: the bubble glides there, then BOT clicks."""
    left, top, w, h = geom
    x, y = left + u * (w - 1), top + v * (h - 1)
    if not BUBBLE.glide_to(x, y, TAP_LABELS.get(kind, "Clicking")):
        return  # someone at the PC moved the mouse / pressed Esc: don't click
    win_input.move_to(x, y)
    if kind == "right":
        win_input.click("right")
    else:
        win_input.click("left", double=(kind == "double"))
    BUBBLE.pulse()


async def run_match(ws, m: matcher.Match, heard: str) -> None:
    if m.intent in ("bubble_on", "bubble_off"):
        set_bubble(m.intent == "bubble_on")
        await send(ws, type="bubble", on=BUBBLE.wanted)
    ok, message = await asyncio.to_thread(actions.execute, m)
    log.info("  -> %s: %s", "ok" if ok else "FAILED", message)
    await send(ws, type="result", ok=ok, message=message, heard=heard)


async def handle_command(sess: Session, msg: dict) -> None:
    text = str(msg.get("text", "")).strip()[:500]
    lang = str(msg.get("lang", "?"))[:5]
    if not text:
        return
    log.info("Heard [%s]: %s", lang, text)
    m = matcher.match(text)
    if m is None:
        record_unmatched(text, lang)
        log.info("  -> not understood")
        await send(sess.ws, type="result", ok=False, heard=text,
                   message=f"Sorry, I don't know that command yet: \"{text}\"")
        return
    log.info("  -> %s %s", m.intent, m.target or m.arg)
    if m.needs_confirm:
        cid = uuid.uuid4().hex
        sess.pending[cid] = (m, text, time.time())
        await send(sess.ws, type="confirm", id=cid,
                   message=actions.CONFIRM_TEXT.get(m.intent, "Are you sure?"))
        return
    await run_match(sess.ws, m, text)


async def handle_confirm(sess: Session, msg: dict) -> None:
    item = sess.pending.pop(str(msg.get("id", "")), None)
    if item is None:
        return
    m, text, asked_at = item
    if not msg.get("yes"):
        await send(sess.ws, type="result", ok=True, message="Okay, cancelled", heard=text)
    elif time.time() - asked_at > CONFIRM_TIMEOUT:
        await send(sess.ws, type="result", ok=False, message="Too late, please say it again", heard=text)
    else:
        await run_match(sess.ws, m, text)


async def dispatch(sess: Session, msg: dict) -> None:
    kind = msg.get("type")
    if kind == "command":
        await handle_command(sess, msg)
    elif kind == "confirm_reply":
        await handle_confirm(sess, msg)
    elif kind == "cursor_track":
        sess.cursor_hz = int(_num(msg.get("hz"), 15, 1, 30)) if msg.get("on") else 0
        if sess.cursor_hz and (sess.cursor_task is None or sess.cursor_task.done()):
            sess.cursor_task = asyncio.create_task(track_cursor(sess))
    elif kind == "screen":
        quality = str(msg.get("quality", "medium"))
        sess.screen_quality = (quality if quality in screen.QUALITY else "medium") if msg.get("on") else None
        if sess.screen_quality and (sess.screen_task is None or sess.screen_task.done()):
            sess.ack.set()
            sess.screen_task = asyncio.create_task(stream_screen(sess))
    elif kind == "frame_ack":
        sess.ack.set()
    elif kind == "set_bubble":
        set_bubble(bool(msg.get("on")))
        await send(sess.ws, type="bubble", on=BUBBLE.wanted)
    elif kind == "tap":
        u, v = _num(msg.get("u"), -1, -1, 2), _num(msg.get("v"), -1, -1, 2)
        if 0 <= u <= 1 and 0 <= v <= 1:
            await asyncio.to_thread(do_tap, u, v, str(msg.get("button", "left")), sess.geom)
    elif kind == "mouse_move":
        win_input.move_rel(_num(msg.get("dx"), 0, -3000, 3000), _num(msg.get("dy"), 0, -3000, 3000))
    elif kind == "mouse_click":
        name = "right" if msg.get("button") == "right" else "left"
        win_input.click(name, double=bool(msg.get("double")))
    elif kind == "mouse_button":
        name = "right" if msg.get("button") == "right" else "left"
        down = bool(msg.get("down"))
        win_input.button(name, down)
        (sess.buttons_down.add if down else sess.buttons_down.discard)(name)
    elif kind == "scroll":
        win_input.scroll(int(_num(msg.get("notches"), 0, -30, 30)))
    elif kind == "type_text":
        text = str(msg.get("text", ""))[:2000]
        if text:
            await asyncio.to_thread(actions.paste_text, text)
    elif kind == "key":
        await asyncio.to_thread(actions.press_key, str(msg.get("key", "")))


def make_handler(cfg: dict):
    async def handler(ws):
        ip = ws.remote_address[0] if ws.remote_address else "?"
        try:
            hello = json.loads(await asyncio.wait_for(ws.recv(), timeout=10))
        except (asyncio.TimeoutError, json.JSONDecodeError, websockets.ConnectionClosed, TypeError):
            return
        if not isinstance(hello, dict):
            return
        if too_many_bad_pins(ip):
            await send(ws, type="error", fatal=True, message="Too many wrong PINs. Wait 5 minutes.")
            return
        pin = str(hello.get("pin", ""))
        if hello.get("type") != "hello" or not hmac.compare_digest(pin, cfg["pin"]):
            _bad_pins.setdefault(ip, []).append(time.time())
            log.warning("Wrong PIN from %s", ip)
            await asyncio.sleep(1)
            await send(ws, type="error", fatal=True, message="Wrong PIN. Check the PIN shown on the PC.")
            return

        log.info("Phone connected from %s", ip)
        await send(ws, type="welcome", pc=socket.gethostname(), tailscale=_tailscale_ip,
                   bubble=BUBBLE.wanted, features=["cursor", "screen", "touchpad", "keys", "bubble"])
        sess = Session(ws)
        try:
            async for raw in ws:
                if not isinstance(raw, str):
                    continue
                try:
                    msg = json.loads(raw)
                except json.JSONDecodeError:
                    continue
                if isinstance(msg, dict):
                    try:
                        await dispatch(sess, msg)
                    except websockets.ConnectionClosed:
                        raise
                    except Exception:
                        log.exception("Failed to handle %s", msg.get("type"))
        except websockets.ConnectionClosed:
            pass
        finally:
            sess.close()
            log.info("Phone disconnected (%s)", ip)

    return handler


def show(text: str) -> None:
    """Print to the console if there is one (there isn't when started in the background)."""
    if sys.stdout is not None:
        print(text, flush=True)


async def main() -> int:
    cfg = load_config()
    CFG.update(cfg)
    cfg = CFG
    port = int(cfg["port"])
    try:
        server = await websockets.serve(make_handler(cfg), "0.0.0.0", port, max_size=64 * 1024)
    except OSError:
        log.error("Port %s is busy: BOT is probably already running in the background. "
                  "Run 'python autostart.py stop' to stop it.", port)
        return 1

    loop = asyncio.get_running_loop()
    transport = None
    try:
        transport, _ = await loop.create_datagram_endpoint(
            lambda: Discovery(port), local_addr=("0.0.0.0", DISCOVERY_PORT))
    except OSError as exc:
        log.warning("Auto-discovery is off (%s). Enter the IP in the app manually.", exc)

    BUBBLE.wanted = bool(cfg.get("bubble_cursor", True))
    BUBBLE.start()
    jobs = [asyncio.create_task(refresh_tailscale_forever())]
    if cfg.get("keep_awake_when_charging", True):
        jobs.append(asyncio.create_task(keep_awake_forever()))

    PID_PATH.write_text(str(os.getpid()), encoding="utf-8")
    ip = local_ip()
    log.info("BOT running on %s at %s:%s", socket.gethostname(), ip, port)
    line = "=" * 46
    show(f"\n{line}\n  BOT is running on {socket.gethostname()}")
    show(f"  IP address : {ip}\n  Port       : {port}\n  PIN        : {cfg['pin']}")
    show(f"  The app finds this PC automatically; just enter the PIN.\n  Press Ctrl+C to stop.\n{line}\n")
    try:
        await asyncio.Future()
    finally:
        for job in jobs:
            job.cancel()
        server.close()
        if transport:
            transport.close()
        PID_PATH.unlink(missing_ok=True)
    return 0


def setup_logging() -> None:
    handlers: list[logging.Handler] = [
        RotatingFileHandler(LOG_PATH, maxBytes=1_000_000, backupCount=1, encoding="utf-8")]
    if sys.stdout is not None:  # None when started with pythonw (background)
        if hasattr(sys.stdout, "reconfigure"):
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        handlers.append(logging.StreamHandler(sys.stdout))
    logging.basicConfig(level=logging.INFO, format="%(asctime)s  %(message)s",
                        datefmt="%H:%M:%S", handlers=handlers)
    logging.getLogger("websockets").setLevel(logging.WARNING)


if __name__ == "__main__":
    setup_logging()
    try:
        sys.exit(asyncio.run(main()))
    except KeyboardInterrupt:
        show("BOT stopped.")
