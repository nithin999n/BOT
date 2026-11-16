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
