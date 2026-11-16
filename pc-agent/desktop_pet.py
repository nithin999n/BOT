"""
BOT on your PC desktop: a small living robot face in the bottom-right corner.

Eyes follow your mouse, it blinks, yawns when you're idle, falls asleep after a while,
gets excited when a task starts (and watches the blue bubble fly out of it), sweats when
the CPU is busy, looks worried on low battery and sparkles while charging. Clicks always pass
through it, and it fades when your mouse comes close so it never hides anything.
"""
from __future__ import annotations

import ctypes
import ctypes.wintypes as wt
import logging
import math
import queue
import random
import threading
import time

from PIL import Image, ImageDraw, ImageFilter

import health
import win_input
from overlay import (AC_SRC_ALPHA, BITMAPINFO, BITMAPINFOHEADER, BLENDFUNCTION, BUBBLE, PM_REMOVE,
                     SW_SHOWNOACTIVATE, ULW_ALPHA, WNDCLASSEXW, WNDPROC, WS_EX_LAYERED, WS_EX_NOACTIVATE,
                     WS_EX_TOOLWINDOW, WS_EX_TOPMOST, WS_EX_TRANSPARENT, WS_POPUP, _font,
                     _premultiplied_bgra, gdi32, kernel32, user32)

log = logging.getLogger("bot")
SS = 2  # supersampling
NAVY = (26, 40, 86, 255)
SCREEN = (7, 12, 32, 255)
PINK = (255, 126, 182)


class _Rect(ctypes.Structure):
    _fields_ = [("left", ctypes.c_long), ("top", ctypes.c_long), ("right", ctypes.c_long), ("bottom", ctypes.c_long)]


def _mix(a, b, k):
    return tuple(int(a[i] + (b[i] - a[i]) * k) for i in range(3))


def _heart(cx, cy, r):
    pts = []
    for i in range(24):
        t = i / 24 * 2 * math.pi
        x = 16 * math.sin(t) ** 3
        y = 13 * math.cos(t) - 5 * math.cos(2 * t) - 2 * math.cos(3 * t) - math.cos(4 * t)
        pts.append((cx + x * r / 16, cy - y * r / 16))
    return pts


def _star(cx, cy, r, points=5, inner=0.45, rot=-math.pi / 2):
    return [(cx + math.cos(rot + i * math.pi / points) * (r if i % 2 == 0 else r * inner),
             cy + math.sin(rot + i * math.pi / points) * (r if i % 2 == 0 else r * inner))
            for i in range(points * 2)]


class Pet:
    """Thread-safe: call react() / set_wanted() / set_color() from anywhere."""

    def __init__(self):
        self.enabled = False      # window works
        self.wanted = True        # user wants it (phone menu / voice)
        self.health: dict = {"feeling": "ok"}
        self.busy_fn = lambda: False
        self._q: queue.Queue = queue.Queue()
        self._thread: threading.Thread | None = None
        self._color = (79, 195, 255)
        self._center = (0.0, 0.0)
        self._shown = False
        self._alpha = 0.0

    # -- public ------------------------------------------------------------------
    def start(self) -> None:
        if self._thread is None:
            self._thread = threading.Thread(target=self._run, name="desktop-pet", daemon=True)
            self._thread.start()

    def set_wanted(self, on: bool) -> None:
        self.wanted = on

    def set_color(self, hex_color: str) -> None:
        h = hex_color.lstrip("#")
        self._q.put(("color", tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))))

    def react(self, mood: str, seconds: float = 2.0) -> None:
        """Show a mood for a moment: happy, excited, sad, love, surprised."""
        self._q.put(("react", mood, seconds))

    def center(self):
        """Where the bubble should fly out from (None if the pet isn't showing)."""
        return self._center if self.enabled and self.wanted and self._alpha > 20 else None

    # -- window thread -------------------------------------------------------------
    def _run(self) -> None:
        try:
            self._setup()
            self.enabled = True
        except Exception as exc:
            log.warning("Desktop BOT disabled: %s", exc)
            return
        msg = wt.MSG()
        st = {"t0": time.perf_counter(), "blink": 0.0, "next_blink": 2.0, "look": (0.0, 0.0),
              "react": None, "react_until": 0.0, "yawn_until": 0.0, "next_yawn": 6.0, "particles": [],
              "next_particle": 0.0, "idle": 0.0, "idle_at": 0.0, "was_busy": False, "ant": 0.0, "ant_v": 0.0}
        last_sig = None
        while True:
            while user32.PeekMessageW(ctypes.byref(msg), None, 0, 0, PM_REMOVE):
                user32.TranslateMessage(ctypes.byref(msg))
                user32.DispatchMessageW(ctypes.byref(msg))
            try:
                while True:
                    cmd = self._q.get_nowait()
                    if cmd[0] == "color":
                        self._color = cmd[1]
                        self._glow = None
                        last_sig = None
                    elif cmd[0] == "react":
                        st["react"], st["react_until"] = cmd[1], time.perf_counter() + cmd[2]
                        st["ant_v"] += 9
            except queue.Empty:
                pass
            try:
                params = self._update(st)
                sig = params["sig"]
                if sig != last_sig:
                    last_sig = sig
                    self._push(self._render(params, st), params["alpha"])
                fps = 24 if params["active"] else (4 if params["mood"] == "asleep" else 12)
            except Exception:
                log.exception("desktop pet frame failed")
                fps = 1
            time.sleep(1 / fps)

    def _setup(self) -> None:
        try:
            scale = user32.GetDpiForSystem() / 96
        except (AttributeError, OSError):
            scale = 1.0
        self.S = int(118 * scale)               # head width
        self.W, self.H = int(self.S * 1.3), int(self.S * 1.45)
        wa = _Rect()
        user32.SystemParametersInfoW(0x0030, 0, ctypes.byref(wa), 0)  # SPI_GETWORKAREA
        self.x = wa.right - self.W - int(8 * scale)
        self.y = wa.bottom - self.H - int(4 * scale)
        self._center = (self.x + self.W / 2, self.y + self.H * 0.6)
        self._glow = None
        self._wndproc = WNDPROC(lambda h, m, w, l: user32.DefWindowProcW(h, m, w, l))
        hinst = kernel32.GetModuleHandleW(None)
        wc = WNDCLASSEXW()
        wc.cbSize = ctypes.sizeof(WNDCLASSEXW)
        wc.lpfnWndProc = self._wndproc
        wc.hInstance = hinst
        wc.lpszClassName = "BotDesktopPet"
        user32.RegisterClassExW(ctypes.byref(wc))
        ex = WS_EX_LAYERED | WS_EX_TRANSPARENT | WS_EX_TOPMOST | WS_EX_TOOLWINDOW | WS_EX_NOACTIVATE
        self._hwnd = user32.CreateWindowExW(ex, "BotDesktopPet", "BOT", WS_POPUP, self.x, self.y,
                                            self.W, self.H, None, None, hinst, None)
        if not self._hwnd:
            raise ctypes.WinError(ctypes.get_last_error())
        BUBBLE.origin = self.center  # the bubble flies out of the desktop BOT

    # -- behaviour -------------------------------------------------------------------
    def _update(self, st: dict) -> dict:
        now = time.perf_counter()
        t = now - st["t0"]
        if now - st["idle_at"] > 0.5:
            st["idle"], st["idle_at"] = health.idle_seconds(), now
            self.health_feeling = self.health.get("feeling", "ok")
        feeling = getattr(self, "health_feeling", "ok")
        bx, by, bubble_on = BUBBLE.position()
        busy = bubble_on or self.busy_fn()
        if busy and not st["was_busy"]:  # a task just started
            st["react"], st["react_until"] = "excited", now + 1.2
            st["ant_v"] += 10
        st["was_busy"] = busy

        if st["react"] and now < st["react_until"]:
            mood = st["react"]
        elif busy:
            mood = "working"
        elif feeling == "hot":
            mood = "sweaty"
        elif feeling == "low_battery":
            mood = "worried"
        elif st["idle"] > 300:
            mood = "asleep"
        elif st["idle"] > 60:
            mood = "drowsy"
        else:
            mood = "idle"

        # blink
        if t > st["next_blink"]:
            st["blink"], st["next_blink"] = t, t + random.uniform(2.5, 6)
        bp = (t - st["blink"]) / 0.15
        blink = math.sin(bp * math.pi) if 0 <= bp <= 1 else 0.0
        # yawn while drowsy
        if mood == "drowsy" and t > st["next_yawn"]:
            st["yawn_until"], st["next_yawn"] = t + 1.8, t + random.uniform(7, 12)
        yawning = mood == "drowsy" and t < st["yawn_until"]

        # where to look: the bubble while working, otherwise your mouse
        mx, my = (bx, by) if bubble_on else win_input.cursor_pos()
        cx, cy = self._center
        dx, dy = mx - cx, my - cy
        dist = max(1.0, math.hypot(dx, dy))
        target = (dx / dist * min(1.0, dist / 300), dy / dist * min(1.0, dist / 300))
        if mood == "asleep":
            target = (0.0, 0.5)
        lx, ly = st["look"]
        st["look"] = (lx + (target[0] - lx) * 0.35, ly + (target[1] - ly) * 0.35)

        # antenna spring
        st["ant_v"] += (-st["ant"] * 120 - st["ant_v"] * 7) * 0.05
        st["ant"] += st["ant_v"] * 0.05

        # particles
        if t > st["next_particle"]:
            st["next_particle"] = t + 1.2
            if mood == "asleep":
                st["particles"].append(["z", 0.3, -0.25, 0.06, -0.12, 2.4])
            elif mood in ("love", "happy") or (mood == "idle" and feeling == "charging" and random.random() < 0.3):
                kind = "heart" if mood == "love" else ("bolt" if mood == "idle" else "sparkle")
                st["particles"].append([kind, random.uniform(-0.3, 0.3), -0.2, random.uniform(-0.05, 0.05), -0.2, 1.6])
        for p in st["particles"]:
            p[1] += p[3] / 12
            p[2] += p[4] / 12
            p[5] -= 1 / 12
        st["particles"] = [p for p in st["particles"] if p[5] > 0]

        # fade when your mouse comes near, so you can see what's underneath
        rx, ry = win_input.cursor_pos()
        near = self.x - 30 < rx < self.x + self.W + 30 and self.y - 30 < ry < self.y + self.H + 30
        target_alpha = 0 if not self.wanted else (70 if near else 255)
        self._alpha += (target_alpha - self._alpha) * 0.35
        if abs(target_alpha - self._alpha) < 3:
            self._alpha = float(target_alpha)

        openness = {"asleep": 0.0, "drowsy": 0.45, "sweaty": 0.7, "worried": 0.9}.get(mood, 1.0)
        if yawning:
            openness = 0.1
        openness *= 1 - blink
        bob = math.sin(t * 9) * 0.03 if mood in ("excited", "happy") else 0.0
        active = bool(st["particles"]) or blink > 0 or mood in ("excited", "happy", "love", "working", "sweaty") \
            or abs(target_alpha - self._alpha) > 0 or abs(st["ant_v"]) > 0.05 or yawning
        sig = (mood, round(openness, 1), round(st["look"][0] * 6), round(st["look"][1] * 6), yawning,
               round(bob * 100), round(st["ant"] * 20), int(self._alpha),
               tuple((p[0], round(p[1] * 40), round(p[2] * 40)) for p in st["particles"]),
               (int(t * 2) if mood == "sweaty" else 0), self._color)
        return {"mood": mood, "open": openness, "look": st["look"], "yawn": yawning, "bob": bob,
                "ant": st["ant"], "alpha": self._alpha, "sig": sig, "active": active, "t": t,
                "particles": list(st["particles"])}

    # -- drawing -----------------------------------------------------------------------
    def _render(self, p: dict, st: dict) -> Image.Image:
        W, H, S = self.W * SS, self.H * SS, self.S * SS
        col = self._color
        light = _mix(col, (255, 255, 255), 0.6)
        img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        hw, hh = S * 0.9, S * 0.74
        cx = W / 2
        top = H * 0.27 + p["bob"] * S
        box = (cx - hw / 2, top, cx + hw / 2, top + hh)

        if self._glow is None:  # soft glow, drawn once per colour
            g = Image.new("RGBA", (W, H), (0, 0, 0, 0))
            ImageDraw.Draw(g).rounded_rectangle((cx - hw / 2 - 4 * SS, H * 0.27 - 4 * SS, cx + hw / 2 + 4 * SS,
                                                  H * 0.27 + hh + 4 * SS), radius=hw * 0.32, fill=col + (120,))
            self._glow = g.filter(ImageFilter.GaussianBlur(8 * SS))
        img.alpha_composite(self._glow)
        d = ImageDraw.Draw(img, "RGBA")

        # antenna + tip
        ax = cx + math.sin(p["ant"]) * hh * 0.25
        tip = (ax, top - hh * 0.22)
        d.line([(cx, top + SS), tip], fill=(46, 66, 120, 255), width=int(3.5 * SS))
        if p["mood"] in ("love", "happy", "excited"):
            d.polygon(_heart(tip[0], tip[1], 7 * SS), fill=PINK + (255,))
        else:
            r = 5 * SS
            d.ellipse((tip[0] - r, tip[1] - r, tip[0] + r, tip[1] + r), fill=col + (255,))
        # ears
        for side in (-1, 1):
            ex, ey, r = cx + side * (hw / 2 + 2 * SS), top + hh / 2, 9 * SS
            d.ellipse((ex - r, ey - r, ex + r, ey + r), fill=(30, 46, 94, 255), outline=col + (200,), width=2 * SS)
        # head + gloss
        d.rounded_rectangle(box, radius=hw * 0.32, fill=NAVY, outline=col + (255,), width=int(2.5 * SS))
        d.ellipse((box[0] + hw * 0.1, top + hh * 0.03, box[0] + hw * 0.55, top + hh * 0.17), fill=(255, 255, 255, 22))
        # screen
        inset = hw * 0.08
        sbox = (box[0] + inset, box[1] + inset, box[2] - inset, box[3] - inset)
        d.rounded_rectangle(sbox, radius=hw * 0.24, fill=SCREEN)
        sw, sh = sbox[2] - sbox[0], sbox[3] - sbox[1]
        scx, scy = (sbox[0] + sbox[2]) / 2, (sbox[1] + sbox[3]) / 2
        lx, ly = p["look"][0] * sw * 0.12, p["look"][1] * sh * 0.12

        mood = p["mood"]
        ew, eh = sw * 0.19, sh * 0.45
        for side in (-1, 1):
            ex, ey = scx + side * sw * 0.21 + lx, scy - sh * 0.08 + ly
            if mood in ("happy", "excited") and mood == "excited" and st:
                d.polygon(_star(ex, ey, ew * 0.75), fill=(255, 226, 122, 255))
            elif mood == "love":
                d.polygon(_heart(ex, ey, ew * 0.7), fill=PINK + (255,))
            elif mood == "happy":
                d.arc((ex - ew * 0.7, ey - eh * 0.25, ex + ew * 0.7, ey + eh * 0.55), 200, 340,
                      fill=light + (255,), width=int(ew * 0.3))
            elif p["open"] < 0.12:  # closed: sleeping / blinking / yawning
                d.arc((ex - ew * 0.6, ey - eh * 0.25, ex + ew * 0.6, ey + eh * 0.2), 20, 160,
                      fill=light + (255,), width=int(ew * 0.22))
            else:
                h = max(eh * p["open"], ew * 0.3)
                d.rounded_rectangle((ex - ew / 2, ey - h / 2, ex + ew / 2, ey + h / 2), radius=ew / 2,
                                    fill=light + (255,))
                if p["open"] > 0.4:
                    r1, r2 = ew * 0.2, ew * 0.09
                    hx, hy = ex - ew * 0.15, ey - h * 0.22
                    d.ellipse((hx - r1, hy - r1, hx + r1, hy + r1), fill=(255, 255, 255, 240))
                    hx, hy = ex + ew * 0.15, ey + h * 0.18
                    d.ellipse((hx - r2, hy - r2, hx + r2, hy + r2), fill=(255, 255, 255, 200))
                if mood == "worried":  # droopy outer corners
                    t0 = ey - h / 2 - 2 * SS
                    ox, ix = ex + side * ew * 0.8, ex - side * ew * 0.8
                    d.polygon([(ox, t0), (ix, t0), (ox, t0 + h * 0.5)], fill=SCREEN)
        # cheeks
        blush = 140 if mood in ("love", "happy", "excited") else 80
        for side in (-1, 1):
            chx, chy = scx + side * sw * 0.34 + lx * 0.5, scy + sh * 0.18 + ly * 0.5
            d.ellipse((chx - sw * 0.08, chy - sh * 0.045, chx + sw * 0.08, chy + sh * 0.045), fill=PINK + (blush,))
        # mouth
        mx, my = scx + lx * 0.3, scy + sh * 0.27 + ly * 0.3
        mw = sw * 0.2
        if p["yawn"]:
            d.ellipse((mx - mw * 0.25, my - sh * 0.1, mx + mw * 0.25, my + sh * 0.12), fill=(10, 35, 80, 255),
                      outline=light + (255,), width=2 * SS)
        elif mood in ("worried", "sad"):
            d.arc((mx - mw / 2, my, mx + mw / 2, my + sh * 0.18), 200, 340, fill=light + (255,), width=int(2.5 * SS))
        elif mood in ("excited", "happy", "surprised"):
            d.chord((mx - mw / 2, my - sh * 0.08, mx + mw / 2, my + sh * 0.14), 0, 180, fill=(14, 42, 92, 255),
                    outline=light + (255,), width=2 * SS)
        elif mood == "asleep":
            d.ellipse((mx - mw * 0.1, my - mw * 0.1, mx + mw * 0.1, my + mw * 0.1), outline=light + (255,), width=2 * SS)
        else:  # cute cat mouth ω
            q = mw * 0.25
            d.arc((mx - 2 * q, my - q, mx, my + q), 0, 180, fill=light + (255,), width=int(2.5 * SS))
            d.arc((mx, my - q, mx + 2 * q, my + q), 0, 180, fill=light + (255,), width=int(2.5 * SS))
        # sweat drop
        if mood == "sweaty":
            sx = box[2] - hw * 0.05
            sy = top + hh * 0.15 + ((p["t"] % 1.5) / 1.5) * hh * 0.3
            r = 6 * SS
            d.polygon([(sx, sy - r * 1.8), (sx - r, sy), (sx + r, sy)], fill=(140, 210, 255, 230))
            d.ellipse((sx - r, sy - r, sx + r, sy + r), fill=(140, 210, 255, 230))
        # particles
        for kind, px, py, _vx, _vy, life in p["particles"]:
            a = int(255 * max(0.0, min(1.0, life / 1.6)))
            x, y = cx + px * S, top + hh * 0.3 + py * S
            if kind == "heart":
                d.polygon(_heart(x, y, 6 * SS), fill=PINK + (a,))
            elif kind == "sparkle":
                d.polygon(_star(x, y, 6 * SS, points=4, inner=0.3), fill=light + (a,))
            elif kind == "bolt":
                d.polygon([(x, y - 8 * SS), (x - 4 * SS, y + SS), (x, y + SS), (x - 2 * SS, y + 8 * SS),
                           (x + 5 * SS, y - 2 * SS), (x + SS, y - 2 * SS)], fill=(255, 226, 122, a))
            else:
                d.text((x, y), "z", font=_font(int(14 * SS)), fill=light + (a,), anchor="mm")
        return img.resize((self.W, self.H), Image.LANCZOS)

    def _push(self, img: Image.Image, alpha: float) -> None:
        if alpha < 1:
            if self._shown:
                user32.ShowWindow(self._hwnd, 0)
                self._shown = False
            return
        data = _premultiplied_bgra(img)
        screen = user32.GetDC(None)
        mem = gdi32.CreateCompatibleDC(screen)
        bmi = BITMAPINFO()
        bmi.bmiHeader.biSize = ctypes.sizeof(BITMAPINFOHEADER)
        bmi.bmiHeader.biWidth, bmi.bmiHeader.biHeight = self.W, -self.H
        bmi.bmiHeader.biPlanes, bmi.bmiHeader.biBitCount = 1, 32
        bits = ctypes.c_void_p()
        hbmp = gdi32.CreateDIBSection(screen, ctypes.byref(bmi), 0, ctypes.byref(bits), None, 0)
        try:
            ctypes.memmove(bits, data, len(data))
            old = gdi32.SelectObject(mem, hbmp)
            dst, size, src = wt.POINT(self.x, self.y), wt.SIZE(self.W, self.H), wt.POINT(0, 0)
            blend = BLENDFUNCTION(0, 0, max(0, min(255, int(alpha))), AC_SRC_ALPHA)
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


PET = Pet()
