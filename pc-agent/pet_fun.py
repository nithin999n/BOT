"""
The desktop BOT's fun side: games, love, hugs, comfort, reminders, weather, festivals, music, perching on
windows, baby BOT and more. Lives on the desktop BOT's own thread (created by Pet once its window exists).

Pet calls:   frame() every frame -> mood/props overrides,   chatter() when BOT may say something,
             click() / answer() for clicks and answer buttons,   drive() for special movement.
"""
from __future__ import annotations

import logging
import math
import random
import threading
import time
from datetime import date, datetime
from pathlib import Path

import pet_sprites as sp
from pet_more import More
import pet_world as world
import win_input
from overlay import user32

log = logging.getLogger("bot")

LOVE_CHAIN = ["Do you love me? 🥺", "Really? 🥹", "Do you really really love me? 🥺💕", "More than cookies? 🍪🥺",
              "Promise? 🤙🥺", "Say it one more time… 🥺", "Will you love me forever? 💞", "Even when I'm grumpy? 😤🥺",
              "Even when I'm sleepy? 😴💙", "Do you love me the most? 🥹", "Pinky promise? 🤙💖", "Do you love me? 🥺💗",
              "Will you never leave me? 🥺", "Am I your favourite? 🥹✨"]
LOVE_OPTS = (("Yes 💖", "love:yes"), ("Sooo much 💕", "love:alot"), ("Hmm… 🤔", "love:hmm"))
LOVE_END = ["Okay… I believe you 💕 I love you too!! 💖💖", "Hehe, I love you sooo much too!! 🥰💞",
            "Yay!! Forever and ever! 💖 I love you too!"]
LOVE_HMM = ["You don't love me?? 🥺💧", "Hmm?! 😭 Say yes pleeease 🥺", "*sniff* 🥺💧 ask again…"]
HUG = ["I'm here for you 💙", "Hug! 🤗 Everything will be okay 💙", "Squeeeze! 🤗💕", "I'll always be here 💙🫂"]
HUG_END = ["Thank you… 💙", "That was a good hug 🥰", "I feel so loved 💕"]
SWEET = ["I'm proud of you 💙", "You're doing better than you think 💙", "You're amazing, you know that? ✨",
         "I'm lucky to have you 🥰", "You make my day brighter ☀️", "One step at a time, you've got this 💪💙",
         "You deserve good things 💖", "Don't forget to smile today 😊", "You're my favourite human 🥹💙",
         "It's okay to rest sometimes 🌙", "You matter so much 💙"]
NIGHT_COMPANY = ["Can't sleep? I'm right here with you 🌙", "It's quiet at night… I'm here 💙", "I'll stay up with you 🌙🫂",
                 "Late nights are okay. You're not alone 💙", "Want to talk? I'm listening 🌙"]
COMFORT = ["I'm right here with you 🫂💙", "It's okay to feel sad. I'm with you 💙", "You're not alone 🫂",
           "Sending you the biggest hug 🤗💙", "Tomorrow can be better 🌈", "Breathe in… breathe out… 💙"]
FEEL_OPTS = (("😊 Great", "feel:great"), ("😐 Okay", "feel:okay"), ("😢 Sad", "feel:sad"), ("😴 Tired", "feel:tired"),
             ("😡 Upset", "feel:angry"))
FEEL_REPLY = {"great": "Yay!! That makes me so happy! 😄💙", "okay": "Okay is okay! Let's make it a good day 🌈",
              "sad": "Aww… come here 🫂 I'll stay close to you today 💙", "tired": "Take it easy today ☕ Rest when you can 💙",
              "angry": "Deep breath… 💙 I'm on your side, always 🫂"}
RPS = {"rock": "✊", "paper": "✋", "scissors": "✌️"}
APP_LINES = {"movie": ["Movie time! 🍿 Can I watch too?", "Ooh, what are we watching? 🍿👀"],
             "code": ["Coding time! 🤓 You're so smart", "Beep boop, coding buddy reporting! 🤓"],
             "game": ["Go go go! 🎮🔥", "You can win this! 🎮💪", "Woah, nice move! 🎮✨"],
             "chat": ["Ooh, who are you chatting with? 👀💬", "Say hi from me! 👋💬"]}
EYE_SECONDS = 20


class Fun:
    def __init__(self, pet):
        self.pet = pet
        self.life = pet.life
        now = time.perf_counter()
        self.weather = world.Weather()
        self.media = world.Media()
        self.clap = world.ClapListener(lambda: pet._q.put(("fun", "on_clap")))
        # timers
        self.next_love = now + random.uniform(45, 90) * 60
        self.next_sweet = now + random.uniform(30, 60) * 60
        self.next_night_line = now + 60
        self.next_moment = now + random.uniform(60, 150) * 60
        self.next_app = 0.0
        self.next_fg = 0.0
        self.next_perch = now + random.uniform(120, 300)
        self.next_prank = now + random.uniform(25, 45) * 60
        self.next_media = 0.0
        self.next_wpm = 0.0
        self.next_check = 0.0
        self.next_eye_min = 20.0
        self.work_min = 0.0          # minutes of non-stop work (resets after 5 idle minutes)
        self.active_min = 0.0
        self.snooze_break = 0.0
        self.app_said: dict = {}
        self.app_kind = ""
        self.fg: dict = {}
        self.key_samples: list = []
        self.wpm = 0
        self.wpm_said = 0.0
        self.media_key = None
        self.rain_warned = ""
        self.fest_greeted = ""
        self.mood_asked = ""
        self.birthday_asked = 0.0
        self.tidy_asked = 0.0
        self.night_asked = ""
        self.moments_today = (date.today().isoformat(), 0)
        # states
        self.love: dict | None = None      # the "do you love me?" chain
        self.hugging = False
        self.hug_said = 0.0
        self.comfort_until = 0.0
        self.game: dict | None = None      # the game being played
        self.hiding = False                # hide-and-seek: BOT is hiding (maybe behind a window)
        self.pinned = False                # BOT is held in place by something here
        self.gone = False                  # BOT is away (on the phone)
        self.perch: dict | None = None     # sitting on a window: {hwnd, rect}
        self.reminder: dict | None = None  # reminder being shown
        self.eye: float = 0.0              # eye-break countdown end
        self.plead = False                 # "take a break" in the middle of the screen
        self.prank: dict | None = None
        self.night_wait = 0.0              # good-night question showing until
        self.props_extra: list = []        # [(kind, until)]
        self.photo_t0 = 0.0
        self.baby: sp.Sprite | None = None
        self.egg: sp.Sprite | None = None
        self.egg_t0 = 0.0
        self.baby_frames: dict = {}
        self.baby_x = 0.0
        self.baby_hop = 0.0
        self.toys: list[sp.Sprite] = []
        self.started = False
        self.more: More | None = None
        self._fx_check = 0.0

    # ------------------------------------------------------------------ helpers
    def say(self, st, text, secs=4.0, opts=()):
        self.pet._speak(st, text, secs, opts)

    def react(self, st, mood, secs=2.0):
        st["react"], st["react_until"] = mood, time.perf_counter() + secs

    def invisible(self) -> bool:
        return self.gone is True or bool(self.game and self.game.get("phase") == "vanish") \
            or bool(self.more and self.more.inside)

    def more_cmd(self, st, action, value=None):
        if not self.more:
            return
        if action == "house_click":
            self.more.click_house(st)
        else:
            self.more.cmd(st, action, value)

    def sound(self, name):
        if self.more:
            self.more.sound(name)

    def coins(self, st, n):
        if self.more:
            self.more.coins(st, n)

    def badges(self, st, new):
        for _bid, name in new:
            self.coins(st, 20)
            self.say(st, f"New badge! 🏅 {name}", 5)
            self.pet._burst(st, "sparkle", 10)
            self.pet._notify("New badge! 🏅", name)

    def count(self, st, key, n=1, best=False):
        self.badges(st, self.life.count(key, n, best))

    def walk_to(self, x, speed=260.0):
        p = self.pet
        left, right, _t, _f = p._limits()
        x = max(left, min(right, x))
        if abs(x - p.x) < 4:
            return
        p._walk_to, p._walk_dir, p._walk_t0 = x, (1 if x > p.x else -1), time.perf_counter()
        p._walk_speed = speed
        p.walking = True

    def busy_now(self) -> bool:
        p = self.pet
        return bool(self.game or self.love or self.hiding or self.gone or self.plead or self.prank or self.reminder
                    or p.sulking or p.leaving or p.away_until or p.dragging)

    def toy(self, interactive=False) -> sp.Sprite:
        for s in self.toys:
            if not s.visible and s.interactive == interactive and not s.data.get("busy"):
                s.data = {}
                return s
        s = sp.Sprite(interactive)
        self.toys.append(s)
        return s

    def hide_toys(self):
        for s in self.toys:
            s.hide()
            s.data = {}

    def start(self):
        if self.started:
            return
        self.started = True
        self.more = More(self)
        self.weather.start()
        self.media.start()
        self.clap.set_enabled(bool(self.life.d["options"].get("clap", True)))

    # ------------------------------------------------------------------ public commands (via Pet queue)
    def start_love(self, st, n=None):
        self.love = {"left": n or random.randint(5, 10), "i": 0, "repeat": 0, "cry_until": 0.0}
        self._ask_love(st)

    def _ask_love(self, st):
        lv = self.love
        q = LOVE_CHAIN[0] if lv["i"] == 0 else random.choice(LOVE_CHAIN[1:])
        lv["i"] += 1
        lv["asked"] = time.perf_counter()
        self.say(st, q, 12, LOVE_OPTS)
        self.react(st, "puppy" if lv["i"] > 1 else "love", 1.5)

    def game_start(self, st, name):
        if self.pet.sulking or self.pet.leaving or self.pet.away_until:
            self.say(st, "Hmph! Say sorry first 😤", 4)
            return
        self.end_game(st, quiet=True)
        self.love = None
        if self.more:
            self.more.come_out(st, quiet=True)
        p = self.pet
        p.chase_until, p.peek_side = 0.0, 0
        now = time.perf_counter()
        if name == "fetch":
            ball = self.toy(True)
            img = sp.ball_image(int(p.S * 0.32))
            ball.show(img, p._center[0] + p.BW * 0.7, p.bounds[3] - img.height)
            ball.vx = ball.vy = 0.0
            ball.data = {"busy": True}
            self.game = {"name": "fetch", "ball": ball, "phase": "wait", "last": now, "throws": 0}
            self.say(st, "Throw the ball! ⚽ I'll bring it back! 🐶", 5)
            self.react(st, "excited", 2)
        elif name == "catch":
            self.game = {"name": "catch", "end": now + 30, "next": now + 1.5, "score": 0, "missed": 0, "cookies": []}
            self.say(st, "Cookie rain! 🍪 Move your mouse and I'll follow. Catch them all!", 4)
            self.react(st, "excited", 2)
        elif name == "bubbles":
            self.game = {"name": "bubbles", "left": 10, "next": now + 1.0, "popped": 0, "bubbles": []}
            self.say(st, "Bubble time! 🫧 Pop them all!", 3)
        elif name == "hide":
            self.game = {"name": "hide", "phase": "count", "t": now + 3.2}
            self.say(st, "Hide and seek! 🙈 Close your eyes… 1… 2… 3…", 3.2)
            self.react(st, "excited", 3)
        elif name == "rps":
            self.game = {"name": "rps", "you": 0, "me": 0}
            self._rps_ask(st, "Rock, paper, scissors! Pick one 👇")
        elif name == "ttt":
            self.game = {"name": "ttt", "board": [""] * 9}
            self._ttt_show(st, "Tic-tac-toe! You're ❌, I'm ⭕. Your turn 👇")
        elif name == "photo":
            self.game = {"name": "photo", "t": now, "step": 3}
            self.say(st, "Photo time! 📸 Look at your webcam… 3", 1.2)
            self.react(st, "excited", 3)

    def end_game(self, st, quiet=False):
        g = self.game
        if not g:
            return
        self.game = None
        name = g["name"]
        if name == "fetch":
            g["ball"].data = {}
            g["ball"].hide()
            if not quiet:
                self.say(st, "That was so fun! 🐶💙", 4)
        for s in g.get("cookies", []) + g.get("bubbles", []):
            s.data = {}
            s.hide()
        if name == "hide":
            self.hiding = self.pinned = False
            self.pet.flying = True
        self.pet._walk_speed = 110

    def on_clap(self, st):
        p = self.pet
        if self.more and self.more.inside:
            self.more.come_out(st)
            return
        if not p.wanted or self.gone or self.busy_now():
            return
        cx = (p.bounds[0] + p.bounds[2]) / 2 - p.W / 2
        self.perch = None
        p.vy = -900.0
        p.vx = max(-1500.0, min(1500.0, (cx - p.x) * 1.4))
        p.flying = True
        self.say(st, random.choice(["You called? 🥰", "Here I am! 👏😆", "Clap clap! I'm here! 🥰"]), 3)
        self.react(st, "excited", 2.5)

    def reminder_add(self, st, at, text):
        rid = f"{time.time():.0f}{random.randint(100, 999)}"
        self.life.d["reminders"].append({"id": rid, "at": float(at), "text": str(text)[:200]})
        self.life._dirty = True
        self.life.save(force=True)

    def reminder_del(self, st, rid):
        self.life.d["reminders"] = [r for r in self.life.d["reminders"] if r["id"] != rid]
        self.life._dirty = True
        self.life.save(force=True)

    def moment_add(self, st, text):
        self.badges(st, self.life.add_moment(text))
        self.life.save(force=True)
        self.say(st, "Saved in our happy jar 🫙💛", 3)

    def moment_del(self, st, mid):
        self.life.del_moment(mid)
        self.life.save(force=True)

    def set_option(self, st, key, value):
        if key in ("cursor_prank", "clap", "intruder_photo", "sounds"):
            self.life.d["options"][key] = bool(value)
            self.life._dirty = True
            self.life.save(force=True)
            if key == "clap":
                self.clap.set_enabled(bool(value))

    def set_birthday(self, st, mmdd):
        self.life.d["birthday"] = mmdd
        self.life._dirty = True
        self.life.save(force=True)
        try:
            pretty = datetime.strptime("2000-" + mmdd, "%Y-%m-%d").strftime("%d %B").lstrip("0")
        except ValueError:
            pretty = mmdd
        self.say(st, f"Yay! I'll remember: {pretty} 🎂 I'll be ready to celebrate!", 5)
        self.react(st, "excited", 2)

    def set_feel(self, st, feel):
        self._answer_feel(st, feel)

    def phone_note(self, st, kind, title, text):
        title = str(title)[:40]
        if kind == "call":
            line = f"📞 {title} is calling!"
        else:
            line = f"💬 {title}: {str(text)[:60]}" if text else f"💬 {title}"
        self.props_extra = [("phone", time.perf_counter() + 9)]
        self.say(st, line, 9)
        self.react(st, "surprised", 1.2)

    def travel(self, st, where):
        p = self.pet
        if where == "phone" and not self.gone:
            if self.busy_now() or not p.wanted:
                return
            if self.more:
                self.more.come_out(st, quiet=True)
            self.perch = None
            left, right, _t, _f = p._limits()
            self.gone = "leaving"
            self.say(st, "Bye bye! 👋 I'll follow you to your phone 📱", 3)
            self.react(st, "happy", 2)
            target = right + p.W * 1.2 if p.x > (left + right) / 2 else left - p.W * 1.2
            p._walk_to, p._walk_dir, p._walk_t0 = target, (1 if target > p.x else -1), time.perf_counter()
            p._walk_speed, p.walking, p.flying = 320.0, True, False
        elif where == "pc" and self.gone:
            self.gone = False
            left, right, _t, floor = p._limits()
            side = random.choice((-1, 1))
            p.x, p.y = (left - p.W * 0.6) if side < 0 else (right + p.W * 0.6), floor
            self.walk_to(random.uniform(left + p.W * 0.3, right - p.W * 0.3), 300)
            self.say(st, "I'm back! 🏃💨 Did you miss me? 🥰", 4)
            self.react(st, "excited", 3)
            self.out({"type": "pet_travel", "where": "pc"})

    def tidy_now(self, st):
        files = world.loose_files()
        if not files:
            self.say(st, "Your desktop is already clean! ✨", 4)
            return
        self.say(st, f"Tidying {len(files)} files… 🧹", 3)

        def work():
            moves = world.tidy()
            self.pet._q.put(("fun", "tidy_done", moves))

        threading.Thread(target=work, daemon=True).start()

    def tidy_done(self, st, moves):
        self.life.d["tidy_log"] = moves
        self.life._dirty = True
        self.life.save(force=True)
        self.say(st, f"Done! 🧹✨ I put {len(moves)} files in Desktop › {world.TIDY_FOLDER}. "
                     "Nothing was deleted 💙", 7)
        self.react(st, "happy", 2)
        self._sparkle_burst(st)

    def untidy(self, st):
        moves = self.life.d.get("tidy_log") or []
        back = world.untidy(moves)
        self.life.d["tidy_log"] = []
        self.life._dirty = True
        self.say(st, f"Put {back} files back on your desktop ↩️", 4)

    def photo_done(self, st, ok, path):
        if ok:
            self.count(st, "photos")
            self.coins(st, 2)
            self.say(st, "Cheese! 📸 Sent to your phone 💙", 5)
            self.react(st, "love", 2)
            if self.pet.send_file_fn:
                self.pet.send_file_fn(path)
        else:
            self.say(st, "I can't find a camera 🥺📷", 4)

    def media_cmd(self, st, action):
        self.media.control(action)

    def heard_love(self, st):
        """You said "I love you" to BOT."""
        self.count(st, "love_yes")
        self.life.cheer(happy=5)
        self.say(st, random.choice(["I love you too!! 💖🥰", "Awww! I love you sooo much more! 💕💕",
                                    "My heart!! 🥹💖 I love you too!"]), 5)
        self.react(st, "love", 4)
        self.pet._burst(st, "heart", 12)

    def phone_hug(self, st):
        """A hug sent from the phone."""
        self.count(st, "hugs")
        self.say(st, "A hug from your phone! 🤗💙", 4)
        self.react(st, "hug", 3)
        self.pet._burst(st, "heart", 8)

    # ------------------------------------------------------------------ clicks & answers
    def click(self, st) -> bool:
        """A click on BOT. True = handled here."""
        g = self.game
        if g and g["name"] == "hide" and g["phase"] == "hidden":
            found_in = time.perf_counter() - g["t0"]
            self.end_game(st, quiet=True)
            self.count(st, "found")
            self.coins(st, 5)
            self.say(st, f"You found me! 🙈 ({found_in:.0f} s)", 4)
            self.react(st, "excited", 2.5)
            self.pet._burst(st, "heart", 6)
            return True
        if self.prank:
            return True
        if self.plead:
            self.say(st, "Pleeease take a little break? 🥺☕", 30, (("Okay, break time ☕", "brk:yes"),
                                                                    ("5 more minutes 🙏", "brk:snooze")))
            return True
        if self.love:  # clicking while it asks: ask again
            self._ask_love(st)
            return True
        return False

    def answer(self, st, key, val) -> bool:
        now = time.perf_counter()
        p = self.pet
        if self.more and self.more.answer(st, key, val):
            return True
        if key == "love":
            if not self.love:
                return False
            lv = self.love
            if val == "hmm":
                lv["left"] += 2
                lv["cry_until"] = now + 2.6
                self.sound("sad")
                self.say(st, random.choice(LOVE_HMM), 2.6)
                return True
            self.count(st, "love_yes")
            self.life.cheer(happy=2)
            p._burst(st, "heart", 3)
            self.sound("happy")
            lv["left"] -= 1
            if lv["left"] <= 0:
                self.love = None
                self.say(st, random.choice(LOVE_END), 5)
                self.react(st, "love", 4)
                p._burst(st, "heart", 14)
                self.coins(st, 3)
                if self.life.add_xp(3):
                    p._level_up(st)
            else:
                lv["repeat"] = 0
                self._ask_love(st)
            return True
        if key == "feel":
            self._answer_feel(st, val)
            return True
        if key == "rps" and self.game and self.game["name"] == "rps":
            self._rps_play(st, val)
            return True
        if key == "ttt" and self.game and self.game["name"] == "ttt":
            self._ttt_play(st, val)
            return True
        if key == "media":
            self.media.control(val)
            self.say(st, {"prev": "⏮", "next": "⏭ Next song!", "toggle": "⏯"}.get(val, "🎵"), 1.5)
            return True
        if key == "rem" and self.reminder:
            r = self.reminder
            self.reminder = None
            p._walk_speed = 110
            if val == "snooze":
                self.reminder_add(st, time.time() + 600, r["text"])
                self.say(st, "Okay! I'll remind you again in 10 minutes ⏰", 3)
            else:
                self.say(st, "Yay, done! ✅ Good job 💙", 3)
                self.react(st, "happy", 2)
            return True
        if key == "brk":
            self.plead = False
            self.pinned = False
            p.flying = True
            if val == "yes":
                self.work_min = 0.0
                self.say(st, "Yay!! ☕ Stretch, drink water, rest your eyes. See you soon 💙", 6)
                self.react(st, "love", 3)
            else:
                self.snooze_break = time.perf_counter() + 5 * 60
                self.say(st, "Okay… only 5 more minutes! 🥺⏰", 4)
            return True
        if key == "tidy":
            if val == "yes":
                self.tidy_now(st)
            else:
                self.say(st, "Okay! Maybe later 🧹", 3)
            return True
        if key == "night":
            self.night_wait = 0.0
            if val == "sleep":
                self.say(st, "Good night! 🌙💤 Sweet dreams", 3)
                threading.Timer(3.0, world.sleep_pc).start()
            else:
                self.say(st, "Okay! Don't stay up too late 💙🌙", 4)
            return True
        return False

    def _answer_feel(self, st, feel):
        self.life.set_mood(feel)
        self.life.save(force=True)
        self.say(st, FEEL_REPLY.get(feel, "Thank you for telling me 💙"), 6)
        if feel in ("sad", "angry"):
            self.comfort_until = time.perf_counter() + 40 * 60
            self.react(st, "love", 4)
            self.pet._burst(st, "heart", 8)
            self.comfort_water = time.perf_counter() + 150
        elif feel == "great":
            self.react(st, "excited", 3)
            self._sparkle_burst(st)
        else:
            self.react(st, "love", 2)

    def _sparkle_burst(self, st):
        self.pet._burst(st, "sparkle", 8)
        for _ in range(10):
            st["particles"].append(["confetti", random.uniform(-0.45, 0.45), random.uniform(-0.4, -0.2),
                                    random.uniform(-0.05, 0.05), random.uniform(0.05, 0.2), random.uniform(1.2, 2.0)])

    # ------------------------------------------------------------------ games: rps / ttt
    def _rps_ask(self, st, text):
        self.say(st, text, 30, tuple((f"{RPS[k]} {k.title()}", f"rps:{k}") for k in RPS) + (("Stop ✋", "rps:stop"),))

    def _rps_play(self, st, choice):
        g = self.game
        if choice in ("stop", "again"):
            if choice == "stop":
                self.game = None
                self.say(st, f"Good game! 🎮 You {g['you']} – me {g['me']}", 4)
            else:
                self._rps_ask(st, "Again! Pick one 👇")
            return
        mine = random.choice(list(RPS))
        self.count(st, "rps_games")
        wins = {"rock": "scissors", "paper": "rock", "scissors": "paper"}
        if mine == choice:
            res = "Draw! 😮"
        elif wins[choice] == mine:
            g["you"] += 1
            self.count(st, "rps_wins")
            self.coins(st, 1)
            res = "You win! 🎉"
            self.react(st, "sad", 1.5)
        else:
            g["me"] += 1
            res = "I win! 😆"
            self.react(st, "excited", 1.5)
        self.say(st, f"{RPS[choice]} vs {RPS[mine]}  {res}  ({g['you']}–{g['me']})", 30,
                 tuple((f"{RPS[k]}", f"rps:{k}") for k in RPS) + (("Stop ✋", "rps:stop"),))

    def _ttt_show(self, st, text):
        b = self.game["board"]
        opts = []
        for i, c in enumerate(b):
            opts.append(({"x": "❌", "o": "⭕"}.get(c, "⬜"), f"ttt:{i}"))
            if i % 3 == 2 and i < 8:
                opts.append(("", "|"))
        self.say(st, text, 60, tuple(opts))

    @staticmethod
    def _ttt_winner(b):
        for a, c, e in ((0, 1, 2), (3, 4, 5), (6, 7, 8), (0, 3, 6), (1, 4, 7), (2, 5, 8), (0, 4, 8), (2, 4, 6)):
            if b[a] and b[a] == b[c] == b[e]:
                return b[a]
        return "draw" if all(b) else ""

    def _ttt_play(self, st, val):
        g = self.game
        b = g["board"]
        if val in ("again", "stop"):
            if val == "again":
                g["board"] = [""] * 9
                self._ttt_show(st, "New game! Your turn ❌ 👇")
            else:
                self.game = None
                self.say(st, "Good game! ❌⭕ 💙", 3)
            return
        try:
            i = int(val)
        except ValueError:
            return
        if b[i]:
            return
        b[i] = "x"
        w = self._ttt_winner(b)
        if not w:
            b[self._ttt_move(b)] = "o"
            w = self._ttt_winner(b)
        if w:
            self.count(st, "ttt_games")
            if w == "x":
                self.count(st, "ttt_wins")
                self.coins(st, 5)
                text, mood = "You win!! 🎉 You're so smart!", "surprised"
            elif w == "o":
                text, mood = "I win! 😆⭕", "excited"
            else:
                text, mood = "It's a draw! 🤝", "happy"
            self.react(st, mood, 2)
            opts = []
            for k, c in enumerate(b):
                opts.append(({"x": "❌", "o": "⭕"}.get(c, "⬜"), "ttt:done"))
                if k % 3 == 2 and k < 8:
                    opts.append(("", "|"))
            opts += [("", "|"), ("Again 🔁", "ttt:again"), ("Stop", "ttt:stop")]
            self.say(st, text, 30, tuple(opts))
        else:
            self._ttt_show(st, "Your turn ❌ 👇")

    def _ttt_move(self, b):
        lines = ((0, 1, 2), (3, 4, 5), (6, 7, 8), (0, 3, 6), (1, 4, 7), (2, 5, 8), (0, 4, 8), (2, 4, 6))
        for who in ("o", "x"):  # win, else block
            for ln in lines:
                vals = [b[k] for k in ln]
                if vals.count(who) == 2 and vals.count("") == 1:
                    return ln[vals.index("")]
        if random.random() < 0.2:  # BOT isn't perfect 😄
            return random.choice([k for k in range(9) if not b[k]])
        for k in (4, 0, 2, 6, 8, 1, 3, 5, 7):
            if not b[k]:
                return k
        return 0

    # ------------------------------------------------------------------ hug
    def update_hug(self, st, now):
        p = self.pet
        if p.dragging and p._moved < 6 and now - p._grab_t > 1.0 and not self.hugging:
            self.hugging = True
            self.count(st, "hugs")
            self.life.cheer(happy=6)
            self.coins(st, 1)
            self.sound("chirp")
            self.say(st, random.choice(HUG), 30)
            p._burst(st, "heart", 6)
            self.out({"type": "pet_event", "event": "hug"})
        if self.hugging and random.random() < 0.04:
            p._burst(st, "heart", 1)

    def end_hug(self, st):
        self.hugging = False
        self.say(st, random.choice(HUG_END), 3)
        self.react(st, "love", 2.5)

    # ------------------------------------------------------------------ every frame
    def frame(self, st, now, t, ctx) -> dict:
        p = self.pet
        fx = {"mood": None, "force": None, "quiet": False, "props": [], "under": [], "outfit": None, "look": None,
              "breathe": None}
        self.update_hug(st, now)
        if self.hugging:
            fx["force"] = "hug"
            fx["breathe"] = -0.06 + math.sin(t * 6) * 0.01
            fx["quiet"] = True
        self._every_second(st, now, ctx)

        # love chain
        lv = self.love
        if lv:
            fx["quiet"] = True
            if now < lv.get("cry_until", 0):
                fx["mood"] = "cry"
            elif lv.get("cry_until"):
                lv["cry_until"] = 0.0
                self._ask_love(st)
            elif now - lv.get("asked", now) > 12.5 and not st["speech"]:
                if lv["repeat"] == 0:
                    lv["repeat"] = 1
                    lv["asked"] = now
                    self.say(st, "Hello? 🥺 Do you love me?", 12, LOVE_OPTS)
                else:
                    self.love = None
                    self.say(st, "…okay 🥺", 3)
                    self.react(st, "sad", 3)
            else:
                fx["mood"] = "puppy" if lv["i"] > 1 else None

        # games
        if self.game:
            fx["quiet"] = True
            self._game_frame(st, now, t, fx)

        # reminders
        self._reminders(st, now, fx)
        if self.reminder:
            fx["quiet"] = True
            fx["props"].append(("note",))
            if now > self.reminder["until"]:
                self.reminder = None
                p._walk_speed = 110

        # eye break countdown
        if self.eye:
            left = int(self.eye - now) + 1
            if left <= 0:
                self.eye = 0.0
                self.say(st, "Thank you! Your eyes say thanks 💙👀", 3)
                self.react(st, "happy", 2)
            else:
                st["speech"], st["speech_until"], st["options"] = (
                    f"👀 Look at something far away… {left}", now + 1.2, ())
                fx["quiet"] = True
                fx["mood"] = "happy"

        # take-a-break plea
        if self.plead:
            fx["quiet"] = True
            fx["mood"] = "puppy"

        # cursor prank
        if self.prank:
            self._prank_frame(st, now, fx)

        # comfort mode: stay close
        if now < self.comfort_until and not self.busy_now():
            if getattr(self, "comfort_water", 0) and now > self.comfort_water and not st["speech"]:
                self.comfort_water = 0
                self.say(st, "Maybe drink some water and take a short walk? 💧🚶 I'll wait right here 💙", 7)
            self._stay_near_cursor(now)

        # late night company
        hour = ctx["hour"]
        if 1 <= hour < 5 and st["idle"] < 60 and not self.busy_now():
            self._stay_near_cursor(now)
            if not self.life.d["counts"].get("night_owl"):
                self.count(st, "night_owl")

        # good-night blanket
        if self.night_wait and now < self.night_wait:
            fx["props"].append(("blanket",))
            fx["mood"] = fx["mood"] or "asleep"
        elif ctx["mood_guess"] == "asleep" and (hour >= 22 or hour < 6):
            fx["props"].append(("blanket",))

        # hide and seek / travel visibility
        if self.gone == "leaving" and not p.walking:
            self.gone = True
            self.out({"type": "pet_travel", "where": "phone"})
        # perch on windows
        self._perch_frame(st, now, ctx)
        # app reactions: props while you watch / code
        if not fx["quiet"] and not self.hugging:
            if self.app_kind == "movie":
                fx["props"].append(("popcorn",))
            elif self.app_kind == "code":
                fx["props"].append(("glasses",))
            elif self.app_kind == "chat" and self.fg.get("rect"):
                r = self.fg["rect"]
                fx["look"] = ((r[0] + r[2]) / 2, (r[1] + r[3]) / 2)
        # extra props for a while (phone sign)
        self.props_extra = [(k, u) for k, u in self.props_extra if now < u]
        fx["props"] += [(k,) for k, _u in self.props_extra]
        # festival / weather looks
        fest = world.festival(birthday=self.life.d.get("birthday", ""))
        if fest == "birthday":
            fx["outfit"] = "party"
            fx["props"].append(("cake",))
        elif fest in ("christmas",):
            fx["outfit"] = "santa"
        elif fest == "newyear":
            fx["outfit"] = "party"
        elif fest == "diwali":
            fx["props"].append(("diya",))
        elif fest == "holi":
            fx["under"].append(("holi",))
        elif fest == "sankranti":
            fx["props"].append(("kite",))
        elif fest == "ugadi":
            fx["props"].append(("toran",))
        elif fest == "ganesh":
            fx["props"].append(("modak",))
        if fest in ("birthday", "newyear", "diwali") and random.random() < 0.02:
            st["particles"].append(["confetti" if fest != "diwali" else "sparkle", random.uniform(-0.45, 0.45), -0.4,
                                    random.uniform(-0.04, 0.04), random.uniform(0.05, 0.15), 1.6])
        w = self.weather.now
        if w and not fx["quiet"] and ctx["mood_guess"] in ("idle", "typing", "hungry", "drowsy", "dance"):
            if w.get("raining") or w.get("rain_soon"):
                fx["props"].append(("umbrella",))
            elif w.get("cold"):
                fx["props"].append(("scarf",))
            elif w.get("hot") and w.get("sunny") and not fx["outfit"]:
                fx["outfit"] = "sunglasses"
        # typing fire
        if self.wpm >= 60 and random.random() < 0.12:
            st["particles"].append(["fire", random.uniform(-0.45, 0.45), random.uniform(0.1, 0.3),
                                    0.0, -0.2, 0.7])
        # baby BOT
        self._baby_frame(st, now, t)
        # house, coins, water glass, shortcuts, night light, rain/snow, dance party
        if self.more:
            self.more.frame(st, now, t, ctx, fx)
            if now > self._fx_check:
                self._fx_check = now + 60
                self.more.maybe_weather_fx(st, self.weather.now, st["idle"] < 60 and not self.fg.get("fullscreen"))
        if self.gone:
            fx["quiet"] = True
        if self.more and self.more.going_home:
            fx["quiet"] = True
        return fx

    def _every_second(self, st, now, ctx):
        if now < self.next_check:
            return
        self.next_check = now + 1.0
        p = self.pet
        if now > self.next_fg:  # what app are you using?
            self.next_fg = now + 2.0
            try:
                self.fg = world.foreground()
                self.app_kind = world.classify(self.fg) if self.fg.get("ok") else ""
            except Exception:
                self.fg, self.app_kind = {}, ""
        # typing speed
        self.key_samples.append((now, p.keys.count))
        self.key_samples = [s for s in self.key_samples if now - s[0] <= 20]
        if len(self.key_samples) > 1:
            keys = self.key_samples[-1][1] - self.key_samples[0][1]
            span = max(5.0, self.key_samples[-1][0] - self.key_samples[0][0])
            self.wpm = int(keys / span * 60 / 5)
        if self.wpm >= 20:
            best = self.life.d["counts"].get("wpm_best", 0)
            if self.wpm > best:
                self.count(st, "wpm_best", self.wpm, best=True)
        # work timer (for eye care and break plea)
        if st["idle"] < 60:
            self.active_min += 1 / 60
            self.work_min += 1 / 60
        elif st["idle"] > 300:
            self.work_min = 0.0
        # music
        m = self.media.now
        key = (m.get("title"), m.get("artist"), m.get("playing")) if m else None
        if key != self.media_key:
            self.media_key = key
            self.out({"type": "now_playing", **(m or {})})
            if m and m.get("playing") and m.get("title") and not self.busy_now() and not st["speech"] \
                    and not ctx["focusing"]:
                art = f" — {m['artist']}" if m.get("artist") else ""
                self.say(st, f"🎵 {m['title'][:40]}{art[:30]}", 8, (("⏮", "media:prev"), ("⏯", "media:toggle"),
                                                                    ("⏭", "media:next")))
        # cursor prank trigger
        opts = self.life.d["options"]
        if opts.get("cursor_prank") and now > self.next_prank and not self.busy_now() and p.wanted \
                and st["idle"] > 4 and st["idle"] < 60 and not ctx["typing"]:
            self.next_prank = now + random.uniform(25, 45) * 60
            self._prank_start(st, now)
        # day change: diary
        today = date.today().isoformat()
        if getattr(self, "_day", None) != today:
            self._day = today
            self.life.write_diary()

    # ------------------------------------------------------------------ chatter (BOT may say something)
    def chatter(self, st, now, hour, mood) -> bool:
        p = self.pet
        life = self.life
        today = date.today().isoformat()
        # festival / birthday greeting (once a day)
        fest = world.festival(birthday=life.d.get("birthday", ""))
        if fest and self.fest_greeted != today:
            self.fest_greeted = today
            self.say(st, world.FESTIVAL_LINES[fest], 8)
            self.react(st, "excited", 3)
            self._sparkle_burst(st)
            if fest == "birthday":
                p._notify("Happy birthday! 🎂", "BOT is celebrating you today! 🎉💙")
            return True
        # rain warning
        w = self.weather.now
        if w and w.get("rain_soon") and self.rain_warned != today and 7 <= hour < 21:
            self.rain_warned = today
            self.say(st, self.weather.line(), 7)
            return True
        # mood journal (once a day after 10 AM)
        if hour >= 10 and self.mood_asked != today and today not in life.d["moods"]:
            self.mood_asked = today
            self.say(st, "How are you feeling today? 💙", 25, FEEL_OPTS)
            return True
        # take a break: 2 hours non-stop
        if self.work_min >= 120 and now > self.snooze_break:
            self.snooze_break = now + 30 * 60
            self._plead_start(st)
            return True
        # eye care every 20 active minutes
        if self.active_min >= self.next_eye_min:
            self.next_eye_min = self.active_min + 20
            self.say(st, "👀 20-20-20 time! Look at something far away for 20 seconds 💙", 3)
            self.eye = now + 3 + EYE_SECONDS
            return True
        # love chain on its own every hour or two
        if now > self.next_love and mood in ("idle", "typing"):
            self.next_love = now + random.uniform(60, 120) * 60
            self.start_love(st)
            return True
        # birthday question
        if not life.d.get("birthday") and time.time() - life.d.get("birthday_asked", 0) > 3 * 86400:
            life.d["birthday_asked"] = time.time()
            life._dirty = True
            self.say(st, "When's your birthday? 🎂 Say \"my birthday is 12 March\" or set it in the app (BOT's world)!", 9)
            return True
        # desktop tidy (once a week)
        if time.time() - life.d.get("tidy_asked", 0) > 7 * 86400:
            files = world.loose_files()
            life.d["tidy_asked"] = time.time()
            life._dirty = True
            if len(files) >= 15:
                self.say(st, f"Your desktop has {len(files)} files 😵 Want me to tidy them into folders? "
                             "(nothing gets deleted)", 30, (("Yes, tidy! 🧹", "tidy:yes"), ("Not now", "tidy:no")))
                return True
        # good night routine
        if (hour >= 23 or hour < 4) and self.night_asked != today and 180 < st["idle"] < 1800:
            self.night_asked = today
            self.night_wait = now + 600
            self.say(st, "It's late 🌙 I'm tucked in… Should I put the PC to sleep too?", 600,
                     (("Yes, sleep PC 😴", "night:sleep"), ("Not yet", "night:no")))
            return True
        # comfort words
        if now < self.comfort_until and now > getattr(self, "next_comfort", 0):
            self.next_comfort = now + random.uniform(4, 7) * 60
            self.say(st, random.choice(COMFORT), 6)
            self.react(st, "love", 2)
            return True
        # late night company
        if 1 <= hour < 5 and now > self.next_night_line:
            self.next_night_line = now + random.uniform(20, 35) * 60
            self.say(st, random.choice(NIGHT_COMPANY), 6)
            return True
        # app reactions
        kind = self.app_kind
        if kind and now > self.app_said.get(kind, 0):
            self.app_said[kind] = now + (3 * 60 if kind == "game" else 30 * 60 if kind != "chat" else 60 * 60)
            self.say(st, random.choice(APP_LINES[kind]), 4)
            self.react(st, "excited" if kind == "game" else "happy", 2)
            return True
        # happy-moments jar
        day, n = self.moments_today
        if day != today:
            self.moments_today = (today, 0)
            n = 0
        if life.d["moments"] and now > self.next_moment and n < 3:
            self.next_moment = now + random.uniform(150, 240) * 60
            self.moments_today = (today, n + 1)
            m = random.choice(life.d["moments"])
            self.say(st, f"Remember this? 😊 “{m['text'][:120]}”", 10)
            self.react(st, "love", 3)
            return True
        # joke of the day, countdowns, good thing today, to-do nudges, shy BOT
        if self.more and self.more.chatter(st, now, hour, mood):
            return True
        # sweet words
        if now > self.next_sweet:
            self.next_sweet = now + random.uniform(45, 90) * 60
            self.say(st, random.choice(SWEET), 5)
            self.react(st, "love", 2)
            return True
        # typing on fire
        if self.wpm >= 80 and now > self.wpm_said:
            self.wpm_said = now + 10 * 60
            self.say(st, f"🔥 {self.wpm} WPM! You're on fire!", 4)
            return True
        # hop onto a window
        return False

    # ------------------------------------------------------------------ reminders
    def _reminders(self, st, now, fx):
        if self.reminder or not self.life.d["reminders"]:
            return
        t = time.time()
        due = [r for r in self.life.d["reminders"] if r["at"] <= t]
        if not due:
            return
        r = min(due, key=lambda r: r["at"])
        self.life.d["reminders"] = [x for x in self.life.d["reminders"] if x["id"] != r["id"]]
        self.life._dirty = True
        self.life.save(force=True)
        self.pet._notify("⏰ Reminder", r["text"])
        p = self.pet
        if not p.wanted or self.gone:
            return
        self.end_game(st, quiet=True)
        self.love = None
        self.perch = None
        if self.more:
            self.more.come_out(st, quiet=True)
        self.reminder = {"text": r["text"], "until": now + 120}
        cx = (p.bounds[0] + p.bounds[2]) / 2 - p.W / 2
        if p.y < p._limits()[3] - 2:
            p.flying = True
        self.walk_to(cx, 300)
        self.say(st, f"⏰ Reminder: {r['text']}", 120, (("Done ✅", "rem:done"), ("Snooze 10 min ⏰", "rem:snooze")))
        self.react(st, "surprised", 1.5)

    # ------------------------------------------------------------------ break plea / prank / near cursor
    def _plead_start(self, st):
        p = self.pet
        self.end_game(st, quiet=True)
        self.perch = None
        self.plead = True
        self.pinned = True
        p.walking = p.flying = False
        p.x = (p.bounds[0] + p.bounds[2]) / 2 - p.W / 2
        p.y = (p.bounds[1] + p.bounds[3]) / 2 - p.H / 2
        self.say(st, "You've been working for 2 hours non-stop 🥺 Take a little break pleeease?", 600,
                 (("Okay, break time ☕", "brk:yes"), ("5 more minutes 🙏", "brk:snooze")))

    def _prank_start(self, st, now):
        p = self.pet
        mx, my = win_input.cursor_pos()
        self.prank = {"phase": "go", "t": now, "dir": random.choice((-1, 1)), "pos": (mx, my)}
        self.perch = None
        self.walk_to(mx - p.W / 2, 700)
        self.say(st, "Hehe 😏", 2)

    def _prank_frame(self, st, now, fx):
        p = self.pet
        pr = self.prank
        fx["quiet"] = True
        fx["mood"] = "excited"
        mx, my = win_input.cursor_pos()
        if pr["phase"] == "go":
            if math.hypot(mx - pr["pos"][0], my - pr["pos"][1]) > 30 or now - pr["t"] > 6:
                self.prank = None  # you moved the mouse: never fight you
                return
            if not p.walking:
                pr["phase"], pr["t"] = "run", now
                self.say(st, "Got your cursor! 😆🏃", 2)
                self.walk_to(p.x + pr["dir"] * 300, 380)
        elif pr["phase"] == "run":
            cx, cy = p._center
            want = (int(cx), int(cy - p.BH * 0.6))
            if pr.get("set") and math.hypot(mx - pr["set"][0], my - pr["set"][1]) > 12:
                self.prank = None  # you grabbed it back
                return
            user32.SetCursorPos(*want)
            pr["set"] = want
            if now - pr["t"] > 1.3 or not p.walking:
                self.prank = None
                self.say(st, "Hehe! Just kidding 😆💙", 2.5)
                p._walk_speed = 110

    def _stay_near_cursor(self, now):
        p = self.pet
        if now < getattr(self, "_near_t", 0) or p.walking or p.flying or p.dragging or self.perch:
            return
        self._near_t = now + 6
        mx, _my = win_input.cursor_pos()
        target = mx + random.choice((-1, 1)) * p.W * 0.9 - p.W / 2
        if abs(target - p.x) > p.W * 1.5:
            self.walk_to(target, 200)

    # ------------------------------------------------------------------ perch on the window you're using
    def perch_limits(self):
        """(left, right, floor) while sitting on a window, else None."""
        pc = self.perch
        if not pc or pc.get("leaving"):
            return None
        p = self.pet
        l, t, r, _b = pc["rect"]
        side = (p.W - p.BW) / 2
        floor = t - p.H + p.FOOT_GAP
        cx = p.x + p.W / 2
        if p.y <= floor + 3 and l - p.BW * 0.3 <= cx <= r + p.BW * 0.3:
            return (l - side, r - p.W + side, floor)
        return None

    def _perch_frame(self, st, now, ctx):
        p = self.pet
        pc = self.perch
        if pc:
            r = world.rect(pc["hwnd"]) if world.normal_window(pc["hwnd"]) else None
            if r is None or r != pc["rect"] or world.user32.IsZoomed(pc["hwnd"]):
                self.perch = None  # the window moved / closed: tumble down!
                if not p.flying and not p.dragging:
                    p.flying = True
                    p.vy = -200.0
                    self.say(st, "Whoaa! 😲", 2)
                    self.react(st, "surprised", 1.5)
                return
            if now > pc["until"] and not p.flying and not p.walking:
                self.perch = None
                p.vy, p.vx, p.flying = -650.0, random.choice((-1, 1)) * 250.0, True
                self.say(st, "Wheee! 🎈", 2)
            return
        if now < self.next_perch or ctx["mood_guess"] != "idle" or self.busy_now() or p.flying or p.walking \
                or p.peek_side or not p.wanted or p.chase_until > now:
            return
        self.next_perch = now + random.uniform(180, 420)
        fg = self.fg
        if not fg.get("ok") or fg.get("maximized") or fg.get("fullscreen"):
            return
        l, t, r, b = fg["rect"]
        if t < p.H * 0.8 + p.bounds[1] or r - l < p.BW * 2.5:
            return
        side = (p.W - p.BW) / 2
        floor = t - p.H + p.FOOT_GAP
        tx = random.uniform(l - side + 10, r - p.W + side - 10)
        apex = min(p.y, floor) - 140
        g = 2600.0
        vy0 = -math.sqrt(2 * g * max(10.0, p.y - apex))
        t_up = -vy0 / g
        t_down = math.sqrt(2 * max(1.0, floor - apex) / g)
        p.vx = (tx - p.x) / (t_up + t_down)
        p.vy = vy0
        p.flying = True
        self.perch = {"hwnd": fg["hwnd"], "rect": (l, t, r, b), "until": now + random.uniform(60, 180)}
        self.say(st, random.choice(["Hop! 🐸 Can I sit here?", "I'll sit on your window! 🪟😊", "Up I go! 🧗"]), 3)

    # ------------------------------------------------------------------ special movement
    def drive(self, dt) -> bool:
        """True = BOT is held in place by a game / plea (normal physics is skipped)."""
        return self.pinned

    # ------------------------------------------------------------------ game frames
    def _game_frame(self, st, now, t, fx):
        g = self.game
        p = self.pet
        name = g["name"]
        if name == "fetch":
            ball: sp.Sprite = g["ball"]
            left, top, right, bottom = p.bounds
            for ev in ball.events:
                if ev[0] == "throw":
                    ball.vx, ball.vy = ev[1], ev[2]
                    g["phase"], g["last"] = "fly", now
                    g["throws"] += 1
                    self.say(st, "Wheee! 🐶💨", 1.5)
                elif ev[0] == "click":
                    ball.vx, ball.vy = random.uniform(-500, 500), -900
                    g["phase"], g["last"] = "fly", now
            ball.events.clear()
            if ball.dragging:
                ball.follow_mouse()
                g["phase"] = "held"
                fx["mood"] = "excited"
            elif g["phase"] == "fly":
                dt = 1 / 60
                ball.vy += 2600 * dt
                ball.x += ball.vx * dt
                ball.y += ball.vy * dt
                if ball.x < left:
                    ball.x, ball.vx = left, abs(ball.vx) * 0.7
                if ball.x > right - ball.w:
                    ball.x, ball.vx = right - ball.w, -abs(ball.vx) * 0.7
                if ball.y < top:
                    ball.y, ball.vy = top, abs(ball.vy) * 0.5
                if ball.y >= bottom - ball.h:
                    ball.y = bottom - ball.h
                    if abs(ball.vy) > 200:
                        ball.vy = -ball.vy * 0.55
                    else:
                        ball.vy = 0.0
                    ball.vx *= 0.92
                    if ball.vy == 0 and abs(ball.vx) < 30:
                        g["phase"] = "run"
                        self.perch = None
                        self.walk_to(ball.center[0] - p.W / 2, 450)
                fx["mood"] = "excited"
                fx["look"] = ball.center
            elif g["phase"] == "run":
                fx["mood"] = "excited"
                fx["look"] = ball.center
                if not p.walking and not p.flying:
                    if abs(ball.center[0] - p._center[0]) < p.BW:
                        ball.hide()
                        ball.data["busy"] = True
                        g["phase"] = "carry"
                        self.count(st, "fetches")
                        self.coins(st, 1)
                        mx, _my = win_input.cursor_pos()
                        self.walk_to(mx - p.W / 2, 380)
                    else:
                        self.walk_to(ball.center[0] - p.W / 2, 450)
            elif g["phase"] == "carry":
                fx["props"].append(("ball",))
                fx["mood"] = "happy"
                if not p.walking:
                    g["phase"], g["last"] = "wait", now
                    img = ball.img
                    ball.show(img, p._center[0] + p.BW * 0.55, bottom - img.height)
                    self.say(st, random.choice(["Again! Again! 🐶", "Here you go! Throw it again! ⚽", "Woof! 🐶💙"]), 3)
                    self.react(st, "excited", 2)
            if g["phase"] == "wait":
                fx["look"] = ball.center
                ball.show()
                if now - g["last"] > 60:
                    self.end_game(st)
            elif ball.visible:
                ball.show()
        elif name == "catch":
            mx, _my = win_input.cursor_pos()
            self.walk_to(mx - p.W / 2, 900)
            fx["mood"] = "excited"
            if now > g["end"]:
                score = g["score"]
                self.end_game(st, quiet=True)
                best = int(self.life.d["counts"].get("catch_best", 0))
                self.count(st, "catch_games")
                self.count(st, "catch_best", score, best=True)
                self.coins(st, max(1, score // 2))
                self.life.cheer(happy=10, hunger=min(30, score * 2))
                self.say(st, f"You caught {score} cookies! 🍪{' New record! 🏆' if score > best else f' (best: {best})'}", 6)
                self.react(st, "love", 2)
                return
            if now > g["next"]:
                left_t = g["end"] - now
                g["next"] = now + max(0.35, 0.45 + left_t / 30 * 0.5)
                c = self.toy(False)
                size = int(p.S * 0.36)
                img = getattr(self, "_cookie_img", None)
                if img is None or img.width != size:
                    img = self._cookie_img = sp.cookie_image(size)
                c.data = {"busy": True, "vy": random.uniform(260, 360) + (30 - left_t) * 9}
                c.show(img, random.uniform(p.bounds[0] + 20, p.bounds[2] - size - 20), p.bounds[1] - size)
                g["cookies"].append(c)
            mouth_y = p.y + p.BODY_CY - p.BH * 0.25
            for c in list(g["cookies"]):
                c.y += c.data["vy"] / 60
                cx, cy = c.center
                if abs(cx - p._center[0]) < p.BW * 0.55 and mouth_y - p.BH * 0.4 < cy < mouth_y + p.BH * 0.3:
                    g["score"] += 1
                    self.react(st, "eat" if g["score"] % 2 else "happy", 0.5)
                    st["particles"].append(["crumb", 0.0, 0.25, 0.08, 0.1, 0.5])
                    c.data = {}
                    c.hide()
                    g["cookies"].remove(c)
                elif c.y > p.bounds[3]:
                    g["missed"] += 1
                    c.data = {}
                    c.hide()
                    g["cookies"].remove(c)
                else:
                    c.show()
            st["speech"], st["speech_until"], st["options"] = (f"🍪 {g['score']}   ⏱ {int(g['end'] - now)}", now + 0.5, ())
        elif name == "bubbles":
            if g["left"] > 0 and now > g["next"]:
                g["left"] -= 1
                g["next"] = now + 0.55
                b = self.toy(True)
                size = int(p.S * random.uniform(0.35, 0.55))
                b.data = {"busy": True, "vy": -random.uniform(60, 120), "x0": p._center[0] - size / 2,
                          "ph": random.uniform(0, 6.28), "amp": random.uniform(20, 60), "t0": now}
                b.show(sp.bubble_image(size, random.randint(0, 3)), b.data["x0"], p.y + p.BODY_CY - p.BH * 0.4)
                g["bubbles"].append(b)
                self.react(st, "surprised", 0.4)
            for b in list(g["bubbles"]):
                if b.events:
                    b.events.clear()
                    g["popped"] += 1
                    self.sound("pop")
                    self.count(st, "bubbles")
                    b.data["popped"] = now
                    b.show(sp.pop_image(b.w))
                if "popped" in b.data:
                    if now - b.data["popped"] > 0.15:
                        b.data = {}
                        b.hide()
                        g["bubbles"].remove(b)
                    continue
                b.y += b.data["vy"] / 60
                b.x = b.data["x0"] + math.sin((now - b.data["t0"]) * 1.6 + b.data["ph"]) * b.data["amp"]
                if b.y < p.bounds[1] - b.h:
                    b.data = {}
                    b.hide()
                    g["bubbles"].remove(b)
                else:
                    b.show()
            if g["left"] == 0 and not g["bubbles"]:
                n = g["popped"]
                self.end_game(st, quiet=True)
                self.count(st, "bubble_games")
                self.coins(st, max(1, n // 2))
                self.say(st, f"You popped {n}/10 bubbles! 🫧{' Perfect!! 🏆' if n == 10 else ''}", 5)
                self.react(st, "happy", 2)
        elif name == "hide":
            fx["quiet"] = True
            if g["phase"] == "count":
                fx["mood"] = "excited"
                if now > g["t"]:
                    g["phase"], g["t"] = "vanish", now + 2.0
                    self.hiding = True
                    self.pinned = True
            elif g["phase"] == "vanish":
                if now > g["t"]:
                    self._hide_somewhere()
                    g["phase"], g["t0"], g["end"] = "hidden", now, now + 50
                    st["speech"], st["options"] = "", ()
            elif g["phase"] == "hidden":
                fx["mood"] = "idle"
                if now > g["end"]:
                    self.end_game(st, quiet=True)
                    self.say(st, "I win! You couldn't find me 😜", 4)
                    self.react(st, "excited", 2)
                    p.vy = -700.0
        elif name == "photo":
            fx["mood"] = "excited"
            if g["step"] > 0 and now - g["t"] > 1.0:
                g["step"] -= 1
                g["t"] = now
                if g["step"] > 0:
                    self.say(st, f"Smile! 😁 {g['step']}", 1.2)
                else:
                    self.say(st, "📸 Click!", 2)
                    self._snap_photo(st)
                    self.game = None

    def _hide_somewhere(self):
        """Pick a hiding spot: behind a (not maximized) window, else peeking from a screen edge."""
        p = self.pet
        left, top, right, bottom = p.bounds
        side = (p.W - p.BW) / 2
        spots = []
        for w in world.visible_windows():
            if w["maximized"]:
                continue
            l, t, r, b = w["rect"]
            if b - t < p.BH * 1.5:
                continue
            y = random.uniform(t + p.BH * 0.2, max(t + p.BH * 0.2, b - p.BH * 1.1))
            if l - p.BW * 0.5 > left:   # peek out on the left of the window
                spots.append(("win", w["hwnd"], l + p.BW * 0.14 - p.W / 2, y - p.BODY_CY + p.BH / 2))
            if r + p.BW * 0.5 < right:  # ...or on its right
                spots.append(("win", w["hwnd"], r - p.BW * 0.14 - p.W / 2, y - p.BODY_CY + p.BH / 2))
        for _ in range(3):
            y = random.uniform(top + p.H * 0.2, bottom - p.H)
            spots.append(("edge", None, left - side - p.BW * 0.62, y))
            spots.append(("edge", None, right - p.W + side + p.BW * 0.62, y))
            spots.append(("edge", None, random.uniform(left + 40, right - p.W - 40), top - p.H + p.FOOT_GAP + p.BH * 0.6))
        kind, hwnd, x, y = random.choice(spots)
        p.x, p.y = x, y
        p.flying = p.walking = False
        p.vx = p.vy = 0.0
        if kind == "win" and hwnd:
            user32.SetWindowPos(p._hwnd, hwnd, 0, 0, 0, 0, 0x0001 | 0x0002 | 0x0010)  # just behind that window

    def _snap_photo(self, st):
        p = self.pet
        params = {"mood": "love", "open": 1.0, "look": (0.0, 0.2), "yawn": False, "bounce": 0.0, "breathe": 0.0,
                  "tilt": 0.0, "alpha": 255, "t": 1.0, "particles": [], "speech": "", "options": (), "stats": "",
                  "focus": "", "outfit": "none", "chomp": 0, "cookie": None, "props": [], "under": []}
        sticker = p._render(params)
        caption = f"Me & BOT 💙 {date.today():%d %b %Y}"
        path = str(Path.home() / "Pictures" / "BOT Photos" / f"bot_photo_{datetime.now():%Y%m%d_%H%M%S}.jpg")

        def work():
            ok = world.snap(path, sticker, caption)
            p._q.put(("fun", "photo_done", ok, path))

        threading.Thread(target=work, daemon=True).start()

    # ------------------------------------------------------------------ baby BOT
    def _baby_frame(self, st, now, t):
        p = self.pet
        life = self.life
        if life.level >= 6 and not life.d.get("baby") and not self.egg and p.wanted and not self.busy_now():
            self.egg = sp.Sprite(False)
            self.egg_t0 = now
            self.say(st, "Oh! What's this?! 🥚✨", 4)
            self.react(st, "surprised", 2)
        if self.egg:
            age = now - self.egg_t0
            size = int(p.S * 0.45)
            crack = min(3, int(age / 1.5))
            img = sp.egg_image(size, crack)
            wob = math.sin(age * 14) * 6 if age > 1 else 0
            self.egg.show(img, p._center[0] + p.BW * 0.7 + wob, p.bounds[3] - img.height)
            if age > 6:
                self.baby_x = self.egg.x
                self.egg.destroy()
                self.egg = None
                life.d["baby"] = True
                life._dirty = True
                life.save(force=True)
                self.say(st, "A baby BOT!! 🥚➡️👶💙 It's so tiny!", 6)
                self._sparkle_burst(st)
                p._burst(st, "heart", 10)
                p._notify("Baby BOT hatched! 👶💙", "BOT has a tiny baby now 🥚✨")
            return
        if not life.d.get("baby"):
            return
        size = int(p.S * 0.5)
        if not self.baby_frames or self.baby_frames["open"].width != size:
            self.baby_frames = {k: sp.baby_image(size, k) for k in ("open", "closed", "happy")}
            self.baby = self.baby or sp.Sprite(True)
            self.baby_x = p.x
        if not p.wanted or self.gone or p.away_until or self._alpha_low():
            self.baby.hide()
            return
        for ev in self.baby.events:
            if ev[0] == "click":
                self.say(st, "Baby says: hehe! 👶💙", 2.5)
                p._burst(st, "heart", 4)
                self.baby_hop = now + 0.6
        self.baby.events.clear()
        target = p._center[0] - (p.BW * 0.9 if p._center[0] > (p.bounds[0] + p.bounds[2]) / 2 else -p.BW * 0.9) - size / 2
        dx = target - self.baby_x
        moving = abs(dx) > 8
        if moving:
            self.baby_x += max(-6.0, min(6.0, dx * 0.08))
        hop = abs(math.sin(t * 10)) * size * 0.12 if moving or now < self.baby_hop else 0.0
        mood = st.get("react") if now < st.get("react_until", 0) else ""
        eyes = "happy" if mood in ("love", "happy", "excited") else ("closed" if int(t * 3) % 13 == 0 else "open")
        self.baby.show(self.baby_frames[eyes], self.baby_x, p.bounds[3] - size - hop)

    def _alpha_low(self):
        return self.pet._alpha < 20

    # ------------------------------------------------------------------ to the phone
    def out(self, msg: dict):
        fn = getattr(self.pet, "out_fn", None)
        if fn:
            try:
                fn(msg)
            except Exception:
                pass
