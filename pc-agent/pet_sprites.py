"""
Little extra windows for the desktop BOT's toys: a ball, soap bubbles, falling cookies, baby BOT, an egg.

Each Sprite is a tiny layered (see-through) window. Create and use them on the desktop BOT's thread.
Pictures are drawn here with Pillow.
"""
from __future__ import annotations

import ctypes
import ctypes.wintypes as wt
import math
import time

from PIL import Image, ImageDraw, ImageFilter

import win_input
from overlay import (AC_SRC_ALPHA, BITMAPINFO, BITMAPINFOHEADER, BLENDFUNCTION, SW_SHOWNOACTIVATE, ULW_ALPHA,
                     WNDCLASSEXW, WNDPROC, WS_EX_LAYERED, WS_EX_NOACTIVATE, WS_EX_TOOLWINDOW, WS_EX_TOPMOST,
                     WS_POPUP, _premultiplied_bgra, gdi32, kernel32, user32)

_SPRITES: dict = {}       # hwnd -> Sprite
_registered = False
_proc_ref = None


def _wndproc(hwnd, msg, wparam, lparam):
    sp = _SPRITES.get(hwnd)
    if sp is not None:
        r = sp._wnd(msg)
        if r is not None:
            return r
    return user32.DefWindowProcW(hwnd, msg, wparam, lparam)


def _register() -> None:
    global _registered, _proc_ref
    if _registered:
        return
    _proc_ref = WNDPROC(_wndproc)
    wc = WNDCLASSEXW()
    wc.cbSize = ctypes.sizeof(WNDCLASSEXW)
    wc.lpfnWndProc = _proc_ref
    wc.hInstance = kernel32.GetModuleHandleW(None)
    wc.lpszClassName = "BotSprite"
    user32.RegisterClassExW(ctypes.byref(wc))
    _registered = True


class Sprite:
    def __init__(self, interactive: bool = False):
        _register()
        self.interactive = interactive
        ex = WS_EX_LAYERED | WS_EX_TOPMOST | WS_EX_TOOLWINDOW | WS_EX_NOACTIVATE
        if not interactive:
            ex |= 0x20  # WS_EX_TRANSPARENT: clicks go straight through
        self.hwnd = user32.CreateWindowExW(ex, "BotSprite", "BOT toy", WS_POPUP, 0, 0, 10, 10, None, None,
                                           kernel32.GetModuleHandleW(None), None)
        _SPRITES[self.hwnd] = self
        self.x = self.y = 0.0
        self.vx = self.vy = 0.0
        self.img: Image.Image | None = None
        self.visible = False
        self._shown = False
        self._last = None
        # mouse
        self.dragging = False
        self.events: list[tuple] = []      # ("click",) / ("throw", vx, vy)
        self._grab_off = (0.0, 0.0)
        self._grab_t = 0.0
        self._moved = 0.0
        self._samples: list = []
        self.data: dict = {}               # whatever the game wants to remember

    @property
    def w(self) -> int:
        return self.img.width if self.img else 0

    @property
    def h(self) -> int:
        return self.img.height if self.img else 0

    @property
    def center(self):
        return self.x + self.w / 2, self.y + self.h / 2

    def _wnd(self, msg):
        if msg == 0x0021:            # WM_MOUSEACTIVATE
            return 3
        if not self.interactive:
            return None
        if msg == 0x0020:            # WM_SETCURSOR: hand
            user32.SetCursor(user32.LoadCursorW(None, ctypes.c_void_p(32649)))
            return 1
        if msg == 0x0201:            # WM_LBUTTONDOWN
            cx, cy = win_input.cursor_pos()
            self.dragging = True
            self._grab_off = (cx - self.x, cy - self.y)
            self._grab_t, self._moved = time.perf_counter(), 0.0
            self._samples = [(self._grab_t, float(cx), float(cy))]
            user32.SetCapture(self.hwnd)
            return 0
        if msg == 0x0202 or (msg == 0x0215 and self.dragging):  # up / capture lost
            if self.dragging:
                self.dragging = False
                user32.ReleaseCapture()
                now = time.perf_counter()
                if self._moved < 6 and now - self._grab_t < 0.35:
                    self.events.append(("click",))
                else:
                    rec = [s for s in self._samples if now - s[0] < 0.1] or self._samples[-2:]
                    vx = vy = 0.0
                    if len(rec) >= 2 and rec[-1][0] > rec[0][0]:
                        dt = rec[-1][0] - rec[0][0]
                        vx, vy = (rec[-1][1] - rec[0][1]) / dt, (rec[-1][2] - rec[0][2]) / dt
                    self.events.append(("throw", max(-5000.0, min(5000.0, vx)), max(-5000.0, min(5000.0, vy))))
            return 0
        return None

    def follow_mouse(self) -> None:
        """While dragging: stick to the mouse."""
        if self.dragging:
            cx, cy = win_input.cursor_pos()
            nx, ny = cx - self._grab_off[0], cy - self._grab_off[1]
            self._moved += math.hypot(nx - self.x, ny - self.y)
            self.x, self.y = nx, ny
            now = time.perf_counter()
            self._samples.append((now, float(cx), float(cy)))
            self._samples = [s for s in self._samples if now - s[0] < 0.15]

    def show(self, img: Image.Image | None = None, x: float | None = None, y: float | None = None,
             alpha: int = 255) -> None:
        if img is not None:
            self.img = img
        if x is not None:
            self.x = x
        if y is not None:
            self.y = y
        self.visible = True
        self._push(alpha)

    def hide(self) -> None:
        self.visible = False
        self.dragging = False
        if self._shown:
            user32.ShowWindow(self.hwnd, 0)
            self._shown = False
            self._last = None

    def destroy(self) -> None:
        self.hide()
        _SPRITES.pop(self.hwnd, None)
        user32.DestroyWindow(self.hwnd)

    def _push(self, alpha: int) -> None:
        if self.img is None or alpha <= 0:
            self.hide()
            return
        key = (id(self.img), int(round(self.x)), int(round(self.y)), alpha)
        if key == self._last and self._shown:
            return
        self._last = key
        img = self.img
        data = _premultiplied_bgra(img)
        screen = user32.GetDC(None)
        mem = gdi32.CreateCompatibleDC(screen)
        bmi = BITMAPINFO()
        bmi.bmiHeader.biSize = ctypes.sizeof(BITMAPINFOHEADER)
        bmi.bmiHeader.biWidth, bmi.bmiHeader.biHeight = img.width, -img.height
        bmi.bmiHeader.biPlanes, bmi.bmiHeader.biBitCount = 1, 32
        bits = ctypes.c_void_p()
        hbmp = gdi32.CreateDIBSection(screen, ctypes.byref(bmi), 0, ctypes.byref(bits), None, 0)
        try:
            ctypes.memmove(bits, data, len(data))
            old = gdi32.SelectObject(mem, hbmp)
            dst = wt.POINT(key[1], key[2])
            size, src = wt.SIZE(img.width, img.height), wt.POINT(0, 0)
            blend = BLENDFUNCTION(0, 0, max(0, min(255, alpha)), AC_SRC_ALPHA)
            user32.UpdateLayeredWindow(self.hwnd, screen, ctypes.byref(dst), ctypes.byref(size), mem,
                                       ctypes.byref(src), 0, ctypes.byref(blend), ULW_ALPHA)
            gdi32.SelectObject(mem, old)
        finally:
            gdi32.DeleteObject(hbmp)
            gdi32.DeleteDC(mem)
            user32.ReleaseDC(None, screen)
        if not self._shown:
            user32.ShowWindow(self.hwnd, SW_SHOWNOACTIVATE)
            self._shown = True


# ---- pictures ------------------------------------------------------------------------------------
def _glow(img: Image.Image, color, r_frac=0.42, blur=0.06) -> None:
    n = img.width
    g = Image.new("RGBA", img.size, (0, 0, 0, 0))
    c, r = n / 2, n * r_frac
    ImageDraw.Draw(g).ellipse((c - r, c - r, c + r, c + r), fill=color)
    img.alpha_composite(g.filter(ImageFilter.GaussianBlur(n * blur)))


def ball_image(size: int) -> Image.Image:
    n = size * 2
    img = Image.new("RGBA", (n, n), (0, 0, 0, 0))
    d = ImageDraw.Draw(img, "RGBA")
    c, r = n / 2, n * 0.44
    d.ellipse((c - r, c - r + n * 0.02, c + r, c + r + n * 0.02), fill=(160, 40, 60, 255))
    d.ellipse((c - r, c - r, c + r, c + r), fill=(255, 92, 120, 255))
    d.arc((c - r * 1.6, c - r * 0.55, c + r * 0.4, c + r * 1.6), 280, 360, fill=(255, 235, 120, 255), width=int(n * 0.06))
    d.arc((c - r * 0.4, c - r * 1.6, c + r * 1.6, c + r * 0.55), 100, 180, fill=(255, 235, 120, 255), width=int(n * 0.06))
    d.ellipse((c - r * 0.6, c - r * 0.7, c - r * 0.1, c - r * 0.3), fill=(255, 255, 255, 150))
    return img.resize((size, size), Image.LANCZOS)


def bubble_image(size: int, hue: int = 0) -> Image.Image:
    n = size * 2
    img = Image.new("RGBA", (n, n), (0, 0, 0, 0))
    d = ImageDraw.Draw(img, "RGBA")
    c, r = n / 2, n * 0.45
    tints = [(150, 210, 255), (255, 170, 230), (180, 255, 210), (255, 230, 150)]
    tint = tints[hue % len(tints)]
    d.ellipse((c - r, c - r, c + r, c + r), fill=tint + (45,), outline=tint + (210,), width=int(n * 0.03))
    d.arc((c - r * 0.8, c - r * 0.8, c + r * 0.8, c + r * 0.8), 200, 260, fill=(255, 255, 255, 230), width=int(n * 0.05))
    d.ellipse((c + r * 0.3, c - r * 0.55, c + r * 0.5, c - r * 0.35), fill=(255, 255, 255, 220))
    return img.resize((size, size), Image.LANCZOS)


def pop_image(size: int) -> Image.Image:
    n = size * 2
    img = Image.new("RGBA", (n, n), (0, 0, 0, 0))
    d = ImageDraw.Draw(img, "RGBA")
    c = n / 2
    for i in range(10):
        a = i * math.pi / 5
        d.line([(c + math.cos(a) * n * 0.22, c + math.sin(a) * n * 0.22),
                (c + math.cos(a) * n * 0.42, c + math.sin(a) * n * 0.42)], fill=(200, 230, 255, 230), width=int(n * 0.04))
    return img.resize((size, size), Image.LANCZOS)


def cookie_image(size: int) -> Image.Image:
    n = size * 2
    img = Image.new("RGBA", (n, n), (0, 0, 0, 0))
    d = ImageDraw.Draw(img, "RGBA")
    c, r = n / 2, n * 0.44
    d.ellipse((c - r, c - r + n * 0.03, c + r, c + r + n * 0.03), fill=(140, 82, 36, 255))
    d.ellipse((c - r, c - r, c + r, c + r), fill=(214, 150, 78, 255))
    for ox, oy, cr in ((-0.45, -0.3, 0.17), (0.36, -0.38, 0.14), (0.06, 0.04, 0.16), (-0.3, 0.42, 0.13), (0.46, 0.26, 0.15)):
        x, y, rr = c + ox * r, c + oy * r, cr * r
        d.ellipse((x - rr, y - rr, x + rr, y + rr), fill=(88, 48, 24, 255))
    return img.resize((size, size), Image.LANCZOS)


def egg_image(size: int, crack: int = 0) -> Image.Image:
    n = size * 2
    img = Image.new("RGBA", (n, int(n * 1.2)), (0, 0, 0, 0))
    d = ImageDraw.Draw(img, "RGBA")
    w, h = n, int(n * 1.2)
    d.ellipse((w * 0.12, h * 0.05, w * 0.88, h * 0.98), fill=(250, 246, 235, 255), outline=(200, 190, 170, 255), width=int(n * 0.02))
    for sx, sy in ((0.35, 0.4), (0.62, 0.6), (0.45, 0.75)):
        d.ellipse((w * sx - n * 0.05, h * sy - n * 0.05, w * sx + n * 0.05, h * sy + n * 0.05), fill=(140, 200, 255, 255))
    if crack:
        pts = [(w * 0.2, h * 0.45), (w * 0.32, h * 0.38), (w * 0.42, h * 0.48), (w * 0.55, h * 0.37), (w * 0.67, h * 0.47),
               (w * 0.8, h * 0.4)]
        d.line(pts[:2 + crack * 2], fill=(120, 100, 80, 255), width=int(n * 0.025), joint="curve")
    return img.resize((size, int(size * 1.2)), Image.LANCZOS)


def baby_image(size: int, eyes: str = "open") -> Image.Image:
    """A tiny version of BOT: blue blob, big black eyes, pink cheeks."""
    n = size * 2
    img = Image.new("RGBA", (n, n), (0, 0, 0, 0))
    d = ImageDraw.Draw(img, "RGBA")
    x0, y0, x1, y1 = n * 0.06, n * 0.18, n * 0.94, n * 0.96
    d.rounded_rectangle((x0, y0 + n * 0.02, x1, y1), radius=n * 0.36, fill=(40, 105, 210, 255))
    d.rounded_rectangle((x0, y0, x1, y1 - n * 0.02), radius=n * 0.36, fill=(98, 168, 255, 255))
    d.ellipse((n * 0.2, y0 + n * 0.06, n * 0.55, y0 + n * 0.2), fill=(255, 255, 255, 100))
    ey = y0 + (y1 - y0) * 0.5
    for sx in (0.33, 0.67):
        ex = n * sx
        if eyes == "closed":
            d.arc((ex - n * 0.09, ey - n * 0.05, ex + n * 0.09, ey + n * 0.05), 20, 160, fill=(22, 24, 38, 255), width=int(n * 0.03))
        elif eyes == "happy":
            d.arc((ex - n * 0.1, ey - n * 0.06, ex + n * 0.1, ey + n * 0.1), 200, 340, fill=(22, 24, 38, 255), width=int(n * 0.035))
        else:
            d.ellipse((ex - n * 0.1, ey - n * 0.12, ex + n * 0.1, ey + n * 0.12), fill=(22, 24, 38, 255))
            d.ellipse((ex - n * 0.07, ey - n * 0.09, ex - n * 0.01, ey - n * 0.03), fill=(255, 255, 255, 255))
    for sx in (0.18, 0.82):
        d.ellipse((n * sx - n * 0.07, ey + n * 0.08, n * sx + n * 0.07, ey + n * 0.14), fill=(255, 126, 182, 180))
    q = n * 0.035
    my = ey + n * 0.15
    d.arc((n * 0.5 - 2 * q, my - q, n * 0.5, my + q), 0, 180, fill=(22, 24, 38, 255), width=int(n * 0.02))
    d.arc((n * 0.5, my - q, n * 0.5 + 2 * q, my + q), 0, 180, fill=(22, 24, 38, 255), width=int(n * 0.02))
    # a tiny sprout on its head
    d.line([(n * 0.5, y0 + n * 0.01), (n * 0.5, y0 - n * 0.1)], fill=(80, 190, 110, 255), width=int(n * 0.03))
    d.ellipse((n * 0.5, y0 - n * 0.16, n * 0.62, y0 - n * 0.08), fill=(110, 220, 130, 255))
    return img.resize((size, size), Image.LANCZOS)
