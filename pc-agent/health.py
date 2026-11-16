"""
How the PC is doing (CPU, RAM, battery), things worth telling the phone about
(battery low, download finished, someone unlocked the PC while you were away),
and helpers for the walk-away lock.
"""
from __future__ import annotations

import ctypes
import os
import subprocess
import time
from datetime import datetime
from pathlib import Path

import psutil

_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)
DOWNLOADS = Path.home() / "Downloads"
PARTIAL = (".crdownload", ".part", ".partial", ".tmp", ".download", ".opdownload")


class _PowerStatus(ctypes.Structure):
    _fields_ = [("ACLineStatus", ctypes.c_ubyte), ("BatteryFlag", ctypes.c_ubyte),
                ("BatteryLifePercent", ctypes.c_ubyte), ("SystemStatusFlag", ctypes.c_ubyte),
                ("BatteryLifeTime", ctypes.c_ulong), ("BatteryFullLifeTime", ctypes.c_ulong)]


class _LastInput(ctypes.Structure):
    _fields_ = [("cbSize", ctypes.c_uint), ("dwTime", ctypes.c_uint)]


def idle_seconds() -> float:
    """Seconds since the last keyboard/mouse input at the PC."""
    lii = _LastInput()
    lii.cbSize = ctypes.sizeof(lii)
    ctypes.windll.user32.GetLastInputInfo(ctypes.byref(lii))
    return ((ctypes.windll.kernel32.GetTickCount() - lii.dwTime) & 0xFFFFFFFF) / 1000.0


def is_locked() -> bool:
    """True when the lock screen is showing."""
    user32 = ctypes.windll.user32
    user32.OpenInputDesktop.restype = ctypes.c_void_p
    user32.SwitchDesktop.argtypes = [ctypes.c_void_p]
    user32.CloseDesktop.argtypes = [ctypes.c_void_p]
    hdesk = user32.OpenInputDesktop(0, False, 0x0100)  # DESKTOP_SWITCHDESKTOP
    if not hdesk:
        return True
    ok = user32.SwitchDesktop(hdesk)
    user32.CloseDesktop(hdesk)
    return not ok


def lock() -> None:
    ctypes.windll.user32.LockWorkStation()


def snapshot() -> dict:
    """Current health numbers, plus the 'feeling' BOT should show."""
    ps = _PowerStatus()
    ctypes.windll.kernel32.GetSystemPowerStatus(ctypes.byref(ps))
    has_battery = not (ps.BatteryFlag == 128 or ps.BatteryLifePercent == 255)
    battery = int(ps.BatteryLifePercent) if has_battery else None
    charging = ps.ACLineStatus == 1
    cpu = psutil.cpu_percent(None)
    ram = psutil.virtual_memory().percent
    if cpu >= 85:
        feeling = "hot"          # sweating
    elif battery is not None and battery <= 20 and not charging:
        feeling = "low_battery"  # worried
    elif battery is not None and charging and battery < 100:
        feeling = "charging"     # happy, little lightning
    else:
        feeling = "ok"
    return {"cpu": round(cpu), "ram": round(ram), "battery": battery, "charging": charging,
            "temp": None, "uptime": int(time.time() - psutil.boot_time()), "feeling": feeling}


def ping(ip: str) -> bool:
    """Is this phone still on the Wi-Fi? (phones usually answer pings even with the screen off)"""
    try:
        r = subprocess.run(["ping", "-n", "1", "-w", "800", ip], capture_output=True, text=True,
                           timeout=4, creationflags=_NO_WINDOW)
        return r.returncode == 0 and "TTL=" in r.stdout.upper()
    except (OSError, subprocess.TimeoutExpired):
        return False


class Watcher:
    """Turns PC changes into alerts for the phone."""

    def __init__(self):
        self._downloads = self._scan()
        self._battery_warned = False
        self._was_locked = is_locked()

    @staticmethod
    def _scan() -> set[str]:
        try:
            return {e.name for e in os.scandir(DOWNLOADS)
                    if e.is_file() and not e.name.lower().endswith(PARTIAL) and not e.name.startswith("~")}
        except OSError:
            return set()

    def check(self, h: dict, phone_nearby: bool) -> list[dict]:
        alerts = []
        now = datetime.now().strftime("%I:%M %p").lstrip("0")
        # battery low (once per discharge)
        if h["battery"] is not None:
            if h["battery"] <= 15 and not h["charging"] and not self._battery_warned:
                self._battery_warned = True
                alerts.append(_alert("battery", "Battery low 🔋", f"Your PC is at {h['battery']}%. Plug it in!"))
            elif h["charging"]:
                self._battery_warned = False
        # finished downloads
        files = self._scan()
        for name in sorted(files - self._downloads):
            alerts.append(_alert("download", "Download finished ✅", name))
        self._downloads = files
        # unlocked while you were away
        locked = is_locked()
        if self._was_locked and not locked and not phone_nearby:
            alerts.append(_alert("unlock", "Someone unlocked your PC 👀",
                                 f"Your PC was unlocked at {now} while you were away."))
        self._was_locked = locked
        return alerts


def _alert(kind: str, title: str, message: str) -> dict:
    return {"kind": kind, "title": title, "message": message, "time": datetime.now().strftime("%H:%M")}
