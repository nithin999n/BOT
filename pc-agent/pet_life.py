"""
The desktop BOT's "life": hunger / happiness / level (saved in config.json), what it remembers
about you, its question bank, a key COUNTER for the daily report (it only counts presses, it never
records which keys), and a music detector so it can dance.
"""
from __future__ import annotations

import ctypes
import ctypes.wintypes as wt
import logging
import random
import threading
import time
from datetime import date, datetime

log = logging.getLogger("bot")

# outfits you unlock by levelling BOT up (the others are always available)
OUTFIT_UNLOCK = {"bow": 2, "sunglasses": 3, "party": 4, "crown": 5}
OUTFITS = ["auto", "none", "bow", "sunglasses", "party", "crown", "santa", "headband", "cap"]

# ---- questions -----------------------------------------------------------------------
# Questions with answer buttons. BOT remembers the answer ("key") and replies.
QA = [
    {"q": "What are you doing? 👀", "key": "activity",
     "opts": [("Working 💼", "working"), ("Studying 📚", "studying"), ("Gaming 🎮", "gaming"), ("Chilling 😎", "chilling")]},
    {"q": "Did you drink water today? 💧", "key": "water", "opts": [("Yes! 💧", "yes"), ("Not yet 🙈", "no")]},
    {"q": "Are you hungry? 🍕", "key": "hungry", "opts": [("Yes 🍕", "yes"), ("Nope 😊", "no")]},
    {"q": "How are you feeling? 🥰", "key": "mood",
     "opts": [("Happy 😄", "happy"), ("Tired 😴", "tired"), ("Stressed 😣", "stressed")]},
    {"q": "Do you like me? 🥺", "key": "likes", "opts": [("Yes! 💖", "yes"), ("A lot! 💕", "alot")]},
    {"q": "Did you sleep well? 😴", "key": "sleep", "opts": [("Yes 😊", "yes"), ("Not really 🥱", "no")]},
    {"q": "Cats or dogs? 🐱🐶", "key": "pets", "opts": [("Cats 🐱", "cats"), ("Dogs 🐶", "dogs"), ("You! 🥰", "bot")]},
    {"q": "Tea or coffee? ☕", "key": "drink", "opts": [("Tea 🍵", "tea"), ("Coffee ☕", "coffee"), ("Juice 🧃", "juice")]},
    {"q": "Should we play a game? 🎮", "key": "play", "opts": [("Yes! 🏃", "yes"), ("Later 🙏", "later")]},
    {"q": "Want to focus for 25 minutes? 🍅", "key": "focus", "opts": [("Let's go! 🍅", "yes"), ("Not now", "no")]},
    {"q": "Pizza or biryani? 🍕🍛", "key": "food", "opts": [("Pizza 🍕", "pizza"), ("Biryani 🍛", "biryani"), ("Both! 😋", "both")]},
    {"q": "Is today a good day? ☀️", "key": "day", "opts": [("Yes! ☀️", "good"), ("Meh 😐", "meh"), ("Not really 🌧️", "bad")]},
    {"q": "Morning person or night owl? 🌅🦉", "key": "chrono", "opts": [("Morning 🌅", "morning"), ("Night 🦉", "night")]},
    {"q": "Can I be your best friend? 🥺", "key": "bff", "opts": [("Of course! 💙", "yes"), ("You already are! 💖", "already")]},
]
REPLIES = {
    ("activity", "working"): "You've got this! 💪", ("activity", "studying"): "Smart human! 📚 I'll be quiet",
    ("activity", "gaming"): "Ooh! Can I watch? 🎮", ("activity", "chilling"): "Yay, chill time! 😎",
    ("water", "yes"): "Good job! 💧✨", ("water", "no"): "Go drink some water! 💧 I'll wait 🥺",
    ("hungry", "yes"): "Go eat something yummy! 🍕 Bring me a cookie? 🍪", ("hungry", "no"): "Okay! 😊",
    ("mood", "happy"): "Yay! That makes me happy too! 😄", ("mood", "tired"): "Aww… take a little rest? 🥺💤",
    ("mood", "stressed"): "Hug! 🤗 You're doing great, one step at a time 💙",
    ("likes", "yes"): "Hehe! I like you too! 💖", ("likes", "alot"): "Aaaa! I like you a LOT too! 💕💕",
    ("sleep", "yes"): "Yay! Well-rested human! 😊", ("sleep", "no"): "Try to sleep early tonight, okay? 🌙",
    ("pets", "cats"): "Meow! 🐱", ("pets", "dogs"): "Woof woof! 🐶", ("pets", "bot"): "Hehe, me?! 🥰",
    ("drink", "tea"): "Cozy! 🍵", ("drink", "coffee"): "Coffee power! ☕⚡", ("drink", "juice"): "Yummy! 🧃",
    ("play", "yes"): "Yay! Catch me if you can! 🏃", ("play", "later"): "Okay, later then! 🎈",
    ("focus", "yes"): "Focus mode ON! 🍅 I'll keep you company", ("focus", "no"): "Okay! 😊",
    ("food", "pizza"): "Pizza party! 🍕", ("food", "biryani"): "Biryani is the best! 🍛", ("food", "both"): "Big appetite! 😋",
    ("day", "good"): "Yay! Let's keep it awesome! ☀️", ("day", "meh"): "I'll try to make it better! 🥰",
    ("day", "bad"): "Aww… I'm here for you 🫂💙",
    ("chrono", "morning"): "Early bird! 🐦", ("chrono", "night"): "Night owl, like me! 🦉",
    ("bff", "yes"): "Best friends forever! 💙🤝", ("bff", "already"): "Awww! 🥹💖",
}
# Questions without buttons, just for fun.
QUESTIONS = [
    "What's your favourite food? 😋", "Do you have a pet? 🐾", "What made you smile today? 😊",
    "Is it sunny outside? ☀️", "Will you play with me later? 🎈", "Have you stretched today? 🙆",
    "What song are you listening to? 🎵", "Do you think I'm cute? 🥹", "Did you finish your work? ✅",
    "Are you texting someone? 👀📱", "What's your dream? ✨", "Do you like my colour? 💙",
    "Can you teach me something new? 🤓", "Is it fun being a human? 🤔", "What's your favourite movie? 🎬",
    "Do you like rain? 🌧️", "Can we watch cartoons later? 📺", "Have you smiled today? 😊",
    "Tell me a secret? 🤫", "What's the best thing that happened today? 🌟", "Do you dream about robots? 🤖",
    "I wonder what clouds taste like ☁️", "Are you proud of yourself? You should be! 🏅",
]
STILL = {"working": "Still working? Don't forget breaks! 💙", "studying": "Still studying? You're so hardworking! 📚",
         "gaming": "Still gaming? Are you winning? 🏆", "chilling": "Still chilling? Me too! 😎"}
BEG = ["You don't wanna pet me? 🥺", "Pet me pleeease? 🥺", "No pats today? 🥺", "Just one little pat? 🥺👉👈"]
CRY = ["Waaah 😭", "Nobody pets me… 😭", "*sob* 😭"]
FORGIVE = ["*sniff*… okay, I forgive you 🥺💕", "Hehe, yay! Pats! 🥹💖"]
BEG_YES = ["Yay!! Pats!! 💕", "Hehe, that feels nice 🥰", "More pats please! 💖"]


def default_life() -> dict:
    return {"xp": 0, "hunger": 80.0, "happy": 80.0, "activity": "", "activity_at": 0.0, "morning": "",
            "report_day": "", "outfit": "auto", "stats": {}}


class Life:
    """Stats that survive restarts (saved through save_fn into config.json)."""

    def __init__(self, data: dict | None, save_fn):
        self.d = {**default_life(), **(data or {})}
        self.save_fn = save_fn
        self._dirty = False
        self._last_save = time.time()
        self.last_interaction = time.time()

    @property
    def level(self) -> int:
        return min(99, 1 + int(self.d["xp"] // 100))

    def unlocked(self, outfit: str) -> bool:
        return self.level >= OUTFIT_UNLOCK.get(outfit, 1)

    def add_xp(self, n: float) -> bool:
        before = self.level
        self.d["xp"] = self.d["xp"] + n
        self._dirty = True
        return self.level > before

    def cheer(self, happy: float = 0, hunger: float = 0) -> None:
        self.d["happy"] = max(0.0, min(100.0, self.d["happy"] + happy))
        self.d["hunger"] = max(0.0, min(100.0, self.d["hunger"] + hunger))
        self.last_interaction = time.time()
        self._dirty = True

    def tick(self, minutes: float) -> None:
        """Hunger and happiness slowly go down while the PC is on."""
        self.d["hunger"] = max(0.0, self.d["hunger"] - minutes / 4)  # ~15% an hour
        if time.time() - self.last_interaction > 600:
            self.d["happy"] = max(0.0, self.d["happy"] - minutes / 15)
        self._dirty = True

    def today(self) -> dict:
        key = date.today().isoformat()
        stats = self.d.setdefault("stats", {})
        if key not in stats:
            stats[key] = {"keys": 0, "active_min": 0.0, "hours": [0] * 24}
            for old in sorted(stats)[:-7]:  # keep a week
                stats.pop(old, None)
        return stats[key]

    def add_keys(self, n: int) -> None:
        if n:
            t = self.today()
            t["keys"] += n
            t["hours"][datetime.now().hour] += n
            self._dirty = True

    def add_active(self, minutes: float) -> None:
        self.today()["active_min"] += minutes
        self._dirty = True

    def report(self) -> str:
        t = self.today()
        mins = int(t["active_min"])
        if t["keys"] < 20 and mins < 5:
            return "Quiet day so far 😴 Let's do something fun!"
        busiest = max(range(24), key=lambda h: t["hours"][h])
        hour = datetime(2000, 1, 1, busiest).strftime("%I %p").lstrip("0")
        return (f"Today you pressed {t['keys']:,} keys ⌨️, were active for {mins // 60}h {mins % 60}m, "
                f"busiest at {hour} 🔥")

    def save(self, force: bool = False) -> None:
        if self._dirty and (force or time.time() - self._last_save > 60):
            self._dirty = False
            self._last_save = time.time()
            try:
                self.save_fn(dict(self.d))
            except Exception:
                log.exception("saving BOT's life failed")

    def public(self) -> dict:
        """What the phone shows in the Care card."""
        return {"level": self.level, "xp": int(self.d["xp"]), "hunger": round(self.d["hunger"]),
                "happy": round(self.d["happy"]), "outfit": self.d.get("outfit", "auto"),
                "unlocked": [o for o in OUTFITS if self.unlocked(o)], "unlock_at": OUTFIT_UNLOCK}


# ---- key counter (counts presses only; never which key) --------------------------------
class KeyCounter:
    def __init__(self):
        self.count = 0
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        if self._thread is None:
            self._thread = threading.Thread(target=self._run, name="key-counter", daemon=True)
            self._thread.start()

    def _run(self) -> None:
        user32, kernel32 = ctypes.windll.user32, ctypes.windll.kernel32
        LRESULT = ctypes.c_ssize_t
        HOOKPROC = ctypes.WINFUNCTYPE(LRESULT, ctypes.c_int, wt.WPARAM, wt.LPARAM)
        user32.CallNextHookEx.argtypes = [ctypes.c_void_p, ctypes.c_int, wt.WPARAM, wt.LPARAM]
        user32.CallNextHookEx.restype = LRESULT
        user32.SetWindowsHookExW.argtypes = [ctypes.c_int, HOOKPROC, wt.HINSTANCE, wt.DWORD]
        user32.SetWindowsHookExW.restype = ctypes.c_void_p
        kernel32.GetModuleHandleW.restype = wt.HMODULE

        def proc(n_code, w_param, l_param):
            if n_code >= 0 and w_param in (0x0100, 0x0104):  # WM_KEYDOWN / WM_SYSKEYDOWN
                self.count += 1
            return user32.CallNextHookEx(None, n_code, w_param, l_param)

        self._proc = HOOKPROC(proc)  # keep a reference
        hook = user32.SetWindowsHookExW(13, self._proc, kernel32.GetModuleHandleW(None), 0)  # WH_KEYBOARD_LL
        if not hook:
            log.warning("Key counter unavailable (daily report will show active time only)")
            return
        msg = wt.MSG()
        while user32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
            user32.TranslateMessage(ctypes.byref(msg))
            user32.DispatchMessageW(ctypes.byref(msg))


# ---- music detector -------------------------------------------------------------------
class MusicMeter:
    """How loud the PC is playing sound right now (0..1). Create and use on one thread."""

    def __init__(self):
        self._meter = None
        self._next_try = 0.0

    def level(self) -> float:
        if self._meter is None:
            if time.time() < self._next_try:
                return 0.0
            self._next_try = time.time() + 10
            try:
                import comtypes
                from comtypes import CLSCTX_ALL
                from pycaw.pycaw import AudioUtilities, IAudioMeterInformation
                comtypes.CoInitialize()
                dev = AudioUtilities.GetSpeakers()
                raw = getattr(dev, "_dev", dev)
                iface = raw.Activate(IAudioMeterInformation._iid_, CLSCTX_ALL, None)
                self._meter = ctypes.cast(iface, ctypes.POINTER(IAudioMeterInformation))
            except Exception as exc:
                log.debug("music meter unavailable: %s", exc)
                return 0.0
        try:
            return float(self._meter.GetPeakValue())
        except Exception:
            self._meter = None  # speakers changed (headphones plugged in...): reconnect
            return 0.0


def pick_question(life: Life, rnd: random.Random = random) -> dict:
    """A question to ask: sometimes a 'still studying?' remark, else a button question or a fun one."""
    act, at = life.d.get("activity", ""), life.d.get("activity_at", 0.0)
    if act in STILL and time.time() - at < 3 * 3600 and rnd.random() < 0.35:
        return {"q": STILL[act]}
    if rnd.random() < 0.6:
        return dict(rnd.choice(QA))
    return {"q": rnd.choice(QUESTIONS)}
