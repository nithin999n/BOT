"""
What the desktop BOT knows about the world around it (all free, no API keys):

* windows: the one you're using (to sit on it), what app it is (to react), windows to hide behind
* weather (Open-Meteo + rough location from your IP) and festivals / your birthday
* claps from the microphone (only loudness is looked at; sound is never saved)
* what music is playing (Windows media controls) + play/pause/next/previous
* the webcam (photo booth, intruder photo), desktop tidy-up, Ctrl+Alt+S "snip to phone"
"""
from __future__ import annotations

import asyncio
import ctypes
import ctypes.wintypes as wt
import json
import logging
import os
import random
import shutil
import threading
import time
import urllib.request
from datetime import date, datetime
from pathlib import Path

log = logging.getLogger("bot")
user32 = ctypes.WinDLL("user32", use_last_error=True)
dwmapi = ctypes.WinDLL("dwmapi")
user32.GetForegroundWindow.restype = wt.HWND
user32.GetWindowRect.argtypes = [wt.HWND, ctypes.POINTER(wt.RECT)]
user32.GetWindowTextW.argtypes = [wt.HWND, wt.LPWSTR, ctypes.c_int]
user32.GetClassNameW.argtypes = [wt.HWND, wt.LPWSTR, ctypes.c_int]
user32.IsWindowVisible.argtypes = [wt.HWND]
user32.IsIconic.argtypes = [wt.HWND]
user32.IsZoomed.argtypes = [wt.HWND]
user32.IsWindow.argtypes = [wt.HWND]
user32.GetWindowThreadProcessId.argtypes = [wt.HWND, ctypes.POINTER(wt.DWORD)]
user32.GetWindowLongW.argtypes = [wt.HWND, ctypes.c_int]
user32.GetAncestor.argtypes = [wt.HWND, ctypes.c_uint]
user32.GetAncestor.restype = wt.HWND
dwmapi.DwmGetWindowAttribute.argtypes = [wt.HWND, wt.DWORD, ctypes.c_void_p, wt.DWORD]

OUR_CLASSES = {"BotDesktopPet", "BotCookie", "BotSprite", "BotBubble"}
SKIP_CLASSES = OUR_CLASSES | {"Progman", "WorkerW", "Shell_TrayWnd", "Shell_SecondaryTrayWnd",
                              "Windows.UI.Core.CoreWindow", "ApplicationFrameWindow_Hidden", "NotifyIconOverflowWindow",
                              "TopLevelWindowForOverflowXamlIsland", "XamlExplorerHostIslandWindow"}


# ---- windows ---------------------------------------------------------------------------------
def rect(hwnd) -> tuple[int, int, int, int] | None:
    """The window's visible frame (without the invisible resize border)."""
    r = wt.RECT()
    if dwmapi.DwmGetWindowAttribute(hwnd, 9, ctypes.byref(r), ctypes.sizeof(r)) != 0:  # DWMWA_EXTENDED_FRAME_BOUNDS
        if not user32.GetWindowRect(hwnd, ctypes.byref(r)):
            return None
    return r.left, r.top, r.right, r.bottom


def _text(hwnd) -> str:
    buf = ctypes.create_unicode_buffer(256)
    user32.GetWindowTextW(hwnd, buf, 256)
    return buf.value


def _class(hwnd) -> str:
    buf = ctypes.create_unicode_buffer(128)
    user32.GetClassNameW(hwnd, buf, 128)
    return buf.value


def _cloaked(hwnd) -> bool:
    val = ctypes.c_int(0)
    dwmapi.DwmGetWindowAttribute(hwnd, 14, ctypes.byref(val), ctypes.sizeof(val))  # DWMWA_CLOAKED
    return bool(val.value)


def _exe(hwnd) -> str:
    pid = wt.DWORD()
    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    try:
        import psutil
        return psutil.Process(pid.value).name().lower()
    except Exception:
        return ""


def normal_window(hwnd) -> bool:
    """A real app window you can see (not ours, not the desktop/taskbar, not minimized or hidden)."""
    if not hwnd or not user32.IsWindow(hwnd) or not user32.IsWindowVisible(hwnd) or user32.IsIconic(hwnd):
        return False
    if _class(hwnd) in SKIP_CLASSES or _cloaked(hwnd) or not _text(hwnd):
        return False
    ex = user32.GetWindowLongW(hwnd, -20)
    return not (ex & 0x80)  # WS_EX_TOOLWINDOW


def screen_size() -> tuple[int, int]:
    return user32.GetSystemMetrics(0), user32.GetSystemMetrics(1)


def foreground() -> dict:
    """The window you're using: {hwnd, title, exe, rect, maximized, fullscreen}."""
    hwnd = user32.GetForegroundWindow()
    if not hwnd:
        return {}
    r = rect(hwnd) or (0, 0, 0, 0)
    sw, sh = screen_size()
    return {"hwnd": hwnd, "title": _text(hwnd), "exe": _exe(hwnd), "cls": _class(hwnd), "rect": r,
            "maximized": bool(user32.IsZoomed(hwnd)), "ok": normal_window(hwnd),
            "fullscreen": not user32.IsZoomed(hwnd) and r[0] <= 0 and r[1] <= 0 and r[2] >= sw and r[3] >= sh
            and _class(hwnd) not in SKIP_CLASSES}


def visible_windows() -> list[dict]:
    out = []
    proto = ctypes.WINFUNCTYPE(wt.BOOL, wt.HWND, wt.LPARAM)

    def cb(hwnd, _lp):
        if normal_window(hwnd):
            r = rect(hwnd)
            if r:
                out.append({"hwnd": hwnd, "rect": r, "maximized": bool(user32.IsZoomed(hwnd)), "title": _text(hwnd)})
        return True

    user32.EnumWindows(proto(cb), 0)
    return out


APP_KINDS = [
    ("movie", ["youtube", "netflix", "prime video", "hotstar", "jiocinema", "vlc media player", "movies & tv",
               "media player", "zee5", "sonyliv", "disney+", "mx player", "twitch"]),
    ("game", ["minecraft", "valorant", "steam", "epic games", "grand theft auto", "gta", "roblox", "fortnite",
              "pubg", "battlegrounds", "free fire", "counter-strike", "league of legends", "genshin", "apex legends",
              "call of duty", "rocket league", "asphalt", "fifa", "ea sports fc"]),
    ("chat", ["whatsapp", "telegram", "instagram", "messenger", "discord", "signal"]),
    ("code", ["visual studio code", "antigravity", "pycharm", "intellij", "android studio", "sublime text",
              "notepad++", "visual studio", "cursor", "jupyter", "eclipse", "github desktop"]),
]
APP_EXES = {"code.exe": "code", "pycharm64.exe": "code", "idea64.exe": "code", "studio64.exe": "code",
            "devenv.exe": "code", "sublime_text.exe": "code", "notepad++.exe": "code", "vlc.exe": "movie",
            "whatsapp.exe": "chat", "whatsapp.root.exe": "chat", "telegram.exe": "chat", "discord.exe": "chat",
            "minecraft.exe": "game", "javaw.exe": "game", "robloxplayerbeta.exe": "game", "valorant.exe": "game",
            "steam.exe": "game", "epicgameslauncher.exe": "game"}


def classify(fg: dict) -> str:
    """What you're doing in the foreground window: movie / game / chat / code / ''."""
    if not fg:
        return ""
    title = fg.get("title", "").lower()
    for kind, words in APP_KINDS:
        if any(w in title for w in words):
            return kind
    return APP_EXES.get(fg.get("exe", ""), "")


# ---- weather (Open-Meteo, no key) -------------------------------------------------------------
RAIN_CODES = {51, 53, 55, 56, 57, 61, 63, 65, 66, 67, 80, 81, 82, 95, 96, 99}


class Weather:
    def __init__(self):
        self.now: dict = {}
        self._thread = None

    def start(self) -> None:
        if self._thread is None:
            self._thread = threading.Thread(target=self._run, name="weather", daemon=True)
            self._thread.start()

    @staticmethod
    def _get(url: str) -> dict:
        req = urllib.request.Request(url, headers={"User-Agent": "BOT-desktop-pet"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read().decode("utf-8"))

    def _run(self) -> None:
        place = None
        while True:
            try:
                if place is None:
                    loc = self._get("http://ip-api.com/json/?fields=status,city,lat,lon")
                    if loc.get("status") == "success":
                        place = loc
                if place:
                    w = self._get(
                        "https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}"
                        "&current=temperature_2m,weather_code,is_day&hourly=precipitation_probability"
                        "&forecast_hours=8&timezone=auto".format(**place))
                    cur = w.get("current", {})
                    probs = [p for p in w.get("hourly", {}).get("precipitation_probability", []) if p is not None]
                    temp = float(cur.get("temperature_2m", 25))
                    code = int(cur.get("weather_code", 0))
                    rain_now = code in RAIN_CODES
                    rain_soon = rain_now or (max(probs[:6] or [0]) >= 55)
                    self.now = {"city": place.get("city", ""), "temp": round(temp), "code": code,
                                "raining": rain_now, "rain_soon": rain_soon, "cold": temp < 17, "hot": temp >= 34,
                                "sunny": code in (0, 1) and bool(cur.get("is_day", 1)), "at": time.time()}
            except Exception as exc:
                log.debug("weather unavailable: %s", exc)
            time.sleep(45 * 60)

    def line(self) -> str:
        w = self.now
        if not w:
            return ""
        city = f" in {w['city']}" if w.get("city") else ""
        if w["raining"]:
            return f"It's raining{city} ☔ {w['temp']}°C. Stay dry!"
        if w["rain_soon"]:
            return f"{w['temp']}°C{city}, rain is coming later ☔ Take an umbrella!"
        if w["cold"]:
            return f"Brrr, {w['temp']}°C{city} 🧣 Wear something warm!"
        if w["hot"]:
            return f"It's hot! {w['temp']}°C{city} 🥵 Drink lots of water!"
        return f"{w['temp']}°C{city} {'☀️' if w['sunny'] else '⛅'} Nice weather!"


# ---- festivals & birthday ------------------------------------------------------------------------
# (lunar festivals move every year)
FESTIVALS = {
    "diwali": ["2026-11-07", "2026-11-08", "2026-11-09", "2027-10-28", "2027-10-29", "2027-10-30",
               "2028-10-16", "2028-10-17", "2028-10-18"],
    "holi": ["2026-03-04", "2027-03-22", "2028-03-11", "2029-03-01"],
    "ugadi": ["2026-03-19", "2027-04-07", "2028-03-27", "2029-03-16"],
    "ganesh": ["2026-09-14", "2027-09-04", "2028-08-23"],
}
FESTIVAL_LINES = {
    "diwali": "Happy Diwali! 🪔✨ May your life be full of light!",
    "holi": "Happy Holi! 🎨 Colours everywhere!",
    "ugadi": "Happy Ugadi! 🌿 A sweet new year to you!",
    "ganesh": "Happy Ganesh Chaturthi! 🐘🙏",
    "sankranti": "Happy Sankranti! 🪁 Let's fly kites!",
    "christmas": "Merry Christmas! 🎄🎅",
    "newyear": "Happy New Year! 🎉🥳",
    "birthday": "HAPPY BIRTHDAY!! 🎂🎉 I love you so much!",
}


def festival(today: date | None = None, birthday: str = "") -> str:
    d = today or date.today()
    md = d.strftime("%m-%d")
    if birthday and md == birthday:
        return "birthday"
    iso = d.isoformat()
    for name, days in FESTIVALS.items():
        if iso in days:
            return name
    if md in ("01-14", "01-15"):
        return "sankranti"
    if md in ("12-24", "12-25"):
        return "christmas"
    if md == "01-01":
        return "newyear"
    return ""


# ---- claps (microphone loudness only) -------------------------------------------------------------
class ClapListener:
    """Calls on_double_clap() when you clap twice. Only the loudness is checked; nothing is recorded."""

    def __init__(self, on_double_clap):
        self.on_double_clap = on_double_clap
        self.enabled = False
        self._thread = None
        self.available = True

    def set_enabled(self, on: bool) -> None:
        self.enabled = on
        if on and self._thread is None and self.available:
            self._thread = threading.Thread(target=self._run, name="clap", daemon=True)
            self._thread.start()

    def _run(self) -> None:
        try:
            import numpy as np
            import sounddevice as sd
        except Exception as exc:
            log.info("Clap detection unavailable: %s", exc)
            self.available = False
            return
        while True:
            if not self.enabled:
                time.sleep(1)
                continue
            try:
                self._listen(np, sd)
            except Exception as exc:
                log.debug("clap listener stopped: %s", exc)
                time.sleep(20)

    def _listen(self, np, sd) -> None:
        rate, block = 16000, 400  # 25 ms blocks
        floor = 0.01
        claps: list[float] = []
        quiet_after = 0
        last_peak_t = 0.0
        with sd.InputStream(samplerate=rate, channels=1, blocksize=block, dtype="float32") as stream:
            while self.enabled:
                data, _ = stream.read(block)
                peak = float(np.max(np.abs(data)))
                now = time.time()
                if peak > max(0.32, floor * 9) and now - last_peak_t > 0.12:
                    last_peak_t = now
                    quiet_after = 4  # a clap is short: the next ~100 ms must be quieter
                    claps.append(now)
                elif quiet_after:
                    quiet_after -= 1
                    if peak > max(0.2, floor * 6) and claps and now - claps[-1] < 0.1:
                        claps.pop()  # loud for too long: speech / music, not a clap
                        quiet_after = 0
                floor = floor * 0.995 + min(peak, 0.2) * 0.005
                claps = [c for c in claps if now - c < 0.9]
                if len(claps) >= 2 and 0.15 < claps[-1] - claps[-2] < 0.8 and quiet_after == 0:
                    claps.clear()
                    try:
                        self.on_double_clap()
                    except Exception:
                        pass


# ---- music: what's playing + controls --------------------------------------------------------------
class Media:
    """Polls Windows' media controls (Spotify, YouTube in the browser, VLC...)."""

    def __init__(self):
        self.now: dict = {}
        self._thread = None
        self._loop = None

    def start(self) -> None:
        if self._thread is None:
            self._thread = threading.Thread(target=self._run, name="media", daemon=True)
            self._thread.start()

    def _run(self) -> None:
        try:
            from winrt.windows.media.control import \
                GlobalSystemMediaTransportControlsSessionManager as Manager
        except Exception as exc:
            log.info("Music info unavailable: %s", exc)
            return
        self._loop = asyncio.new_event_loop()

        async def poll():
            mgr = await Manager.request_async()
            self._mgr = mgr
            while True:
                try:
                    s = mgr.get_current_session()
                    if s is None:
                        self.now = {}
                    else:
                        props = await s.try_get_media_properties_async()
                        status = s.get_playback_info().playback_status
                        self.now = {"title": props.title or "", "artist": props.artist or "",
                                    "playing": int(status) == 4, "app": s.source_app_user_model_id or ""}
                except Exception as exc:
                    log.debug("media poll: %s", exc)
                await asyncio.sleep(2)

        try:
            self._loop.run_until_complete(poll())
        except Exception as exc:
            log.info("Music info stopped: %s", exc)

    def control(self, action: str) -> None:
        """prev / next / toggle."""
        key = {"prev": "prevtrack", "next": "nexttrack", "toggle": "playpause"}.get(action)
        if key:
            try:
                import pyautogui
                pyautogui.press(key)
            except Exception as exc:
                log.debug("media key failed: %s", exc)


# ---- webcam ---------------------------------------------------------------------------------------------
def snap(path: str, sticker=None, caption: str = "") -> bool:
    """Take a webcam photo (optionally with BOT standing in the corner) and save it as JPEG."""
    try:
        import cv2
        from PIL import Image, ImageDraw, ImageFont
    except Exception as exc:
        log.info("Camera unavailable: %s", exc)
        return False
    cam = cv2.VideoCapture(0, cv2.CAP_DSHOW)
    try:
        if not cam.isOpened():
            return False
        cam.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
        cam.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
        frame = None
        for _ in range(12):  # let the camera adjust its exposure
            ok, f = cam.read()
            if ok:
                frame = f
            time.sleep(0.05)
        if frame is None:
            return False
    finally:
        cam.release()
    img = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)).convert("RGBA")
    if sticker is not None:
        s = sticker.copy()
        k = img.height * 0.55 / s.height
        s = s.resize((int(s.width * k), int(s.height * k)), Image.LANCZOS)
        img.alpha_composite(s, (img.width - s.width - int(img.width * 0.02), img.height - s.height))
    if caption:
        d = ImageDraw.Draw(img, "RGBA")
        try:
            font = ImageFont.truetype("seguiemj.ttf", max(18, img.height // 22))
        except OSError:
            font = ImageFont.load_default()
        pad = img.height // 40
        tw = d.textlength(caption, font=font)
        d.rounded_rectangle((pad, img.height - pad * 3 - font.size, pad * 3 + tw, img.height - pad),
                            radius=pad, fill=(255, 255, 255, 210))
        d.text((pad * 2, img.height - pad * 2 - font.size), caption, font=font, fill=(30, 36, 64, 255),
               embedded_color=True)
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    img.convert("RGB").save(path, quality=90)
    return True


# ---- desktop tidy-up ----------------------------------------------------------------------------
TIDY_GROUPS = {
    "Pictures": {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp", ".heic", ".svg", ".ico", ".tif", ".tiff"},
    "Videos": {".mp4", ".mkv", ".avi", ".mov", ".wmv", ".webm", ".flv", ".m4v"},
    "Music": {".mp3", ".wav", ".m4a", ".flac", ".aac", ".ogg", ".wma"},
    "Documents": {".pdf", ".doc", ".docx", ".txt", ".rtf", ".odt", ".xls", ".xlsx", ".csv", ".ppt", ".pptx",
                  ".md", ".json", ".xml", ".html", ".htm"},
    "Archives": {".zip", ".rar", ".7z", ".tar", ".gz", ".iso"},
    "Installers": {".exe", ".msi", ".apk", ".msix", ".appx"},
}
KEEP_ON_DESKTOP = {".lnk", ".url", ".ini"}
TIDY_FOLDER = "BOT Tidy"


def desktop_dir() -> Path:
    buf = ctypes.create_unicode_buffer(260)
    ctypes.windll.shell32.SHGetFolderPathW(None, 0x0010, None, 0, buf)  # CSIDL_DESKTOPDIRECTORY
    return Path(buf.value or (Path.home() / "Desktop"))


def loose_files() -> list[Path]:
    try:
        return [p for p in desktop_dir().iterdir()
                if p.is_file() and p.suffix.lower() not in KEEP_ON_DESKTOP and not p.name.startswith("~")]
    except OSError:
        return []


def tidy() -> list[list[str]]:
    """Move loose desktop files into Desktop\\BOT Tidy\\<group>. Nothing is ever deleted. Returns [[from, to]]."""
    moved = []
    base = desktop_dir() / TIDY_FOLDER
    for p in loose_files():
        group = next((g for g, exts in TIDY_GROUPS.items() if p.suffix.lower() in exts), "Other")
        dest_dir = base / group
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest = dest_dir / p.name
        n = 1
        while dest.exists():
            dest = dest_dir / f"{p.stem} ({n}){p.suffix}"
            n += 1
        try:
            shutil.move(str(p), str(dest))
            moved.append([str(p), str(dest)])
        except OSError as exc:
            log.info("tidy: couldn't move %s: %s", p.name, exc)
    return moved


def untidy(moves: list) -> int:
    back = 0
    for src, dest in moves:
        if os.path.exists(dest) and not os.path.exists(src):
            try:
                shutil.move(dest, src)
                back += 1
            except OSError:
                pass
    return back


# ---- Ctrl+Alt+S: snip to phone -------------------------------------------------------------------------
class SnipHotkey:
    """Ctrl+Alt+S opens the Windows snipping bar; the snip you take is handed to on_image(path)."""

    def __init__(self, on_image, save_dir: Path, on_status=None):
        self.on_image, self.save_dir, self.on_status = on_image, save_dir, on_status
        self._thread = None

    def start(self) -> None:
        if self._thread is None:
            self._thread = threading.Thread(target=self._run, name="snip-hotkey", daemon=True)
            self._thread.start()

    label = "tray menu"

    def _run(self) -> None:
        # Ctrl+Alt+S, else Ctrl+Alt+P ("phone"), else Ctrl+Shift+S (whichever is free); 0x4000 = no repeat
        for mods, key, label in ((0x0003, "S", "Ctrl+Alt+S"), (0x0003, "P", "Ctrl+Alt+P"), (0x0006, "S", "Ctrl+Shift+S")):
            if user32.RegisterHotKey(None, 0xB07, mods | 0x4000, ord(key)):
                self.label = label
                log.info("Snip to phone: press %s", label)
                break
        else:
            log.info("No free snip shortcut: snip-to-phone is only in the tray menu")
            return
        msg = wt.MSG()
        while user32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
            if msg.message == 0x0312:  # WM_HOTKEY
                threading.Thread(target=self.snip, daemon=True).start()

    def snip(self) -> None:
        from PIL import ImageGrab
        seq = user32.GetClipboardSequenceNumber()
        os.startfile("ms-screenclip:")
        deadline = time.time() + 90
        while time.time() < deadline:
            time.sleep(0.4)
            if user32.GetClipboardSequenceNumber() == seq:
                continue
            seq = user32.GetClipboardSequenceNumber()
            try:
                img = ImageGrab.grabclipboard()
            except Exception:
                img = None
            if img is not None and hasattr(img, "save"):
                self.save_dir.mkdir(parents=True, exist_ok=True)
                path = self.save_dir / f"snip_{datetime.now():%Y%m%d_%H%M%S}.png"
                img.save(path)
                self.on_image(str(path))
                return
        if self.on_status:
            self.on_status("No snip taken")


# ---- power ---------------------------------------------------------------------------------------------
def sleep_pc() -> None:
    ctypes.windll.powrprof.SetSuspendState(False, False, False)


def random_point_away(bounds, avoid, min_dist, size) -> tuple[float, float]:
    left, top, right, bottom = bounds
    x = y = 0.0
    for _ in range(40):
        x = random.uniform(left + 40, right - 40 - size)
        y = random.uniform(top + 60, bottom - size - 40)
        if (x + size / 2 - avoid[0]) ** 2 + (y + size / 2 - avoid[1]) ** 2 > min_dist ** 2:
            break
    return x, y
