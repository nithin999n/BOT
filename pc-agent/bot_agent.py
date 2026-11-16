"""
BOT PC agent: listens for the BOT phone app on your Wi-Fi (and on Tailscale when you're outside).

    python bot_agent.py

It prints this PC's IP address and a PIN; type the PIN into the phone app once.
The phone finds the PC by itself (UDP discovery on port 8766).
"""
from __future__ import annotations

import win_input  # first: makes the process DPI-aware so all coordinates are real pixels

import asyncio
import base64
import ctypes
import hmac
import json
import logging
import os
import re
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
import ai_agent
import matcher
import pyperclip

import autostart
import health
import router
import routines
import tray as tray_mod
from desktop_pet import PET
import screen
import security
import smart
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
    for key, default in (("bubble_cursor", True), ("keep_awake_when_charging", True), ("desktop_pet", True),
                         ("walkaway", {"enabled": False, "minutes": 1})):
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
AGENT = ai_agent.Agent(CFG)
LANG_NAMES = {"en": "English", "hi": "Hindi", "kn": "Kannada", "te": "Telugu"}


def save_config() -> None:
    CONFIG_PATH.write_text(json.dumps(CFG, indent=2), encoding="utf-8")


TRAY = None  # the icon in the Windows system tray


def tray_refresh() -> None:
    if TRAY is not None:
        TRAY.refresh()


def set_pet(on: bool) -> None:
    """Show/hide the little BOT on the PC desktop and remember it."""
    PET.set_wanted(on)
    if CFG.get("desktop_pet") != on:
        CFG["desktop_pet"] = on
        save_config()
    tray_refresh()


def set_bubble(on: bool) -> None:
    """Switch BOT's bubble cursor on/off and remember it."""
    BUBBLE.set_wanted(on)
    if CFG.get("bubble_cursor") != on:
        CFG["bubble_cursor"] = on
        save_config()
    log.info("Bubble cursor %s", "on" if on else "off")
    tray_refresh()


_net = {"mac": "", "broadcast": ""}  # for Wake-on-LAN from the phone
DOWNLOADS = Path.home() / "Downloads" / "BOT"
MAX_UPLOAD = 500 * 1024 * 1024


def find_mac(ip: str) -> dict:
    """MAC address and broadcast address of the network card the phone talks to."""
    ps = (f"$a = Get-NetIPAddress -IPAddress '{ip}' -ErrorAction Stop; "
          "$n = Get-NetAdapter -InterfaceIndex $a.InterfaceIndex; "
          "Write-Output ($n.MacAddress + '|' + $a.PrefixLength)")
    try:
        out = subprocess.run(["powershell", "-NoProfile", "-Command", ps], capture_output=True, text=True,
                             timeout=15, creationflags=_NO_WINDOW).stdout.strip()
        mac, prefix = out.split("|")
        parts = [int(p) for p in ip.split(".")]
        mask = (0xFFFFFFFF << (32 - int(prefix))) & 0xFFFFFFFF
        num = sum(p << (24 - 8 * i) for i, p in enumerate(parts))
        bcast = num | (~mask & 0xFFFFFFFF)
        return {"mac": mac.replace("-", ":").upper(),
                "broadcast": ".".join(str((bcast >> (24 - 8 * i)) & 255) for i in range(4))}
    except Exception as exc:
        log.warning("Couldn't read the network card's MAC address: %s", exc)
        return {"mac": "", "broadcast": ""}


def apply_style() -> None:
    color = str(CFG.get("style", {}).get("color", ""))
    if re.fullmatch(r"#?[0-9a-fA-F]{6}", color):
        BUBBLE.set_color(color)
        PET.set_color(color)


SESSIONS: set = set()           # connected phones
ALERTS: list[dict] = []         # alerts waiting for a phone to connect
_presence = {"last_lan_ip": "", "last_seen": 0.0, "armed": False, "next_ping": 0.0}


def phone_nearby() -> bool:
    """Is your phone on the same Wi-Fi right now? (connected, or answering pings)"""
    if any(s.lan for s in SESSIONS):
        _presence["last_seen"] = time.time()
        return True
    return time.time() - _presence["last_seen"] < 90


async def broadcast(**msg) -> None:
    for s in list(SESSIONS):
        await _send_quietly(s.ws, **msg)


async def push_alert(alert: dict) -> None:
    log.info("Alert: %s - %s", alert["title"], alert["message"])
    if SESSIONS:
        await broadcast(type="alert", **alert)
    else:
        ALERTS.append(alert)  # delivered as "While you were away…" next time
        del ALERTS[:-20]


async def watch_forever() -> None:
    """Every 2 s: health -> phones + desktop BOT; alerts; walk-away lock."""
    watcher = await asyncio.to_thread(health.Watcher)
    tick = 0
    while True:
        try:
            h = await asyncio.to_thread(health.snapshot)
            PET.health = h
            if SESSIONS:
                await broadcast(type="health", **h)
            # presence: ping the phone now and then when it isn't connected over Wi-Fi
            ip = _presence["last_lan_ip"]
            if ip and not any(s.lan for s in SESSIONS) and time.time() > _presence["next_ping"]:
                _presence["next_ping"] = time.time() + 20
                if await asyncio.to_thread(health.ping, ip):
                    _presence["last_seen"] = time.time()
            nearby = phone_nearby()
            if nearby:
                _presence["armed"] = True
            if tick % 2 == 0:
                for alert in await asyncio.to_thread(watcher.check, h, nearby):
                    await push_alert(alert)
            # walk-away lock: phone gone for N minutes, nobody using the PC, not already locked
            wa = CFG.get("walkaway", {})
            if wa.get("enabled") and _presence["armed"] and not nearby:
                away = time.time() - _presence["last_seen"]
                if away >= max(30, int(wa.get("minutes", 1)) * 60) and health.idle_seconds() >= 60 \
                        and not await asyncio.to_thread(health.is_locked):
                    health.lock()
                    _presence["armed"] = False
                    log.info("Walk-away lock: phone left, PC locked")
                    await push_alert({"kind": "walkaway", "title": "PC locked 🔒",
                                      "message": "You walked away, so I locked your PC.",
                                      "time": datetime.now().strftime("%H:%M")})
        except Exception:
            log.exception("watcher tick failed")
        tick += 1
        await asyncio.sleep(2)


def safe_filename(name: str) -> str:
    name = os.path.basename(name.replace("\\", "/")) or "file"
    name = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", name).strip(" .") or "file"
    return name[:150]


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
        net = await asyncio.to_thread(find_mac, local_ip())  # Wi-Fi may have changed
        if net["mac"]:
            _net.update(net)
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
        self.bad_old_words = 0
        self.uploads: dict[str, dict] = {}  # files being sent from the phone
        self.keys_down: set[str] = set()     # gamepad keys being held
        ip = ws.remote_address[0] if ws.remote_address else ""
        # On the home Wi-Fi (not Tailscale 100.x, not this PC itself)?
        self.lan = bool(ip) and not ip.startswith(("100.", "127.")) and ip != "::1"
        if self.lan:
            _presence["last_lan_ip"], _presence["last_seen"] = ip, time.time()

    def close(self) -> None:
        self.cursor_hz = 0
        self.screen_quality = None
        if AGENT.busy and AGENT.owner is self:  # phone went away: don't keep acting on the PC
            AGENT.stop()
        if smart.RUNNER.busy and smart.RUNNER.owner is self:
            smart.RUNNER.stop()
        for item in self.pending.values():
            fut = item.get("future")
            if fut is not None and not fut.done():
                fut.set_result(False)
        for up in self.uploads.values():  # phone went away mid-transfer: remove the partial file
            up["fh"].close()
            Path(up["path"]).unlink(missing_ok=True)
        self.uploads.clear()
        for task in (self.cursor_task, self.screen_task):
            if task and not task.done():
                task.cancel()
        for name in self.buttons_down:  # never leave a mouse button stuck down
            win_input.button(name, False)
        self.buttons_down.clear()
        for key in self.keys_down:  # ...or a game key
            win_input.game_key(key, False)
        self.keys_down.clear()
        if self.lan:
            _presence["last_seen"] = time.time()  # the walk-away timer starts now


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
    if m.intent in ("pet_on", "pet_off"):
        set_pet(m.intent == "pet_on")
        await send(ws, type="pet", on=PET.wanted)
    ok, message = await asyncio.to_thread(actions.execute, m)
    PET.react("happy" if ok else "sad", 1.5)
    log.info("  -> %s: %s", "ok" if ok else "FAILED", message)
    await send(ws, type="result", ok=ok, message=message, heard=heard)


async def handle_command(sess: Session, msg: dict) -> None:
    text = str(msg.get("text", "")).strip()[:500]
    lang = str(msg.get("lang", "?"))[:5]
    if not text:
        return
    log.info("Heard [%s]: %s", lang, text)
    if AGENT.busy or smart.RUNNER.busy:
        if router.is_stop(text):
            AGENT.stop()
            smart.RUNNER.stop()
            await send(sess.ws, type="result", ok=True, message="Stopping…", heard=text)
        else:
            await send(sess.ws, type="result", ok=False, heard=text,
                       message="I'm still working on the last task. Say \"stop\" to cancel it.")
        return
    routine = routines.match(CFG, text)
    if routine is not None:
        await start_routine(sess, routine, lang, heard=text)
        return
    p = smart.plan(text)
    m = p.steps[0] if p and p.is_single_builtin else None
    if p and not p.is_single_builtin:
        if any(isinstance(s, matcher.Match) and s.needs_confirm for s in p.steps):
            await send(sess.ws, type="result", ok=False, heard=text,
                       message="Please say shutdown / restart / sleep on its own, not in a chain.")
            return
        log.info("  -> smart plan: %s", p.steps)
        asyncio.create_task(run_smart(sess, text, lang, p))
        return
    if m is not None and (not AGENT.available or router.prefer_builtin(text, m)):
        log.info("  -> %s %s", m.intent, m.target or m.arg)
        if m.intent in SAFETY_INTENTS:  # "delete it" / "send it": safety word first
            asyncio.create_task(run_smart(sess, text, lang, smart.Plan([m])))
            return
        if m.needs_confirm:
            cid = uuid.uuid4().hex
            sess.pending[cid] = {"kind": "intent", "match": m, "text": text, "at": time.time()}
            await send(sess.ws, type="confirm", id=cid,
                       message=actions.CONFIRM_TEXT.get(m.intent, "Are you sure?"))
            return
        await run_match(sess.ws, m, text)
        return
    if AGENT.available:
        log.info("  -> AI task")
        # A background task, so this connection can still receive "stop" and safety-word replies.
        asyncio.create_task(run_ai(sess, text, lang))
        return
    record_unmatched(text, lang)
    log.info("  -> not understood")
    await send(sess.ws, type="result", ok=False, heard=text,
               message=f"Sorry, I don't know \"{text}\" yet. Tip: say \"click <word>\" to click anything "
                       "on the screen, and join steps with \"and\".")


async def start_routine(sess: Session, routine: dict, lang: str, heard: str = "") -> None:
    steps: list = []
    for step_text in routine["steps"]:
        p = smart.plan(step_text)
        if p is None:
            await send(sess.ws, type="result", ok=False, heard=heard or routine["name"],
                       message=f"Routine “{routine['name']}”: I don't understand the step “{step_text}”.")
            return
        steps.extend(p.steps)
    log.info("  -> routine %s: %s", routine["name"], steps)
    asyncio.create_task(run_smart(sess, " and ".join(routine["steps"]), lang, smart.Plan(steps)))


async def run_smart(sess: Session, text: str, lang: str, p: "smart.Plan") -> None:
    """Free smart mode: click-by-name and chains. Falls back to the AI (if set up) when stuck."""
    loop = asyncio.get_running_loop()
    try:
        guarded = any(isinstance(s, matcher.Match) and s.intent in SAFETY_INTENTS for s in p.steps)
        clicks_something_risky = security.is_sensitive(text) and any(isinstance(s, smart.ClickStep) for s in p.steps)
        if guarded or clicks_something_risky:
            ok = await ask_safety_word(sess, f"This may delete, send or share something:\n“{text}”\n\n"
                                             "Say or type your safety word to continue.")
            if not ok:
                await send(sess.ws, type="result", ok=False, heard=text, busy=False,
                           message=cancelled_msg())
                return

        def progress(message: str) -> None:
            asyncio.run_coroutine_threadsafe(_send_quietly(sess.ws, type="progress", message=message), loop)

        await send(sess.ws, type="progress", message="On it…", busy=True)
        ok, message = await asyncio.to_thread(smart.RUNNER.run, p, progress, sess)
        log.info("  -> smart %s: %s", "ok" if ok else "FAILED", message)
        if not ok and AGENT.available and "couldn't find" in message:
            await send(sess.ws, type="progress", message="Couldn't find it myself, asking the AI…", busy=True)
            await run_ai(sess, text, lang, safety_checked=True)
            return
        await send(sess.ws, type="result", ok=ok, message=message, heard=text, busy=False)
    except websockets.ConnectionClosed:
        pass
    except Exception:
        log.exception("Smart task crashed")
        await _send_quietly(sess.ws, type="result", ok=False, heard=text, busy=False,
                            message="Something went wrong with that task (see bot.log).")


SAFETY_INTENTS = {"send_enter", "delete_key"}  # always ask for the safety word first
QUICK_ACTIONS = {"lock", "mute", "play_pause", "screenshot", "show_desktop", "volume_up", "volume_down"}

NO_WORD_MSG ="This needs your safety word, but you haven't set one yet. Set it in the app: ⋮ menu → Set safety word."


def cancelled_msg() -> str:
    return "Cancelled: safety word not confirmed." if security.is_set(CFG) else NO_WORD_MSG


async def ask_safety_word(sess: Session, message: str) -> bool:
    """Ask the phone for the safety word; True only if the right word comes back."""
    if not security.is_set(CFG):
        await send(sess.ws, type="progress", message=NO_WORD_MSG)
        return False
    fut = asyncio.get_running_loop().create_future()
    cid = uuid.uuid4().hex
    sess.pending[cid] = {"kind": "keyword", "future": fut, "attempts": 0, "message": message}
    try:
        await send(sess.ws, type="confirm", id=cid, message=message, keyword=True)
        return await asyncio.wait_for(fut, timeout=150)
    except (asyncio.TimeoutError, websockets.ConnectionClosed):
        return False
    finally:
        sess.pending.pop(cid, None)


async def run_ai(sess: Session, text: str, lang: str, safety_checked: bool = False) -> None:
    loop = asyncio.get_running_loop()
    try:
        if security.is_sensitive(text) and not safety_checked:
            ok = await ask_safety_word(sess, f"This task may delete, send or share something:\n“{text}”\n\n"
                                             "Say or type your safety word to continue.")
            if not ok:
                await send(sess.ws, type="result", ok=False, heard=text, busy=False,
                           message=cancelled_msg())
                return

        def progress(message: str) -> None:
            asyncio.run_coroutine_threadsafe(_send_quietly(sess.ws, type="progress", message=message), loop)

        def confirm(action: str) -> bool:
            fut = asyncio.run_coroutine_threadsafe(
                ask_safety_word(sess, f"BOT wants to: {action}\n\nSay or type your safety word to allow it."), loop)
            try:
                return bool(fut.result(timeout=170))
            except Exception:
                return False

        await send(sess.ws, type="progress", message="On it…", busy=True)
        ok, message = await asyncio.to_thread(AGENT.run, text, LANG_NAMES.get(lang, "English"),
                                              progress, confirm, sess)
        log.info("  -> AI %s: %s", "ok" if ok else "FAILED", message)
        await send(sess.ws, type="result", ok=ok, message=message, heard=text, busy=False)
    except websockets.ConnectionClosed:
        pass
    except Exception:
        log.exception("AI task crashed")
        await _send_quietly(sess.ws, type="result", ok=False, heard=text, busy=False,
                            message="Something went wrong with that task (see bot.log).")


async def _send_quietly(ws, **msg) -> None:
    try:
        await send(ws, **msg)
    except websockets.ConnectionClosed:
        pass


async def handle_confirm(sess: Session, msg: dict) -> None:
    cid = str(msg.get("id", ""))
    item = sess.pending.get(cid)
    if item is None:
        return
    if item["kind"] == "keyword":
        fut = item["future"]
        if fut.done():
            return
        if not msg.get("yes"):
            fut.set_result(False)
        elif security.verify(CFG, str(msg.get("keyword", ""))):
            fut.set_result(True)
        else:
            item["attempts"] += 1
            left = 3 - item["attempts"]
            if left <= 0:
                fut.set_result(False)
                await send(sess.ws, type="result", ok=False, message="Wrong safety word 3 times. Cancelled.")
            else:
                await send(sess.ws, type="confirm", id=cid, keyword=True,
                           message=f"Wrong safety word ({left} tries left).\n\n{item['message']}")
        return
    sess.pending.pop(cid, None)
    m, text = item["match"], item["text"]
    if not msg.get("yes"):
        await send(sess.ws, type="result", ok=True, message="Okay, cancelled", heard=text)
    elif time.time() - item["at"] > CONFIRM_TIMEOUT:
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
    elif kind == "stop":
        AGENT.stop()
        smart.RUNNER.stop()
    elif kind == "quick":  # one-tap buttons in the app (e.g. Lock)
        action = str(msg.get("action", ""))
        if action in QUICK_ACTIONS:
            log.info("Quick action: %s", action)
            await run_match(sess.ws, matcher.Match(action), action)
    elif kind == "routine_run":
        name = str(msg.get("name", ""))
        routine = next((r for r in routines.get(CFG) if r["name"] == name), None)
        if routine:
            await start_routine(sess, routine, str(msg.get("lang", "en")), heard=name)
    elif kind == "routines_set":
        CFG["routines"] = routines.clean(msg.get("routines"))
        save_config()
        await send(sess.ws, type="routines", items=routines.get(CFG))
        await send(sess.ws, type="result", ok=True, message="Routines saved")
    elif kind == "set_style":
        name = str(msg.get("name", "BOT")).strip()[:20] or "BOT"
        color = str(msg.get("color", "#4FC3FF"))
        if re.fullmatch(r"#[0-9a-fA-F]{6}", color):
            CFG["style"] = {"name": name, "color": color}
            save_config()
            apply_style()
            tray_refresh()
            BUBBLE.pop(f"Hi, I'm {name}!", hold=2.5)
    elif kind == "clip_set":  # phone clipboard -> PC clipboard
        text = str(msg.get("text", ""))[:200_000]
        await asyncio.to_thread(pyperclip.copy, text)
        BUBBLE.pop("📋 Clipboard from phone", hold=1.5)
        await send(sess.ws, type="result", ok=True,
                   message=f"Copied to the PC clipboard ({len(text)} characters). Paste with Ctrl+V.")
    elif kind == "clip_get":  # PC clipboard -> phone
        try:
            text = await asyncio.to_thread(pyperclip.paste)
        except pyperclip.PyperclipException:
            text = ""
        await send(sess.ws, type="clip", text=(text or "")[:200_000])
    elif kind in ("file_begin", "file_chunk", "file_end"):
        await handle_file(sess, kind, msg)
    elif kind == "key_state":  # gamepad: hold / release a key
        key = str(msg.get("key", ""))
        down = bool(msg.get("down"))
        if win_input.game_key(key, down):
            (sess.keys_down.add if down else sess.keys_down.discard)(key)
    elif kind == "set_pet":
        set_pet(bool(msg.get("on")))
        await send(sess.ws, type="pet", on=PET.wanted)
    elif kind == "pet_react":  # petting / tapping BOT on the phone makes the desktop BOT react too
        mood = str(msg.get("mood", "happy"))
        if mood in ("happy", "love", "excited", "surprised", "sad"):
            PET.react(mood, 2.0)
    elif kind == "set_walkaway":
        CFG["walkaway"] = {"enabled": bool(msg.get("enabled")),
                           "minutes": int(_num(msg.get("minutes"), 1, 1, 30))}
        save_config()
        if CFG["walkaway"]["enabled"]:
            _presence["armed"] = sess.lan
        tray_refresh()
        await send(sess.ws, type="walkaway", **CFG["walkaway"])
        await send(sess.ws, type="result", ok=True,
                   message=("Walk-away lock is ON: I'll lock the PC "
                            f"{CFG['walkaway']['minutes']} min after your phone leaves the Wi-Fi."
                            if CFG["walkaway"]["enabled"] else "Walk-away lock is off."))
    elif kind == "set_keyword":
        if sess.bad_old_words >= 5:
            await send(sess.ws, type="keyword_status", ok=False, set=security.is_set(CFG),
                       message="Too many wrong tries. Reconnect and try again.")
            return
        ok, message = security.set_word(CFG, str(msg.get("new", ""))[:100], str(msg.get("old", ""))[:100])
        if ok:
            save_config()
            log.info("Safety word set/changed")
        elif security.is_set(CFG):
            sess.bad_old_words += 1
        await send(sess.ws, type="keyword_status", ok=ok, set=security.is_set(CFG), message=message)
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


async def handle_file(sess: Session, kind: str, msg: dict) -> None:
    """Phone -> PC file transfer, in base64 chunks. Saved to Downloads\\BOT."""
    fid = str(msg.get("id", ""))[:40]
    if kind == "file_begin":
        size = int(_num(msg.get("size"), 0, 0, MAX_UPLOAD + 1))
        if size > MAX_UPLOAD:
            await send(sess.ws, type="file_status", id=fid, ok=False, message="That file is too big (max 500 MB).")
            return
        DOWNLOADS.mkdir(parents=True, exist_ok=True)
        name = safe_filename(str(msg.get("name", "file")))
        path = DOWNLOADS / name
        stem, suffix, n = path.stem, path.suffix, 1
        while path.exists():
            path = DOWNLOADS / f"{stem} ({n}){suffix}"
            n += 1
        sess.uploads[fid] = {"fh": open(path, "wb"), "path": str(path), "size": size, "got": 0}
        await send(sess.ws, type="file_ack", id=fid, got=0)
        return
    up = sess.uploads.get(fid)
    if up is None:
        return
    if kind == "file_chunk":
        try:
            data = base64.b64decode(str(msg.get("data", "")), validate=True)
        except ValueError:
            data = b""
        up["got"] += len(data)
        if not data or up["got"] > up["size"]:
            up["fh"].close()
            Path(up["path"]).unlink(missing_ok=True)
            sess.uploads.pop(fid, None)
            await send(sess.ws, type="file_status", id=fid, ok=False, message="The file got corrupted on the way.")
            return
        await asyncio.to_thread(up["fh"].write, data)
        await send(sess.ws, type="file_ack", id=fid, got=up["got"])
        return
    # file_end
    sess.uploads.pop(fid, None)
    up["fh"].close()
    if up["got"] != up["size"]:
        Path(up["path"]).unlink(missing_ok=True)
        await send(sess.ws, type="file_status", id=fid, ok=False, message="The transfer was incomplete.")
        return
    name = Path(up["path"]).name
    log.info("Received file %s (%d bytes)", name, up["size"])
    BUBBLE.pop(f"📥 {name}", hold=2.5)
    await send(sess.ws, type="file_status", id=fid, ok=True,
               message=f"Saved {name} to Downloads\\BOT")


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
                   bubble=BUBBLE.wanted, ai=AGENT.available, busy=AGENT.busy or smart.RUNNER.busy,
                   keyword_set=security.is_set(CFG), mac=_net["mac"], broadcast=_net["broadcast"],
                   routines=routines.get(CFG), style=CFG.get("style", {}),
                   pet=PET.wanted, walkaway=CFG.get("walkaway", {}), health=PET.health,
                   away_alerts=list(ALERTS),
                   features=["cursor", "screen", "touchpad", "keys", "bubble", "ai", "keyword",
                             "routines", "files", "clipboard", "style", "health", "alerts", "gamepad", "pet"])
        ALERTS.clear()
        sess = Session(ws)
        SESSIONS.add(sess)
        PET.react("happy", 2.0)
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
            SESSIONS.discard(sess)
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
        server = await websockets.serve(make_handler(cfg), "0.0.0.0", port, max_size=1024 * 1024)
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
    PET.wanted = bool(cfg.get("desktop_pet", True))
    PET.busy_fn = lambda: AGENT.busy or smart.RUNNER.busy
    # Thrown / petted on the PC -> the BOT on your phone reacts too
    PET.on_event = lambda ev: asyncio.run_coroutine_threadsafe(broadcast(type="pet_event", event=ev), loop)
    PET.start()
    apply_style()
    jobs = [asyncio.create_task(refresh_tailscale_forever()), asyncio.create_task(watch_forever())]
    if cfg.get("keep_awake_when_charging", True):
        jobs.append(asyncio.create_task(keep_awake_forever()))

    PID_PATH.write_text(str(os.getpid()), encoding="utf-8")
    ip = local_ip()
    log.info("BOT running on %s at %s:%s", socket.gethostname(), ip, port)
    log.info("AI tasks: %s", f"on ({CFG.get('ai_model') or ai_agent.DEFAULT_MODEL})" if AGENT.available
             else "off (run set_api_key.bat to turn on)")
    line = "=" * 46
    show(f"\n{line}\n  BOT is running on {socket.gethostname()}")
    show(f"  IP address : {ip}\n  Port       : {port}\n  PIN        : {cfg['pin']}")
    show(f"  The app finds this PC automatically; just enter the PIN.\n  Press Ctrl+C to stop.\n{line}\n")
    # ---- system tray icon --------------------------------------------------------------
    global TRAY
    stop_bot = loop.create_future()

    def from_tray(coro_fn):  # run something on BOT's main loop from the tray thread
        return lambda: asyncio.run_coroutine_threadsafe(coro_fn(), loop)

    async def tray_toggle_pet():
        set_pet(not PET.wanted)
        await broadcast(type="pet", on=PET.wanted)

    async def tray_toggle_bubble():
        set_bubble(not BUBBLE.wanted)
        await broadcast(type="bubble", on=BUBBLE.wanted)

    async def tray_toggle_walkaway():
        wa = dict(CFG.get("walkaway", {"minutes": 1}))
        wa["enabled"] = not wa.get("enabled")
        CFG["walkaway"] = wa
        save_config()
        _presence["armed"] = wa["enabled"] and phone_nearby()
        tray_refresh()
        await broadcast(type="walkaway", **wa)

    def tray_set_autostart():
        if autostart.LAUNCHER.exists():
            autostart.remove_launcher()
        else:
            autostart.write_launcher()

    def tray_quit():
        log.info("Quit from the tray")
        PET.set_wanted(False)
        loop.call_soon_threadsafe(lambda: stop_bot.done() or stop_bot.set_result(None))

    def tray_bring():
        PET.bring_here()
        if not CFG.get("desktop_pet", True):
            set_pet(True)
            asyncio.run_coroutine_threadsafe(broadcast(type="pet", on=True), loop)

    TRAY = tray_mod.Tray(
        pet=PET, bubble=BUBBLE, cfg=CFG,
        toggle_pet=from_tray(tray_toggle_pet), toggle_bubble=from_tray(tray_toggle_bubble),
        toggle_walkaway=from_tray(tray_toggle_walkaway), bring_pet=tray_bring,
        autostart_on=lambda: autostart.LAUNCHER.exists(), set_autostart=tray_set_autostart,
        open_files=lambda: tray_mod.open_folder(str(DOWNLOADS)), quit_bot=tray_quit)
    TRAY.start()

    try:
        await stop_bot
    finally:
        TRAY.stop()
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
