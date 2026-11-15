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
from matcher import Match

pyautogui.PAUSE = 0.05
pyautogui.FAILSAFE = True  # slam the mouse into a screen corner to abort

_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)


def _run(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(list(args), capture_output=True, text=True, creationflags=_NO_WINDOW)


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


def close_app(m: Match):
    spec = P.APPS[m.target]
    res = _run("taskkill", "/im", spec["process"])  # no /f: lets the app ask "save changes?"
    if res.returncode == 0:
        return True, f"Closed {spec['label']}"
    return False, f"{spec['label']} doesn't seem to be running"


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
    def run(_m):
        pyautogui.scroll(amount)
        return True, msg
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
    "scroll_up": scroll(600, "Scrolled up"),
    "scroll_down": scroll(-600, "Scrolled down"),
    "click": click,
    "double_click": double_click,
    "right_click": right_click,
    "help": lambda _m: (True, HELP_TEXT),
    "greeting": lambda _m: (True, "Hi! I'm listening. Say 'help' to see what I can do."),
}

CONFIRM_TEXT = {
    "shutdown": "Shut down the PC?",
    "restart": "Restart the PC?",
    "sleep": "Put the PC to sleep?",
}


def execute(m: Match):
    action = ACTIONS.get(m.intent)
    if action is None:
        return False, f"'{m.intent}' isn't implemented yet"
    try:
        return action(m)
    except pyautogui.FailSafeException:
        return False, "Stopped: mouse was moved to a screen corner (safety stop)"
    except Exception as exc:  # report any failure back to the phone instead of crashing
        return False, f"Something went wrong: {exc}"
