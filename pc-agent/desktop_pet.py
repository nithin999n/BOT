"""
BOT on your PC desktop: a squishy blue cube-blob with big round black eyes.

* Eyes follow your mouse and blink. It gets happy and bouncy while you type or work,
  and cheers you on. Now and then it asks cute questions in a speech bubble.
* Click it and it feels loved: "Do you love me? 🥺". Click again: "Yay!! I love you too! 💖"
* Grab it and throw it: it flies, spins, bounces, and gets dizzy after a hard throw.
* Yawns when you're idle, sleeps after 5 minutes, says "welcome back" when you return.
* Sweats when the CPU is busy, looks worried on low battery, sparkles while charging.
* The blue bubble cursor flies out of it when BOT works. Never steals keyboard focus.
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

from PIL import Image, ImageDraw, ImageFilter, ImageFont

import health
import win_input
from overlay import (AC_SRC_ALPHA, BITMAPINFO, BITMAPINFOHEADER, BLENDFUNCTION, BUBBLE, PM_REMOVE,
                     SW_SHOWNOACTIVATE, ULW_ALPHA, WNDCLASSEXW, WNDPROC, WS_EX_LAYERED, WS_EX_NOACTIVATE,
                     WS_EX_TOOLWINDOW, WS_EX_TOPMOST, WS_POPUP, _premultiplied_bgra, gdi32, kernel32, user32)

log = logging.getLogger("bot")
SS = 2  # supersampling for smooth edges
INK = (22, 24, 38)            # the black of the eyes
BLUE = (58, 141, 255)         # BOT's body colour
PINK = (255, 126, 182)
WHITE = (255, 255, 255)

QUESTIONS = [
    "What are you doing? 👀", "Are you working hard? 💪", "Did you drink water today? 💧",
    "Can we play later? 🎮", "You're doing great! ✨", "Ooh, is that code? So smart! 🤓",
    "Do you want a hug? 🤗", "Take a little break? ☕", "What's your favourite song? 🎵",
    "Are you hungry? 🍕", "I like watching you work 🥰", "Can I help with something? 🙋",
    "Did you eat something today? 🍎", "You look busy! 👀", "Is it fun? 😊", "Tell me a secret? 🤫",
]
TYPING_CHEERS = ["You're typing so fast! ✨", "Wow, so productive! 💪", "Keep going, you've got this! 🔥",
                 "Clickety clack! 🎹", "Look at you go! 🚀"]
LOVE_ASK = ["Do you love me? 🥺", "Do you love me? 🥺💕", "Am I cute? 🥹", "Pat pat? 🥺"]
LOVE_YES = ["Yay!! I love you too! 💖", "Hehe, best human ever! 🥰", "Aww, you're the best! 💕",
            "My heart is so full! 💗"]
WELCOME = ["Welcome back! I missed you 🥺", "You're back! Yay! 🎉", "Hiii! I waited for you 🥰"]
DIZZY = ["Wheee… 😵", "Everything is spinning! 😵", "Be gentle with me! 🥺", "Again? No no no! 😵"]
PICKED = ["Whoa! 😲", "Where are we going? 👀", "Wheee! 🎈", "Up up up! 😲"]
SLEEPY = ["*yawn* 😪", "So sleepy… 😴"]
CHARGING = ["Yummy electricity ⚡", "Charging up! 🔋"]
HOT = ["Phew, so hot in here! 🥵", "The PC is working hard! 😅"]
LOW_BATTERY = ["Battery is low… plug me in? 🥺"]


class _Rect(ctypes.Structure):
    _fields_ = [("left", ctypes.c_long), ("top", ctypes.c_long), ("right", ctypes.c_long), ("bottom", ctypes.c_long)]


class _LastInput(ctypes.Structure):
    _fields_ = [("cbSize", ctypes.c_uint), ("dwTime", ctypes.c_uint)]


def _last_input_tick() -> int:
    li = _LastInput()
    li.cbSize = ctypes.sizeof(li)
    user32.GetLastInputInfo(ctypes.byref(li))
    return li.dwTime


def _mix(a, b, k):
    return tuple(int(a[i] + (b[i] - a[i]) * k) for i in range(3))


def _heart(cx, cy, r):
    pts = []
    for i in range(28):
        t = i / 28 * 2 * math.pi
        x = 16 * math.sin(t) ** 3
        y = 13 * math.cos(t) - 5 * math.cos(2 * t) - 2 * math.cos(3 * t) - math.cos(4 * t)
        pts.append((cx + x * r / 16, cy - y * r / 16))
    return pts


def _star(cx, cy, r, points=5, inner=0.45, rot=-math.pi / 2):
    return [(cx + math.cos(rot + i * math.pi / points) * (r if i % 2 == 0 else r * inner),
             cy + math.sin(rot + i * math.pi / points) * (r if i % 2 == 0 else r * inner))
            for i in range(points * 2)]


def _font(size: int):
    for name in ("seguiemj.ttf", "segoeui.ttf", "arial.ttf"):  # Segoe UI Emoji draws text + colour emoji
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default()


class Pet:
    """Thread-safe: call react() / say() / set_wanted() / set_color() from anywhere."""

    def __init__(self):
        self.enabled = False      # window works
        self.wanted = True        # user wants it (phone menu / voice / tray)
        self.health: dict = {"feeling": "ok"}
        self.busy_fn = lambda: False
        self.on_event = None      # callback(event) -> "dizzy", "petted" (tells the phone)
        self._q: queue.Queue = queue.Queue()
        self._thread: threading.Thread | None = None
        self._color = BLUE        # the desktop BOT is always a cute blue
        self._center = (0.0, 0.0)
        self._shown = False
        self._alpha = 0.0
        # physics: grab, drag, throw
        self.vx = self.vy = 0.0
        self.angle = self.spin = self.squish = 0.0
        self.dragging = self.flying = self.walking = False
        self._samples: list[tuple[float, float, float]] = []
        self._grab_off = (0.0, 0.0)
        self._grab_t = self._moved = 0.0
        self._hard_hit = False
        self._dizzy_until = 0.0
        self._walk_dir, self._walk_to, self._walk_t0 = 1, 0.0, 0.0
        self._next_walk = time.perf_counter() + 25
        self._last_img = None
        self._body_cache = None
        self._shadow_cache = None
        self._bubble_cache: dict[str, Image.Image] = {}

    # -- public ------------------------------------------------------------------
    def start(self) -> None:
        if self._thread is None:
            self._thread = threading.Thread(target=self._run, name="desktop-pet", daemon=True)
            self._thread.start()

    def set_wanted(self, on: bool) -> None:
        self.wanted = on

    def set_color(self, hex_color: str) -> None:
        """The app colour changes the phone BOT and the bubble cursor; the desktop BOT stays blue."""
        return

    def bring_here(self) -> None:
        """Drop BOT in from the top of the screen, above your mouse."""
        self.wanted = True
        self._q.put(("bring",))

    def react(self, mood: str, seconds: float = 2.0) -> None:
        """Show a mood for a moment: happy, excited, sad, love, surprised."""
        self._q.put(("react", mood, seconds))

    def say(self, text: str, seconds: float = 4.0) -> None:
        self._q.put(("say", text, seconds))

    def center(self):
        """Where the blue bubble cursor flies out from (None if BOT isn't showing)."""
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
        if msg == 0x0020:            # WM_SETCURSOR: grabbing hand over BOT
            user32.SetCursor(self._hand)
            return 1
        if msg == 0x0201:            # WM_LBUTTONDOWN
            self._grab()
            return 0
        if msg == 0x0202:            # WM_LBUTTONUP
            self._release()
            return 0
        if msg == 0x0215 and self.dragging:  # WM_CAPTURECHANGED
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
        if self._moved < 6 and now - self._grab_t < 0.35:  # a click, not a throw
            self._q.put(("click",))
            self.flying, self.vx, self.vy = True, 0.0, 0.0  # settle on the floor
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

    def _limits(self):
        """Window positions where BOT's body touches the screen edges / taskbar."""
        side = (self.W - self.BW) / 2
        return (self.bounds[0] - side, self.bounds[2] - self.W + side, self.bounds[1] - self.H * 0.35,
                self.bounds[3] - self.H + self.FOOT_GAP)

    def _physics(self, dt: float) -> None:
        left, right, top, floor = self._limits()
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
                        self._q.put(("say", random.choice(DIZZY), 3.0))
                        self._emit("dizzy")
        elif self.walking:
            self.x += self._walk_dir * 110 * dt
            hop = abs(math.sin((time.perf_counter() - self._walk_t0) * 9)) * self.H * 0.05
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
        self._center = (self.x + self.W / 2, self.y + self.BODY_CY)

    def _hit(self, speed: float) -> None:
        if speed > 1100:  # slammed into the edge of the screen
            self._hard_hit = True

    def _maybe_walk(self, mood: str) -> None:
        now = time.perf_counter()
        if mood != "idle" or self.flying or self.dragging or self.walking or now < self._next_walk:
            return
        self._next_walk = now + random.uniform(25, 50)
        left, right, _top, _floor = self._limits()
        target = random.uniform(left + 20, right - 20)
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
        now = time.perf_counter()
        st = {"t0": now, "blink": 0.0, "next_blink": 2.0, "look": (0.0, 0.0), "react": None, "react_until": 0.0,
              "yawn_until": 0.0, "next_yawn": 6.0, "particles": [], "next_particle": 0.0, "idle": 0.0,
              "idle_at": 0.0, "was_busy": False, "speech": "", "speech_until": 0.0, "love_asked": -99.0,
              "next_question": now + random.uniform(90, 180), "next_cheer": now + 40, "typing": 0.0,
              "last_tick": _last_input_tick(), "last_cursor": win_input.cursor_pos(), "type_check": 0.0,
              "was_away": False, "last_feeling": "ok"}
        last_sig = None
        last_pos = None
        last_t = time.perf_counter()
        while True:
            while user32.PeekMessageW(ctypes.byref(msg), None, 0, 0, PM_REMOVE):
                user32.TranslateMessage(ctypes.byref(msg))
                user32.DispatchMessageW(ctypes.byref(msg))
            try:
                while True:
                    self._command(self._q.get_nowait(), st)
                    last_sig = None
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
                    self._last_img = self._transform(self._render(params))
                    self._push(self._last_img, params["alpha"])
                elif pos != last_pos:  # only moved: reuse the picture
                    last_pos = pos
                    self._push(self._last_img, params["alpha"])
                moving = self.dragging or self.flying or self.walking
                fps = 60 if moving else (24 if params["active"] else (4 if params["mood"] == "asleep" else 10))
            except Exception:
                log.exception("desktop pet frame failed")
                fps = 1
            time.sleep(1 / fps)

    def _command(self, cmd, st: dict) -> None:
        now = time.perf_counter()
        kind = cmd[0]
        if kind == "color":
            self._color = cmd[1]
            self._body_cache = None
        elif kind == "react":
            st["react"], st["react_until"] = cmd[1], now + cmd[2]
            if cmd[1] == "love":
                self._burst(st, "heart", 5)
        elif kind == "say":
            st["speech"], st["speech_until"] = cmd[1], now + cmd[2]
        elif kind == "click":  # you clicked BOT: it feels loved
            self._burst(st, "heart", 6)
            st["react"], st["react_until"] = "love", now + 3.0
            if now - st["love_asked"] < 8:
                st["speech"], st["speech_until"] = random.choice(LOVE_YES), now + 3.5
                st["love_asked"] = -99.0
                self._burst(st, "heart", 6)
            else:
                st["speech"], st["speech_until"] = random.choice(LOVE_ASK), now + 6.0
                st["love_asked"] = now
            self._emit("petted")
        elif kind == "bring":
            mx, _my = win_input.cursor_pos()
            left, right, _top, _floor = self._limits()
            self.x = float(max(left, min(right, mx - self.W / 2)))
            self.y = float(self.bounds[1] - self.H * 0.5)
            self.vx, self.vy, self.spin = 0.0, 300.0, 0.0
            self.dragging = self.walking = False
            self.flying = True
            st["react"], st["react_until"] = "happy", now + 2.5
            st["speech"], st["speech_until"] = "Here I am! 🥰", now + 3.0

    def _burst(self, st: dict, kind: str, n: int) -> None:
        for _ in range(n):
            st["particles"].append([kind, random.uniform(-0.35, 0.35), random.uniform(-0.25, 0.0),
                                    random.uniform(-0.08, 0.08), random.uniform(-0.35, -0.18), random.uniform(1.2, 1.9)])

    def _transform(self, img: Image.Image) -> Image.Image:
        """Spin while flying, squish on landing."""
        if abs(self.angle) > 0.5:
            img = img.rotate(self.angle, resample=Image.BICUBIC, center=(self.W / 2, self.BODY_CY))
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
        self.scale = scale
        self.S = int(104 * scale)                    # body size
        self.BW, self.BH = int(self.S * 0.98), int(self.S * 0.88)
        self.W, self.H = int(self.S * 2.5), int(self.S * 1.85)  # room for the speech bubble
        self.FOOT_GAP = int(self.S * 0.04)
        self.BODY_CY = self.H - self.FOOT_GAP - self.S * 0.08 - self.BH / 2
        wa = _Rect()
        user32.SystemParametersInfoW(0x0030, 0, ctypes.byref(wa), 0)  # SPI_GETWORKAREA
        self.bounds = (wa.left, wa.top, wa.right, wa.bottom)
        left, right, _top, floor = self._limits()
        self.x, self.y = float(right - 8 * scale), float(floor)
        self._center = (self.x + self.W / 2, self.y + self.BODY_CY)
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
        # Layered windows only catch the mouse on visible pixels, so clicks around BOT
        # still reach whatever is underneath.
        ex = WS_EX_LAYERED | WS_EX_TOPMOST | WS_EX_TOOLWINDOW | WS_EX_NOACTIVATE
        self._hwnd = user32.CreateWindowExW(ex, "BotDesktopPet", "BOT", WS_POPUP, int(self.x), int(self.y),
                                            self.W, self.H, None, None, hinst, None)
        if not self._hwnd:
            raise ctypes.WinError(ctypes.get_last_error())
        BUBBLE.origin = self.center  # the bubble cursor flies out of the desktop BOT

    # -- behaviour -------------------------------------------------------------------
    def _update(self, st: dict) -> dict:
        now = time.perf_counter()
        t = now - st["t0"]
        if now - st["idle_at"] > 0.5:
            idle = health.idle_seconds()
            if st["idle"] > 120 and idle < 2:  # you came back!
                st["speech"], st["speech_until"] = random.choice(WELCOME), now + 4
                st["react"], st["react_until"] = "excited", now + 2
            st["idle"], st["idle_at"] = idle, now
            feeling = self.health.get("feeling", "ok")
            if feeling != st["last_feeling"] and not st["speech"]:
                line = {"hot": HOT, "low_battery": LOW_BATTERY, "charging": CHARGING}.get(feeling)
                if line:
                    st["speech"], st["speech_until"] = random.choice(line), now + 4
            st["last_feeling"] = feeling
        feeling = st["last_feeling"]

        # typing detection: input happened but the mouse didn't move -> keyboard
        if now - st["type_check"] > 0.25:
            st["type_check"] = now
            tick, cur = _last_input_tick(), win_input.cursor_pos()
            if tick != st["last_tick"] and cur == st["last_cursor"]:
                st["typing"] = min(10.0, st["typing"] + 1.5)
            st["typing"] *= 0.88
            st["last_tick"], st["last_cursor"] = tick, cur
        typing = st["typing"] > 2.5

        bx, by, bubble_on = BUBBLE.position()
        busy = bubble_on or self.busy_fn()
        if busy and not st["was_busy"]:  # a task just started
            st["react"], st["react_until"] = "excited", now + 1.2
        st["was_busy"] = busy

        if self.dragging:
            mood = "surprised"
            if not st["speech"] or st["speech"] not in PICKED:
                st["speech"], st["speech_until"] = random.choice(PICKED), now + 1.5
        elif now < self._dizzy_until:
            mood = "dizzy"
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
        elif typing:
            mood = "typing"          # happy while you work
        elif st["idle"] > 300:
            mood = "asleep"
        elif st["idle"] > 60:
            mood = "drowsy"
        else:
            mood = "idle"

        # chatter: cheers while typing, random cute questions while you're around
        talking = now < st["speech_until"]
        if not talking:
            st["speech"] = ""
        if not talking and not self.flying and not self.dragging and mood not in ("asleep", "dizzy"):
            if mood == "typing" and now > st["next_cheer"]:
                st["speech"], st["speech_until"] = random.choice(TYPING_CHEERS), now + 3.5
                st["next_cheer"] = now + random.uniform(80, 160)
            elif st["idle"] < 30 and now > st["next_question"]:
                st["speech"], st["speech_until"] = random.choice(QUESTIONS), now + 6
                st["next_question"] = now + random.uniform(150, 300)
        if mood == "drowsy" and t > st["next_yawn"]:
            st["yawn_until"], st["next_yawn"] = t + 1.8, t + random.uniform(7, 12)
            if not st["speech"] and random.random() < 0.3:
                st["speech"], st["speech_until"] = random.choice(SLEEPY), now + 2
        yawning = mood == "drowsy" and t < st["yawn_until"]

        # blink
        if t > st["next_blink"]:
            st["blink"], st["next_blink"] = t, t + random.uniform(2.2, 5.5)
        bp = (t - st["blink"]) / 0.14
        blink = math.sin(bp * math.pi) if 0 <= bp <= 1 else 0.0

        # where to look: the bubble cursor while working, otherwise your mouse
        mx, my = (bx, by) if bubble_on else win_input.cursor_pos()
        cx, cy = self._center
        dx, dy = mx - cx, my - cy
        dist = max(1.0, math.hypot(dx, dy))
        target = (dx / dist * min(1.0, dist / 300), dy / dist * min(1.0, dist / 300))
        if mood in ("asleep", "dizzy"):
            target = (0.0, 0.3)
        lx, ly = st["look"]
        st["look"] = (lx + (target[0] - lx) * 0.35, ly + (target[1] - ly) * 0.35)

        # particles
        if t > st["next_particle"]:
            st["next_particle"] = t + 1.0
            if mood == "asleep":
                st["particles"].append(["z", 0.3, -0.35, 0.06, -0.12, 2.4])
            elif mood in ("love",):
                self._burst(st, "heart", 1)
            elif mood in ("typing", "excited", "happy") and random.random() < 0.6:
                self._burst(st, "sparkle", 1)
            elif mood == "idle" and feeling == "charging" and random.random() < 0.3:
                self._burst(st, "bolt", 1)
        for p in st["particles"]:
            p[1] += p[3] / 12
            p[2] += p[4] / 12
            p[5] -= 1 / 12
        st["particles"] = [p for p in st["particles"] if p[5] > 0]

        target_alpha = 255 if self.wanted else 0
        self._alpha += (target_alpha - self._alpha) * 0.35
        if abs(target_alpha - self._alpha) < 3:
            self._alpha = float(target_alpha)

        openness = {"asleep": 0.0, "drowsy": 0.5, "sweaty": 0.8}.get(mood, 1.0)
        if yawning:
            openness = 0.05
        openness *= 1 - blink
        bounce = 0.0
        if mood in ("typing", "excited", "happy", "love"):
            bounce = abs(math.sin(t * (9 if mood == "typing" else 7))) * 0.05
        breathe = math.sin(t * 2.2) * 0.012 if mood in ("idle", "drowsy", "asleep") else 0.0
        show_speech = st["speech"] if not (self.flying and not self.dragging) else ""
        active = bool(st["particles"]) or blink > 0 or bounce > 0 or mood in ("dizzy", "surprised", "sweaty") \
            or abs(target_alpha - self._alpha) > 0 or yawning
        sig = (mood, round(openness, 1), round(st["look"][0] * 6), round(st["look"][1] * 6), yawning,
               round(bounce * 200), round(breathe * 400), int(self._alpha), show_speech,
               tuple((p[0], round(p[1] * 40), round(p[2] * 40)) for p in st["particles"]),
               (int(t * 2) if mood == "sweaty" else 0), (int(t * 12) if mood == "dizzy" else 0),
               round(self.angle), round(self.squish * 10), self._color)
        return {"mood": mood, "open": openness, "look": st["look"], "yawn": yawning, "bounce": bounce,
                "breathe": breathe, "alpha": self._alpha, "sig": sig, "active": active, "t": t,
                "particles": list(st["particles"]), "speech": show_speech}

    # -- drawing -----------------------------------------------------------------------
    def _body(self) -> Image.Image:
        """The squishy blue cube-blob (drawn once)."""
        if self._body_cache is None:
            col = self._color
            bw, bh = self.BW * SS, self.BH * SS
            img = Image.new("RGBA", (bw, bh), (0, 0, 0, 0))
            top_c, bot_c = _mix(col, WHITE, 0.22), _mix(col, (0, 0, 0), 0.14)
            grad = Image.new("RGBA", (bw, bh))
            gd = ImageDraw.Draw(grad)
            for y in range(bh):
                gd.line([(0, y), (bw, y)], fill=_mix(top_c, bot_c, y / max(1, bh - 1)) + (255,))
            mask = Image.new("L", (bw, bh), 0)
            radius = int(bw * 0.42)
            ImageDraw.Draw(mask).rounded_rectangle((0, 0, bw - 1, bh - 1), radius=radius, fill=255)
            img.paste(grad, (0, 0), mask)
            d = ImageDraw.Draw(img, "RGBA")
            d.rounded_rectangle((1, 1, bw - 2, bh - 2), radius=radius, outline=_mix(col, (0, 0, 0), 0.22) + (255,),
                                width=int(2.2 * SS))
            d.ellipse((bw * 0.16, bh * 0.07, bw * 0.56, bh * 0.25), fill=(255, 255, 255, 95))   # gloss
            d.ellipse((bw * 0.64, bh * 0.1, bw * 0.73, bh * 0.18), fill=(255, 255, 255, 130))
            self._body_cache = img
        return self._body_cache

    def _shadow(self) -> Image.Image:
        if self._shadow_cache is None:
            w, h = int(self.BW * SS * 0.9), int(self.S * 0.12 * SS)
            sh = Image.new("RGBA", (w + 20 * SS, h + 20 * SS), (0, 0, 0, 0))
            ImageDraw.Draw(sh).ellipse((10 * SS, 10 * SS, 10 * SS + w, 10 * SS + h), fill=(0, 0, 0, 70))
            self._shadow_cache = sh.filter(ImageFilter.GaussianBlur(5 * SS))
        return self._shadow_cache

    def _speech_bubble(self, text: str) -> Image.Image:
        if text not in self._bubble_cache:
            font = _font(int(13.5 * self.scale * SS))
            pad = int(10 * self.scale * SS)
            max_w = self.W * SS - 2 * pad - 8 * SS
            words, lines, cur = text.split(), [], ""
            probe = ImageDraw.Draw(Image.new("RGBA", (1, 1)))
            for w in words:  # wrap to the window width
                trial = (cur + " " + w).strip()
                if cur and probe.textlength(trial, font=font) > max_w:
                    lines.append(cur)
                    cur = w
                else:
                    cur = trial
            lines.append(cur)
            lh = int(font.size * 1.3)
            tw = int(max(probe.textlength(line, font=font) for line in lines))
            bw, bh = tw + 2 * pad, lh * len(lines) + pad * 2 - int(lh * 0.2)
            tail = int(9 * self.scale * SS)
            img = Image.new("RGBA", (bw + 6 * SS, bh + tail + 6 * SS), (0, 0, 0, 0))
            d = ImageDraw.Draw(img, "RGBA")
            d.rounded_rectangle((3 * SS, 3 * SS, 3 * SS + bw, 3 * SS + bh), radius=int(14 * self.scale * SS),
                                fill=(255, 255, 255, 248), outline=_mix(self._color, (0, 0, 0), 0.1) + (255,),
                                width=int(1.6 * SS))
            mid = 3 * SS + bw // 2
            d.polygon([(mid - tail, 3 * SS + bh - 2 * SS), (mid + tail, 3 * SS + bh - 2 * SS),
                       (mid, 3 * SS + bh + tail)], fill=(255, 255, 255, 248))
            for i, line in enumerate(lines):
                d.text((3 * SS + pad, 3 * SS + pad + i * lh), line, font=font, fill=(30, 36, 64, 255),
                       embedded_color=True)
            if len(self._bubble_cache) > 40:
                self._bubble_cache.clear()
            self._bubble_cache[text] = img
        return self._bubble_cache[text]

    def _render(self, p: dict) -> Image.Image:
        W, H = self.W * SS, self.H * SS
        img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        body = self._body()
        bw, bh = self.BW * SS, self.BH * SS
        mood, t = p["mood"], p["t"]
        lift = int(p["bounce"] * self.S * SS)
        x0 = (W - bw) // 2
        y0 = int(H - self.FOOT_GAP * SS - body.height) - lift
        if not self.flying:  # soft shadow on the floor
            sh = self._shadow()
            img.alpha_composite(sh, ((W - sh.width) // 2, int(H - self.FOOT_GAP * SS - sh.height * 0.62)))
        # breathing: a gentle squash and stretch
        if p["breathe"]:
            k = 1 + p["breathe"]
            b2 = body.resize((int(body.width / k), int(body.height * k)), Image.BILINEAR)
            img.alpha_composite(b2, ((W - b2.width) // 2, y0 + body.height - b2.height))
        else:
            img.alpha_composite(body, (x0, y0))
        d = ImageDraw.Draw(img, "RGBA")
        cx = W / 2
        lx, ly = p["look"][0] * bw * 0.06, p["look"][1] * bh * 0.05
        ey = y0 + bh * 0.5 + ly
        er = bw * 0.13  # big round eyes

        for side in (-1, 1):
            ex = cx + side * bw * 0.19 + lx
            if mood == "dizzy":  # black spiral eyes
                ex, eyy = cx + side * bw * 0.2, y0 + bh * 0.46
                spin = t * 7 * side
                pts = [(ex + math.cos(spin + a / 5) * er * 1.05 * a / 36, eyy + math.sin(spin + a / 5) * er * 1.05 * a / 36)
                       for a in range(37)]
                d.line(pts, fill=INK + (255,), width=int(3.2 * SS), joint="curve")
            elif mood in ("typing", "happy", "excited"):  # ^ ^ happy eyes
                d.arc((ex - er, ey - er * 0.7, ex + er, ey + er * 1.1), 200, 340, fill=INK + (255,), width=int(4 * SS))
            elif mood == "love":  # heart eyes
                d.polygon(_heart(ex, ey, er * 1.05), fill=(255, 77, 141, 255))
                d.ellipse((ex - er * 0.45, ey - er * 0.45, ex - er * 0.15, ey - er * 0.15), fill=(255, 255, 255, 220))
            elif p["open"] < 0.12:  # closed: sleeping, blinking, yawning
                d.arc((ex - er * 0.8, ey - er * 0.5, ex + er * 0.8, ey + er * 0.5), 20, 160, fill=INK + (255,),
                      width=int(3.2 * SS))
            else:  # big glossy anime-style eyes: tall oval, blue shine at the bottom, two sparkles
                r = er * (1.18 if mood == "surprised" else 1.0)
                ry = r * 1.2 * max(0.2, p["open"])
                d.ellipse((ex - r, ey - ry, ex + r, ey + ry), fill=INK + (255,))
                if p["open"] > 0.45:
                    # a soft blue glow low in the eye (gives it depth)
                    d.ellipse((ex - r * 0.5, ey + ry * 0.38, ex + r * 0.5, ey + ry * 0.86), fill=(70, 110, 230, 95))
                    # big sparkle (top) + small sparkle (bottom) + a tiny twinkle
                    hr = r * 0.46
                    d.ellipse((ex - r * 0.62, ey - ry * 0.72, ex - r * 0.62 + hr * 2, ey - ry * 0.72 + hr * 1.9),
                              fill=WHITE + (255,))
                    sr = r * 0.2
                    d.ellipse((ex + r * 0.22, ey + ry * 0.18, ex + r * 0.22 + sr * 2, ey + ry * 0.18 + sr * 2),
                              fill=WHITE + (240,))
                    tw = r * 0.09
                    d.ellipse((ex + r * 0.42, ey - ry * 0.45, ex + r * 0.42 + tw * 2, ey - ry * 0.45 + tw * 2),
                              fill=WHITE + (220,))
                if mood == "drowsy" or (mood == "sweaty" and p["open"] < 0.9):  # sleepy eyelid in body colour
                    k = (ey - ry - y0) / bh
                    lid = _mix(_mix(self._color, WHITE, 0.22), _mix(self._color, (0, 0, 0), 0.14), max(0.0, min(1.0, k)))
                    # cover the top half of the eye with a lid, then draw the lid's edge
                    d.chord((ex - r - 3, ey - ry - 3, ex + r + 3, ey + ry + 3), 180, 360, fill=lid + (255,))
                    d.line([(ex - r, ey), (ex + r, ey)], fill=INK + (255,), width=int(2.6 * SS))
                if mood == "worried":  # little worried brows
                    d.line([(ex - side * r * 0.9, ey - r * 1.55), (ex + side * r * 0.5, ey - r * 1.25)],
                           fill=INK + (255,), width=int(2.4 * SS))

        # blush (always a little, lots when loved/happy)
        blush = 165 if mood in ("love", "happy", "typing", "excited") else 105
        for side in (-1, 1):
            bcx, bcy = cx + side * bw * 0.34 + lx * 0.5, ey + bh * 0.15
            d.ellipse((bcx - bw * 0.085, bcy - bh * 0.045, bcx + bw * 0.085, bcy + bh * 0.045), fill=PINK + (blush,))
            if mood == "love":  # shy lines
                for i in (-1, 0, 1):
                    xx = bcx + i * bw * 0.035
                    d.line([(xx + bw * 0.012, bcy - bh * 0.03), (xx - bw * 0.012, bcy + bh * 0.03)],
                           fill=(255, 90, 150, 220), width=int(1.6 * SS))

        # mouth
        mx, my = cx + lx * 0.4, y0 + bh * 0.67 + ly * 0.4
        mw = bw * 0.16
        if p["yawn"] or mood in ("surprised", "dizzy"):
            r = mw * (0.42 if p["yawn"] else 0.28)
            d.ellipse((mx - r, my - r * 0.7, mx + r, my + r * 1.2), fill=INK + (255,))
        elif mood in ("typing", "happy", "excited", "love"):  # open happy smile with tongue
            box = (mx - mw * 0.75, my - mw * 0.45, mx + mw * 0.75, my + mw * 0.8)
            d.chord(box, 0, 180, fill=INK + (255,))
            d.chord((mx - mw * 0.42, my + mw * 0.05, mx + mw * 0.42, my + mw * 0.78), 0, 180, fill=(255, 120, 150, 255))
        elif mood in ("worried", "sad"):
            d.arc((mx - mw * 0.6, my, mx + mw * 0.6, my + mw * 0.8), 200, 340, fill=INK + (255,), width=int(2.6 * SS))
        elif mood == "asleep":
            d.ellipse((mx - mw * 0.12, my, mx + mw * 0.12, my + mw * 0.24), fill=INK + (200,))
        else:  # cute "ω" cat mouth
            q = mw * 0.3
            d.arc((mx - 2 * q, my - q, mx, my + q), 0, 180, fill=INK + (255,), width=int(2.6 * SS))
            d.arc((mx, my - q, mx + 2 * q, my + q), 0, 180, fill=INK + (255,), width=int(2.6 * SS))

        # extras
        if mood == "dizzy":  # stars circling the head
            for i in range(3):
                a = t * 4 + i * 2 * math.pi / 3
                sx, sy = cx + math.cos(a) * bw * 0.45, y0 + math.sin(a) * bh * 0.08 - bh * 0.02
                d.polygon(_star(sx, sy, 7 * SS * self.scale), fill=(255, 210, 80, 255))
        if mood == "sweaty":
            sx = x0 + bw * 0.88
            sy = y0 + bh * (0.18 + 0.25 * ((t % 1.5) / 1.5))
            r = 6 * SS * self.scale
            d.polygon([(sx, sy - r * 1.8), (sx - r, sy), (sx + r, sy)], fill=(140, 210, 255, 230))
            d.ellipse((sx - r, sy - r, sx + r, sy + r), fill=(140, 210, 255, 230))
        for kind, px, py, _vx, _vy, life in p["particles"]:
            a = int(255 * max(0.0, min(1.0, life / 1.6)))
            x, y = cx + px * bw * 1.4, y0 + bh * 0.2 + py * bh * 1.4
            s = 7 * SS * self.scale
            if kind == "heart":
                d.polygon(_heart(x, y, s), fill=(255, 77, 141, a))
            elif kind == "sparkle":
                d.polygon(_star(x, y, s, points=4, inner=0.3), fill=(255, 230, 140, a))
            elif kind == "bolt":
                d.polygon([(x, y - s), (x - s * 0.5, y + s * 0.1), (x, y + s * 0.1), (x - s * 0.25, y + s),
                           (x + s * 0.6, y - s * 0.25), (x + s * 0.1, y - s * 0.25)], fill=(255, 210, 80, a))
            else:
                d.text((x, y), "z", font=_font(int(15 * SS * self.scale)), fill=_mix(self._color, (0, 0, 0), 0.3) + (a,),
                       anchor="mm")
        # speech bubble above BOT
        if p["speech"]:
            sb = self._speech_bubble(p["speech"])
            bx = int(max(0, min(W - sb.width, cx - sb.width / 2)))
            by = max(0, y0 - sb.height - int(2 * SS))
            img.alpha_composite(sb, (bx, by))
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
            dst = wt.POINT(int(round(self.x)), int(round(self.y)))
            size, src = wt.SIZE(self.W, self.H), wt.POINT(0, 0)
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
