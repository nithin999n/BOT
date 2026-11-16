"""
Run BOT in the background (no window) every time you log in to Windows.

    python autostart.py on       start with Windows + start now
    python autostart.py off      don't start with Windows + stop now
    python autostart.py stop     stop the background BOT
    python autostart.py status   is it running? shows IP and PIN
    python autostart.py setup    create/update BOT's private Python environment
    python autostart.py set-key  save your Anthropic API key (for "do anything" tasks)
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
AGENT = HERE / "bot_agent.py"
PID_PATH = HERE / "bot.pid"
CONFIG_PATH = HERE / "config.json"
STARTUP_DIR = Path(os.environ["APPDATA"]) / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup"
LAUNCHER = STARTUP_DIR / "BOT agent.vbs"


VENV = Path(os.environ["LOCALAPPDATA"]) / "BOT" / "venv"  # BOT's own packages (not your global Python)


def base_python() -> Path:
    exe = Path(sys.executable)
    if exe.name.lower() == "pythonw.exe":
        exe = exe.with_name("python.exe")
    return exe


def python_exe() -> Path:
    # python.exe (not pythonw.exe) with a hidden window, so the Windows Firewall
    # permission you already gave Python also covers the background BOT.
    venv_python = VENV / "Scripts" / "python.exe"
    return venv_python if venv_python.exists() else base_python()


def setup() -> None:
    """Create BOT's private Python environment and install/update its packages."""
    if not (VENV / "Scripts" / "python.exe").exists():
        print("Creating BOT's Python environment (first time only)…")
        subprocess.run([str(base_python()), "-m", "venv", str(VENV)], check=True)
    print("Installing / updating BOT's packages…")
    subprocess.run([str(python_exe()), "-m", "pip", "install", "-q", "--disable-pip-version-check",
                    "-r", str(HERE / "requirements.txt")], check=True)


def set_key() -> None:
    """Save your Anthropic API key so BOT can do free-form tasks with Claude."""
    import getpass
    key = getpass.getpass("Paste your Anthropic API key (it won't be shown) and press Enter: ").strip()
    if not key.startswith("sk-ant-"):
        sys.exit("That doesn't look like an Anthropic API key (it should start with sk-ant-).")
    cfg = json.loads(CONFIG_PATH.read_text(encoding="utf-8")) if CONFIG_PATH.exists() else {}
    cfg["anthropic_api_key"] = key
    CONFIG_PATH.write_text(json.dumps(cfg, indent=2), encoding="utf-8")
    print("Saved. Restarting BOT so it picks up the key…")
    stop()
    start_now()


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
    flags = subprocess.CREATE_NO_WINDOW | subprocess.CREATE_NEW_PROCESS_GROUP
    subprocess.Popen([str(python_exe()), str(AGENT)], cwd=HERE, creationflags=flags, close_fds=True,
                     stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    for _ in range(80):  # wait up to 20 s for it to come up
        time.sleep(0.25)
        if running_pid():
            print("BOT started in the background.")
            return
    print("BOT did not start. See the last lines of bot.log:")
    log = HERE / "bot.log"
    if log.exists():
        print("\n".join(log.read_text(encoding="utf-8", errors="replace").splitlines()[-5:]))


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


def write_launcher() -> None:
    """Start BOT (hidden) every time you log in to Windows."""
    STARTUP_DIR.mkdir(parents=True, exist_ok=True)
    cmd = f'"{python_exe()}" "{AGENT}"'
    script = (
        'Set sh = CreateObject("WScript.Shell")\r\n'
        f"sh.CurrentDirectory = {vbs_quote(str(HERE))}\r\n"
        f"sh.Run {vbs_quote(cmd)}, 0, False\r\n"
    )
    LAUNCHER.write_text(script, encoding="utf-16")  # UTF-16 so any folder name works


def remove_launcher() -> None:
    LAUNCHER.unlink(missing_ok=True)


def on() -> None:
    write_launcher()
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
        print(f"AI tasks (API key)    : {'ready' if cfg.get('anthropic_api_key') else 'not set (run set_api_key.bat)'}")
    print(f"Log file              : {HERE / 'bot.log'}")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "status"
    actions = {"on": on, "off": off, "stop": stop, "start": start_now, "status": status,
               "setup": setup, "set-key": set_key}
    if cmd not in actions:
        sys.exit(__doc__)
    actions[cmd]()
