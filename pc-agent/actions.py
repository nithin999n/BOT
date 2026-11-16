"""Carries out a Match on this Windows PC. Every function returns (ok, message)."""
from __future__ import annotations

import ctypes
import os
import subprocess
import time
import urllib.parse
import webbrowser

import pyautogui
import pyperclip

import phrases as P
import win_input
from matcher import Match
from overlay import BUBBLE

pyautogui.PAUSE = 0.05
pyautogui.FAILSAFE = True  # slam the mouse into a screen corner to abort

_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)


def _run(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(list(args), capture_output=True, text=True, creationflags=_NO_WINDOW)


def paste_text(text: str) -> None:
    _paste_text(text)


# Keys the phone's keyboard bar may press.
ALLOWED_KEYS = {"enter", "backspace", "esc", "tab", "left", "right", "up", "down", "win", "space",
                "delete", "home", "end", "pageup", "pagedown", "f5"}


def press_key(name: str) -> None:
    if name in ALLOWED_KEYS:
        pyautogui.press(name)


def _paste_text(text: str) -> None:
    """Type any text (including Hindi/Kannada/Telugu) via the clipboard."""
    try:
        old = pyperclip.paste()
    except pyperclip.PyperclipException:
        old = None
    pyperclip.copy(text)
    pyautogui.hotkey("ctrl", "v")
    time.sleep(0.3)
    if old is not None:
        pyperclip.copy(old)


def _start_menu(name: str) -> None:
    pyautogui.press("win")
    time.sleep(0.7)
    _paste_text(name)
    time.sleep(0.9)
    pyautogui.press("enter")


def _open_url(url: str) -> None:
    webbrowser.open(url, new=2)


# ---- argument commands --------------------------------------------------------

def open_app(m: Match):
    spec = P.APPS[m.target]
    for target in spec["launch"]:
        target = os.path.expandvars(target)
        if "\\" in target and not os.path.exists(target):
            continue
        try:
            os.startfile(target)
            return True, f"Opened {spec['label']}"
        except OSError:
            continue
    _start_menu(spec["menu"])
    return True, f"Opened {spec['label']} from the Start menu"


def open_site(m: Match):
    spec = P.SITES[m.target]
    _open_url(spec["url"])
    return True, f"Opened {spec['label']}"


def open_url(m: Match):
    _open_url(m.arg)
    return True, f"Opened {m.arg}"


def start_menu(m: Match):
    _start_menu(m.arg)
    return True, f"Searched the Start menu for '{m.arg}'"


def unknown_app(m: Match):
    return False, f"I don't know an app called '{m.arg}' yet. Add it to pc-agent/phrases.py"


def _windows_of(process: str) -> list[int]:
    """Visible top-level windows of an app, front-most first."""
    user32, kernel32 = ctypes.windll.user32, ctypes.windll.kernel32
    found: list[int] = []
    proc_cb = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)

    def visit(hwnd, _lparam):
        if not user32.IsWindowVisible(hwnd) or user32.GetWindowTextLengthW(hwnd) == 0:
            return True
        if user32.GetWindow(hwnd, 4):  # GW_OWNER: skip dialogs owned by another window
            return True
        pid = ctypes.c_ulong()
        user32.GetWindowThreadProcessId(ctypes.c_void_p(hwnd), ctypes.byref(pid))
        h = kernel32.OpenProcess(0x1000, False, pid.value)  # PROCESS_QUERY_LIMITED_INFORMATION
        if h:
            buf = ctypes.create_unicode_buffer(512)
            size = ctypes.c_ulong(512)
            if kernel32.QueryFullProcessImageNameW(h, 0, buf, ctypes.byref(size)):
                if os.path.basename(buf.value).lower() == process.lower():
                    found.append(hwnd)
            kernel32.CloseHandle(h)
        return True

    user32.GetWindow.argtypes = [ctypes.c_void_p, ctypes.c_uint]
    user32.GetWindow.restype = ctypes.c_void_p
    user32.IsWindowVisible.argtypes = [ctypes.c_void_p]
    user32.GetWindowTextLengthW.argtypes = [ctypes.c_void_p]
    user32.PostMessageW.argtypes = [ctypes.c_void_p, ctypes.c_uint, ctypes.c_size_t, ctypes.c_ssize_t]
    kernel32.OpenProcess.restype = ctypes.c_void_p
    kernel32.QueryFullProcessImageNameW.argtypes = [ctypes.c_void_p, ctypes.c_ulong, ctypes.c_wchar_p,
                                                     ctypes.POINTER(ctypes.c_ulong)]
    kernel32.CloseHandle.argtypes = [ctypes.c_void_p]
    user32.EnumWindows(proc_cb(visit), 0)  # enumerates front-most window first
    return found


def close_app(m: Match):
    spec = P.APPS[m.target]
    if m.arg != "all":
        windows = _windows_of(spec["process"])
        if windows:  # close just the front-most window, like clicking its X
            ctypes.windll.user32.PostMessageW(ctypes.c_void_p(windows[0]), 0x0010, 0, 0)  # WM_CLOSE
            left = len(windows) - 1
            return True, f"Closed a {spec['label']} window" + (f" ({left} still open)" if left else "")
    res = _run("taskkill", "/im", spec["process"])  # no /f: lets the app ask "save changes?"
    if res.returncode == 0:
        return True, f"Closed {'all ' if m.arg == 'all' else ''}{spec['label']}"
    return False, f"{spec['label']} doesn't seem to be running"


def send_enter(_m):
    pyautogui.press("enter")
    return True, "Sent (pressed Enter)"


def delete_key(m: Match):
    if m.arg == "permanent":
        pyautogui.hotkey("shift", "delete")
        return True, "Deleted permanently (Shift+Delete)"
    pyautogui.press("delete")
    return True, "Deleted (pressed Delete)"


def google_search(m: Match):
    _open_url("https://www.google.com/search?q=" + urllib.parse.quote_plus(m.arg))
    return True, f"Searching Google for '{m.arg}'"


def youtube_search(m: Match):
    _open_url("https://www.youtube.com/results?search_query=" + urllib.parse.quote_plus(m.arg))
    return True, f"Searching YouTube for '{m.arg}'"


def type_text(m: Match):
    if not m.arg:
        return False, "What should I type? Say e.g. 'type hello'"
    _paste_text(m.arg)
    return True, f"Typed: {m.arg}"


# ---- system commands ----------------------------------------------------------

def _keys(*keys: str, msg: str):
    def run(_m: Match):
        if len(keys) == 1:
            pyautogui.press(keys[0])
        else:
            pyautogui.hotkey(*keys)
        return True, msg
    return run


def _press(key: str, times: int, msg: str):
    def run(_m: Match):
        pyautogui.press(key, presses=times, interval=0.02)
        return True, msg
    return run


def lock(_m):
    ctypes.windll.user32.LockWorkStation()
    return True, "PC locked"


def shutdown(_m):
    _run("shutdown", "/s", "/t", "15")
    return True, "Shutting down in 15 seconds. Say 'cancel shutdown' to stop it."


def restart(_m):
    _run("shutdown", "/r", "/t", "15")
    return True, "Restarting in 15 seconds. Say 'cancel shutdown' to stop it."


def cancel_shutdown(_m):
    res = _run("shutdown", "/a")
    if res.returncode == 0:
        return True, "Shutdown cancelled"
    return False, "There was no shutdown to cancel"


def sleep(_m):
    _run("rundll32.exe", "powrprof.dll,SetSuspendState", "0,1,0")
    return True, "Going to sleep"


def scroll(amount: int, msg: str):
    def run(m):
        factor = {"little": 0.4, "lot": 2.5}.get(getattr(m, "arg", ""), 1.0)
        pyautogui.scroll(int(amount * factor))
        return True, msg + {"little": " a little", "lot": " a lot"}.get(getattr(m, "arg", ""), "")
    return run


def click(_m):
    pyautogui.click()
    return True, "Clicked"


def double_click(_m):
    pyautogui.doubleClick()
    return True, "Double-clicked"


def right_click(_m):
    pyautogui.rightClick()
    return True, "Right-clicked"


class _PowerStatus(ctypes.Structure):
    _fields_ = [("ACLineStatus", ctypes.c_ubyte), ("BatteryFlag", ctypes.c_ubyte),
                ("BatteryLifePercent", ctypes.c_ubyte), ("SystemStatusFlag", ctypes.c_ubyte),
                ("BatteryLifeTime", ctypes.c_ulong), ("BatteryFullLifeTime", ctypes.c_ulong)]


def power_status() -> _PowerStatus:
    s = _PowerStatus()
    ctypes.windll.kernel32.GetSystemPowerStatus(ctypes.byref(s))
    return s


def battery(_m):
    s = power_status()
    if s.BatteryFlag == 128 or s.BatteryLifePercent == 255:
        return True, "This PC has no battery"
    state = "charging" if s.ACLineStatus == 1 else "on battery"
    return True, f"Battery {s.BatteryLifePercent}% ({state})"


HELP_TEXT = (
    "Try: open chrome · volume up · mute · search <anything> · play <song> on youtube · "
    "type <text> · close chrome · screenshot · scroll down · lock · shutdown.\n"
    "हिंदी: क्रोम खोलो · आवाज़ बढ़ाओ · ಕನ್ನಡ: ಕ್ರೋಮ್ ತೆರೆ · తెలుగు: క్రోమ్ ఓపెన్ చేయి"
)

ACTIONS = {
    "open_app": open_app,
    "open_site": open_site,
    "open_url": open_url,
    "start_menu": start_menu,
    "unknown_app": unknown_app,
    "close_app": close_app,
    "google_search": google_search,
    "youtube_search": youtube_search,
    "type_text": type_text,
    "volume_up": _press("volumeup", 5, "Volume up"),
    "volume_down": _press("volumedown", 5, "Volume down"),
    "mute": _keys("volumemute", msg="Toggled mute"),
    "play_pause": _keys("playpause", msg="Play / pause"),
    "next_track": _keys("nexttrack", msg="Next track"),
    "previous_track": _keys("prevtrack", msg="Previous track"),
    "lock": lock,
    "shutdown": shutdown,
    "restart": restart,
    "sleep": sleep,
    "cancel_shutdown": cancel_shutdown,
    "screenshot": _keys("win", "printscreen", msg="Screenshot saved to Pictures\\Screenshots"),
    "show_desktop": _keys("win", "d", msg="Showing desktop"),
    "minimize": _keys("win", "down", msg="Minimized window"),
    "maximize": _keys("win", "up", msg="Maximized window"),
    "close_window": _keys("alt", "f4", msg="Closed window"),
    "close_tab": _keys("ctrl", "w", msg="Closed tab"),
    "switch_window": _keys("alt", "tab", msg="Switched window"),
    "new_tab": _keys("ctrl", "t", msg="Opened a new tab"),
    "refresh": _keys("f5", msg="Refreshed"),
    "go_back": _keys("alt", "left", msg="Went back"),
    "copy": _keys("ctrl", "c", msg="Copied"),
    "paste": _keys("ctrl", "v", msg="Pasted"),
    "undo": _keys("ctrl", "z", msg="Undone"),
    "select_all": _keys("ctrl", "a", msg="Selected all"),
    "enter": _keys("enter", msg="Pressed Enter"),
    "send_enter": send_enter,
    "delete_key": delete_key,
    "scroll_up": scroll(600, "Scrolled up"),
    "scroll_down": scroll(-600, "Scrolled down"),
    "click": click,
    "double_click": double_click,
    "right_click": right_click,
    "battery": battery,
    "bubble_off": lambda _m: (True, "BOT cursor hidden"),   # the switch itself is flipped in bot_agent
    "bubble_on": lambda _m: (True, "BOT cursor is back"),
    "help": lambda _m: (True, HELP_TEXT),
    "greeting": lambda _m: (True, "Hi! I'm listening. Say 'help' to see what I can do."),
}

CONFIRM_TEXT = {
    "shutdown": "Shut down the PC?",
    "restart": "Restart the PC?",
    "sleep": "Put the PC to sleep?",
}


# Mouse actions: the bubble glides to the spot first, then pulses when BOT acts.
POINTER_LABELS = {
    "click": "Clicking", "double_click": "Double-clicking", "right_click": "Right-clicking",
    "scroll_up": "Scrolling up", "scroll_down": "Scrolling down",
}
# No bubble for these (screen is about to lock / turn off, or the text is too long).
NO_BUBBLE = {"lock", "shutdown", "restart", "sleep", "help", "bubble_off"}


def execute(m: Match):
    action = ACTIONS.get(m.intent)
    if action is None:
        return False, f"'{m.intent}' isn't implemented yet"
    try:
        if m.intent in POINTER_LABELS:
            x, y = win_input.cursor_pos()
            if not BUBBLE.glide_to(x, y, POINTER_LABELS[m.intent]):
                return False, "Cancelled: you took over the mouse"
            ok, message = action(m)
            BUBBLE.pulse()
            return ok, message
        ok, message = action(m)
        if m.intent not in NO_BUBBLE:
            BUBBLE.pop(message, ok)
        return ok, message
    except pyautogui.FailSafeException:
        return False, "Stopped: mouse was moved to a screen corner (safety stop)"
    except Exception as exc:  # report any failure back to the phone instead of crashing
        return False, f"Something went wrong: {exc}"
