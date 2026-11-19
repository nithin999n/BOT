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
OUTFITS = ["auto", "none", "bow", "sunglasses", "party", "crown", "santa", "headband", "cap", "flower", "grad", "halo"]
BADGE_OUTFITS = {"flower": "fed_7", "grad": "focus_10", "halo": "love_100"}  # outfits a badge unlocks

# ---- badges (achievements) -------------------------------------------------------------
# (id, emoji + name, how to get it, counter, needed)
BADGES = [
    ("first_cookie", "🍪 First cookie", "Feed BOT a cookie", "cookies", 1),
    ("cookie_50", "🍪 Cookie lover", "Feed BOT 50 cookies", "cookies", 50),
    ("fed_7", "🔥 Fed 7 days in a row", "Feed BOT every day for a week (unlocks 🌸)", "fed_streak", 7),
    ("focus_1", "🍅 First focus", "Finish a focus session", "focus", 1),
    ("focus_10", "🍅 Focus master", "Finish 10 focus sessions (unlocks 🎓)", "focus", 10),
    ("love_10", "💖 Sweetheart", "Tell BOT you love it 10 times", "love_yes", 10),
    ("love_100", "💞 True love", "Tell BOT you love it 100 times (unlocks 😇)", "love_yes", 100),
    ("hug_10", "🤗 Hugger", "Hug BOT 10 times", "hugs", 10),
    ("fetch_20", "⚽ Good boy!", "Play fetch 20 times", "fetches", 20),
    ("seek_5", "🙈 Seeker", "Find BOT in hide-and-seek 5 times", "found", 5),
    ("ttt_win", "❌ Tic-tac-toe champ", "Beat BOT at tic-tac-toe", "ttt_wins", 1),
    ("rps_10", "✊ Rock star", "Win rock-paper-scissors 10 times", "rps_wins", 10),
    ("catch_20", "🧺 Cookie catcher", "Catch 20 cookies in one game", "catch_best", 20),
    ("bubbles_50", "🫧 Bubble popper", "Pop 50 bubbles", "bubbles", 50),
    ("chase_10", "🏃 Speedy", "Catch BOT 10 times in chase", "catches", 10),
    ("wpm_80", "⌨️ Typing star", "Type 80 words per minute", "wpm_best", 80),
    ("night_owl", "🦉 Night owl", "Keep BOT company after 1 AM", "night_owl", 1),
    ("sorry_1", "🫶 Forgiven", "Say sorry to BOT", "sorry", 1),
    ("level_5", "⭐ Level 5", "Reach level 5", "level", 5),
    ("level_10", "🌟 Level 10", "Reach level 10", "level", 10),
    ("photo_1", "📸 Say cheese!", "Take a photo with BOT", "photos", 1),
    ("moments_5", "🫙 Happy jar", "Save 5 happy moments", "moments", 5),
]
MOODS = {"great": "😊", "okay": "😐", "sad": "😢", "tired": "😴", "angry": "😡"}

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
            "report_day": "", "outfit": "auto", "stats": {}, "counts": {}, "badges": [], "fed_days": [],
            "moods": {}, "diary": {}, "moments": [], "reminders": [], "birthday": "",
            "options": {"cursor_prank": False, "clap": True, "intruder_photo": True}}


class Life:
    """Stats that survive restarts (saved through save_fn into config.json)."""

    def __init__(self, data: dict | None, save_fn):
        self.d = {**default_life(), **(data or {})}
        self.d["options"] = {**default_life()["options"], **self.d.get("options", {})}
        self.save_fn = save_fn
        self._dirty = False
        self._last_save = time.time()
        self.last_interaction = time.time()

    @property
    def level(self) -> int:
        return min(99, 1 + int(self.d["xp"] // 100))

    def unlocked(self, outfit: str) -> bool:
        if outfit in BADGE_OUTFITS:
            return BADGE_OUTFITS[outfit] in self.d["badges"]
        return self.level >= OUTFIT_UNLOCK.get(outfit, 1)

    # -- counters, badges, streaks --------------------------------------------------------
    def count(self, key: str, n: float = 1, best: bool = False) -> list:
        """Add to a counter (or keep the best value). Returns newly earned badges [(id, name)]."""
        counts = self.d["counts"]
        if best:
            counts[key] = max(counts.get(key, 0), n)
        else:
            counts[key] = counts.get(key, 0) + n
            day = self.today()
            day[key] = day.get(key, 0) + n
        self._dirty = True
        return self.check_badges()

    def fed_today(self) -> list:
        today = date.today().isoformat()
        days = self.d["fed_days"]
        if today not in days:
            days.append(today)
            del days[:-60]
        streak, d = 0, date.today()
        while d.isoformat() in days:
            streak += 1
            d = date.fromordinal(d.toordinal() - 1)
        return self.count("fed_streak", streak, best=True)

    def check_badges(self) -> list:
        counts = dict(self.d["counts"], level=self.level, moments=len(self.d["moments"]))
        new = []
        for bid, name, _how, key, need in BADGES:
            if bid not in self.d["badges"] and counts.get(key, 0) >= need:
                self.d["badges"].append(bid)
                new.append((bid, name))
                self._dirty = True
        return new

    # -- mood journal, diary, moments --------------------------------------------------------
    def set_mood(self, mood: str) -> None:
        if mood in MOODS:
            moods = self.d["moods"]
            moods[date.today().isoformat()] = mood
            for old in sorted(moods)[:-60]:
                moods.pop(old, None)
            self._dirty = True

    def diary_text(self, day: str) -> str:
        t = self.d["stats"].get(day, {})

        def times(n, word="time"):
            n = int(n)
            return f"{n} {word}{'s' if n != 1 else ''}"

        bits = []
        if t.get("cookies"):
            bits.append(f"my human fed me {times(t['cookies'], 'cookie')} 🍪")
        if t.get("keys", 0) > 50:
            bits.append(f"they typed {int(t['keys']):,} keys ⌨️")
        if t.get("love_yes"):
            bits.append(f"they said they love me {times(t['love_yes'])} 💖")
        if t.get("hugs"):
            bits.append(f"they hugged me {times(t['hugs'])} 🤗")
        games = sum(int(t.get(k, 0)) for k in ("fetches", "found", "ttt_games", "rps_games", "catch_games",
                                                "bubble_games", "catches"))
        if games:
            bits.append("we played games together 🎮")
        if t.get("focus"):
            bits.append(f"they focused for {times(t['focus'], 'session')} 🍅")
        if t.get("sorry"):
            bits.append("they said sorry after throwing me 🥺 (I forgave them 💕)")
        mins = int(t.get("active_min", 0))
        if mins >= 60:
            bits.append(f"they worked for {mins // 60}h {mins % 60}m 💪")
        feel = {"great": " They felt great today 😊", "okay": " They felt okay today 😐",
                "sad": " They felt sad today… I stayed close 🫂", "tired": " They were tired today 😴",
                "angry": " They were upset today… I hope tomorrow is better 💙"}.get(self.d["moods"].get(day), "")
        if not bits:
            return "Dear diary, today was quiet… I waited for my human 🥺💙" + feel
        body = (", ".join(bits[:-1]) + " and " + bits[-1]) if len(bits) > 1 else bits[0]
        return f"Dear diary, today {body}.{feel} I love my human! 💙"

    def write_diary(self) -> None:
        """Keep a diary entry for every finished day."""
        today = date.today().isoformat()
        for day in sorted(self.d["stats"]):
            if day < today and day not in self.d["diary"]:
                self.d["diary"][day] = self.diary_text(day)
                self._dirty = True
        for old in sorted(self.d["diary"])[:-30]:
            self.d["diary"].pop(old, None)

    def add_moment(self, text: str) -> list:
        text = text.strip()[:300]
        if text:
            self.d["moments"].append({"id": f"{time.time():.0f}{random.randint(100, 999)}", "text": text,
                                      "date": date.today().isoformat()})
            del self.d["moments"][:-200]
            self._dirty = True
        return self.check_badges()

    def del_moment(self, mid: str) -> None:
        self.d["moments"] = [m for m in self.d["moments"] if m["id"] != mid]
        self._dirty = True

    def world(self) -> dict:
        """Everything the phone's "BOT's world" page shows."""
        today = date.today()
        week = []
        for i in range(6, -1, -1):
            day = date.fromordinal(today.toordinal() - i).isoformat()
            week.append({"day": day, "mood": self.d["moods"].get(day, "")})
        diary = [{"day": today.isoformat(), "text": self.diary_text(today.isoformat()) + " (so far)"}]
        diary += [{"day": d, "text": self.d["diary"][d]} for d in sorted(self.d["diary"], reverse=True)[:14]]
        counts = dict(self.d["counts"], level=self.level, moments=len(self.d["moments"]))
        return {"love": int(self.d["counts"].get("love_yes", 0)), "hugs": int(self.d["counts"].get("hugs", 0)),
                "badges": [{"id": b, "name": n, "how": h, "got": b in self.d["badges"],
                            "progress": min(int(counts.get(k, 0)), need), "need": need}
                           for b, n, h, k, need in BADGES],
                "week": week, "diary": diary, "moments": list(reversed(self.d["moments"]))[:100],
                "reminders": sorted(self.d["reminders"], key=lambda r: r["at"]),
                "birthday": self.d.get("birthday", ""), "options": dict(self.d["options"]),
                "catch_best": int(self.d["counts"].get("catch_best", 0)), "level": self.level}

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
            for old in sorted(stats)[:-14]:  # keep two weeks
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
