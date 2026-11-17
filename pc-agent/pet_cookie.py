"""
A cookie 🍪 that pops up somewhere on the screen when the desktop BOT is hungry.

Drag it onto BOT to feed it (or just click it and it flies to BOT's mouth).
It is a tiny layered window of its own, created on the desktop BOT's thread.
"""
from __future__ import annotations

import ctypes
import ctypes.wintypes as wt
import math
import random
import time

from PIL import Image, ImageDraw, ImageFilter

import win_input
from overlay import (AC_SRC_ALPHA, BITMAPINFO, BITMAPINFOHEADER, BLENDFUNCTION, SW_SHOWNOACTIVATE, ULW_ALPHA,
                     WNDCLASSEXW, WNDPROC, WS_EX_LAYERED, WS_EX_NOACTIVATE, WS_EX_TOOLWINDOW, WS_EX_TOPMOST,
                     WS_POPUP, _premultiplied_bgra, gdi32, kernel32, user32)


def _star(cx, cy, r, inner=0.3):
    pts = []
    for i in range(8):
        a = -math.pi / 2 + i * math.pi / 4
        rr = r if i % 2 == 0 else r * inner
        pts.append((cx + math.cos(a) * rr, cy + math.sin(a) * rr))
    return pts


class Cookie:
    def __init__(self):
        self.visible = False   # waiting on the screen to be eaten
        self.dragging = False
        self.flying = False    # flying into BOT's mouth
        self.x = self.y = 0.0
        self.size = 80
        self._hwnd = None
        self._shown = False
        self._frames: list[Image.Image] = []
        self._grab_off = (0.0, 0.0)
        self._grab_t = self._moved = 0.0
        self._released = ""    # "click" / "drop", handled on the next step()
        self._t0 = 0.0
        self._last = None

    @property
    def center(self):
        return self.x + self.size / 2, self.y + self.size / 2

    def setup(self, body_size: int, bounds) -> None:
        self.S, self.bounds = body_size, bounds
        self.size = int(body_size * 0.72)
        self._frames = [self._draw(False), self._draw(True)]
        self._hand = user32.LoadCursorW(None, ctypes.c_void_p(32649))  # IDC_HAND
        self._wndproc = WNDPROC(self._wnd)
        hinst = kernel32.GetModuleHandleW(None)
        wc = WNDCLASSEXW()
        wc.cbSize = ctypes.sizeof(WNDCLASSEXW)
        wc.lpfnWndProc = self._wndproc
        wc.hInstance = hinst
        wc.lpszClassName = "BotCookie"
        user32.RegisterClassExW(ctypes.byref(wc))
        ex = WS_EX_LAYERED | WS_EX_TOPMOST | WS_EX_TOOLWINDOW | WS_EX_NOACTIVATE
        self._hwnd = user32.CreateWindowExW(ex, "BotCookie", "Cookie", WS_POPUP, 0, 0, self.size, self.size,
                                            None, None, hinst, None)

    # -- what BOT asks for -----------------------------------------------------------
    def spawn(self, avoid) -> None:
        """Put a cookie somewhere on the screen, away from BOT."""
        left, top, right, bottom = self.bounds
        x = y = 0.0
        for _ in range(40):
            x = random.uniform(left + 60, right - 60 - self.size)
            y = random.uniform(top + 80, bottom - self.size - 60)
            if math.hypot(x + self.size / 2 - avoid[0], y + self.size / 2 - avoid[1]) > self.S * 3.2:
                break
        self.x, self.y = x, y
        self.visible, self.flying, self.dragging = True, False, False
        self._t0 = time.perf_counter()
        self._last = None
        self._shown = False  # show again -> it pops on top of other windows

    def fly_home(self) -> None:
        if self.visible:
            self.dragging, self.flying = False, True

    # -- mouse ---------------------------------------------------------------------
    def _wnd(self, hwnd, msg, wparam, lparam):
        if msg == 0x0021:            # WM_MOUSEACTIVATE: never steal focus
            return 3
        if msg == 0x0020:            # WM_SETCURSOR
            user32.SetCursor(self._hand)
            return 1
        if msg == 0x0201 and self.visible and not self.flying:  # WM_LBUTTONDOWN
            cx, cy = win_input.cursor_pos()
            self.dragging = True
            self._grab_off = (cx - self.x, cy - self.y)
            self._grab_t, self._moved = time.perf_counter(), 0.0
            user32.SetCapture(self._hwnd)
            return 0
        if msg == 0x0202 or (msg == 0x0215 and self.dragging):  # WM_LBUTTONUP / WM_CAPTURECHANGED
            if self.dragging:
                self.dragging = False
                user32.ReleaseCapture()
                quick = time.perf_counter() - self._grab_t < 0.35
                self._released = "click" if self._moved < 6 and quick else "drop"
            return 0
        return user32.DefWindowProcW(hwnd, msg, wparam, lparam)

    # -- every frame -----------------------------------------------------------------
    def step(self, dt: float, mouth, reach: float, show: bool) -> str:
        """Move / draw the cookie. Returns "eaten" when it reached BOT."""
        if not self.visible:
            self._hide()
            return ""
        now = time.perf_counter()
        if self.dragging:
            cx, cy = win_input.cursor_pos()
            nx, ny = cx - self._grab_off[0], cy - self._grab_off[1]
            self._moved += math.hypot(nx - self.x, ny - self.y)
            self.x, self.y = nx, ny
        elif self.flying:
            tx, ty = mouth[0] - self.size / 2, mouth[1] - self.size / 2
            dx, dy = tx - self.x, ty - self.y
            dist = math.hypot(dx, dy)
            step = 1500 * dt
            if dist <= step + 4:
                return self._eaten()
            self.x += dx / dist * step
            self.y += dy / dist * step
        released, self._released = self._released, ""
        if released == "click":
            self.flying = True
        elif released == "drop":
            cx, cy = self.center
            if math.hypot(cx - mouth[0], cy - mouth[1]) < reach:  # dropped on BOT: nom!
                return self._eaten()
        idle = not (self.dragging or self.flying)
        frame = int((now - self._t0) / 0.6) % 2 if idle else 0
        bob = math.sin((now - self._t0) * 2.6) * self.size * 0.05 if idle else 0.0
        self._push(frame, self.x, self.y + bob, 255 if show else 0)
        return ""

    def _eaten(self) -> str:
        self.visible = self.dragging = self.flying = False
        self._hide()
        return "eaten"

    def _hide(self) -> None:
        if self._shown and self._hwnd:
            user32.ShowWindow(self._hwnd, 0)
            self._shown = False
            self._last = None

    def _push(self, frame: int, x: float, y: float, alpha: int) -> None:
        if alpha <= 0:
            self._hide()
            return
        key = (frame, int(round(x)), int(round(y)))
        if key == self._last and self._shown:
            return
        self._last = key
        img = self._frames[frame]
        data = _premultiplied_bgra(img)
        screen = user32.GetDC(None)
        mem = gdi32.CreateCompatibleDC(screen)
        bmi = BITMAPINFO()
        bmi.bmiHeader.biSize = ctypes.sizeof(BITMAPINFOHEADER)
        bmi.bmiHeader.biWidth, bmi.bmiHeader.biHeight = self.size, -self.size
        bmi.bmiHeader.biPlanes, bmi.bmiHeader.biBitCount = 1, 32
        bits = ctypes.c_void_p()
        hbmp = gdi32.CreateDIBSection(screen, ctypes.byref(bmi), 0, ctypes.byref(bits), None, 0)
        try:
            ctypes.memmove(bits, data, len(data))
            old = gdi32.SelectObject(mem, hbmp)
            dst = wt.POINT(key[1], key[2])
            size, src = wt.SIZE(self.size, self.size), wt.POINT(0, 0)
            blend = BLENDFUNCTION(0, 0, alpha, AC_SRC_ALPHA)
            user32.UpdateLayeredWindow(self._hwnd, screen, ctypes.byref(dst), ctypes.byref(size), mem,
                                       ctypes.byref(src), 0, ctypes.byref(blend), ULW_ALPHA)
            gdi32.SelectObject(mem, old)
        finally:
            gdi32.DeleteObject(hbmp)
            gdi32.DeleteDC(mem)
            user32.ReleaseDC(None, screen)
        if not self._shown:
            user32.ShowWindow(self._hwnd, SW_SHOWNOACTIVATE)
            self._shown = True

    # -- drawing -------------------------------------------------------------------
    def _draw(self, sparkle: bool) -> Image.Image:
        n = self.size * 2
        c, r = n / 2, n * 0.3
        img = Image.new("RGBA", (n, n), (0, 0, 0, 0))
        glow = Image.new("RGBA", (n, n), (0, 0, 0, 0))
        ImageDraw.Draw(glow).ellipse((c - r * 1.4, c - r * 1.4, c + r * 1.4, c + r * 1.4), fill=(255, 210, 110, 110))
        img.alpha_composite(glow.filter(ImageFilter.GaussianBlur(n * 0.05)))
        d = ImageDraw.Draw(img, "RGBA")
        d.ellipse((c - r, c - r + n * 0.02, c + r, c + r + n * 0.02), fill=(140, 82, 36, 255))   # underside
        d.ellipse((c - r, c - r, c + r, c + r), fill=(214, 150, 78, 255))
        shine = Image.new("RGBA", (n, n), (0, 0, 0, 0))
        ImageDraw.Draw(shine).ellipse((c - r * 0.75, c - r * 0.8, c + r * 0.25, c - r * 0.05), fill=(255, 225, 160, 120))
        img.alpha_composite(shine.filter(ImageFilter.GaussianBlur(n * 0.03)))
        d = ImageDraw.Draw(img, "RGBA")
        for ox, oy, cr in ((-0.45, -0.3, 0.16), (0.36, -0.38, 0.13), (0.06, 0.04, 0.15), (-0.3, 0.42, 0.12),
                           (0.46, 0.26, 0.14), (-0.62, 0.12, 0.09)):
            x, y, rr = c + ox * r, c + oy * r, cr * r
            d.ellipse((x - rr, y - rr, x + rr, y + rr), fill=(88, 48, 24, 255))
            d.ellipse((x - rr * 0.6, y - rr * 0.6, x - rr * 0.05, y - rr * 0.05), fill=(150, 95, 60, 200))
        if sparkle:
            d.polygon(_star(c + r * 0.92, c - r * 0.92, n * 0.085), fill=(255, 255, 235, 255))
            d.polygon(_star(c - r * 1.05, c + r * 0.7, n * 0.05), fill=(255, 245, 200, 230))
        return img.resize((self.size, self.size), Image.LANCZOS)
