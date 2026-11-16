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
                     WS_EX_TOOLWINDOW, WS_EX_TOPMOST, WS_POPUP, _font,
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
        self.on_event = None      # callback(event: str) -> e.g. "dizzy", "petted" (tells the phone)
        # physics: you can grab BOT, drag it and throw it around
        self.vx = self.vy = 0.0
        self.angle = 0.0          # degrees (spins while flying)
        self.spin = 0.0
        self.squish = 0.0
        self.dragging = self.flying = self.walking = False
        self._samples: list[tuple[float, float, float]] = []
        self._grab_off = (0.0, 0.0)
        self._grab_t = 0.0
        self._moved = 0.0
        self._hard_hit = False
        self._dizzy_until = 0.0
        self._walk_dir = 1
        self._walk_to = 0.0
        self._next_walk = time.perf_counter() + 25
        self._last_img = None

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

    def bring_here(self) -> None:
        """Drop BOT in from the top of the screen, above your mouse."""
        self.wanted = True
        self._q.put(("bring",))

    def react(self, mood: str, seconds: float = 2.0) -> None:
        """Show a mood for a moment: happy, excited, sad, love, surprised."""
        self._q.put(("react", mood, seconds))

    def center(self):
        """Where the bubble should fly out from (None if the pet isn't showing)."""
        return self._center if self.enabled and self.wanted and self._alpha > 20 else None

    def _emit(self, event: str) -> None:
        if self.on_event:
            try:
                self.on_event(event)
            except Exception:
                pass

    # -- grab, drag, throw ---------------------------------------------------------
    def _wnd(self, hwnd, msg, wparam, lparam):
        if msg == 0x0021:            # WM_MOUSEACTIVATE: never steal focus from your app
            return 3                 # MA_NOACTIVATE
        if msg == 0x0020:            # WM_SETCURSOR: show a grabbing hand over BOT
            user32.SetCursor(self._hand)
            return 1
        if msg == 0x0201:            # WM_LBUTTONDOWN
            self._grab()
            return 0
        if msg == 0x0202:            # WM_LBUTTONUP
            self._release()
            return 0
        if msg == 0x0215 and self.dragging:  # WM_CAPTURECHANGED (e.g. alt-tab while holding)
            self._release()
            return 0
        return user32.DefWindowProcW(hwnd, msg, wparam, lparam)

    def _grab(self) -> None:
        cx, cy = win_input.cursor_pos()
        now = time.perf_counter()
        self.dragging, self.flying, self.walking = True, False, False
        self._grab_off = (cx - self.x, cy - self.y)
        self._samples = [(now, float(cx), float(cy))]
        self._grab_t, self._moved = now, 0.0
        user32.SetCapture(self._hwnd)

    def _release(self) -> None:
        if not self.dragging:
            return
        self.dragging = False
        user32.ReleaseCapture()
        now = time.perf_counter()
        if self._moved < 6 and now - self._grab_t < 0.35:  # a click, not a throw: giggle
            self._q.put(("react", "love", 2.0))
            self._emit("petted")
            self.flying = True  # let it settle on the floor
            self.vx = self.vy = 0.0
            return
        recent = [s for s in self._samples if now - s[0] < 0.1] or self._samples[-2:]
        if len(recent) >= 2 and recent[-1][0] > recent[0][0]:
            dt = recent[-1][0] - recent[0][0]
            self.vx = max(-6000.0, min(6000.0, (recent[-1][1] - recent[0][1]) / dt))
            self.vy = max(-6000.0, min(6000.0, (recent[-1][2] - recent[0][2]) / dt))
        else:
            self.vx = self.vy = 0.0
        self.spin = self.vx * 0.12
        self._hard_hit = math.hypot(self.vx, self.vy) > 2600  # a big throw makes BOT dizzy
        self.flying = True

    def _physics(self, dt: float) -> None:
        floor = self.bounds[3] - self.H
        left, right, top = self.bounds[0] - self.W * 0.15, self.bounds[2] - self.W * 0.85, self.bounds[1]
        if self.dragging:
            cx, cy = win_input.cursor_pos()
            now = time.perf_counter()
            nx, ny = cx - self._grab_off[0], cy - self._grab_off[1]
            self._moved += math.hypot(nx - self.x, ny - self.y)
            self.x, self.y = nx, ny
            self._samples.append((now, float(cx), float(cy)))
            self._samples = [s for s in self._samples if now - s[0] < 0.15]
            self.angle *= 0.8
        elif self.flying:
            self.vy += 2600 * dt  # gravity
            self.x += self.vx * dt
            self.y += self.vy * dt
            self.angle += self.spin * dt
            if self.x < left or self.x > right:  # bounce off the sides of the screen
                self.x = left if self.x < left else right
                self._hit(abs(self.vx))
                self.vx, self.spin = -self.vx * 0.6, -self.spin * 0.7
            if self.y < top:
                self.y, self.vy = top, abs(self.vy) * 0.5
            if self.y >= floor:  # land on the taskbar
                self.y = floor
                self._hit(abs(self.vy))
                if abs(self.vy) > 250:
                    self.vy, self.vx = -self.vy * 0.45, self.vx * 0.8
                    self.squish = min(1.0, abs(self.vy) / 1200)
                else:
                    self.vy, self.vx, self.spin = 0.0, self.vx * 0.8, self.spin * 0.7
                if self.vy == 0 and abs(self.vx) < 25:  # settled
                    self.flying, self.vx = False, 0.0
                    if self._hard_hit:
                        self._hard_hit = False
                        self._dizzy_until = time.perf_counter() + 3.2
                        self._emit("dizzy")
        elif self.walking:
            self.x += self._walk_dir * 110 * dt
            hop = abs(math.sin((time.perf_counter() - self._walk_t0) * 9)) * self.H * 0.06
            self.y = floor - hop
            if (self._walk_dir > 0 and self.x >= self._walk_to) or (self._walk_dir < 0 and self.x <= self._walk_to):
                self.walking, self.y = False, floor
        else:
            self.y = min(self.y, floor)
            if self.y < floor - 1:  # somehow in the air: fall down
                self.flying = True
        if not self.flying and not self.dragging:
            self.angle *= 0.75  # stand back up
            if abs(self.angle) < 0.5:
                self.angle = 0.0
        self.angle = (self.angle + 180) % 360 - 180
        self.squish = max(0.0, self.squish - dt * 3)
        self._center = (self.x + self.W / 2, self.y + self.H * 0.6)

    def _hit(self, speed: float) -> None:
        if speed > 1100:  # slammed into the edge of the screen
            self._hard_hit = True

    def _maybe_walk(self, mood: str) -> None:
        now = time.perf_counter()
        if mood != "idle" or self.flying or self.dragging or self.walking or now < self._next_walk:
            return
        self._next_walk = now + random.uniform(25, 50)
        lo, hi = self.bounds[0] + 20, self.bounds[2] - self.W - 20
        target = random.uniform(lo, hi)
        if abs(target - self.x) < 80:
            return
        self._walk_to, self._walk_dir = target, (1 if target > self.x else -1)
        self._walk_t0 = now
        self.walking = True

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
        last_pos = None
        last_t = time.perf_counter()
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
                    elif cmd[0] == "bring":
                        mx, _my = win_input.cursor_pos()
                        lo, hi = self.bounds[0], self.bounds[2] - self.W
                        self.x = float(max(lo, min(hi, mx - self.W / 2)))
                        self.y = float(self.bounds[1] - self.H * 0.5)
                        self.vx, self.vy, self.spin = 0.0, 300.0, 0.0
                        self.dragging = self.walking = False
                        self.flying = True
                        st["react"], st["react_until"] = "happy", time.perf_counter() + 2.5
            except queue.Empty:
                pass
            try:
                now = time.perf_counter()
                dt, last_t = min(0.05, now - last_t), now
                self._physics(dt)
                params = self._update(st)
                self._maybe_walk(params["mood"])
                sig = params["sig"]
                pos = (int(self.x), int(self.y))
                if sig != last_sig or self._last_img is None:
                    last_sig, last_pos = sig, pos
                    self._last_img = self._transform(self._render(params, st))
                    self._push(self._last_img, params["alpha"])
                elif pos != last_pos:  # only moved: reuse the picture
                    last_pos = pos
                    self._push(self._last_img, params["alpha"])
                moving = self.dragging or self.flying or self.walking
                fps = 60 if moving else (24 if params["active"] else (4 if params["mood"] == "asleep" else 12))
            except Exception:
                log.exception("desktop pet frame failed")
                fps = 1
            time.sleep(1 / fps)

    def _transform(self, img: Image.Image) -> Image.Image:
        """Spin while flying, squish on landing."""
        if abs(self.angle) > 0.5:
            img = img.rotate(self.angle, resample=Image.BICUBIC)
        if self.squish > 0.02:
            nw, nh = int(self.W * (1 + 0.18 * self.squish)), int(self.H * (1 - 0.22 * self.squish))
            out = Image.new("RGBA", (self.W, self.H), (0, 0, 0, 0))
            out.paste(img.resize((nw, nh), Image.BILINEAR), ((self.W - nw) // 2, self.H - nh))
            img = out
        return img

    def _setup(self) -> None:
        try:
            scale = user32.GetDpiForSystem() / 96
        except (AttributeError, OSError):
            scale = 1.0
        self.S = int(118 * scale)               # head width
        self.W, self.H = int(self.S * 1.3), int(self.S * 1.45)
        wa = _Rect()
        user32.SystemParametersInfoW(0x0030, 0, ctypes.byref(wa), 0)  # SPI_GETWORKAREA
        self.bounds = (wa.left, wa.top, wa.right, wa.bottom + int(4 * scale))
        self.x = float(wa.right - self.W - int(8 * scale))
        self.y = float(self.bounds[3] - self.H)
        self._center = (self.x + self.W / 2, self.y + self.H * 0.6)
        self._glow = None
        user32.LoadCursorW.restype = ctypes.c_void_p
        user32.LoadCursorW.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
        user32.SetCursor.argtypes = [ctypes.c_void_p]
        user32.SetCapture.argtypes = [ctypes.c_void_p]
        self._hand = user32.LoadCursorW(None, ctypes.c_void_p(32649))  # IDC_HAND
        self._wndproc = WNDPROC(self._wnd)
        hinst = kernel32.GetModuleHandleW(None)
        wc = WNDCLASSEXW()
        wc.cbSize = ctypes.sizeof(WNDCLASSEXW)
        wc.lpfnWndProc = self._wndproc
        wc.hInstance = hinst
        wc.lpszClassName = "BotDesktopPet"
        user32.RegisterClassExW(ctypes.byref(wc))
        # Not click-through any more (so you can grab BOT). Layered windows only catch the mouse
        # on visible pixels, so clicks around BOT still reach whatever is underneath.
        ex = WS_EX_LAYERED | WS_EX_TOPMOST | WS_EX_TOOLWINDOW | WS_EX_NOACTIVATE
        self._hwnd = user32.CreateWindowExW(ex, "BotDesktopPet", "BOT", WS_POPUP, int(self.x), int(self.y),
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

        if self.dragging:
            mood = "surprised"      # whoa, I'm being carried!
        elif now < self._dizzy_until:
            mood = "dizzy"          # you threw me!
        elif self.flying and abs(self.vx) + abs(self.vy) > 600:
            mood = "surprised"
        elif st["react"] and now < st["react_until"]:
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

        target_alpha = 255 if self.wanted else 0
        self._alpha += (target_alpha - self._alpha) * 0.35
        if abs(target_alpha - self._alpha) < 3:
            self._alpha = float(target_alpha)

        openness = {"asleep": 0.0, "drowsy": 0.45, "sweaty": 0.7, "worried": 0.9}.get(mood, 1.0)
        if yawning:
            openness = 0.1
        openness *= 1 - blink
        bob = math.sin(t * 9) * 0.03 if mood in ("excited", "happy") else 0.0
        active = bool(st["particles"]) or blink > 0 or mood in ("excited", "happy", "love", "working", "sweaty",
                                                                "dizzy", "surprised") \
            or abs(target_alpha - self._alpha) > 0 or abs(st["ant_v"]) > 0.05 or yawning
        if self.flying or self.dragging:
            st["ant_v"] += (self.vx + self.vy) * 0.00004  # antenna wobbles in the air
        sig = (mood, round(openness, 1), round(st["look"][0] * 6), round(st["look"][1] * 6), yawning,
               round(bob * 100), round(st["ant"] * 20), int(self._alpha),
               tuple((p[0], round(p[1] * 40), round(p[2] * 40)) for p in st["particles"]),
               (int(t * 2) if mood == "sweaty" else 0), (int(t * 12) if mood == "dizzy" else 0),
               round(self.angle), round(self.squish * 10), self._color)
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
            if mood == "dizzy":  # spinning spiral eyes
                ex, ey = scx + side * sw * 0.21, scy - sh * 0.08
                spin = p["t"] * 7 * side
                pts = [(ex + math.cos(spin + a / 5) * ew * 0.8 * a / 36, ey + math.sin(spin + a / 5) * ew * 0.8 * a / 36)
                       for a in range(37)]
                d.line(pts, fill=light + (255,), width=int(3 * SS), joint="curve")
            elif mood == "surprised":  # big round eyes
                r = ew * 0.62
                d.ellipse((ex - r, ey - r * 1.15, ex + r, ey + r * 1.15), fill=light + (255,))
                d.ellipse((ex - r * 0.5, ey - r * 0.7, ex - r * 0.05, ey - r * 0.25), fill=(255, 255, 255, 240))
            elif mood == "excited":
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
        elif mood in ("surprised", "dizzy"):  # "o" mouth
            r = mw * (0.22 if mood == "surprised" else 0.14)
            d.ellipse((mx - r, my - r * 0.6, mx + r, my + r * 1.3), fill=(10, 35, 80, 255),
                      outline=light + (255,), width=2 * SS)
        elif mood in ("excited", "happy"):
            d.chord((mx - mw / 2, my - sh * 0.08, mx + mw / 2, my + sh * 0.14), 0, 180, fill=(14, 42, 92, 255),
                    outline=light + (255,), width=2 * SS)
        elif mood == "asleep":
            d.ellipse((mx - mw * 0.1, my - mw * 0.1, mx + mw * 0.1, my + mw * 0.1), outline=light + (255,), width=2 * SS)
        else:  # cute cat mouth ω
            q = mw * 0.25
            d.arc((mx - 2 * q, my - q, mx, my + q), 0, 180, fill=light + (255,), width=int(2.5 * SS))
            d.arc((mx, my - q, mx + 2 * q, my + q), 0, 180, fill=light + (255,), width=int(2.5 * SS))
        # stars circling the head when dizzy
        if mood == "dizzy":
            for i in range(3):
                a = p["t"] * 4 + i * 2 * math.pi / 3
                sx, sy = cx + math.cos(a) * hw * 0.5, top - hh * 0.02 + math.sin(a) * hh * 0.12
                d.polygon(_star(sx, sy, 7 * SS), fill=(255, 226, 122, 255))
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
            dst, size, src = wt.POINT(int(round(self.x)), int(round(self.y))), wt.SIZE(self.W, self.H), wt.POINT(0, 0)
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
