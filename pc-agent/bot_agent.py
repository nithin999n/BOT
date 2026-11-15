"""
BOT PC agent: listens on your Wi-Fi for commands from the BOT phone app.

    python bot_agent.py

It prints this PC's IP address and a PIN; type those into the phone app once.
"""
from __future__ import annotations

import asyncio
import hmac
import json
import logging
import secrets
import socket
import sys
import time
import uuid
from datetime import datetime
from pathlib import Path

import websockets

import actions
import matcher

HERE = Path(__file__).resolve().parent
CONFIG_PATH = HERE / "config.json"
UNMATCHED_PATH = HERE / "unmatched.txt"
DEFAULT_PORT = 8765
CONFIRM_TIMEOUT = 30          # seconds the phone has to answer "are you sure?"
MAX_BAD_PINS = 5              # per IP, per 5 minutes

log = logging.getLogger("bot")
_bad_pins: dict[str, list[float]] = {}


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


def record_unmatched(text: str, lang: str) -> None:
    with UNMATCHED_PATH.open("a", encoding="utf-8") as f:
        f.write(f"{datetime.now():%Y-%m-%d %H:%M:%S}\t{lang}\t{text}\n")


def too_many_bad_pins(ip: str) -> bool:
    now = time.time()
    recent = [t for t in _bad_pins.get(ip, []) if now - t < 300]
    _bad_pins[ip] = recent
    return len(recent) >= MAX_BAD_PINS


async def send(ws, **msg) -> None:
    await ws.send(json.dumps(msg, ensure_ascii=False))


async def run_match(ws, m: matcher.Match, heard: str) -> None:
    ok, message = await asyncio.to_thread(actions.execute, m)
    log.info("  -> %s: %s", "ok" if ok else "FAILED", message)
    await send(ws, type="result", ok=ok, message=message, heard=heard)


async def handle_command(ws, msg: dict, pending: dict) -> None:
    text = str(msg.get("text", "")).strip()[:500]
    lang = str(msg.get("lang", "?"))[:5]
    if not text:
        return
    log.info("Heard [%s]: %s", lang, text)
    m = matcher.match(text)
    if m is None:
        record_unmatched(text, lang)
        log.info("  -> not understood")
        await send(ws, type="result", ok=False, heard=text,
                   message=f"Sorry, I don't know that command yet: \"{text}\"")
        return
    log.info("  -> %s %s", m.intent, m.target or m.arg)
    if m.needs_confirm:
        cid = uuid.uuid4().hex
        pending[cid] = (m, text, time.time())
        await send(ws, type="confirm", id=cid, message=actions.CONFIRM_TEXT.get(m.intent, "Are you sure?"))
        return
    await run_match(ws, m, text)


async def handle_confirm(ws, msg: dict, pending: dict) -> None:
    item = pending.pop(str(msg.get("id", "")), None)
    if item is None:
        return
    m, text, asked_at = item
    if not msg.get("yes"):
        await send(ws, type="result", ok=True, message="Okay, cancelled", heard=text)
    elif time.time() - asked_at > CONFIRM_TIMEOUT:
        await send(ws, type="result", ok=False, message="Too late, please say it again", heard=text)
    else:
        await run_match(ws, m, text)


def make_handler(cfg: dict):
    async def handler(ws):
        ip = ws.remote_address[0] if ws.remote_address else "?"
        try:
            hello = json.loads(await asyncio.wait_for(ws.recv(), timeout=10))
        except (asyncio.TimeoutError, json.JSONDecodeError, websockets.ConnectionClosed, TypeError):
            return
        if too_many_bad_pins(ip):
            await send(ws, type="error", fatal=True, message="Too many wrong PINs. Wait 5 minutes.")
            return
        if not isinstance(hello, dict):
            return
        pin = str(hello.get("pin", ""))
        if hello.get("type") != "hello" or not hmac.compare_digest(pin, cfg["pin"]):
            _bad_pins.setdefault(ip, []).append(time.time())
            log.warning("Wrong PIN from %s", ip)
            await asyncio.sleep(1)
            await send(ws, type="error", fatal=True, message="Wrong PIN. Check the PIN shown on the PC.")
            return

        log.info("Phone connected from %s", ip)
        await send(ws, type="welcome", pc=socket.gethostname())
        pending: dict = {}
        try:
            async for raw in ws:
                try:
                    msg = json.loads(raw)
                except (json.JSONDecodeError, TypeError):
                    continue
                if not isinstance(msg, dict):
                    continue
                kind = msg.get("type")
                if kind == "command":
                    await handle_command(ws, msg, pending)
                elif kind == "confirm_reply":
                    await handle_confirm(ws, msg, pending)
        except websockets.ConnectionClosed:
            pass
        finally:
            log.info("Phone disconnected (%s)", ip)

    return handler


async def main() -> None:
    cfg = load_config()
    port = int(cfg["port"])
    async with websockets.serve(make_handler(cfg), "0.0.0.0", port, max_size=64 * 1024):
        line = "=" * 46
        print(f"\n{line}\n  BOT is running on {socket.gethostname()}")
        print(f"  IP address : {local_ip()}\n  Port       : {port}\n  PIN        : {cfg['pin']}")
        print(f"  Enter these in the BOT app on your phone.\n  Press Ctrl+C to stop.\n{line}\n", flush=True)
        await asyncio.Future()


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    logging.basicConfig(level=logging.INFO, format="%(asctime)s  %(message)s", datefmt="%H:%M:%S")
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("BOT stopped.")
