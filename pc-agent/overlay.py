"""
BOT's own cursor: a glowing blue bubble with a pointer that glides to wherever BOT
is about to act, pulses when it clicks, and shows a small label ("Opening Chrome").

It is a click-through, always-on-top window that never takes keyboard focus,
so it can't get in the way of what you (or BOT) are doing.
"""
from __future__ import annotations

import ctypes
import ctypes.wintypes as wt
import logging
import math
import queue
import threading
import time

from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont

import win_input

log = logging.getLogger("bot")

# ---- Win32 plumbing -------------------------------------------------------------
user32 = ctypes.WinDLL("user32", use_last_error=True)
gdi32 = ctypes.WinDLL("gdi32", use_last_error=True)
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

LRESULT = ctypes.c_ssize_t
WNDPROC = ctypes.WINFUNCTYPE(LRESULT, wt.HWND, wt.UINT, wt.WPARAM, wt.LPARAM)

WS_POPUP = 0x80000000
WS_EX_LAYERED, WS_EX_TRANSPARENT, WS_EX_TOPMOST = 0x00080000, 0x00000020, 0x00000008
WS_EX_TOOLWINDOW, WS_EX_NOACTIVATE = 0x00000080, 0x08000000
SW_HIDE, SW_SHOWNOACTIVATE = 0, 4
ULW_ALPHA, AC_SRC_ALPHA, PM_REMOVE = 2, 1, 1


class WNDCLASSEXW(ctypes.Structure):
    _fields_ = [("cbSize", wt.UINT), ("style", wt.UINT), ("lpfnWndProc", WNDPROC),
                ("cbClsExtra", ctypes.c_int), ("cbWndExtra", ctypes.c_int), ("hInstance", wt.HINSTANCE),
                ("hIcon", wt.HICON), ("hCursor", wt.HANDLE), ("hbrBackground", wt.HBRUSH),
                ("lpszMenuName", wt.LPCWSTR), ("lpszClassName", wt.LPCWSTR), ("hIconSm", wt.HICON)]


class BLENDFUNCTION(ctypes.Structure):
    _fields_ = [("BlendOp", ctypes.c_ubyte), ("BlendFlags", ctypes.c_ubyte),
                ("SourceConstantAlpha", ctypes.c_ubyte), ("AlphaFormat", ctypes.c_ubyte)]


class BITMAPINFOHEADER(ctypes.Structure):
    _fields_ = [("biSize", wt.DWORD), ("biWidth", wt.LONG), ("biHeight", wt.LONG), ("biPlanes", wt.WORD),
                ("biBitCount", wt.WORD), ("biCompression", wt.DWORD), ("biSizeImage", wt.DWORD),
                ("biXPelsPerMeter", wt.LONG), ("biYPelsPerMeter", wt.LONG), ("biClrUsed", wt.DWORD),
                ("biClrImportant", wt.DWORD)]


class BITMAPINFO(ctypes.Structure):
    _fields_ = [("bmiHeader", BITMAPINFOHEADER), ("bmiColors", wt.DWORD * 3)]


user32.DefWindowProcW.argtypes = [wt.HWND, wt.UINT, wt.WPARAM, wt.LPARAM]
user32.DefWindowProcW.restype = LRESULT
user32.RegisterClassExW.argtypes = [ctypes.POINTER(WNDCLASSEXW)]
user32.RegisterClassExW.restype = wt.ATOM
user32.CreateWindowExW.argtypes = [wt.DWORD, wt.LPCWSTR, wt.LPCWSTR, wt.DWORD, ctypes.c_int, ctypes.c_int,
                                   ctypes.c_int, ctypes.c_int, wt.HWND, wt.HMENU, wt.HINSTANCE, wt.LPVOID]
user32.CreateWindowExW.restype = wt.HWND
user32.ShowWindow.argtypes = [wt.HWND, ctypes.c_int]
user32.UpdateLayeredWindow.argtypes = [wt.HWND, wt.HDC, ctypes.POINTER(wt.POINT), ctypes.POINTER(wt.SIZE), wt.HDC,
                                       ctypes.POINTER(wt.POINT), wt.COLORREF, ctypes.POINTER(BLENDFUNCTION),
                                       wt.DWORD]
user32.GetAsyncKeyState.argtypes = [ctypes.c_int]
user32.GetAsyncKeyState.restype = ctypes.c_short
user32.GetDC.argtypes = [wt.HWND]
user32.GetDC.restype = wt.HDC
user32.ReleaseDC.argtypes = [wt.HWND, wt.HDC]
user32.PeekMessageW.argtypes = [ctypes.POINTER(wt.MSG), wt.HWND, wt.UINT, wt.UINT, wt.UINT]
user32.TranslateMessage.argtypes = [ctypes.POINTER(wt.MSG)]
user32.DispatchMessageW.argtypes = [ctypes.POINTER(wt.MSG)]
user32.DispatchMessageW.restype = LRESULT
gdi32.CreateCompatibleDC.argtypes = [wt.HDC]
gdi32.CreateCompatibleDC.restype = wt.HDC
gdi32.CreateDIBSection.argtypes = [wt.HDC, ctypes.POINTER(BITMAPINFO), wt.UINT, ctypes.POINTER(ctypes.c_void_p),
                                   wt.HANDLE, wt.DWORD]
gdi32.CreateDIBSection.restype = wt.HBITMAP
gdi32.SelectObject.argtypes = [wt.HDC, wt.HGDIOBJ]
gdi32.SelectObject.restype = wt.HGDIOBJ
gdi32.DeleteObject.argtypes = [wt.HGDIOBJ]
gdi32.DeleteDC.argtypes = [wt.HDC]
kernel32.GetModuleHandleW.argtypes = [wt.LPCWSTR]
kernel32.GetModuleHandleW.restype = wt.HMODULE

# ---- drawing --------------------------------------------------------------------
BLUE = (79, 195, 255)
BLUE_DEEP = (47, 123, 255)
LIGHT = (184, 236, 255)
NAVY = (12, 20, 48)
RED = (255, 120, 120)
IMG_W, IMG_H = 460, 112     # window size
ANCHOR = 56                 # bubble centre (the click point) inside the window
SS = 2                      # supersampling for smooth edges
ARROW = [(0, 0), (0, 21), (5, 16.5), (8.6, 24.5), (12, 23), (8.4, 15.2), (15, 15)]

_base_cache: Image.Image | None = None
_label_cache: dict[tuple[str, bool], Image.Image] = {}


def _font(size: int):
    for name in ("segoeuib.ttf", "segoeui.ttf", "arial.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default()


def _base() -> Image.Image:
    """Glow + bubble + pointer (drawn once, at 2x)."""
    global _base_cache
    if _base_cache is None:
        w, h, c = IMG_W * SS, IMG_H * SS, ANCHOR * SS
        glow = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        r = 31 * SS
        ImageDraw.Draw(glow).ellipse((c - r, c - r, c + r, c + r), fill=BLUE + (160,))
        img = glow.filter(ImageFilter.GaussianBlur(9 * SS))
        d = ImageDraw.Draw(img)
        r = 22 * SS
        d.ellipse((c - r, c - r, c + r, c + r), fill=BLUE_DEEP + (165,), outline=LIGHT + (255,), width=3 * SS)
        pts = [(c + x * SS * 1.1, c + y * SS * 1.1) for x, y in ARROW]
        d.polygon(pts, fill=(255, 255, 255, 255), outline=(10, 30, 70, 255))
        _base_cache = img
    return _base_cache


def _label(text: str, ok: bool) -> Image.Image:
    key = (text, ok)
    if key not in _label_cache:
        w, h, c = IMG_W * SS, IMG_H * SS, ANCHOR * SS
        img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        if text:
            d = ImageDraw.Draw(img)
            f = _font(15 * SS)
            text = text if len(text) <= 44 else text[:43] + "…"
            x0 = (ANCHOR + 36) * SS
            x1 = min(x0 + d.textlength(text, font=f) + 28 * SS, w - 2 * SS)
            d.rounded_rectangle((x0, c - 17 * SS, x1, c + 17 * SS), radius=17 * SS, fill=NAVY + (235,),
                                outline=(BLUE if ok else RED) + (255,), width=2 * SS)
            d.text((x0 + 14 * SS, c), text, font=f, fill=(235, 245, 255, 255), anchor="lm")
        if len(_label_cache) > 64:
            _label_cache.clear()
        _label_cache[key] = img
    return _label_cache[key]


def render(text: str, ok: bool = True, ring: float = -1.0) -> Image.Image:
    img = Image.alpha_composite(_base(), _label(text, ok))
    if 0 <= ring < 1:  # click pulse: a ring that grows and fades
        c = ANCHOR * SS
        rr = (22 + 28 * ring) * SS
        ring_img = Image.new("RGBA", img.size, (0, 0, 0, 0))
        ImageDraw.Draw(ring_img).ellipse((c - rr, c - rr, c + rr, c + rr),
                                         outline=LIGHT + (int(255 * (1 - ring)),), width=3 * SS)
        img = Image.alpha_composite(img, ring_img)
    return img.resize((IMG_W, IMG_H), Image.LANCZOS)


def _premultiplied_bgra(img: Image.Image) -> bytes:
    r, g, b, a = img.split()
    return Image.merge("RGBA", (ImageChops.multiply(b, a), ImageChops.multiply(g, a),
                                ImageChops.multiply(r, a), a)).tobytes()


# ---- the overlay ----------------------------------------------------------------

class Overlay:
    """Thread-safe: call pop / glide_to / pulse from any thread."""

    def __init__(self):
        self.enabled = False        # the window works
        self.wanted = True          # the user wants to see it (can be switched off from the phone)
        self._cancelled = False
        self.origin = None          # callable -> (x, y) or None: where the bubble appears (the desktop BOT)
        self._q: queue.Queue = queue.Queue()
        self._thread: threading.Thread | None = None
        self._hwnd = None
        self._wndproc = None
        self._pos = (0.0, 0.0)
        self._alpha = 0.0
        self._alpha_target = 0.0
        self._shown = False
        self._data = b""
        self._text, self._ok = "", True
        self._glide = None          # (from, to, t0, duration, event)
        self._mouse_at_start = (0, 0)
        self._pulse_t0 = None
        self._hide_at = None

    # -- public API -------------------------------------------------------------
    def start(self) -> None:
        if self._thread is None:
            self._thread = threading.Thread(target=self._run, name="bubble-cursor", daemon=True)
            self._thread.start()

    @property
    def active(self) -> bool:
        return self.enabled and self.wanted

    def set_wanted(self, on: bool) -> None:
        """Switch the bubble on/off (from the phone or by voice)."""
        self.wanted = on
        if not on and self.enabled:
            self._q.put(("hide",))

    def pop(self, text: str, ok: bool = True, hold: float = 2.0) -> None:
        """Show the bubble (at the mouse, if hidden) with a message, then fade out."""
        if self.active:
            self._q.put(("pop", text, ok, hold))

    def glide_to(self, x: float, y: float, text: str = "") -> bool:
        """Glide smoothly to (x, y) and wait until it arrives, so the caller can click there.

        Returns False if YOU cancelled it (moved the mouse or pressed Esc during the glide):
        the caller must then NOT click. With the bubble switched off it returns True at once.
        """
        if not self.active:
            return True
        done = threading.Event()
        self._q.put(("glide", float(x), float(y), text, done))
        done.wait(2.0)
        return not self._cancelled

    def pulse(self, hold: float = 1.2) -> None:
        if self.active:
            self._q.put(("pulse", hold))

    def set_color(self, hex_color: str) -> None:
        """Recolour the bubble (e.g. '#FF7EB6' for a pink BOT)."""
        h = hex_color.lstrip("#")
        rgb = tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))
        self._q.put(("color", rgb))

    def position(self) -> tuple[float, float, bool]:
        """(x, y, visible): lets the phone's eyes follow the bubble while BOT works."""
        x, y = self._pos
        return x, y, self.active and self._alpha > 10

    # -- window thread ----------------------------------------------------------
    def _run(self) -> None:
        try:
            self._create_window()
            self.enabled = True
        except Exception as exc:  # no desktop, odd system... BOT still works without the bubble
            log.warning("Bubble cursor disabled: %s", exc)
            return
        msg = wt.MSG()
        while True:
            while user32.PeekMessageW(ctypes.byref(msg), None, 0, 0, PM_REMOVE):
                user32.TranslateMessage(ctypes.byref(msg))
                user32.DispatchMessageW(ctypes.byref(msg))
            try:
                while True:
                    self._handle(self._q.get_nowait())
            except queue.Empty:
                pass
            except Exception:
                log.exception("bubble command failed")
            busy = self._animate()
            time.sleep(1 / 60 if busy else 0.04)

    def _create_window(self) -> None:
        self._wndproc = WNDPROC(lambda h, m, w, l: user32.DefWindowProcW(h, m, w, l))  # keep a reference
        hinst = kernel32.GetModuleHandleW(None)
        wc = WNDCLASSEXW()
        wc.cbSize = ctypes.sizeof(WNDCLASSEXW)
        wc.lpfnWndProc = self._wndproc
        wc.hInstance = hinst
        wc.lpszClassName = "BotBubbleCursor"
        user32.RegisterClassExW(ctypes.byref(wc))
        ex = WS_EX_LAYERED | WS_EX_TRANSPARENT | WS_EX_TOPMOST | WS_EX_TOOLWINDOW | WS_EX_NOACTIVATE
        self._hwnd = user32.CreateWindowExW(ex, "BotBubbleCursor", "BOT cursor", WS_POPUP,
                                            0, 0, IMG_W, IMG_H, None, None, hinst, None)
        if not self._hwnd:
            raise ctypes.WinError(ctypes.get_last_error())
        self._set_image("", True)

    def _set_image(self, text: str, ok: bool, ring: float = -1.0) -> None:
        self._text, self._ok = text, ok
        self._data = _premultiplied_bgra(render(text, ok, ring))

    def _push(self) -> None:
        screen = user32.GetDC(None)
        mem = gdi32.CreateCompatibleDC(screen)
        bmi = BITMAPINFO()
        bmi.bmiHeader.biSize = ctypes.sizeof(BITMAPINFOHEADER)
        bmi.bmiHeader.biWidth, bmi.bmiHeader.biHeight = IMG_W, -IMG_H  # top-down
        bmi.bmiHeader.biPlanes, bmi.bmiHeader.biBitCount = 1, 32
        bits = ctypes.c_void_p()
        hbmp = gdi32.CreateDIBSection(screen, ctypes.byref(bmi), 0, ctypes.byref(bits), None, 0)
        try:
            ctypes.memmove(bits, self._data, len(self._data))
            old = gdi32.SelectObject(mem, hbmp)
            x, y = self._pos
            dst = wt.POINT(int(round(x)) - ANCHOR, int(round(y)) - ANCHOR)
            size = wt.SIZE(IMG_W, IMG_H)
            src = wt.POINT(0, 0)
            blend = BLENDFUNCTION(0, 0, max(0, min(255, int(self._alpha))), AC_SRC_ALPHA)
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

    def _handle(self, cmd) -> None:
        now = time.perf_counter()
        kind = cmd[0]
        if kind == "pop":
            _, text, ok, hold = cmd
            if self._alpha <= 1:
                self._pos = self._start_point()
            self._set_image(text, ok)
            self._alpha_target, self._hide_at = 255.0, now + hold
        elif kind == "glide":
            _, x, y, text, done = cmd
            if self._alpha <= 1:  # appear at the desktop BOT (or the mouse), then glide from there
                self._pos = self._start_point()
            self._set_image(text, True)
            dist = math.hypot(x - self._pos[0], y - self._pos[1])
            dur = min(0.5, 0.12 + dist / 2500)
            self._cancelled = False
            self._mouse_at_start = win_input.cursor_pos()
            self._glide = (self._pos, (x, y), now, dur, done)
            self._alpha_target, self._hide_at = 255.0, now + dur + 3.0  # a pulse/pop shortens this
        elif kind == "pulse":
            self._pulse_t0, self._hide_at = now, now + cmd[1]
        elif kind == "color":
            global BLUE, BLUE_DEEP, LIGHT, _base_cache
            rgb = cmd[1]
            BLUE = rgb
            BLUE_DEEP = tuple(int(c * 0.62) for c in rgb)
            LIGHT = tuple(int(c + (255 - c) * 0.65) for c in rgb)
            _base_cache = None
            _label_cache.clear()
            self._set_image(self._text, self._ok)
        elif kind == "hide":
            if self._glide:
                self._glide[4].set()
                self._glide = None
            self._alpha_target, self._hide_at = 0.0, None

    def _start_point(self) -> tuple[float, float]:
        try:
            p = self.origin() if self.origin else None
        except Exception:
            p = None
        return tuple(map(float, p)) if p else tuple(map(float, win_input.cursor_pos()))

    def _user_took_over(self) -> bool:
        """You moved the real mouse, or pressed Esc, while the bubble was on its way."""
        if user32.GetAsyncKeyState(0x1B) & 0x8000:  # Esc
            return True
        mx, my = win_input.cursor_pos()
        sx, sy = self._mouse_at_start
        return math.hypot(mx - sx, my - sy) > 25

    def _animate(self) -> bool:
        now = time.perf_counter()
        dirty = busy = False
        if self._glide and self._user_took_over():
            self._cancelled = True
            self._glide[4].set()
            self._glide = None
            self._set_image("Cancelled", False)
            self._hide_at = now + 1.2
            dirty = busy = True
        if self._glide:
            (fx, fy), (tx, ty), t0, dur, done = self._glide
            p = 1.0 if dur <= 0 else min(1.0, (now - t0) / dur)
            e = p * p * (3 - 2 * p)  # smooth start and stop
            self._pos = (fx + (tx - fx) * e, fy + (ty - fy) * e)
            dirty = busy = True
            if p >= 1:
                self._glide = None
                done.set()
        if self._pulse_t0 is not None:
            p = (now - self._pulse_t0) / 0.35
            if p >= 1:
                self._pulse_t0 = None
                self._set_image(self._text, self._ok)
            else:
                self._set_image(self._text, self._ok, ring=p)
            dirty = busy = True
        if self._hide_at is not None and now >= self._hide_at:
            self._alpha_target, self._hide_at = 0.0, None
        if self._alpha != self._alpha_target:
            step = 255 / (0.18 * 60)  # fade in/out in ~0.18 s
            if self._alpha < self._alpha_target:
                self._alpha = min(self._alpha_target, self._alpha + step)
            else:
                self._alpha = max(self._alpha_target, self._alpha - step)
            dirty = busy = True
        if dirty:
            if self._alpha > 0:
                self._push()
            elif self._shown:
                user32.ShowWindow(self._hwnd, SW_HIDE)
                self._shown = False
        return busy


BUBBLE = Overlay()
