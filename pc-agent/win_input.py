"""Fast, direct mouse control (no delays) for the touchpad and screen-tap features."""
from __future__ import annotations

import ctypes
import ctypes.wintypes as wt

user32 = ctypes.windll.user32

# Work in real screen pixels even on scaled (125% / 150%) displays.
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(2)
except (AttributeError, OSError):
    try:
        user32.SetProcessDPIAware()
    except (AttributeError, OSError):
        pass

_BUTTONS = {"left": (0x0002, 0x0004), "right": (0x0008, 0x0010), "middle": (0x0020, 0x0040)}
_WHEEL = 0x0800


def cursor_pos() -> tuple[int, int]:
    p = wt.POINT()
    user32.GetCursorPos(ctypes.byref(p))
    return p.x, p.y


def virtual_screen() -> tuple[int, int, int, int]:
    """(left, top, width, height) covering all monitors."""
    return (user32.GetSystemMetrics(76), user32.GetSystemMetrics(77),
            max(1, user32.GetSystemMetrics(78)), max(1, user32.GetSystemMetrics(79)))


def primary_screen() -> tuple[int, int, int, int]:
    return 0, 0, max(1, user32.GetSystemMetrics(0)), max(1, user32.GetSystemMetrics(1))


def move_to(x: float, y: float) -> None:
    left, top, w, h = virtual_screen()
    xi = max(left, min(left + w - 1, int(round(x))))
    yi = max(top, min(top + h - 1, int(round(y))))
    user32.SetCursorPos(xi, yi)


def move_rel(dx: float, dy: float) -> None:
    x, y = cursor_pos()
    move_to(x + dx, y + dy)


def button(name: str, down: bool) -> None:
    down_flag, up_flag = _BUTTONS.get(name, _BUTTONS["left"])
    user32.mouse_event(down_flag if down else up_flag, 0, 0, 0, 0)


def click(name: str = "left", double: bool = False) -> None:
    for _ in range(2 if double else 1):
        button(name, True)
        button(name, False)


def scroll(notches: int) -> None:
    """Positive = scroll up, negative = scroll down."""
    user32.mouse_event(_WHEEL, 0, 0, int(notches) * 120, 0)


def hscroll(notches: int) -> None:
    """Positive = scroll right, negative = scroll left."""
    user32.mouse_event(0x01000, 0, 0, int(notches) * 120, 0)


def esc_pressed() -> bool:
    return bool(user32.GetAsyncKeyState(0x1B) & 0x8000)


# ---- game keys: hardware scan codes, which games notice (unlike plain virtual keys) -----------
class _KI(ctypes.Structure):
    _fields_ = [("wVk", wt.WORD), ("wScan", wt.WORD), ("dwFlags", wt.DWORD), ("time", wt.DWORD),
                ("dwExtraInfo", ctypes.c_size_t)]


class _MI(ctypes.Structure):
    _fields_ = [("dx", wt.LONG), ("dy", wt.LONG), ("mouseData", wt.DWORD), ("dwFlags", wt.DWORD),
                ("time", wt.DWORD), ("dwExtraInfo", ctypes.c_size_t)]


class _U(ctypes.Union):
    _fields_ = [("mi", _MI), ("ki", _KI)]


class _INPUT(ctypes.Structure):
    _fields_ = [("type", wt.DWORD), ("u", _U)]


GAME_KEYS = {  # name -> (scan code, extended key?)
    "w": (0x11, False), "a": (0x1E, False), "s": (0x1F, False), "d": (0x20, False),
    "up": (0x48, True), "down": (0x50, True), "left": (0x4B, True), "right": (0x4D, True),
    "space": (0x39, False), "enter": (0x1C, False), "esc": (0x01, False), "tab": (0x0F, False),
    "shift": (0x2A, False), "ctrl": (0x1D, False), "alt": (0x38, False),
    "e": (0x12, False), "f": (0x21, False), "q": (0x10, False), "r": (0x13, False), "c": (0x2E, False),
    "x": (0x2D, False), "z": (0x2C, False), "j": (0x24, False), "k": (0x25, False), "l": (0x26, False),
    "m": (0x32, False), "1": (0x02, False), "2": (0x03, False), "3": (0x04, False), "4": (0x05, False),
}
user32.SendInput.argtypes = [wt.UINT, ctypes.POINTER(_INPUT), ctypes.c_int]


def game_key(name: str, down: bool) -> bool:
    spec = GAME_KEYS.get(name)
    if not spec:
        return False
    scan, extended = spec
    flags = 0x0008 | (0 if down else 0x0002) | (0x0001 if extended else 0)  # SCANCODE | KEYUP | EXTENDED
    inp = _INPUT(type=1, u=_U(ki=_KI(wVk=0, wScan=scan, dwFlags=flags, time=0, dwExtraInfo=0)))
    user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(_INPUT))
    return True
