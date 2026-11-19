"""
BOT on your PC desktop: a squishy blue cube-blob with big round black eyes.

Personality
* Eyes follow your mouse; happy and bouncy while you type; dances when music plays 💃.
* Asks cute questions (some with answer buttons it remembers), begs for pats with puppy eyes
  and cries if you ignore it for 10 seconds 😭, peeks out from the screen edge (peek-a-boo).
* Click = "Do you love me? 🥺". Grab and throw it (it gets dizzy). Play chase: catch it!
* Care: hunger / happiness / level. When hungry a cookie 🍪 pops up somewhere on the screen:
  drag it to BOT (or click it). With a full tummy it gets sleepy and asks "Can I sleep?" 😴
  Levels unlock outfits 🎀😎🎉👑.
* Focus buddy 🍅, water & stretch reminders, good morning / good night, daily report.
* Drop a file on it: it swallows it and sends it to your phone 📲.
* Sweats when the CPU is busy, worried on low battery, sparkles while charging.
"""
from __future__ import annotations

import ctypes
import ctypes.wintypes as wt
import logging
import math
import os
import queue
import random
import threading
import time
from datetime import date, datetime

from PIL import Image, ImageDraw, ImageFilter, ImageFont

import health
import pet_outfits
import pet_dragdrop
import pet_props
import win_input
from pet_cookie import Cookie
from pet_fun import Fun
from overlay import (AC_SRC_ALPHA, BITMAPINFO, BITMAPINFOHEADER, BLENDFUNCTION, BUBBLE, PM_REMOVE,
                     SW_SHOWNOACTIVATE, ULW_ALPHA, WNDCLASSEXW, WNDPROC, WS_EX_LAYERED, WS_EX_NOACTIVATE,
                     WS_EX_TOOLWINDOW, WS_EX_TOPMOST, WS_POPUP, _premultiplied_bgra, gdi32, kernel32, user32)
from pet_life import (BEG, BEG_YES, CRY, FORGIVE, REPLIES, KeyCounter, Life, MusicMeter, pick_question)

log = logging.getLogger("bot")
user32.SetWindowPos.argtypes = [wt.HWND, wt.HWND, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, wt.UINT]
user32.GetForegroundWindow.restype = wt.HWND
user32.GetWindowRect.argtypes = [wt.HWND, ctypes.POINTER(wt.RECT)]
user32.GetClassNameW.argtypes = [wt.HWND, wt.LPWSTR, ctypes.c_int]
user32.IsWindowVisible.argtypes = [wt.HWND]
HWND_TOPMOST = wt.HWND(-1)
SS = 2                       # supersampling for smooth edges
INK = (22, 24, 38)            # the black of the eyes
BLUE = (58, 141, 255)         # BOT's body colour
PINK = (255, 126, 182)
WHITE = (255, 255, 255)
TEAR = (120, 200, 255)

TYPING_CHEERS = ["You're typing so fast! ✨", "Wow, so productive! 💪", "Keep going, you've got this! 🔥",
                 "Clickety clack! 🎹", "Look at you go! 🚀"]
LOVE_ASK = ["Do you love me? 🥺", "Do you love me? 🥺💕", "Am I cute? 🥹", "Pat pat? 🥺"]
LOVE_YES = ["Yay!! I love you too! 💖", "Hehe, best human ever! 🥰", "Aww, you're the best! 💕", "My heart is so full! 💗"]
WELCOME = ["Welcome back! I missed you 🥺", "You're back! Yay! 🎉", "Hiii! I waited for you 🥰"]
DIZZY = ["Wheee… 😵", "Everything is spinning! 😵", "Be gentle with me! 🥺", "Again? No no no! 😵"]
PICKED = ["Whoa! 😲", "Where are we going? 👀", "Wheee! 🎈", "Up up up! 😲"]
SLEEPY = ["*yawn* 😪", "So sleepy… 😴"]
CHARGING = ["Yummy electricity ⚡", "Charging up! 🔋"]
HOT = ["Phew, so hot in here! 🥵", "The PC is working hard! 😅"]
LOW_BATTERY = ["Battery is low… plug me in? 🥺"]
WATER = ["Time to drink some water! 💧", "Water break? 💧 Stay hydrated!"]
STRETCH = ["Stretch break! 🙆 Arms up!", "Roll your shoulders! 🙆 You've been working hard"]
NIGHT = ["It's late… go to sleep? 🌙", "Sleepy time soon? 🌙 You need rest!"]
HUNGRY_AT = 30                # below this BOT is hungry and a cookie appears on the screen
HUNGRY = ["I'm hungry… 🥺 I see a cookie over there! Can you bring it to me? 🍪👉",
          "My tummy is rumbling 🥺 There's a cookie on the screen… bring it pleeease? 🍪"]
HUNGRY_REMIND = ["The cookie is right there! 🥺🍪 Drag it to me?", "Cookie… 👀🍪 pleeease? 🥺"]
GIMME = ["Gimme gimme! 🤤🍪", "Is that for me?! 🤤", "Cookie! Cookie! 🤩🍪"]
GOT_COOKIE = ["Nom nom nom! 😋🍪", "My cookie!! 🤩 Nom nom!"]
ASK_SLEEP = ["Mmm… my tummy is full and I'm sooo sleepy 😪 Can I sleep?",
             "*yawn* 😪 Full tummy… sleepy eyes… can I take a nap?"]
SLEEP_OPTS = (("Yes, sleep 😴", "sleep:yes"), ("No, stay with me 🥺", "sleep:no"))
GOOD_NIGHT = ["Yay… good night 💤 Wake me if you need me!", "Thank you… nap time 😴💙"]
STAY = ["Okay! I'll stay awake with you 🥰💪", "Okay okay! I'm awake! I'll stay with you 💕"]
NAP_DONE = ["That was a yummy nap! 😊✨", "*stretch* I feel so fresh now! 🌟"]
WOKE = ["Huh? 🥱 …I'm awake! Hi!", "Mmm? 😪 Oh, it's you! Hehe 💙"]
NAP_SECONDS = 240
DANCE = ["I love this song! 🎶", "Dance with me! 💃", "Ooh, music! 🎵"]
BOO = ["Boo! 😆", "Peek-a-boo! 😆", "You found me! 🙈"]
LEAVING = ["That's it! I'm leaving! You're being too hard on me 😤", "Hmph! I'm going away! Too rough! 😤💢"]
ASK_SORRY = ["…Aren't you going to say sorry? 🥺", "I came back… will you say sorry? 🥺", "Say sorry pleeease? 🥺"]
SULK = ["Hmph! Say sorry first 😤", "Not until you say sorry! 😤"]
FORGIVEN = ["Okay… I forgive you 🥺💕 Just be gentle, okay?", "Hehe, okay! Friends again! 💖🤝"]
SORRY_OPTS = (("Sorry 🥺", "sorry:yes"), ("I'm really sorry 💕", "sorry:yes"))


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


shell32 = ctypes.windll.shell32
shell32.DragAcceptFiles.argtypes = [ctypes.c_void_p, ctypes.c_bool]
shell32.DragQueryFileW.argtypes = [ctypes.c_void_p, ctypes.c_uint, ctypes.c_wchar_p, ctypes.c_uint]
shell32.DragQueryFileW.restype = ctypes.c_uint
shell32.DragFinish.argtypes = [ctypes.c_void_p]


class Pet:
    """Thread-safe: the public methods only queue commands for BOT's own thread."""

    def __init__(self):
        self.enabled = False      # window works
        self.wanted = True        # user wants it (phone menu / voice / tray)
        self.health: dict = {"feeling": "ok"}
        self.busy_fn = lambda: False
        self.on_event = None      # callback(event) -> "dizzy", "petted" (tells the phone)
        self.notify_fn = None     # callback(title, message) -> alert on the phone
        self.send_file_fn = None  # callback(path) -> sends a dropped file to the phone
        self.life = Life(None, lambda d: None)
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
        # games & modes
        self.peek_side = 0         # -1 left / +1 right while hiding at the edge, else 0
        self._peek_x = 0.0
        self._peek_until = 0.0
        self.chase_until = 0.0
        self.catches = 0
        self.focus_until = 0.0
        self.focus_minutes = 25
        # too many throws -> angry, leaves, comes back sulking until you say sorry
        self._throws: list[float] = []
        self.leaving = 0           # direction it stomps off (-1 / +1), 0 = not leaving
        self.away_until = 0.0
        self.sulking = False
        self._return_happy = False
        self._chips: list[tuple[float, float, float, float, str]] = []  # answer buttons (window px)
        self._last_img = None
        self._body_cache = None
        self._shadow_cache = None
        self._bubble_cache: dict = {}
        self.keys = KeyCounter()
        self.cookie = Cookie()
        self.fun: Fun | None = None   # games, love, hugs, reminders... (made on BOT's thread)
        self.out_fn = None            # callback(dict) -> sent to the phone
        self.send_text_fn = None      # callback(text) -> phone clipboard
        self.gemini_key = ""          # optional free Gemini key for "Talk to BOT"
        self._glass_rect = None       # where the water glass is (window px), to click it
        self._drop = None
        self._walk_speed = 110.0
        self._fx: dict = {}

    # -- public ------------------------------------------------------------------
    def load_life(self, data: dict | None, save_fn) -> None:
        self.life = Life(data, save_fn)

    def start(self) -> None:
        if self._thread is None:
            self.keys.start()
            self._thread = threading.Thread(target=self._run, name="desktop-pet", daemon=True)
            self._thread.start()

    def set_wanted(self, on: bool) -> None:
        self.wanted = on

    def set_color(self, hex_color: str) -> None:
        """The app colour changes the phone BOT and the bubble cursor; the desktop BOT stays blue."""
        return

    def bring_here(self) -> None:
        self.wanted = True
        self._q.put(("bring",))

    def react(self, mood: str, seconds: float = 2.0) -> None:
        self._q.put(("react", mood, seconds))

    def say(self, text: str, seconds: float = 4.0) -> None:
        self._q.put(("say", text, seconds))

    def feed(self) -> None:
        self.wanted = True
        self._q.put(("feed",))

    def start_chase(self, seconds: float = 45) -> None:
        self.wanted = True
        self._q.put(("chase", seconds))

    def start_focus(self, minutes: int = 25) -> None:
        self.wanted = True
        self._q.put(("focus", minutes))

    def stop_focus(self) -> None:
        self._q.put(("focus_stop",))

    def set_outfit(self, outfit: str) -> None:
        self._q.put(("outfit", outfit))

    def show_report(self) -> str:
        text = self.life.report()
        self._q.put(("say", text, 8.0))
        return text

    def apologize(self) -> str:
        """You said sorry (button or voice)."""
        self._q.put(("answer", "sorry:yes"))
        return "You said sorry to BOT 💕" if self.sulking else "BOT says: no need, I love you! 💖"

    def file_sent(self, ok: bool, message: str) -> None:
        self._q.put(("say", message, 4.0))
        if ok:
            self._q.put(("react", "happy", 2.0))

    def fun_cmd(self, name: str, *args) -> None:
        """Run a Fun method on BOT's thread (games, reminders, moments, options...)."""
        self.wanted = self.wanted or name in ("game_start",)
        self._q.put(("fun", name) + tuple(args))

    def world(self) -> dict:
        w = self.life.world()
        if self.fun:
            w["weather"] = self.fun.weather.now
            w["playing"] = self.fun.media.now
            w["baby"] = bool(self.life.d.get("baby"))
            if self.fun.more:
                w.update(self.fun.more.world())
        w["options"] = dict(self.life.d["options"])
        return w

    def stats(self) -> dict:
        s = self.life.public()
        s["focus_left"] = max(0, int(self.focus_until - time.time())) if self.focus_until else 0
        s["love"] = int(self.life.d["counts"].get("love_yes", 0))
        s["away"] = bool(self.fun and self.fun.gone)
        return s

    def center(self):
        """Where the blue bubble cursor flies out from (None if BOT isn't showing)."""
        return self._center if self.enabled and self.wanted and self._alpha > 20 else None

    def _emit(self, event: str) -> None:
        if self.on_event:
            try:
                self.on_event(event)
            except Exception:
                pass

    def _notify(self, title: str, message: str) -> None:
        if self.notify_fn:
            try:
                self.notify_fn(title, message)
            except Exception:
                pass

    # -- window messages: grab / drag / throw / drop files ---------------------------
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
        if msg == 0x020A:            # WM_MOUSEWHEEL over BOT: change the volume
            delta = ctypes.c_short((wparam >> 16) & 0xFFFF).value
            self._q.put(("fun", "more_cmd", "volume", delta / 120))
            return 0
        if msg == 0x0233:            # WM_DROPFILES: you dropped files on BOT
            self._dropped(wparam)
            return 0
        return user32.DefWindowProcW(hwnd, msg, wparam, lparam)

    def _dropped(self, hdrop) -> None:
        paths = []
        try:
            n = shell32.DragQueryFileW(hdrop, 0xFFFFFFFF, None, 0)
            for i in range(n):
                buf = ctypes.create_unicode_buffer(1024)
                shell32.DragQueryFileW(hdrop, i, buf, 1024)
                if os.path.isfile(buf.value):
                    paths.append(buf.value)
        finally:
            shell32.DragFinish(hdrop)
        if paths:
            self._q.put(("swallow", paths))

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
        if self.fun and self.fun.hugging:  # a long hold was a hug
            self._q.put(("fun", "end_hug"))
            self.flying, self.vx, self.vy = True, 0.0, 0.0
            return
        if self._moved < 6 and now - self._grab_t < 0.35:  # a click, not a throw
            cx, cy = win_input.cursor_pos()
            px, py = cx - self.x, cy - self.y
            gr = self._glass_rect
            for x0, y0, x1, y1, value in self._chips:  # an answer button?
                if x0 <= px <= x1 and y0 <= py <= y1:
                    self._q.put(("answer", value))
                    break
            else:
                if gr and gr[0] <= px <= gr[2] and gr[1] <= py <= gr[3]:
                    self._q.put(("fun", "more_cmd", "water"))  # clicked the water glass
                else:
                    self._q.put(("click",))
            if not self.peek_side:
                self.flying, self.vx, self.vy = True, 0.0, 0.0  # settle on the floor
            return
        self.peek_side = 0
        recent = [s for s in self._samples if now - s[0] < 0.1] or self._samples[-2:]
        if len(recent) >= 2 and recent[-1][0] > recent[0][0]:
            dt = recent[-1][0] - recent[0][0]
            self.vx = max(-6000.0, min(6000.0, (recent[-1][1] - recent[0][1]) / dt))
            self.vy = max(-6000.0, min(6000.0, (recent[-1][2] - recent[0][2]) / dt))
        else:
            self.vx = self.vy = 0.0
        self.spin = self.vx * 0.12
        speed = math.hypot(self.vx, self.vy)
        self._hard_hit = speed > 2600  # a big throw makes BOT dizzy
        self.flying = True
        if speed > 1200 and now > self.chase_until:  # count real throws (not games)
            self._throws = [t for t in self._throws if now - t < 60] + [now]
            if len(self._throws) >= 3:
                self._throws = []
                self._q.put(("angry",))

    # -- physics -------------------------------------------------------------------
    def _limits(self):
        """Window positions where BOT's body touches the screen edges / taskbar."""
        side = (self.W - self.BW) / 2
        perch = self.fun.perch_limits() if self.fun else None
        if perch:
            return (perch[0], perch[1], self.bounds[1] - self.H * 0.35, perch[2])
        return (self.bounds[0] - side, self.bounds[2] - self.W + side, self.bounds[1] - self.H * 0.35,
                self.bounds[3] - self.H + self.FOOT_GAP)

    def _physics(self, dt: float) -> None:
        left, right, top, floor = self._limits()
        now = time.perf_counter()
        if self.dragging:
            cx, cy = win_input.cursor_pos()
            nx, ny = cx - self._grab_off[0], cy - self._grab_off[1]
            self._moved += math.hypot(nx - self.x, ny - self.y)
            self.x, self.y = nx, ny
            self._samples.append((now, float(cx), float(cy)))
            self._samples = [s for s in self._samples if now - s[0] < 0.15]
            self.angle *= 0.8
        elif self.away_until:  # gone off-screen, sulking somewhere
            pass
        elif self.fun and self.fun.drive(dt):  # hiding / begging for a break: stay put
            pass
        elif self.leaving and not self.flying:  # stomping off the screen
            self.x += self.leaving * 420 * dt
            self.y = floor - abs(math.sin(now * 14)) * self.H * 0.03
            if self.x < left - self.W or self.x > right + self.W:
                self.leaving = 0
                self.away_until = now + random.uniform(60, 120)
        elif self.peek_side:  # sliding behind the screen edge (peek-a-boo)
            step = 260 * dt
            self.x += max(-step, min(step, self._peek_x - self.x))
            self.y = floor
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
                    if self.fun and abs(self.vy) > 500:
                        self.fun.sound("boing")
                    self.vy, self.vx = -self.vy * 0.45, self.vx * 0.8
                    self.squish = min(1.0, abs(self.vy) / 1200)
                else:
                    self.vy, self.vx, self.spin = 0.0, self.vx * 0.8, self.spin * 0.7
                if self.vy == 0 and abs(self.vx) < 25:  # settled
                    self.flying, self.vx = False, 0.0
                    if self._hard_hit:
                        self._hard_hit = False
                        self._dizzy_until = now + 3.2
                        self._q.put(("say", random.choice(DIZZY), 3.0))
                        if self.fun:
                            self.fun.sound("squeak")
                        self._emit("dizzy")
        elif self.walking:
            self.x += self._walk_dir * self._walk_speed * dt
            hop = abs(math.sin((now - self._walk_t0) * 9)) * self.H * 0.04
            self.y = floor - hop
            if (self._walk_dir > 0 and self.x >= self._walk_to) or (self._walk_dir < 0 and self.x <= self._walk_to):
                self.walking, self.y = False, floor
                self._walk_speed = 110.0 if not (self.fun and self.fun.game) else self._walk_speed
        else:
            self.y = min(self.y, floor)
            if self.y < floor - 1:  # somehow in the air: fall down
                self.flying = True
            elif now < self.chase_until:  # chase game: hop away from your mouse!
                mx, my = win_input.cursor_pos()
                cx, cy = self.x + self.W / 2, self.y + self.BODY_CY
                if math.hypot(mx - cx, my - cy) < self.S * 2.1:
                    away = 1 if cx >= mx else -1
                    if (away > 0 and self.x > right - 40) or (away < 0 and self.x < left + 40):
                        away = -away  # cornered: jump over you
                    self.vx = away * random.uniform(700, 1100)
                    self.vy = -random.uniform(900, 1300)
                    self.spin = self.vx * 0.05
                    self.flying = True
        if not self.flying and not self.dragging:
            self.angle *= 0.75  # stand back up
            if abs(self.angle) < 0.5:
                self.angle = 0.0
        self.angle = (self.angle + 180) % 360 - 180
        self.squish = max(0.0, self.squish - dt * 3)
        self._center = (self.x + self.W / 2, self.y + self.BODY_CY)

    def _hit(self, speed: float) -> None:
        if speed > 1100 and time.perf_counter() > self.chase_until:  # slammed into the edge (not in chase)
            self._hard_hit = True

    def _maybe_walk(self, mood: str) -> None:
        now = time.perf_counter()
        if mood != "idle" or self.flying or self.dragging or self.walking or self.peek_side or now < self._next_walk:
            return
        if self.fun and (self.fun.busy_now() or self.fun.pinned):
            return
        self._walk_speed = 110.0
        self._next_walk = now + random.uniform(25, 50)
        left, right, _top, _floor = self._limits()
        target = random.uniform(left + 20, right - 20)
        if abs(target - self.x) < 80:
            return
        self._walk_to, self._walk_dir = target, (1 if target > self.x else -1)
        self._walk_t0 = now
        self.walking = True

    # -- main loop -------------------------------------------------------------------
    def _run(self) -> None:
        try:
            self._setup()
            self.enabled = True
        except Exception as exc:
            log.warning("Desktop BOT disabled: %s", exc)
            return
        self.music = MusicMeter()
        try:
            self.fun = Fun(self)
            self.fun.start()
        except Exception:
            log.exception("BOT's fun features failed to start")
            self.fun = None
        msg = wt.MSG()
        now = time.perf_counter()
        st = {"t0": now, "blink": 0.0, "next_blink": 2.0, "look": (0.0, 0.0), "react": None, "react_until": 0.0,
              "yawn_until": 0.0, "next_yawn": 6.0, "particles": [], "next_particle": 0.0, "idle": 0.0,
              "idle_at": 0.0, "was_busy": False, "speech": "", "speech_until": 0.0, "options": (),
              "love_asked": -99.0, "next_question": now + random.uniform(60, 150), "next_cheer": now + 40,
              "typing": 0.0, "last_tick": _last_input_tick(), "last_cursor": win_input.cursor_pos(),
              "type_check": 0.0, "last_feeling": "ok", "music": 0.0, "music_check": 0.0, "dancing_since": 0.0,
              "next_dance_line": 0.0, "beg_until": 0.0, "cry_until": 0.0, "next_beg": now + random.uniform(300, 600),
              "cookie_t0": -99.0, "eat_until": 0.0, "swallow_until": 0.0, "hover_since": 0.0,
              "next_peek": now + random.uniform(240, 480), "life_tick": now, "keys_seen": 0, "active_min": 0.0,
              "next_reminder_min": 60.0, "reminder_i": 0, "next_night": 0.0, "next_hungry": now + 60,
              "water_followup": 0.0, "was_focus": False, "cookie_food": 35, "sleepy_at": 0.0,
              "sleep_ask_until": 0.0, "nap_until": 0.0, "stay_until": 0.0, "gimme_said": False}
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
                if now - st.get("top_check", 0.0) > 2:
                    st["top_check"] = now
                    self._keep_on_top()
                self._life_tick(st)
                self._physics(dt)
                show_cookie = self._alpha > 20 and not self.leaving
                if self.cookie.step(dt, self._center, self.S * 0.8, show_cookie) == "eaten":
                    self._eat(st, 60, skip_fall=True)
                params = self._update(st)
                self._maybe_walk(params["mood"])
                self._maybe_peek(st, params["mood"])
                sig = params["sig"]
                pos = (int(self.x), int(self.y))
                if sig != last_sig or self._last_img is None:
                    last_sig, last_pos = sig, pos
                    self._last_img = self._transform(self._render(params), params["tilt"])
                    self._push(self._last_img, params["alpha"])
                elif pos != last_pos:  # only moved: reuse the picture
                    last_pos = pos
                    self._push(self._last_img, params["alpha"])
                moving = self.dragging or self.flying or self.walking or self.peek_side \
                    or self.cookie.dragging or self.cookie.flying or bool(self.fun and self.fun.game)
                fps = 60 if moving else (24 if params["active"] else (4 if params["mood"] == "asleep" else 10))
            except Exception:
                log.exception("desktop pet frame failed")
                fps = 1
            time.sleep(1 / fps)

    def _keep_on_top(self) -> None:
        """Windows sometimes drops "always on top" (e.g. after locking the PC): claim it back.
        Stays politely behind true fullscreen apps (videos, games, slideshows)."""
        if self.fun and self.fun.hiding:
            return
        house = self.fun.more.house.hwnd if (self.fun and self.fun.more and self.fun.more.house) else None
        fg = user32.GetForegroundWindow()
        if fg and fg not in (self._hwnd, self.cookie._hwnd):
            r, mon = wt.RECT(), wt.RECT()
            user32.GetWindowRect(fg, ctypes.byref(r))
            mon.right, mon.bottom = user32.GetSystemMetrics(0), user32.GetSystemMetrics(1)
            cls = ctypes.create_unicode_buffer(64)
            user32.GetClassNameW(fg, cls, 64)
            fullscreen = (r.left, r.top, r.right, r.bottom) == (0, 0, mon.right, mon.bottom) \
                and cls.value not in ("Progman", "WorkerW")  # (the desktop itself isn't "fullscreen")
            if fullscreen:
                return
        for hwnd in (house, self._hwnd, self.cookie._hwnd):
            if hwnd and user32.IsWindowVisible(hwnd):
                user32.SetWindowPos(hwnd, HWND_TOPMOST, 0, 0, 0, 0, 0x0001 | 0x0002 | 0x0010)  # NOSIZE|NOMOVE|NOACTIVATE

    def _eat(self, st: dict, food: float, skip_fall: bool = False) -> None:
        """Start munching a cookie (a falling one, or the one you brought from the screen)."""
        now = time.perf_counter()
        st["cookie_food"] = food
        st["cookie_t0"] = now - (0.7 if skip_fall else 0.0)
        if self.fun:
            self.fun.sound("munch")
        st["nap_until"] = st["sleep_ask_until"] = 0.0
        st["beg_until"] = st["cry_until"] = 0.0
        self._speak(st, random.choice(GOT_COOKIE) if skip_fall else "A cookie! For me?! 🍪🥺", 2.0)

    def _speak(self, st: dict, text: str, seconds: float, options=()) -> None:
        st["speech"], st["speech_until"], st["options"] = text, time.perf_counter() + seconds, tuple(options)

    def _command(self, cmd, st: dict) -> None:
        now = time.perf_counter()
        kind = cmd[0]
        life = self.life
        if kind == "react":
            st["react"], st["react_until"] = cmd[1], now + cmd[2]
            if cmd[1] == "love":
                self._burst(st, "heart", 5)
        elif kind == "say":
            self._speak(st, cmd[1], cmd[2])
        elif kind == "fun":
            if self.fun:
                try:
                    getattr(self.fun, cmd[1])(st, *cmd[2:])
                except Exception:
                    log.exception("BOT fun command %s failed", cmd[1])
        elif kind == "angry":  # thrown too many times: storm off
            self._dizzy_until = 0.0
            st["beg_until"] = st["cry_until"] = 0.0
            self.chase_until, self.peek_side = 0.0, 0
            left, right, _top, _floor = self._limits()
            self.leaving = 1 if self.x > (left + right) / 2 else -1
            self._speak(st, random.choice(LEAVING), 3.5)
            life.cheer(happy=-15)
        elif kind == "click" and self.sulking:  # no pats until you say sorry
            self._speak(st, random.choice(SULK), 8, SORRY_OPTS)
        elif kind == "click" and now < st["nap_until"]:  # woke it up from its nap
            st["nap_until"] = 0.0
            self._speak(st, random.choice(WOKE), 3)
            st["react"], st["react_until"] = "happy", now + 2
        elif kind == "click" and now < st["sleep_ask_until"]:  # still waiting for an answer
            st["sleep_ask_until"] = now + 15
            self._speak(st, "So sleepy… can I sleep? 🥺😪", 15, SLEEP_OPTS)
        elif kind == "click" and self.fun and self.fun.click(st):  # games, love chain, break plea...
            self._emit("petted")
        elif kind == "click":
            life.cheer(happy=5)
            if self.fun:
                self.fun.sound("chirp")
            if life.add_xp(2):
                self._level_up(st)
            if now < st["cry_until"]:  # pat while crying: forgiven
                st["cry_until"] = 0.0
                self._speak(st, random.choice(FORGIVE), 3.5)
                st["react"], st["react_until"] = "love", now + 3
                self._burst(st, "heart", 6)
            elif now < st["beg_until"]:  # it asked for pats and you did!
                st["beg_until"] = 0.0
                self._speak(st, random.choice(BEG_YES), 3.0)
                st["react"], st["react_until"] = "love", now + 3
                self._burst(st, "heart", 8)
                life.cheer(happy=8)
            elif now < self.chase_until:  # caught it!
                self.catches += 1
                self._speak(st, f"Caught me! 😆 ({self.catches})", 2.0)
                self._burst(st, "heart", 4)
                if life.add_xp(3):
                    self._level_up(st)
            elif self.peek_side:
                self._boo(st)
            else:  # you clicked BOT: it feels loved and asks "do you love me?" again and again
                self._burst(st, "heart", 6)
                st["react"], st["react_until"] = "love", now + 3.0
                if self.fun:
                    self.fun.start_love(st)
                else:
                    self._speak(st, random.choice(LOVE_ASK), 7.0, (("Yes! 💖", "love:yes"), ("Sooo much! 💕", "love:alot")))
            self._emit("petted")
        elif kind == "answer":
            self._answer(st, cmd[1])
        elif kind == "feed":
            if self.cookie.visible:  # the cookie on the screen flies into BOT's mouth
                self.cookie.fly_home()
                self._speak(st, "My cookie! 🤤🍪", 2.0)
            elif life.d["hunger"] >= 95:
                self._speak(st, "I'm full! 🥴 Maybe later?", 3)
            else:
                self._eat(st, 35)
        elif kind == "chase":
            self.chase_until, self.catches = now + cmd[1], 0
            self.peek_side = 0
            self._speak(st, "Catch me if you can! 🏃💨", 3)
            st["react"], st["react_until"] = "excited", now + 1.5
        elif kind == "focus":
            self.focus_minutes = int(cmd[1])
            self.focus_until = time.time() + self.focus_minutes * 60
            self.peek_side = 0
            self._speak(st, f"Focus mode ON! 🍅 {self.focus_minutes} minutes. I'll keep you company", 4)
            st["react"], st["react_until"] = "excited", now + 1.5
        elif kind == "focus_stop":
            if self.focus_until:
                self.focus_until = 0.0
                self._speak(st, "Focus stopped. Good effort! 💙", 3)
        elif kind == "outfit":
            outfit = cmd[1]
            if outfit in ("auto", "none", "santa", "headband", "cap") or life.unlocked(outfit):
                life.d["outfit"] = outfit
                life._dirty = True
                life.save(force=True)
                self._speak(st, "Do I look cute? 🥹✨", 3)
                st["react"], st["react_until"] = "happy", now + 2
            else:
                self._speak(st, "I need to level up for that! 🥺", 3)
        elif kind == "dropped":  # OLE drop: files or text
            files, text = cmd[1], cmd[2]
            files = [f for f in files if os.path.isfile(f)]
            if files:
                self._command(("swallow", files), st)
            elif text.strip():
                st["swallow_until"] = now + 1.6
                short = text.strip().replace("\n", " ")
                self._speak(st, f"Nom! 📋 Sending “{short[:30]}{'…' if len(short) > 30 else ''}” to your phone", 3.5)
                if self.send_text_fn:
                    self.send_text_fn(text.strip()[:100_000])
        elif kind == "swallow":  # files dropped on BOT -> phone
            names = [os.path.basename(p) for p in cmd[1]]
            st["swallow_until"] = now + 1.6
            self._speak(st, f"Nom nom! 😋 Sending {names[0] if len(names) == 1 else f'{len(names)} files'} "
                            "to your phone 📲", 3)
            for p in cmd[1]:
                if self.send_file_fn:
                    self.send_file_fn(p)
        elif kind == "bring":
            mx, _my = win_input.cursor_pos()
            left, right, _top, _floor = self._limits()
            self.peek_side = 0
            self.x = float(max(left, min(right, mx - self.W / 2)))
            self.y = float(self.bounds[1] - self.H * 0.5)
            self.vx, self.vy, self.spin = 0.0, 300.0, 0.0
            self.dragging = self.walking = False
            self.flying = True
            st["react"], st["react_until"] = "happy", now + 2.5
            self._speak(st, "Here I am! 🥰", 3.0)

    def _answer(self, st: dict, value: str) -> None:
        now = time.perf_counter()
        life = self.life
        key, _, val = value.partition(":")
        if self.fun and self.fun.answer(st, key, val):
            return
        if key == "sleep":
            st["sleep_ask_until"] = 0.0
            if val == "yes":
                st["nap_until"] = now + NAP_SECONDS
                self._speak(st, random.choice(GOOD_NIGHT), 3)
                life.cheer(happy=3)
            else:
                st["stay_until"] = now + 15 * 60
                self._speak(st, random.choice(STAY), 4)
                st["react"], st["react_until"] = "love", now + 3
                self._burst(st, "heart", 6)
                life.cheer(happy=5)
            return
        if key == "sorry":
            if self.sulking or self.away_until or self.leaving:
                self.sulking, self.leaving = False, 0
                if self.away_until:  # come back right away, happy
                    self.away_until = 1.0
                    self._return_happy = True
                self._speak(st, random.choice(FORGIVEN), 5)
                st["react"], st["react_until"] = "love", now + 4
                self._burst(st, "heart", 10)
                life.cheer(happy=20)
            else:
                self._speak(st, "Aww, no need! I love you! 💖", 3)
                st["react"], st["react_until"] = "love", now + 2
            return
        life.cheer(happy=3)
        if life.add_xp(2):
            self._level_up(st)
        if key == "love":
            self._speak(st, random.choice(LOVE_YES), 3.5)
            st["react"], st["react_until"] = "love", now + 3
            self._burst(st, "heart", 8)
            return
        self._speak(st, REPLIES.get((key, val), "Hehe, okay! 😊"), 4)
        st["react"], st["react_until"] = "happy", now + 2
        if key == "activity":
            life.d["activity"], life.d["activity_at"] = val, time.time()
        elif key == "water" and val == "no":
            st["water_followup"] = now + 15 * 60
        elif key == "likes" or key == "bff":
            st["react"] = "love"
            self._burst(st, "heart", 6)
        elif key == "play" and val == "yes":
            self.chase_until, self.catches = now + 45, 0
        elif key == "focus" and val == "yes":
            self.focus_minutes = 25
            self.focus_until = time.time() + 25 * 60

    def _level_up(self, st: dict) -> None:
        lvl = self.life.level
        unlocked = [o for o, need in {"bow": 2, "sunglasses": 3, "party": 4, "crown": 5}.items() if need == lvl]
        extra = {"bow": " I unlocked a bow 🎀", "sunglasses": " I unlocked sunglasses 😎",
                 "party": " I unlocked a party hat 🎉", "crown": " I unlocked a crown 👑"}.get(unlocked[0] if unlocked else "", "")
        self._speak(st, f"Level up! I'm level {lvl} now! 🎉{extra}", 5)
        self._burst(st, "sparkle", 8)
        self._notify("BOT levelled up! 🎉", f"Level {lvl}.{extra}")

    def _boo(self, st: dict) -> None:
        """Jump out from behind the screen edge."""
        side = self.peek_side
        self.peek_side = 0
        self.vx, self.vy = -side * 650.0, -950.0
        self.flying = True
        self._speak(st, random.choice(BOO), 2.5)
        st["react"], st["react_until"] = "excited", time.perf_counter() + 2

    def _maybe_peek(self, st: dict, mood: str) -> None:
        now = time.perf_counter()
        if self.peek_side:
            cx, cy = win_input.cursor_pos()
            near = math.hypot(cx - self._center[0], cy - self._center[1]) < self.S * 1.6
            if near or now > self._peek_until:
                self._boo(st)
            return
        if mood != "idle" or self.flying or self.dragging or self.walking or now < st["next_peek"] \
                or self.focus_until or now < self.chase_until:
            return
        st["next_peek"] = now + random.uniform(300, 600)
        left, right, _top, _floor = self._limits()
        self.peek_side = random.choice((-1, 1))
        hide = self.BW * 0.62  # most of the body goes off-screen, only the eyes peek out
        self._peek_x = (left - hide) if self.peek_side < 0 else (right + hide)
        self._peek_until = now + random.uniform(20, 40)

    def _burst(self, st: dict, kind: str, n: int) -> None:
        for _ in range(n):
            st["particles"].append([kind, random.uniform(-0.35, 0.35), random.uniform(-0.25, 0.0),
                                    random.uniform(-0.08, 0.08), random.uniform(-0.35, -0.18), random.uniform(1.2, 1.9)])

    def _life_tick(self, st: dict) -> None:
        """Once a minute: hunger, happiness, daily stats, saving."""
        now = time.perf_counter()
        if now - st["life_tick"] < 60:
            return
        minutes = (now - st["life_tick"]) / 60
        st["life_tick"] = now
        life = self.life
        life.tick(minutes)
        count = self.keys.count
        life.add_keys(count - st["keys_seen"])
        st["keys_seen"] = count
        if st["idle"] < 60:
            life.add_active(minutes)
            st["active_min"] += minutes
        life.save()

    def _transform(self, img: Image.Image, tilt: float = 0.0) -> Image.Image:
        """Spin while flying, sway while dancing, squish on landing."""
        angle = self.angle + tilt
        if abs(angle) > 0.5:
            img = img.rotate(angle, resample=Image.BICUBIC, center=(self.W / 2, self.BODY_CY))
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
        self.W, self.H = int(self.S * 2.6), int(self.S * 2.25)  # room for hats + speech bubble
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
        ex = WS_EX_LAYERED | WS_EX_TOPMOST | WS_EX_TOOLWINDOW | WS_EX_NOACTIVATE | 0x00000010  # + WS_EX_ACCEPTFILES
        self._hwnd = user32.CreateWindowExW(ex, "BotDesktopPet", "BOT", WS_POPUP, int(self.x), int(self.y),
                                            self.W, self.H, None, None, hinst, None)
        if not self._hwnd:
            raise ctypes.WinError(ctypes.get_last_error())
        shell32.DragAcceptFiles(self._hwnd, True)
        # also accept dragged text / links (OLE drop target; files keep working through it too)
        self._drop = pet_dragdrop.register(self._hwnd, lambda files, text: self._q.put(("dropped", files, text)))
        BUBBLE.origin = self.center  # the bubble cursor flies out of the desktop BOT
        self.cookie.setup(self.S, self.bounds)

    # -- behaviour -------------------------------------------------------------------
    def _update(self, st: dict) -> dict:
        now = time.perf_counter()
        t = now - st["t0"]
        life = self.life
        hour = datetime.now().hour
        if self.away_until and now > self.away_until:  # back from sulking somewhere
            self.away_until = 0.0
            left, right, _top, floor = self._limits()
            side = random.choice((-1, 1))
            self.x, self.y = (left - self.W * 0.6) if side < 0 else (right + self.W * 0.6), floor
            self._walk_to = random.uniform(left + self.W * 0.3, right - self.W * 0.3)
            self._walk_dir, self._walk_t0, self.walking = (1 if self._walk_to > self.x else -1), now, True
            self.sulking = not self._return_happy
            self._return_happy = False
            if self.sulking:
                self._speak(st, random.choice(ASK_SORRY), 25, SORRY_OPTS)
                st["next_sorry_ask"] = now + 40
        if now - st["idle_at"] > 0.5:
            idle = health.idle_seconds()
            if st["idle"] > 120 and idle < 2:  # you came back!
                self._speak(st, random.choice(WELCOME), 4)
                st["react"], st["react_until"] = "excited", now + 2
            st["idle"], st["idle_at"] = idle, now
            feeling = self.health.get("feeling", "ok")
            if feeling != st["last_feeling"] and not st["speech"]:
                line = {"hot": HOT, "low_battery": LOW_BATTERY, "charging": CHARGING}.get(feeling)
                if line:
                    self._speak(st, random.choice(line), 4)
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

        # music -> dance
        if now - st["music_check"] > 0.1:
            st["music_check"] = now
            lvl = self.music.level()
            st["music"] = st["music"] * 0.7 + lvl * 0.3
        playing = st["music"] > 0.035
        if playing and not st["dancing_since"]:
            st["dancing_since"] = now
        elif not playing:
            st["dancing_since"] = 0.0
        dancing = bool(st["dancing_since"]) and now - st["dancing_since"] > 1.0

        bx, by, bubble_on = BUBBLE.position()
        busy = bubble_on or self.busy_fn()
        if busy and not st["was_busy"]:  # a task just started
            st["react"], st["react_until"] = "excited", now + 1.2
        st["was_busy"] = busy

        focusing = self.focus_until and time.time() < self.focus_until
        if self.focus_until and not focusing:  # focus session finished
            self.focus_until = 0.0
            self._speak(st, "Break time! You did great 🎉", 6)
            self._burst(st, "sparkle", 10)
            self._burst(st, "heart", 4)
            st["react"], st["react_until"] = "excited", now + 3
            if life.add_xp(10):
                self._level_up(st)
            self._notify("Focus done 🍅", f"{self.focus_minutes} minutes done! Take a short break 🎉")
            if self.fun:
                self.fun.coins(st, 10)
                self.fun.count(st, "focus")
        chasing = now < self.chase_until
        if self.chase_until and not chasing and now - self.chase_until < 0.5:
            self.chase_until = 0.0
            self._speak(st, f"Game over! You caught me {self.catches} time{'s' if self.catches != 1 else ''} 🎉", 5)
            life.cheer(happy=15)

        # cookie: falling, then munching
        cookie_age = now - st["cookie_t0"]
        eating = 0.7 < cookie_age < 2.4
        if 2.4 < cookie_age < 2.6:
            st["cookie_t0"] = -99.0
            life.cheer(happy=8, hunger=st["cookie_food"])
            st["food_emoji"] = ""
            if self.fun:
                self.fun.coins(st, 1)
                self.fun.count(st, "cookies")
                self.fun.badges(st, life.fed_today())
            if life.add_xp(5):
                self._level_up(st)
            self._speak(st, "Yum! 😋 Thank you! 💕", 3)
            st["react"], st["react_until"] = "love", now + 2
            self._burst(st, "heart", 5)
            if not st["sleepy_at"] and life.d["hunger"] > 60:  # full tummy -> sleepy in a little while
                st["sleepy_at"] = now + random.uniform(60, 120)
        swallowing = now < st["swallow_until"]

        # games, love, hugs, reminders, festivals, weather...
        fx = {}
        if self.fun:
            try:
                fx = self.fun.frame(st, now, t, {"typing": typing, "focusing": bool(focusing), "hour": hour,
                                                 "mood_guess": st.get("last_mood", "idle")})
            except Exception:
                log.exception("BOT fun frame failed")
                fx = {}
        self._fx = fx

        # full tummy -> "Can I sleep?" -> nap (or stay awake with you)
        napping = now < st["nap_until"]
        if napping and (self.dragging or self.flying or self.leaving):  # picked up: wide awake now
            st["nap_until"], napping = 0.0, False
        elif st["nap_until"] and not napping:  # the nap is over
            st["nap_until"] = 0.0
            self._speak(st, random.choice(NAP_DONE), 4)
            st["react"], st["react_until"] = "happy", now + 2
            life.cheer(happy=10)
        asking_sleep = now < st["sleep_ask_until"]
        if st["sleep_ask_until"] and not asking_sleep:  # no answer: it just dozes off
            st["sleep_ask_until"] = 0.0
            st["nap_until"], napping = now + NAP_SECONDS, True
            self._speak(st, "…zzz 😴", 2)
        staying = now < st["stay_until"]

        # dragging the cookie close: puppy eyes
        ccx, ccy = self.cookie.center
        cookie_near = self.cookie.dragging and math.hypot(ccx - self._center[0], ccy - self._center[1]) < self.S * 2.6
        if cookie_near and not st["gimme_said"]:
            st["gimme_said"] = True
            self._speak(st, random.choice(GIMME), 2.5)
        elif not self.cookie.dragging:
            st["gimme_said"] = False

        # pat begging -> crying
        begging = now < st["beg_until"]
        crying = now < st["cry_until"]
        if st["beg_until"] and not begging and not crying and now - st["beg_until"] < 1:
            st["beg_until"] = 0.0
            st["cry_until"] = now + 9
            crying = True
            self._speak(st, random.choice(CRY), 9)
            life.cheer(happy=-3)

        if fx.get("force"):
            mood = fx["force"]
        elif self.leaving:
            mood = "angry"
        elif self.dragging:
            mood = "surprised" if not self.sulking else "sulk"
            if st["speech"] not in PICKED and not self.sulking:
                self._speak(st, random.choice(PICKED), 1.5)
        elif now < self._dizzy_until:
            mood = "dizzy"
        elif self.flying and abs(self.vx) + abs(self.vy) > 600:
            mood = "surprised"
        elif eating or swallowing:
            mood = "eat"
        elif crying:
            mood = "cry"
        elif begging or cookie_near:
            mood = "puppy"
        elif fx.get("mood"):
            mood = fx["mood"]
        elif napping:
            mood = "asleep"
        elif asking_sleep:
            mood = "drowsy"
        elif st["react"] and now < st["react_until"]:
            mood = st["react"]
        elif self.sulking:
            mood = "sulk"
        elif chasing:
            mood = "excited"
        elif busy:
            mood = "working"
        elif dancing and not focusing:
            mood = "dance"
        elif focusing:
            mood = "focus"
        elif feeling == "hot":
            mood = "sweaty"
        elif feeling == "low_battery":
            mood = "worried"
        elif life.d["hunger"] < HUNGRY_AT:
            mood = "hungry"
        elif typing:
            mood = "typing"
        elif st["idle"] > 300 and not staying:
            mood = "asleep"
        elif st["idle"] > 60 and not staying:
            mood = "drowsy"
        else:
            mood = "idle"

        # chatter (one thing at a time, never while busy / playing / focusing)
        talking = now < st["speech_until"]
        if not talking:
            st["speech"], st["options"] = "", ()
        if self.sulking and not talking and not self.walking and now > st.get("next_sorry_ask", 0):
            st["next_sorry_ask"] = now + 40
            self._speak(st, random.choice(ASK_SORRY), 25, SORRY_OPTS)
            talking = True
        st["last_mood"] = mood
        quiet = bool(fx.get("quiet")) or self.sulking or self.leaving or bool(self.away_until) or focusing or chasing or self.flying or self.dragging or self.peek_side or mood in ("asleep", "dizzy", "cry", "eat")
        if not talking and not quiet and st["idle"] < 60:
            today = date.today().isoformat()
            if self.fun and self.fun.chatter(st, now, hour, mood):
                pass
            elif st["sleepy_at"] and now > st["sleepy_at"] and not busy:
                st["sleepy_at"] = 0.0
                st["sleep_ask_until"] = now + 15
                st["next_yawn"] = t  # big yawn first
                self._speak(st, random.choice(ASK_SLEEP), 15, SLEEP_OPTS)
            elif life.d.get("morning") != today and 5 <= hour < 12:
                life.d["morning"] = today
                life._dirty = True
                wline = self.fun.weather.line() if self.fun else ""
                self._speak(st, "Good morning! ☀️ Let's have a great day!" + (f" {wline}" if wline else ""), 7)
                st["react"], st["react_until"] = "excited", now + 2
            elif hour >= 21 and life.d.get("report_day") != today:
                life.d["report_day"] = today
                life._dirty = True
                text = life.report()
                self._speak(st, text, 9)
                self._notify("Your day 📊", text)
            elif st["water_followup"] and now > st["water_followup"]:
                st["water_followup"] = 0.0
                self._speak(st, "Did you drink that water? 💧👀", 5, (("Yes! 💧", "water:yes"), ("Oops 🙈", "water:no")))
            elif st["active_min"] >= st["next_reminder_min"]:
                st["next_reminder_min"] = st["active_min"] + 60
                st["reminder_i"] += 1
                if st["reminder_i"] % 2:
                    self._speak(st, random.choice(WATER), 20, (("I drank! 💧", "water:drank"),))
                else:
                    self._speak(st, random.choice(STRETCH), 6)
            elif (hour >= 23 or hour < 5) and now > st["next_night"]:
                st["next_night"] = now + 30 * 60
                self._speak(st, random.choice(NIGHT), 5)
            elif life.d["hunger"] < HUNGRY_AT and now > st["next_hungry"]:
                st["next_hungry"] = now + 4 * 60
                if not self.cookie.visible:  # a cookie pops up somewhere on the screen
                    self.cookie.spawn(self._center)
                    self._speak(st, random.choice(HUNGRY), 7)
                else:
                    self._speak(st, random.choice(HUNGRY_REMIND), 6)
            elif dancing and now > st["next_dance_line"]:
                st["next_dance_line"] = now + 180
                self._speak(st, random.choice(DANCE), 3)
            elif mood in ("idle", "typing") and now > st["next_beg"]:
                st["next_beg"] = now + random.uniform(480, 900)
                st["beg_until"] = now + 10
                self._speak(st, random.choice(BEG), 10)
            elif mood == "typing" and now > st["next_cheer"]:
                self._speak(st, random.choice(TYPING_CHEERS), 3.5)
                st["next_cheer"] = now + random.uniform(80, 160)
            elif now > st["next_question"]:
                q = pick_question(life)
                opts = tuple((label, f"{q['key']}:{val}") for label, val in q.get("opts", ()))
                self._speak(st, q["q"], 12 if opts else 6, opts)
                st["next_question"] = now + random.uniform(150, 300)
        if mood == "drowsy" and t > st["next_yawn"]:
            st["yawn_until"], st["next_yawn"] = t + 1.8, t + random.uniform(7, 12)
            if not st["speech"] and random.random() < 0.3:
                self._speak(st, random.choice(SLEEPY), 2)
        yawning = mood == "drowsy" and t < st["yawn_until"]

        # blink
        if t > st["next_blink"]:
            st["blink"], st["next_blink"] = t, t + random.uniform(2.2, 5.5)
        bp = (t - st["blink"]) / 0.14
        blink = math.sin(bp * math.pi) if 0 <= bp <= 1 else 0.0

        # where to look: the bubble cursor while working, otherwise your mouse
        if bubble_on:
            mx, my = bx, by
        elif fx.get("look"):
            mx, my = fx["look"]
        elif self.cookie.visible:  # can't stop looking at the cookie 👀🍪
            mx, my = self.cookie.center
        else:
            mx, my = win_input.cursor_pos()
        cx, cy = self._center
        dx, dy = mx - cx, my - cy
        dist = max(1.0, math.hypot(dx, dy))
        target = (dx / dist * min(1.0, dist / 300), dy / dist * min(1.0, dist / 300))
        if mood in ("asleep", "dizzy", "cry"):
            target = (0.0, 0.3)
        if mood == "sulk":  # won't look at you
            target = (-0.9 if dx > 0 else 0.9, 0.25)
        if self.peek_side:  # peek towards the screen
            target = (-self.peek_side * 0.9, 0.0)
        lx, ly = st["look"]
        st["look"] = (lx + (target[0] - lx) * 0.35, ly + (target[1] - ly) * 0.35)

        # hovering your mouse over BOT shows its care stats
        rx, ry = win_input.cursor_pos()
        bx0 = self.x + (self.W - self.BW) / 2
        by0 = self.y + self.BODY_CY - self.BH / 2
        over = bx0 <= rx <= bx0 + self.BW and by0 <= ry <= by0 + self.BH and not self.dragging
        if over and not st["hover_since"]:
            st["hover_since"] = now
        elif not over:
            st["hover_since"] = 0.0
        stats_text = ""
        if over and now - st["hover_since"] > 0.8 and not st["speech"]:
            stats_text = f"Lv {life.level} · 🍪 {round(life.d['hunger'])}% · 💖 {round(life.d['happy'])}%"
            if self.fun and self.fun.wpm >= 15:
                stats_text += f" · ⌨️ {self.fun.wpm} WPM"
            if self.fun and self.fun.more:
                stats_text += f" · 🪙 {int(life.d.get('coins', 0))}"
                cd = self.fun.more.countdown_line()
                if cd:
                    stats_text += f" · {cd}"
        focus_text = ""
        if focusing and not st["speech"] and not stats_text:
            left_s = int(self.focus_until - time.time())
            focus_text = f"🍅 {left_s // 60:02d}:{left_s % 60:02d}"

        # particles
        if t > st["next_particle"]:
            st["next_particle"] = t + (0.5 if mood == "dance" else 1.0)
            if mood == "asleep":
                st["particles"].append(["z", 0.3, -0.35, 0.06, -0.12, 2.4])
            elif mood == "love":
                self._burst(st, "heart", 1)
            elif mood == "dance":
                self._burst(st, "note", 1)
            elif mood in ("typing", "excited", "happy") and random.random() < 0.6:
                self._burst(st, "sparkle", 1)
            elif mood == "idle" and feeling == "charging" and random.random() < 0.3:
                self._burst(st, "bolt", 1)
        if mood == "eat" and random.random() < 0.3:
            st["particles"].append(["crumb", random.uniform(-0.12, 0.12), 0.25, random.uniform(-0.1, 0.1), 0.15, 0.6])
        for p in st["particles"]:
            p[1] += p[3] / 12
            p[2] += p[4] / 12
            p[5] -= 1 / 12
        st["particles"] = [p for p in st["particles"] if p[5] > 0]

        target_alpha = 255 if self.wanted and not self.away_until and not (self.fun and self.fun.invisible()) else 0
        self._alpha += (target_alpha - self._alpha) * 0.35
        if abs(target_alpha - self._alpha) < 3:
            self._alpha = float(target_alpha)

        if mood == "angry" and random.random() < 0.08:
            st["particles"].append(["anger", random.uniform(0.2, 0.35), -0.3, 0.0, -0.05, 0.8])
        openness = {"asleep": 0.0, "drowsy": 0.5, "sweaty": 0.8, "focus": 0.85, "sulk": 0.7}.get(mood, 1.0)
        if yawning:
            openness = 0.05
        openness *= 1 - blink
        bounce, tilt = 0.0, 0.0
        if mood in ("typing", "excited", "happy", "love"):
            bounce = abs(math.sin(t * (9 if mood == "typing" else 7))) * 0.05
        if mood == "dance":
            beat = t * 6.5
            bounce = abs(math.sin(beat)) * (0.04 + min(0.05, st["music"] * 0.2))
            tilt = math.sin(beat / 2) * 8
        if mood == "puppy":
            tilt = math.sin(t * 25) * 1.2  # trembling a little
        breathe = math.sin(t * 2.2) * 0.012 if mood in ("idle", "drowsy", "asleep", "hungry") else 0.0
        if fx.get("breathe") is not None:
            breathe = fx["breathe"]

        outfit = self._outfit(mood, feeling, focusing, hour, fx.get("outfit"))
        props = tuple(fx.get("props", ()))
        under = tuple(fx.get("under", ()))
        show_speech = st["speech"] if not (self.flying and not self.dragging) else ""
        options = st["options"] if show_speech else ()
        cookie_y = None
        if 0 <= cookie_age < 0.7:
            cookie_y = cookie_age / 0.7
        active = bool(st["particles"]) or blink > 0 or bounce > 0 or tilt != 0 or cookie_y is not None \
            or mood in ("dizzy", "surprised", "sweaty", "cry", "eat", "puppy", "angry", "hug") or bool(props) \
            or abs(target_alpha - self._alpha) > 0 or yawning or bool(focus_text)
        chomp = int(t * 7) % 2 if mood == "eat" else 0
        sig = (mood, round(openness, 1), round(st["look"][0] * 6), round(st["look"][1] * 6), yawning,
               round(bounce * 200), round(breathe * 400), round(tilt), int(self._alpha), show_speech, options,
               stats_text, focus_text, outfit, chomp, None if cookie_y is None else round(cookie_y * 20),
               tuple((p[0], round(p[1] * 40), round(p[2] * 40)) for p in st["particles"]),
               (int(t * 2) if mood == "sweaty" else 0), (int(t * 12) if mood in ("dizzy", "cry") else 0),
               round(self.angle), round(self.squish * 10), props, under,
               int(min(0.0, self.bounds[2] - (self.x + self.W)) // 12), int(max(0.0, self.bounds[0] - self.x) // 12),
               int(t * 8) if props or under else 0, bool(fx.get("night")))
        return {"mood": mood, "open": openness, "look": st["look"], "yawn": yawning, "bounce": bounce,
                "breathe": breathe, "tilt": tilt, "alpha": self._alpha, "sig": sig, "active": active, "t": t,
                "particles": list(st["particles"]), "speech": show_speech, "options": options,
                "stats": stats_text, "focus": focus_text, "outfit": outfit, "chomp": chomp, "cookie": cookie_y,
                "props": props, "under": under, "night": bool(fx.get("night")), "food": st.get("food_emoji", "")}

    def _outfit(self, mood: str, feeling: str, focusing: bool, hour: int, special: str | None = None) -> str:
        choice = self.life.d.get("outfit", "auto")
        if choice != "auto":
            return choice if self.life.unlocked(choice) else "none"
        if special:  # birthday / festival / sunny weather
            return special
        if focusing:
            return "headband"
        if mood in ("asleep", "drowsy") and (hour >= 22 or hour < 6):
            return "cap"
        if datetime.now().month == 12:
            return "santa"
        if feeling == "charging" and self.life.unlocked("sunglasses") and mood in ("idle", "typing", "dance"):
            return "sunglasses"
        return "none"

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

    def _night_glow(self) -> Image.Image:
        g = getattr(self, "_glow_cache", None)
        if g is None:
            w, h = int(self.BW * SS * 1.7), int(self.BH * SS * 1.7)
            g = Image.new("RGBA", (w, h), (0, 0, 0, 0))
            ImageDraw.Draw(g).ellipse((w * 0.12, h * 0.12, w * 0.88, h * 0.88), fill=(255, 220, 140, 95))
            g = g.filter(ImageFilter.GaussianBlur(14 * SS))
            self._glow_cache = g
        return g

    def _shadow(self) -> Image.Image:
        if self._shadow_cache is None:
            w, h = int(self.BW * SS * 0.9), int(self.S * 0.12 * SS)
            sh = Image.new("RGBA", (w + 20 * SS, h + 20 * SS), (0, 0, 0, 0))
            ImageDraw.Draw(sh).ellipse((10 * SS, 10 * SS, 10 * SS + w, 10 * SS + h), fill=(0, 0, 0, 70))
            self._shadow_cache = sh.filter(ImageFilter.GaussianBlur(5 * SS))
        return self._shadow_cache

    def _speech_bubble(self, text: str, options=(), pill: bool = False, small: bool = False, avail: int = 0):
        """Speech bubble (optionally with answer buttons). Returns (image, [(x0,y0,x1,y1,value)...])."""
        key = (text, options, pill, small, avail)
        if key not in self._bubble_cache:
            font = _font(int((12.5 if pill else 13.5) * (0.88 if small else 1.0) * self.scale * SS))
            small = _font(int(12 * self.scale * SS))
            pad = int((7 if pill else 10) * self.scale * SS)
            max_w = min(self.W * SS, avail or self.W * SS) - 2 * pad - 8 * SS  # narrower near a screen edge
            probe = ImageDraw.Draw(Image.new("RGBA", (1, 1)))
            words, lines, cur = text.split(), [], ""
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
            # answer buttons, wrapped into rows
            chip_pad, gap = int(8 * self.scale * SS), int(6 * self.scale * SS)
            ch = int(small.size * 1.7)
            rows, row, row_w = [], [], 0
            for label, value in options:
                if value == "|":  # forced new row
                    if row:
                        rows.append(row)
                    row, row_w = [], 0
                    continue
                cw = int(probe.textlength(label, font=small)) + 2 * chip_pad
                if row and row_w + gap + cw > max_w:
                    rows.append(row)
                    row, row_w = [], 0
                row.append((label, value, cw))
                row_w += (gap if len(row) > 1 else 0) + cw
            if row:
                rows.append(row)
            rows_w = max([sum(c[2] for c in r) + gap * (len(r) - 1) for r in rows] or [0])
            bw = max(tw, rows_w) + 2 * pad
            bh = lh * len(lines) + pad * 2 - int(lh * 0.2) + (len(rows) * (ch + gap) + gap if rows else 0)
            tail = 0 if pill else int(9 * self.scale * SS)
            img = Image.new("RGBA", (bw + 6 * SS, bh + tail + 6 * SS), (0, 0, 0, 0))
            d = ImageDraw.Draw(img, "RGBA")
            fill = (255, 255, 255, 245) if not pill else (20, 30, 60, 220)
            d.rounded_rectangle((3 * SS, 3 * SS, 3 * SS + bw, 3 * SS + bh), radius=int(14 * self.scale * SS),
                                fill=fill, outline=_mix(self._color, (0, 0, 0), 0.1) + (255,), width=int(1.6 * SS))
            if tail:
                mid = 3 * SS + bw // 2
                d.polygon([(mid - tail, 3 * SS + bh - 2 * SS), (mid + tail, 3 * SS + bh - 2 * SS),
                           (mid, 3 * SS + bh + tail)], fill=fill)
            ink = (30, 36, 64, 255) if not pill else (240, 245, 255, 255)
            for i, line in enumerate(lines):
                d.text((3 * SS + pad, 3 * SS + pad + i * lh), line, font=font, fill=ink, embedded_color=True)
            chips = []
            y = 3 * SS + pad + lh * len(lines) + gap
            for r in rows:
                x = 3 * SS + pad
                for label, value, cw in r:
                    d.rounded_rectangle((x, y, x + cw, y + ch), radius=ch // 2, fill=_mix(self._color, WHITE, 0.82) + (255,),
                                        outline=_mix(self._color, (0, 0, 0), 0.05) + (255,), width=int(1.4 * SS))
                    d.text((x + chip_pad, y + ch / 2), label, font=small, fill=(30, 36, 64, 255), anchor="lm",
                           embedded_color=True)
                    chips.append((x, y, x + cw, y + ch, value))
                    x += cw + gap
                y += ch + gap
            if len(self._bubble_cache) > 60:
                self._bubble_cache.clear()
            self._bubble_cache[key] = (img, chips)
        return self._bubble_cache[key]

    def _render(self, p: dict) -> Image.Image:
        W, H = self.W * SS, self.H * SS
        img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        body = self._body()
        bw, bh = self.BW * SS, self.BH * SS
        mood, t = p["mood"], p["t"]
        lift = int(p["bounce"] * self.S * SS)
        x0 = (W - bw) // 2
        y0 = int(H - self.FOOT_GAP * SS - self.S * 0.08 * SS - bh) - lift
        if p.get("night"):  # night light: a soft warm glow
            glow = self._night_glow()
            img.alpha_composite(glow, ((W - glow.width) // 2, int(y0 + bh / 2 - glow.height / 2)))
        if not self.flying:  # soft shadow on the floor
            sh = self._shadow()
            img.alpha_composite(sh, ((W - sh.width) // 2, int(H - self.FOOT_GAP * SS - sh.height * 0.62)))
        if p["breathe"]:  # gentle squash and stretch
            k = 1 + p["breathe"]
            b2 = body.resize((int(body.width / k), int(body.height * k)), Image.BILINEAR)
            img.alpha_composite(b2, ((W - b2.width) // 2, y0 + body.height - b2.height))
        else:
            img.alpha_composite(body, (x0, y0))
        d = ImageDraw.Draw(img, "RGBA")
        for item in p.get("under", ()):  # paint on BOT (Holi colours)
            pet_props.under(d, item[0], x0, y0, bw, bh, SS, t)
        cx = W / 2
        lx, ly = p["look"][0] * bw * 0.06, p["look"][1] * bh * 0.05
        if mood == "puppy":
            lx += math.sin(t * 30) * bw * 0.004
        ey = y0 + bh * 0.5 + ly
        er = bw * 0.13
        eyes = []

        for side in (-1, 1):
            ex = cx + side * bw * 0.19 + lx
            eyes.append((ex, ey))
            if mood == "dizzy":  # black spiral eyes
                exx, eyy = cx + side * bw * 0.19, y0 + bh * 0.5
                spin = t * 7 * side
                pts = [(exx + math.cos(spin + a / 5) * er * 1.05 * a / 36, eyy + math.sin(spin + a / 5) * er * 1.05 * a / 36)
                       for a in range(37)]
                d.line(pts, fill=INK + (255,), width=int(3.2 * SS), joint="curve")
            elif mood == "cry":  # squeezed > < eyes
                w_, h_ = er * 0.8, er * 0.55
                d.line([(ex + side * w_, ey - h_), (ex - side * w_ * 0.2, ey), (ex + side * w_, ey + h_)],
                       fill=INK + (255,), width=int(3.4 * SS), joint="curve")
            elif mood in ("typing", "happy", "excited", "dance", "eat", "hug"):  # ^ ^ happy eyes
                d.arc((ex - er, ey - er * 0.7, ex + er, ey + er * 1.1), 200, 340, fill=INK + (255,), width=int(4 * SS))
            elif mood == "love":  # heart eyes
                d.polygon(_heart(ex, ey, er * 1.05), fill=(255, 77, 141, 255))
                d.ellipse((ex - er * 0.45, ey - er * 0.45, ex - er * 0.15, ey - er * 0.15), fill=(255, 255, 255, 220))
            elif p["open"] < 0.12:  # closed: sleeping, blinking, yawning
                d.arc((ex - er * 0.8, ey - er * 0.5, ex + er * 0.8, ey + er * 0.5), 20, 160, fill=INK + (255,),
                      width=int(3.2 * SS))
            else:  # big glossy anime-style eyes
                r = er * (1.18 if mood == "surprised" else (1.14 if mood == "puppy" else 1.0))
                ry = r * 1.2 * max(0.2, p["open"])
                d.ellipse((ex - r, ey - ry, ex + r, ey + ry), fill=INK + (255,))
                if p["open"] > 0.45:
                    d.ellipse((ex - r * 0.5, ey + ry * 0.38, ex + r * 0.5, ey + ry * 0.86), fill=(70, 110, 230, 95))
                    hr = r * (0.52 if mood == "puppy" else 0.46)
                    d.ellipse((ex - r * 0.62, ey - ry * 0.72, ex - r * 0.62 + hr * 2, ey - ry * 0.72 + hr * 1.9),
                              fill=WHITE + (255,))
                    sr = r * (0.26 if mood == "puppy" else 0.2)
                    d.ellipse((ex + r * 0.22, ey + ry * 0.18, ex + r * 0.22 + sr * 2, ey + ry * 0.18 + sr * 2),
                              fill=WHITE + (240,))
                    tw = r * 0.09
                    d.ellipse((ex + r * 0.42, ey - ry * 0.45, ex + r * 0.42 + tw * 2, ey - ry * 0.45 + tw * 2),
                              fill=WHITE + (220,))
                    if mood == "puppy":  # watery shine at the bottom
                        d.arc((ex - r * 0.8, ey - ry * 0.2, ex + r * 0.8, ey + ry * 0.95), 30, 150,
                              fill=(160, 210, 255, 230), width=int(2.4 * SS))
                if mood in ("drowsy", "focus", "angry", "sulk") or (mood == "sweaty" and p["open"] < 0.9):
                    # eyelid in body colour
                    k = (ey - ry - y0) / bh
                    lid = _mix(_mix(self._color, WHITE, 0.22), _mix(self._color, (0, 0, 0), 0.14), max(0.0, min(1.0, k)))
                    cover = 180 if mood not in ("focus", "angry", "sulk") else 205
                    d.chord((ex - r - 3, ey - ry - 3, ex + r + 3, ey + ry + 3), cover, 360 - (cover - 180),
                            fill=lid + (255,))
                    if mood != "focus":
                        d.line([(ex - r, ey), (ex + r, ey)], fill=INK + (255,), width=int(2.6 * SS))
                if mood in ("worried", "hungry", "puppy"):  # little worried brows
                    d.line([(ex - side * r * 0.9, ey - r * 1.55), (ex + side * r * 0.5, ey - r * 1.25)],
                           fill=INK + (255,), width=int(2.4 * SS))
                if mood == "angry":  # angry brows: low in the middle
                    d.line([(ex + side * r * 0.95, ey - r * 1.7), (ex - side * r * 0.65, ey - r * 1.15)],
                           fill=INK + (255,), width=int(3.4 * SS))

        # tears
        if mood == "cry":
            for side in (-1, 1):
                ex = cx + side * bw * 0.19 + lx
                for k in range(3):
                    ph = ((t * 1.6) + k / 3) % 1.0
                    tx = ex + side * er * 0.7
                    ty = ey + er * 0.4 + ph * bh * 0.45
                    r = er * (0.22 - 0.05 * ph)
                    d.polygon([(tx, ty - r * 1.9), (tx - r, ty), (tx + r, ty)], fill=TEAR + (int(230 * (1 - ph)),))
                    d.ellipse((tx - r, ty - r, tx + r, ty + r), fill=TEAR + (int(230 * (1 - ph)),))

        # blush
        blush = 165 if mood in ("love", "happy", "typing", "excited", "dance", "puppy", "hug") else 105
        puff = 1.35 if mood in ("angry", "sulk") else 1.0  # puffed cheeks
        cheek = (255, 80, 90) if mood == "angry" else PINK
        for side in (-1, 1):
            bcx, bcy = cx + side * bw * 0.34 + lx * 0.5, ey + bh * 0.15
            d.ellipse((bcx - bw * 0.085 * puff, bcy - bh * 0.045 * puff, bcx + bw * 0.085 * puff, bcy + bh * 0.045 * puff),
                      fill=cheek + (190 if mood in ("angry", "sulk") else blush,))
            if mood in ("love", "puppy", "hug"):  # shy lines
                for i in (-1, 0, 1):
                    xx = bcx + i * bw * 0.035
                    d.line([(xx + bw * 0.012, bcy - bh * 0.03), (xx - bw * 0.012, bcy + bh * 0.03)],
                           fill=(255, 90, 150, 220), width=int(1.6 * SS))

        # mouth
        mx, my = cx + lx * 0.4, y0 + bh * 0.67 + ly * 0.4
        mw = bw * 0.16
        if mood == "eat":
            if p["chomp"]:
                d.ellipse((mx - mw * 0.45, my - mw * 0.35, mx + mw * 0.45, my + mw * 0.7), fill=INK + (255,))
            else:
                d.line([(mx - mw * 0.4, my + mw * 0.15), (mx + mw * 0.4, my + mw * 0.15)], fill=INK + (255,),
                       width=int(3 * SS))
        elif mood == "angry":  # grumpy frown
            d.arc((mx - mw * 0.55, my + mw * 0.05, mx + mw * 0.55, my + mw * 0.75), 200, 340, fill=INK + (255,),
                  width=int(3 * SS))
        elif mood == "sulk":  # little pout
            d.ellipse((mx - mw * 0.16, my + mw * 0.12, mx + mw * 0.16, my + mw * 0.42), fill=INK + (255,))
        elif mood == "cry":  # wobbly "waah" mouth
            d.chord((mx - mw * 0.55, my - mw * 0.1, mx + mw * 0.55, my + mw * 0.9), 180, 360, fill=INK + (255,))
        elif p["yawn"] or mood in ("surprised", "dizzy"):
            r = mw * (0.42 if p["yawn"] else 0.28)
            d.ellipse((mx - r, my - r * 0.7, mx + r, my + r * 1.2), fill=INK + (255,))
        elif mood in ("typing", "happy", "excited", "love", "dance", "hug"):  # open happy smile with tongue
            d.chord((mx - mw * 0.75, my - mw * 0.45, mx + mw * 0.75, my + mw * 0.8), 0, 180, fill=INK + (255,))
            d.chord((mx - mw * 0.42, my + mw * 0.05, mx + mw * 0.42, my + mw * 0.78), 0, 180, fill=(255, 120, 150, 255))
        elif mood in ("worried", "sad", "hungry"):
            d.arc((mx - mw * 0.6, my, mx + mw * 0.6, my + mw * 0.8), 200, 340, fill=INK + (255,), width=int(2.6 * SS))
        elif mood == "puppy":  # tiny pouty mouth
            d.arc((mx - mw * 0.3, my + mw * 0.1, mx + mw * 0.3, my + mw * 0.55), 200, 340, fill=INK + (255,),
                  width=int(2.4 * SS))
        elif mood == "asleep":
            d.ellipse((mx - mw * 0.12, my, mx + mw * 0.12, my + mw * 0.24), fill=INK + (200,))
        else:  # cute "ω" cat mouth
            q = mw * 0.3
            d.arc((mx - 2 * q, my - q, mx, my + q), 0, 180, fill=INK + (255,), width=int(2.6 * SS))
            d.arc((mx, my - q, mx + 2 * q, my + q), 0, 180, fill=INK + (255,), width=int(2.6 * SS))

        # outfit
        if p["outfit"] != "none":
            if not pet_props.outfit(d, p["outfit"], x0, y0, bw, bh, SS, t):
                pet_outfits.draw(d, p["outfit"], x0, y0, bw, bh, eyes, er, SS, t)
        self._glass_rect = None
        for item in p.get("props", ()):  # popcorn, glasses, umbrella, note, festival things, water glass...
            pet_props.over(d, item[0], x0, y0, bw, bh, eyes, er, SS, t, font=_font(int(15 * SS * self.scale)),
                           arg=item[1] if len(item) > 1 else None)
            if item[0] == "glass":
                self._glass_rect = ((x0 - bw * 0.4) / SS, (y0 + bh * 0.45) / SS, (x0 - bw * 0.06) / SS, (y0 + bh * 1.02) / SS)

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
        if p["cookie"] is not None and p.get("food"):  # a treat from the shop falling into BOT's mouth
            cyk = (y0 - bh * 0.6) + (my - (y0 - bh * 0.6)) * p["cookie"]
            d.text((cx, cyk), p["food"], font=_font(int(24 * SS * self.scale)), anchor="mm", embedded_color=True)
        elif p["cookie"] is not None:  # a cookie falling into BOT's mouth
            ck = 11 * SS * self.scale
            cyk = (y0 - bh * 0.6) + (my - (y0 - bh * 0.6)) * p["cookie"]
            d.ellipse((cx - ck, cyk - ck, cx + ck, cyk + ck), fill=(205, 140, 70, 255), outline=(160, 100, 45, 255),
                      width=int(1.5 * SS))
            for ox, oy in ((-0.4, -0.3), (0.35, -0.1), (-0.1, 0.4), (0.3, 0.45)):
                r = ck * 0.17
                d.ellipse((cx + ox * ck - r, cyk + oy * ck - r, cx + ox * ck + r, cyk + oy * ck + r), fill=(90, 50, 25, 255))
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
            elif kind == "crumb":
                d.ellipse((x - s * 0.2, y - s * 0.2, x + s * 0.2, y + s * 0.2), fill=(160, 100, 45, a))
            elif kind == "anger":
                d.text((x, y), "💢", font=_font(int(16 * SS * self.scale)), anchor="mm", embedded_color=True)
            elif kind == "note":
                d.text((x, y), "🎵", font=_font(int(16 * SS * self.scale)), anchor="mm", embedded_color=True)
            elif kind == "coin":
                d.text((x, y), "🪙", font=_font(int(14 * SS * self.scale)), anchor="mm", embedded_color=True)
            elif kind == "fire":
                d.text((x, y), "🔥", font=_font(int(13 * SS * self.scale)), anchor="mm", embedded_color=True)
            elif kind == "confetti":
                col = [(255, 90, 140), (255, 210, 60), (90, 200, 255), (130, 230, 120), (190, 140, 255)][int(px * 97) % 5]
                d.rectangle((x - s * 0.25, y - s * 0.12, x + s * 0.25, y + s * 0.12), fill=col + (a,))
            else:
                d.text((x, y), "z", font=_font(int(15 * SS * self.scale)), fill=_mix(self._color, (0, 0, 0), 0.3) + (a,),
                       anchor="mm")

        # speech bubble / stats / focus timer above BOT (higher if wearing a hat)
        self._chips = []
        hat = pet_outfits.HAT_HEIGHT * bh if (pet_outfits.has_hat(p["outfit"])
                                              or p["outfit"] in ("grad", "halo", "bunny", "chef", "cowboy")
                                              or any(i[0] in ("umbrella", "kite", "toran") for i in p.get("props", ()))) else 0
        label = p["speech"] or p["stats"] or p["focus"]
        if label:
            vis_l = max(0, int((self.bounds[0] - self.x) * SS))
            vis_r = min(W, int((self.bounds[2] - self.x) * SS))
            avail = (vis_r - vis_l) - 6 * SS
            avail = avail if avail < W - 8 * SS else 0
            sb, chips = self._speech_bubble(label, p["options"], pill=not p["speech"], small=bool(p.get("night")),
                                            avail=max(int(150 * SS * self.scale), avail) if avail else 0)
            # keep the bubble on the screen even when BOT stands at the very edge
            lo = max(0, int((self.bounds[0] - self.x) * SS) + 2 * SS)
            hi = min(W, int((self.bounds[2] - self.x) * SS) - 2 * SS) - sb.width
            bx = int(max(lo, min(hi, cx - sb.width / 2))) if hi >= lo else int(max(0, min(W - sb.width, cx - sb.width / 2)))
            by = max(0, int(y0 - hat - sb.height - 2 * SS))
            img.alpha_composite(sb, (bx, by))
            self._chips = [((bx + a) / SS, (by + b) / SS, (bx + c) / SS, (by + e) / SS, v) for a, b, c, e, v in chips]
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
