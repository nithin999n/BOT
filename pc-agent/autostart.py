"""
Run BOT in the background (no window) every time you log in to Windows.

    python autostart.py on       start with Windows + start now
    python autostart.py off      don't start with Windows + stop now
    python autostart.py stop     stop the background BOT
    python autostart.py status   is it running? shows IP and PIN
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
AGENT = HERE / "bot_agent.py"
PID_PATH = HERE / "bot.pid"
CONFIG_PATH = HERE / "config.json"
STARTUP_DIR = Path(os.environ["APPDATA"]) / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup"
LAUNCHER = STARTUP_DIR / "BOT agent.vbs"


def pythonw() -> Path:
    exe = Path(sys.executable)
    w = exe.with_name("pythonw.exe")
    return w if w.exists() else exe


def running_pid() -> int | None:
    try:
        pid = int(PID_PATH.read_text(encoding="utf-8").strip())
    except (OSError, ValueError):
        return None
    out = subprocess.run(["tasklist", "/FI", f"PID eq {pid}", "/NH", "/FO", "CSV"],
                         capture_output=True, text=True).stdout.lower()
    return pid if f'"{pid}"' in out and "python" in out else None


def start_now() -> None:
    if running_pid():
        print("BOT is already running in the background.")
        return
    flags = subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP
    subprocess.Popen([str(pythonw()), str(AGENT)], cwd=HERE, creationflags=flags, close_fds=True)
    print("BOT started in the background.")


def stop() -> None:
    pid = running_pid()
    if not pid:
        print("BOT is not running in the background.")
        return
    subprocess.run(["taskkill", "/PID", str(pid), "/F"], capture_output=True)
    PID_PATH.unlink(missing_ok=True)
    print("BOT stopped.")


def vbs_quote(s: str) -> str:
    return '"' + s.replace('"', '""') + '"'


def on() -> None:
    STARTUP_DIR.mkdir(parents=True, exist_ok=True)
    cmd = f'"{pythonw()}" "{AGENT}"'
    script = (
        'Set sh = CreateObject("WScript.Shell")\r\n'
        f"sh.CurrentDirectory = {vbs_quote(str(HERE))}\r\n"
        f"sh.Run {vbs_quote(cmd)}, 0, False\r\n"
    )
    LAUNCHER.write_text(script, encoding="utf-16")  # UTF-16 so any folder name works
    print(f"BOT will now start automatically when you log in.\n  ({LAUNCHER})")
    start_now()
    status()


def off() -> None:
    if LAUNCHER.exists():
        LAUNCHER.unlink()
        print("BOT will no longer start with Windows.")
    else:
        print("Autostart was not enabled.")
    stop()


def status() -> None:
    pid = running_pid()
    print(f"Running in background : {'yes (pid %d)' % pid if pid else 'no'}")
    print(f"Starts with Windows   : {'yes' if LAUNCHER.exists() else 'no'}")
    if CONFIG_PATH.exists():
        cfg = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        print(f"PIN                   : {cfg.get('pin')}")
    print(f"Log file              : {HERE / 'bot.log'}")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "status"
    actions = {"on": on, "off": off, "stop": stop, "start": start_now, "status": status}
    if cmd not in actions:
        sys.exit(__doc__)
    actions[cmd]()
