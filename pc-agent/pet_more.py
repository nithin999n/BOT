"""
More life for the desktop BOT: its tiny house, coins & shop, cute sounds, scroll-for-volume, shortcut cheers,
to-do list, water glass, "good thing today", joke of the day, countdowns, night light, chat, rain/snow, dance party.

Owned by Fun (pet_fun.py) and run on the desktop BOT's thread.
"""
from __future__ import annotations

import json
import logging
import math
import os
import random
import threading
import time
import urllib.request
import wave
from datetime import date, datetime
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

import pet_sprites as sp
import pet_ui
import win_input

log = logging.getLogger("bot")

# ---- shop -------------------------------------------------------------------------------------------
# id: (name, price, kind)   kind: outfit / decor / treat
SHOP = {
    "bunny": ("🐰 Bunny ears", 30, "outfit"), "chef": ("👨‍🍳 Chef hat", 30, "outfit"),
    "cowboy": ("🤠 Cowboy hat", 40, "outfit"), "beret": ("🎨 Beret", 25, "outfit"),
    "flowers": ("🌷 Flower pots", 20, "decor"), "lights": ("✨ Fairy lights", 35, "decor"),
    "mailbox": ("📮 Mailbox", 15, "decor"), "garden": ("🌳 Little tree", 25, "decor"),
    "flag": ("🚩 Flag", 10, "decor"), "pink": ("🎀 Pink paint", 20, "decor"),
    "cake": ("🍰 Cake", 15, "treat"), "icecream": ("🍦 Ice cream", 10, "treat"),
    "pizza": ("🍕 Pizza", 12, "treat"), "donut": ("🍩 Donut", 8, "treat"),
}
TREAT_EMOJI = {"cake": "🍰", "icecream": "🍦", "pizza": "🍕", "donut": "🍩"}
SHOP_OUTFITS = {k for k, v in SHOP.items() if v[2] == "outfit"}

JOKES = [
    "Why did the computer go to the doctor? It had a virus! 🤒💻",
    "Why was the robot so tired? It had a hard drive! 😴",
    "What do you call a bear with no teeth? A gummy bear! 🐻",
    "Why don't eggs tell jokes? They'd crack each other up! 🥚😂",
    "What did the ocean say to the beach? Nothing, it just waved! 🌊👋",
    "Why can't a bicycle stand up by itself? It's two tired! 🚲",
    "What do you call a sleeping dinosaur? A dino-snore! 🦖💤",
    "Why did the cookie go to the hospital? It felt crummy! 🍪",
    "Why was the math book sad? It had too many problems! 📚",
    "What do you call a fish with no eyes? A fsh! 🐟",
    "Why did the scarecrow win an award? He was outstanding in his field! 🌾",
    "How do robots eat guacamole? With computer chips! 🤖🥑",
    "Why did the phone wear glasses? It lost its contacts! 📱👓",
    "What's a computer's favourite snack? Microchips! 🍟",
    "Why do bees have sticky hair? Because they use honeycombs! 🐝",
    "What did one wall say to the other? I'll meet you at the corner! 🧱",
    "Why did the banana go to the doctor? It wasn't peeling well! 🍌",
    "What do you call cheese that isn't yours? Nacho cheese! 🧀",
    "Why are ghosts bad liars? You can see right through them! 👻",
    "What did the zero say to the eight? Nice belt! 0️⃣8️⃣",
    "Why did the golfer bring two pants? In case he got a hole in one! ⛳",
    "What do you call a dog magician? A labracadabrador! 🐶✨",
    "Why did the tomato blush? It saw the salad dressing! 🍅",
    "How does the moon cut his hair? Eclipse it! 🌙✂️",
    "What has keys but can't open locks? A keyboard! ⌨️",
]
FACTS = [
    "Fun fact: octopuses have three hearts! 🐙💙💙💙", "Fun fact: honey never spoils! 🍯",
    "Fun fact: bananas are berries, but strawberries aren't! 🍌🍓", "Fun fact: a group of flamingos is called a flamboyance! 🦩",
    "Fun fact: sloths can hold their breath longer than dolphins! 🦥", "Fun fact: the Eiffel Tower grows taller in summer! 🗼",
    "Fun fact: cows have best friends! 🐄💕", "Fun fact: sea otters hold hands while they sleep! 🦦🤝",
    "Fun fact: a day on Venus is longer than its year! 🪐", "Fun fact: butterflies taste with their feet! 🦋",
    "Fun fact: the first computer bug was a real moth! 🐛💻", "Fun fact: elephants can't jump! 🐘",
    "Fun fact: your heart beats about 100,000 times a day! 💓", "Fun fact: penguins propose with pebbles! 🐧🪨",
    "Fun fact: the dot over an 'i' is called a tittle! ✏️", "Fun fact: Saturn could float in water! 🪐🛁",
]
GOOD_THING = ["What's one good thing that happened today? ✨", "Tell me one nice thing about today? 🌟"]
TODO_DONE = ["Yay! Done! ✅🎉", "Woohoo! One less thing! 💪✅", "Look at you go! ✅✨"]

# ---- offline chat ------------------------------------------------------------------------------------
CHAT = [
    (["kill myself", "suicide", "end my life", "want to die", "self harm", "hurt myself", "don't want to live",
      "dont want to live"],
     ["I'm really glad you told me 💙 You matter so much. Please talk to someone right now: call Tele-MANAS "
      "at 14416 (free, 24/7, India), or a friend you trust. I'm right here with you 🫂"]),
    (["breakup", "broke up", "she left", "he left", "left me", "heartbroken", "heart broken", "my ex", "miss her",
      "miss him"],
     ["I'm so sorry 💙 Hearts take time to heal, and that's okay. I'm right here with you 🫂",
      "That really hurts 🥺 You deserve someone who chooses you every single day. Be gentle with yourself 💙",
      "It's okay to miss her. It means you loved for real 💙 One day at a time, okay? I'm staying right here",
      "You're not alone tonight 🫂 Maybe call a friend or family member? And I'll keep you company too 💙"]),
    (["sad", "lonely", "alone", "cry", "crying", "depressed", "hurt", "upset", "down"],
     ["Come here 🫂 I'm right here with you 💙", "I'm sorry you feel this way 🥺 Want to tell me more?",
      "It's okay to feel sad sometimes 💙 You're not alone, I'm always here",
      "Sending you the biggest hug 🤗💙 Maybe some water and a little walk could help a bit?"]),
    (["love you", "i love u", "luv you"], ["I love you too!! 💖🥰", "Awww! I love you sooo much more! 💕"]),
    (["do you love me", "u love me"], ["Of course I love you!! 💖 More than cookies! 🍪"]),
    (["miss you"], ["I missed you too!! 🥺💙 Don't leave me alone so long!"]),
    (["hello", "hi ", "hey", "hii", "namaste", "hlo"], ["Hiii! 👋💙 How are you?", "Hey there, best human! 🥰"]),
    (["how are you", "how r u", "hru"], ["I'm great now that you're here! 😊 How are you?", "Happy and blue! 💙😄 You?"]),
    (["tired", "sleepy", "exhausted"], ["Take a little rest, okay? 😴💙", "You worked hard. Rest is important too 🌙"]),
    (["bored"], ["Let's play! Try hide and seek 🙈 or fetch ⚽ from my tray menu!", "Want a joke? " + JOKES[0]]),
    (["joke", "funny", "make me laugh"], JOKES),
    (["fact"], FACTS),
    (["happy", "great", "awesome", "good day", "amazing"], ["Yay!! That makes me so happy! 😄💙", "Woohoo! 🎉"]),
    (["angry", "mad", "annoyed", "frustrated"], ["Deep breath with me… in… and out 💙 I'm on your side",
                                                  "That sounds frustrating 😣 Want to take a short break?"]),
    (["thank", "thanks", "thx"], ["You're welcome! 💙", "Anytime, buddy! 🥰"]),
    (["who are you", "your name", "what are you"], ["I'm BOT, your little blue buddy! 💙🤖"]),
    (["what can you do", "help"], ["I can play games, remind you of things, track your water, cheer you on, "
                                   "and love you lots! 💙"]),
    (["hungry", "food", "eat"], ["Go eat something yummy! 🍲 And bring me a cookie? 🍪🥺"]),
    (["good night", "gn", "sleep"], ["Good night! 🌙 Sweet dreams, I'll be right here 💙"]),
    (["good morning", "gm"], ["Good morning! ☀️ Let's make today awesome!"]),
    (["sorry"], ["Aww, it's okay! I forgive you 💕"]),
    (["bye", "see you", "cya"], ["Bye bye! 👋 Come back soon, I'll miss you 🥺💙"]),
    (["work", "study", "exam", "project"], ["You've got this! 💪 One step at a time", "I believe in you! 📚✨"]),
]
CHAT_DEFAULT = ["Tell me more 🥺", "I'm listening 💙", "Hmm! That's interesting 🤔", "Really? 😮 And then?",
                "I like talking with you 🥰", "Ooh, okay! 💙"]
PERSONA = ("You are BOT, a tiny cute blue robot pet that lives on the user's Windows desktop. You love the user very "
           "much. Reply in 1-2 short sentences, warm, playful and kind, with 1-2 emojis. You are not a human and "
           "never pretend to be one. If the user is sad or heartbroken, be gentle and supportive. If they mention "
           "self-harm, kindly urge them to call Tele-MANAS 14416 (India, free, 24/7) or someone they trust.")


def offline_reply(text: str) -> str:
    t = " " + text.lower() + " "
    for words, replies in CHAT:
        if any(w in t for w in words):
            return random.choice(replies)
    return random.choice(CHAT_DEFAULT)


def chat_reply(text: str, history: list, key: str = "") -> str:
    """Free: canned replies. With a free Google Gemini key: real AI replies."""
    if any(w in text.lower() for w in CHAT[0][0]):
        return CHAT[0][1][0]  # always the safe answer
    if key:
        contents = []
        for who, msg in history[-12:]:
            contents.append({"role": "user" if who == "user" else "model", "parts": [{"text": msg}]})
        if not contents or contents[-1]["role"] != "user":
            contents.append({"role": "user", "parts": [{"text": text}]})
        body = json.dumps({"system_instruction": {"parts": [{"text": PERSONA}]}, "contents": contents,
                           "generationConfig": {"maxOutputTokens": 200, "temperature": 0.9}}).encode("utf-8")
        for model in ("gemini-flash-latest", "gemini-2.5-flash", "gemini-2.0-flash"):
            try:
                req = urllib.request.Request(
                    f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
                    data=body, headers={"Content-Type": "application/json", "x-goog-api-key": key})
                with urllib.request.urlopen(req, timeout=20) as resp:
                    data = json.loads(resp.read().decode("utf-8"))
                parts = data["candidates"][0]["content"]["parts"]
                reply = "".join(p.get("text", "") for p in parts).strip()
                if reply:
                    return reply[:400]
            except Exception as exc:
                log.debug("gemini %s failed: %s", model, exc)
    return offline_reply(text)


# ---- sounds (tiny synthesized beeps, played with winsound) -------------------------------------------------
SOUND_DIR = Path(os.environ.get("LOCALAPPDATA", ".")) / "BOT" / "sounds"


def _tone(path: Path, parts, rate=22050, vol=0.35):
    import struct
    frames = bytearray()
    for f0, f1, dur, kind in parts:
        n = int(rate * dur)
        for i in range(n):
            k = i / max(1, n - 1)
            f = f0 + (f1 - f0) * k
            env = min(1.0, i / 120) * (1 - k) ** 1.4
            if kind == "noise":
                v = (random.random() * 2 - 1) * env
            else:
                v = math.sin(2 * math.pi * f * i / rate) * env
            frames += struct.pack("<h", int(v * vol * 32767))
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(bytes(frames))


def make_sounds() -> None:
    SOUND_DIR.mkdir(parents=True, exist_ok=True)
    defs = {
        "chirp": [(1400, 2100, 0.07, "s"), (2100, 2600, 0.08, "s")],
        "happy": [(1200, 1500, 0.06, "s"), (1600, 1900, 0.06, "s"), (2000, 2600, 0.1, "s")],
        "boing": [(180, 520, 0.18, "s")],
        "squeak": [(2600, 1700, 0.12, "s"), (1700, 2400, 0.1, "s")],
        "munch": [(300, 200, 0.05, "noise"), (0, 0, 0.04, "s"), (300, 200, 0.05, "noise")],
        "pop": [(900, 200, 0.06, "s")],
        "coin": [(1800, 1800, 0.06, "s"), (2700, 2700, 0.14, "s")],
        "sad": [(900, 500, 0.3, "s")],
        "party": [(110, 60, 0.12, "s"), (0, 0, 0.13, "s"), (2000, 2000, 0.03, "noise"), (0, 0, 0.1, "s"),
                  (110, 60, 0.12, "s"), (0, 0, 0.13, "s"), (2000, 2000, 0.03, "noise"), (0, 0, 0.1, "s")],
    }
    for name, parts in defs.items():
        p = SOUND_DIR / f"{name}.wav"
        if not p.exists():
            try:
                _tone(p, parts)
            except Exception as exc:
                log.debug("sound %s: %s", name, exc)


# ---- the house -----------------------------------------------------------------------------------------
def house_image(size: int, decor: set, lit: bool, sleeping: bool) -> Image.Image:
    n = size * 2
    W, H = int(n * 1.15), n
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img, "RGBA")
    wall = (255, 196, 222) if "pink" in decor else (255, 241, 214)
    wall_dark = tuple(int(c * 0.85) for c in wall)
    bx0, bx1, by0, by1 = W * 0.16, W * 0.84, H * 0.42, H * 0.98
    if "garden" in decor:  # a little tree on the left
        d.rectangle((W * 0.05, H * 0.62, W * 0.09, H * 0.98), fill=(140, 95, 60, 255))
        d.ellipse((W * -0.02, H * 0.4, W * 0.16, H * 0.68), fill=(90, 190, 110, 255))
    d.rounded_rectangle((bx0, by0, bx1, by1), radius=n * 0.03, fill=wall + (255,), outline=wall_dark + (255,),
                        width=int(n * 0.012))
    # roof
    d.polygon([(W * 0.08, H * 0.46), (W * 0.5, H * 0.08), (W * 0.92, H * 0.46)], fill=(58, 141, 255, 255))
    d.line([(W * 0.08, H * 0.46), (W * 0.5, H * 0.08), (W * 0.92, H * 0.46)], fill=(38, 100, 200, 255), width=int(n * 0.025))
    d.rectangle((W * 0.66, H * 0.14, W * 0.74, H * 0.3), fill=(200, 110, 90, 255))  # chimney
    if sleeping or lit:
        for i in range(3):
            r = n * (0.025 + 0.012 * i)
            cx, cy = W * 0.7 + i * n * 0.03, H * (0.1 - i * 0.045)
            d.ellipse((cx - r, cy - r, cx + r, cy + r), fill=(235, 235, 245, 170))
    # door + window
    d.rounded_rectangle((W * 0.42, H * 0.64, W * 0.58, by1), radius=n * 0.06, fill=(150, 100, 70, 255))
    d.ellipse((W * 0.54, H * 0.8, W * 0.565, H * 0.825), fill=(255, 220, 90, 255))
    win = (255, 225, 120, 255) if (lit or sleeping) else (170, 215, 255, 255)
    d.rounded_rectangle((W * 0.22, H * 0.55, W * 0.36, H * 0.7), radius=n * 0.015, fill=win, outline=wall_dark + (255,),
                        width=int(n * 0.01))
    d.line([(W * 0.29, H * 0.55), (W * 0.29, H * 0.7)], fill=wall_dark + (255,), width=int(n * 0.008))
    d.rounded_rectangle((W * 0.64, H * 0.55, W * 0.78, H * 0.7), radius=n * 0.015, fill=win, outline=wall_dark + (255,),
                        width=int(n * 0.01))
    if sleeping:
        d.text((W * 0.78, H * 0.3), "z", fill=(90, 110, 180, 255))
        d.text((W * 0.84, H * 0.22), "Z", fill=(90, 110, 180, 255))
    if "flowers" in decor:
        for x in (0.2, 0.33, 0.67, 0.8):
            d.rectangle((W * x - n * 0.03, H * 0.9, W * x + n * 0.03, H * 0.98), fill=(200, 110, 70, 255))
            for k, col in enumerate(((255, 120, 170), (255, 210, 80), (190, 140, 255))):
                d.ellipse((W * x - n * 0.03 + k * n * 0.02, H * 0.85, W * x - n * 0.01 + k * n * 0.02, H * 0.88),
                          fill=col + (255,))
    if "lights" in decor:
        for i in range(9):
            t = i / 8
            x = W * (0.12 + 0.76 * t)
            y = H * 0.46 + math.sin(t * math.pi) * H * 0.04
            col = [(255, 90, 120), (255, 220, 80), (90, 210, 255), (130, 240, 130)][i % 4]
            d.ellipse((x - n * 0.018, y - n * 0.018, x + n * 0.018, y + n * 0.018), fill=col + (255,))
    if "mailbox" in decor:
        d.rectangle((W * 0.9, H * 0.72, W * 0.92, H * 0.98), fill=(120, 90, 70, 255))
        d.rounded_rectangle((W * 0.86, H * 0.64, W * 0.98, H * 0.74), radius=n * 0.02, fill=(230, 60, 70, 255))
    if "flag" in decor:
        d.line([(W * 0.5, H * 0.08), (W * 0.5, H * -0.02 + n * 0.02)], fill=(90, 90, 90, 255), width=int(n * 0.012))
        d.polygon([(W * 0.5, H * 0.01), (W * 0.62, H * 0.04), (W * 0.5, H * 0.07)], fill=(255, 80, 80, 255))
    return img.resize((W // 2, H // 2), Image.LANCZOS)


def disco_image(size: int, phase: int) -> Image.Image:
    n = size * 2
    img = Image.new("RGBA", (n, int(n * 1.4)), (0, 0, 0, 0))
    d = ImageDraw.Draw(img, "RGBA")
    d.line([(n / 2, 0), (n / 2, n * 0.4)], fill=(200, 200, 210, 255), width=int(n * 0.02))
    c, r = (n / 2, n * 0.9), n * 0.42
    d.ellipse((c[0] - r, c[1] - r, c[0] + r, c[1] + r), fill=(190, 195, 210, 255))
    rnd = random.Random(phase)
    for gy in range(-4, 5):
        for gx in range(-4, 5):
            x, y = c[0] + gx * r * 0.22, c[1] + gy * r * 0.22
            if (x - c[0]) ** 2 + (y - c[1]) ** 2 < (r * 0.92) ** 2:
                v = rnd.randint(150, 255)
                tint = rnd.choice([(v, v, v), (v, 200, 255), (255, v, 230), (255, 240, v)])
                d.rectangle((x - r * 0.1, y - r * 0.1, x + r * 0.1, y + r * 0.1), fill=tint + (255,))
    return img.resize((size, int(size * 1.4)), Image.LANCZOS)


def light_image(size: int, color) -> Image.Image:
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    ImageDraw.Draw(img).ellipse((size * 0.15, size * 0.15, size * 0.85, size * 0.85), fill=color + (70,))
    return img.filter(ImageFilter.GaussianBlur(size * 0.12))


def drop_image(kind: str, scale: float) -> Image.Image:
    if kind == "rain":
        w, h = int(4 * scale) + 2, int(20 * scale)
        img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        ImageDraw.Draw(img).rounded_rectangle((0, 0, w - 1, h - 1), radius=w // 2, fill=(130, 190, 255, 170))
        return img
    s = int(random.uniform(7, 13) * scale)
    img = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    ImageDraw.Draw(img).ellipse((0, 0, s - 1, s - 1), fill=(255, 255, 255, 230))
    return img.filter(ImageFilter.GaussianBlur(0.6))


# ---- More --------------------------------------------------------------------------------------------------
class More:
    def __init__(self, fun):
        self.fun = fun
        self.pet = fun.pet
        self.life = fun.life
        d = self.life.d
        d.setdefault("coins", 0)
        d.setdefault("owned", [])
        d.setdefault("todos", [])
        d.setdefault("countdowns", [])
        d.setdefault("water_goal", 8)
        d["options"].setdefault("sounds", False)
        now = time.perf_counter()
        self.house: sp.Sprite | None = None
        self.house_key = None
        self.inside = ""            # "" / "shy" / "sleep" / "visit"
        self.inside_until = 0.0
        self.going_home = ""
        self.next_shy = now + random.uniform(40, 80) * 60
        self.next_todo = now + random.uniform(60, 120) * 60
        self.last_combo = 0.0
        self.combo_said: dict = {}
        self.clip_until = 0.0
        self.vol_until = 0.0
        self.vol_level = None
        self._endpoint = None
        self.fx: dict | None = None        # rain / snow
        self.party: dict | None = None
        self.joke_day = ""
        self.good_day = ""
        self.count_day = ""
        self.login_day = ""
        self.chat_history: list = []
        self.next_sound = 0.0
        self.sounds_ready = False

    # ---------------------------------------------------------------- helpers
    def say(self, st, text, secs=4.0, opts=()):
        self.pet._speak(st, text, secs, opts)

    def sound(self, name: str) -> None:
        if not self.life.d["options"].get("sounds"):
            return
        now = time.perf_counter()
        if now < self.next_sound and name not in ("coin", "pop"):
            return
        self.next_sound = now + 0.25
        if not self.sounds_ready:
            make_sounds()
            self.sounds_ready = True
        try:
            import winsound
            winsound.PlaySound(str(SOUND_DIR / f"{name}.wav"),
                               winsound.SND_FILENAME | winsound.SND_ASYNC | winsound.SND_NODEFAULT)
        except Exception:
            pass

    def coins(self, st, n: int) -> None:
        if n <= 0:
            return
        self.life.d["coins"] = int(self.life.d.get("coins", 0)) + int(n)
        self.life._dirty = True
        st["particles"].append(["coin", random.uniform(-0.2, 0.2), -0.3, 0.0, -0.18, 1.3])
        self.sound("coin")

    # ---------------------------------------------------------------- commands (from Fun.more)
    def cmd(self, st, action, value=None):
        f = getattr(self, "do_" + action, None)
        if f:
            f(st, value)

    def do_buy(self, st, item):
        if item not in SHOP:
            return
        name, price, kind = SHOP[item]
        d = self.life.d
        if kind != "treat" and item in d["owned"]:
            self.say(st, f"I already have {name}! 🥰", 3)
            return
        if d.get("coins", 0) < price:
            self.say(st, f"I need {price - d.get('coins', 0)} more coins 🪙🥺 Let's play games!", 4)
            return
        d["coins"] -= price
        self.life._dirty = True
        self.life.save(force=True)
        self.sound("coin")
        if kind == "treat":
            st["food_emoji"] = TREAT_EMOJI[item]
            self.pet._eat(st, 25)
            self.life.cheer(happy=15)
            self.say(st, f"{name}! For me?! 🥹💕", 3)
            return
        d["owned"].append(item)
        if kind == "outfit":
            d["outfit"] = item
            self.say(st, f"New {name}! Do I look cute? 🥹✨", 4)
        else:
            self.house_key = None
            self.say(st, f"New {name} for my house! 🏠✨ Thank you!", 4)
        self.fun.react(st, "love", 3)
        self.pet._burst(st, "heart", 8)

    def do_dance(self, st, _v=None):
        self.fun.end_game(st, quiet=True)
        self.come_out(st, quiet=True)
        now = time.perf_counter()
        p = self.pet
        cols = [(255, 80, 160), (80, 200, 255), (255, 220, 60), (140, 255, 120), (190, 120, 255), (255, 140, 60)]
        lights = []
        size = int(p.S * 2.2)
        for c in cols:
            s = self.fun.toy(False)
            s.data = {"busy": True, "ph": random.uniform(0, 6.28), "sp": random.uniform(0.4, 0.9)}
            s.show(light_image(size, c), p.bounds[0], p.bounds[1])
            lights.append(s)
        ball = self.fun.toy(False)
        ball.data = {"busy": True}
        frames = [disco_image(int(p.S * 0.8), i) for i in range(4)]
        self.party = {"end": now + 22, "lights": lights, "ball": ball, "frames": frames}
        self.say(st, "DANCE PARTY!! 🪩💃🕺", 3)
        if self.life.d["options"].get("sounds") and not (self.fun.media.now or {}).get("playing"):
            try:
                import winsound
                make_sounds()
                winsound.PlaySound(str(SOUND_DIR / "party.wav"),
                                   winsound.SND_FILENAME | winsound.SND_ASYNC | winsound.SND_LOOP)
            except Exception:
                pass

    def do_rain(self, st, _v=None):
        self._weather_fx(st, "rain")

    def do_snow(self, st, _v=None):
        self._weather_fx(st, "snow")

    def do_water(self, st, _v=None):
        day = self.life.today()
        day["water"] = day.get("water", 0) + 1
        self.life._dirty = True
        goal = int(self.life.d.get("water_goal", 8))
        n = day["water"]
        if n == goal:
            self.say(st, f"You hit your water goal! 💧🏆 {n}/{goal}", 5)
            self.coins(st, 5)
            self.fun._sparkle_burst(st)
        else:
            self.say(st, random.choice(["Gulp gulp! 💧", "Yay, hydrated! 💧✨", "Glug glug! 💧"]) + f" {n}/{goal}", 3)
        self.fun.react(st, "happy", 2)
        self.sound("happy")

    def do_todo_add(self, st, text):
        text = str(text or "").strip()[:120]
        if not text:
            return
        self.life.d["todos"].append({"id": f"{time.time():.0f}{random.randint(100, 999)}", "text": text, "done": False})
        self.life._dirty = True
        self.life.save(force=True)
        self.say(st, f"Added to your list 📝 “{text}”", 4)

    def do_todo_toggle(self, st, tid):
        for t in self.life.d["todos"]:
            if t["id"] == tid:
                t["done"] = not t["done"]
                if t["done"]:
                    t["at"] = time.time()
                    self.say(st, random.choice(TODO_DONE) + f" “{t['text'][:40]}”", 4)
                    self.fun.react(st, "excited", 3)
                    self.fun._sparkle_burst(st)
                    self.coins(st, 3)
                    self.fun.count(st, "todos_done")
                    self.sound("happy")
        # keep done tasks for a day
        self.life.d["todos"] = [t for t in self.life.d["todos"]
                                if not t["done"] or time.time() - t.get("at", time.time()) < 86400]
        self.life._dirty = True
        self.life.save(force=True)

    def do_todo_del(self, st, tid):
        self.life.d["todos"] = [t for t in self.life.d["todos"] if t["id"] != tid]
        self.life._dirty = True
        self.life.save(force=True)

    def do_todo_show(self, st, _v=None):
        todo = [t for t in self.life.d["todos"] if not t["done"]]
        if not todo:
            self.say(st, "Your to-do list is empty! 🎉 Add things in the app or say \"add buy milk to my list\"", 6)
            return
        opts = tuple((f"⬜ {t['text'][:28]}", f"todo:{t['id']}") for t in todo[:5]) + (("Close", "todo:close"),)
        self.say(st, f"Your list 📝 ({len(todo)}) Tap one when it's done!", 40, opts)

    def do_countdown_add(self, st, value):
        try:
            name, day = value
            datetime.strptime(day, "%Y-%m-%d")
        except (TypeError, ValueError):
            return
        self.life.d["countdowns"].append({"id": f"{time.time():.0f}{random.randint(100, 999)}",
                                          "name": str(name)[:40], "date": day})
        self.life._dirty = True
        self.life.save(force=True)
        left = (date.fromisoformat(day) - date.today()).days
        self.say(st, f"📅 {name}: {left} day{'s' if left != 1 else ''} to go!", 4)

    def do_countdown_del(self, st, cid):
        self.life.d["countdowns"] = [c for c in self.life.d["countdowns"] if c["id"] != cid]
        self.life._dirty = True
        self.life.save(force=True)

    def do_chat(self, st, _v=None):
        key = getattr(self.pet, "gemini_key", "") or ""
        pet = self.pet
        pet_ui.open_chat(lambda text, hist: chat_reply(text, hist, key),
                         on_reply=lambda reply: pet._q.put(("say", reply, 6.0)))

    def do_good_thing(self, st, _v=None):
        pet = self.pet

        def done(text):
            if text:
                pet._q.put(("fun", "moment_add", text))

        pet_ui.ask_text("BOT 💙", random.choice(GOOD_THING), done)

    def do_joke(self, st, _v=None):
        self.say(st, random.choice(JOKES + FACTS), 10, (("😂 Another one!", "joke:more"), ("Haha 😄", "joke:ok")))
        self.fun.react(st, "happy", 2)

    def do_volume(self, st, notches):
        try:
            import comtypes
            from comtypes import CLSCTX_ALL
            from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
            import ctypes
            if self._endpoint is None:
                comtypes.CoInitialize()
                dev = AudioUtilities.GetSpeakers()
                raw = getattr(dev, "_dev", dev)
                iface = raw.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
                self._endpoint = ctypes.cast(iface, ctypes.POINTER(IAudioEndpointVolume))
            ep = self._endpoint
            v = ep.GetMasterVolumeLevelScalar()
            v = max(0.0, min(1.0, v + 0.04 * float(notches)))
            ep.SetMasterVolumeLevelScalar(v, None)
            if v > 0 and ep.GetMute():
                ep.SetMute(0, None)
        except Exception as exc:
            self._endpoint = None
            log.debug("volume: %s", exc)
            return
        pct = int(round(v * 100))
        bars = "▮" * (pct // 10) + "▯" * (10 - pct // 10)
        icon = "🔇" if pct == 0 else ("🔈" if pct < 35 else ("🔉" if pct < 70 else "🔊"))
        st["speech"], st["speech_until"], st["options"] = f"{icon} {pct}%  {bars}", time.perf_counter() + 1.5, ()
        self.vol_until = time.perf_counter() + 1.5

    # ---------------------------------------------------------------- answers & clicks
    def answer(self, st, key, val) -> bool:
        if key == "todo":
            if val != "close":
                self.do_todo_toggle(st, val)
                if any(not t["done"] for t in self.life.d["todos"]):
                    self.do_todo_show(st)
            else:
                st["speech_until"] = 0
            return True
        if key == "joke":
            if val == "more":
                self.do_joke(st)
            else:
                self.say(st, "Hehe 😄", 2)
            return True
        if key == "good":
            if val == "tell":
                self.do_good_thing(st)
            else:
                self.say(st, "That's okay 💙 Tomorrow will have good things too", 4)
            return True
        if key == "water":
            if val == "drank":
                self.do_water(st)
                return True
        return False

    def click_house(self, st) -> None:
        if self.inside:
            self.come_out(st, knocked=True)
        else:
            self.say(st, "That's my house! 🏠💙", 3)
            self.fun.react(st, "happy", 2)

    def come_out(self, st, quiet=False, knocked=False):
        if not self.inside and not self.going_home:
            return
        was = self.inside
        self.inside, self.going_home = "", ""
        p = self.pet
        if self.house is not None:
            p.x = self.house.x + self.house.w / 2 - p.W / 2
            p.y = p._limits()[3]
        if quiet:
            return
        if knocked:
            self.say(st, "You knocked! 🚪😊 Hiii!", 3)
        elif was == "sleep":
            h = datetime.now().hour
            self.say(st, "Good morning! ☀️ I slept so well in my house 🏠" if 5 <= h < 12 else "I'm awake! 😊", 4)
        else:
            self.say(st, "Peekaboo! 😊", 3)
        self.fun.react(st, "excited", 2)
        self.sound("chirp")

    # ---------------------------------------------------------------- every frame
    def frame(self, st, now, t, ctx, fx):
        p = self.pet
        self._house_frame(st, now, ctx)
        # keyboard shortcut cheers (only Ctrl+S / Ctrl+Z / Ctrl+C are noticed)
        combo = getattr(p.keys, "combo", None)
        if combo and combo[1] > self.last_combo:
            self.last_combo = combo[1]
            name = combo[0]
            if not fx["quiet"] and not self.inside:
                if name == "save" and now > self.combo_said.get("save", 0):
                    self.combo_said["save"] = now + 120
                    self.say(st, random.choice(["Saved! 💾✨", "Good thinking! 💾", "Saved and safe! 💾💙"]), 2.5)
                    self.fun.react(st, "happy", 1.5)
                elif name == "undo" and now > self.combo_said.get("undo", 0):
                    self.combo_said["undo"] = now + 180
                    self.say(st, random.choice(["Oopsie, undo! 🙈", "Undo undo! ↩️😆"]), 2.5)
                elif name == "copy":
                    self.clip_until = now + 3
        if now < self.clip_until:
            fx["props"].append(("clipboard",))
        if now < self.vol_until:
            fx["props"].append(("ears",))
            fx["mood"] = fx["mood"] or "happy"
        # water glass next to BOT
        if not fx["quiet"] and ctx["mood_guess"] in ("idle", "typing", "drowsy", "hungry", "happy") and not self.inside:
            goal = max(1, int(self.life.d.get("water_goal", 8)))
            fx["props"].append(("glass", min(1.0, self.life.today().get("water", 0) / goal)))
        # night light
        fx["night"] = ctx["hour"] >= 22 or ctx["hour"] < 6
        # rain / snow
        if self.fx:
            self._fx_frame(now)
        # dance party
        if self.party:
            fx["force"] = fx["force"] or "dance"
            fx["quiet"] = True
            self._party_frame(st, now, t)
        if self.inside:
            fx["quiet"] = True
        # daily coins for showing up
        today = date.today().isoformat()
        if self.login_day != today and st["idle"] < 30:
            self.login_day = today
            if self.life.d.get("login_day") != today:
                self.life.d["login_day"] = today
                self.coins(st, 5)

    def chatter(self, st, now, hour, mood) -> bool:
        life = self.life
        today = date.today().isoformat()
        # joke / fact of the day (morning)
        if hour >= 8 and self.joke_day != today and life.d.get("joke_day") != today:
            self.joke_day = today
            life.d["joke_day"] = today
            life._dirty = True
            self.say(st, ("Joke of the day! " if random.random() < 0.6 else "") + random.choice(JOKES + FACTS), 10,
                     (("😂 Another one!", "joke:more"), ("Haha 😄", "joke:ok")))
            self.fun.react(st, "happy", 2)
            return True
        # countdowns (once a day)
        if self.count_day != today:
            self.count_day = today
            line = self.countdown_line(days_max=30, long=True)
            if line:
                self.say(st, line, 6)
                return True
        # good thing today (night)
        if 21 <= hour <= 23 and self.good_day != today and life.d.get("good_day") != today:
            self.good_day = today
            life.d["good_day"] = today
            life._dirty = True
            self.say(st, random.choice(GOOD_THING), 40, (("Tell me ✍️", "good:tell"), ("Not today", "good:no")))
            return True
        # to-do nudge
        todo = [t for t in life.d["todos"] if not t["done"]]
        if todo and now > self.next_todo:
            self.next_todo = now + random.uniform(120, 180) * 60
            self.do_todo_show(st)
            return True
        # shy: run into the house for a bit
        if mood == "idle" and now > self.next_shy and self.house is not None and not self.fun.busy_now():
            self.next_shy = now + random.uniform(40, 80) * 60
            self._go_home(st, "shy")
            return True
        return False

    def countdown_line(self, days_max=99999, long=False) -> str:
        items = list(self.life.d["countdowns"])
        bday = self.life.d.get("birthday", "")
        if bday:
            y = date.today().year
            try:
                nxt = date.fromisoformat(f"{y}-{bday}")
                if nxt < date.today():
                    nxt = date.fromisoformat(f"{y + 1}-{bday}")
                items.append({"name": "your birthday 🎂", "date": nxt.isoformat()})
            except ValueError:
                pass
        best = None
        for c in items:
            try:
                left = (date.fromisoformat(c["date"]) - date.today()).days
            except ValueError:
                continue
            if 0 <= left <= days_max and (best is None or left < best[0]):
                best = (left, c["name"])
        if not best:
            return ""
        left, name = best
        if left == 0:
            return f"Today is {name}! 🎉" if long else f"📅 {name} today!"
        if long:
            return f"📅 {left} day{'s' if left != 1 else ''} until {name}!"
        return f"📅 {name[:14]} {left}d"

    # ---------------------------------------------------------------- house
    def _house_frame(self, st, now, ctx):
        p = self.pet
        size = int(p.S * 0.95)
        if self.house is None:
            self.house = sp.Sprite(True)
        if not p.wanted or (self.fun.gone is True):
            self.house.hide()
            return
        for ev in self.house.events:
            if ev[0] == "click":
                p._q.put(("fun", "more", "house_click"))
        self.house.events.clear()
        hour = ctx["hour"]
        night = hour >= 21 or hour < 6
        key = (tuple(sorted(o for o in self.life.d["owned"] if SHOP.get(o, ("", 0, ""))[2] == "decor")),
               night, self.inside == "sleep", size)
        if key != self.house_key:
            self.house_key = key
            self.house_img = house_image(size, set(key[0]), night, self.inside == "sleep")
        img = self.house_img
        self.house.show(img, p.bounds[0] + 6, p.bounds[3] - img.height)
        # going home
        if self.going_home and not p.walking and not p.flying:
            hx = self.house.x + self.house.w / 2 - p.W / 2
            if abs(p.x - hx) > 12:
                self.fun.walk_to(hx, 240)
            else:
                self.inside = self.going_home
                self.going_home = ""
                self.inside_until = now + (random.uniform(15, 30) if self.inside == "shy" else 10 ** 9)
                self.sound("chirp")
        if self.inside == "shy" and now > self.inside_until:
            self.come_out(st)
        if self.inside == "sleep" and st["idle"] < 2:
            self.come_out(st)
        # bedtime: sleep in the house
        if not self.inside and not self.going_home and (hour >= 23 or hour < 5) and st["idle"] > 360 \
                and not self.fun.busy_now() and not self.fun.night_wait:
            self._go_home(st, "sleep")

    def _go_home(self, st, why):
        if self.house is None:
            return
        self.fun.perch = None
        self.going_home = why
        if why == "shy":
            self.say(st, random.choice(["Eep! I'm shy 🙈", "Hehe, I'm going home for a bit! 🏠"]), 2.5)
        elif why == "sleep":
            self.say(st, "Sleepy… going to bed in my house 🏠😴", 3)

    # ---------------------------------------------------------------- rain / snow
    def _weather_fx(self, st, kind):
        self._fx_stop()
        p = self.pet
        drops = []
        for _ in range(26 if kind == "rain" else 30):
            s = self.fun.toy(False)
            img = drop_image(kind, p.scale)
            s.data = {"busy": True, "vy": random.uniform(900, 1300) if kind == "rain" else random.uniform(70, 150),
                      "vx": -120.0 if kind == "rain" else 0.0, "ph": random.uniform(0, 6.28)}
            s.show(img, random.uniform(p.bounds[0], p.bounds[2]), random.uniform(p.bounds[1] - 400, p.bounds[3]))
            drops.append(s)
        self.fx = {"kind": kind, "drops": drops, "end": time.perf_counter() + 40, "last": time.perf_counter()}
        self.say(st, "It's raining outside! ☔🌧️" if kind == "rain" else "Snow! ❄️☃️ So pretty!", 4)

    def _fx_frame(self, now):
        fx = self.fx
        p = self.pet
        dt = min(0.05, now - fx["last"])
        fx["last"] = now
        ending = now > fx["end"]
        alive = 0
        for s in fx["drops"]:
            if not s.visible:
                continue
            s.y += s.data["vy"] * dt
            s.x += s.data["vx"] * dt + (math.sin(now * 2 + s.data["ph"]) * 0.6 if fx["kind"] == "snow" else 0)
            if s.y > p.bounds[3]:
                if ending:
                    s.data = {}
                    s.hide()
                    continue
                s.y = p.bounds[1] - s.h - random.uniform(0, 200)
                s.x = random.uniform(p.bounds[0], p.bounds[2] + 200)
            s.show()
            alive += 1
        if ending and not alive:
            self.fx = None

    def _fx_stop(self):
        if self.fx:
            for s in self.fx["drops"]:
                s.data = {}
                s.hide()
            self.fx = None

    def maybe_weather_fx(self, st, weather: dict, active: bool):
        """Called now and then: it's actually raining / snowing outside -> show it for a while."""
        if not weather or not active or self.fx or self.party:
            return
        code = weather.get("code", 0)
        kind = "snow" if code in (71, 73, 75, 77, 85, 86) else ("rain" if weather.get("raining") else "")
        if not kind:
            return
        last = self.life.d.get("fx_at", 0)
        if time.time() - last > 3 * 3600:
            self.life.d["fx_at"] = time.time()
            self._weather_fx(st, kind)

    # ---------------------------------------------------------------- dance party
    def _party_frame(self, st, now, t):
        party = self.party
        p = self.pet
        left, top, right, bottom = p.bounds
        for i, s in enumerate(party["lights"]):
            a = t * s.data["sp"] + s.data["ph"]
            x = (left + right) / 2 + math.cos(a + i) * (right - left) * 0.38 - s.w / 2
            y = (top + bottom) / 2 + math.sin(a * 1.3 + i) * (bottom - top) * 0.35 - s.h / 2
            s.show(None, x, y)
        frame = party["frames"][int(t * 6) % 4]
        party["ball"].show(frame, (left + right) / 2 - frame.width / 2, top)
        if random.random() < 0.2:
            st["particles"].append(["note", random.uniform(-0.4, 0.4), -0.2, random.uniform(-0.05, 0.05), -0.2, 1.2])
        if random.random() < 0.05:
            self.fun._sparkle_burst(st)
        if now > party["end"]:
            for s in party["lights"] + [party["ball"]]:
                s.data = {}
                s.hide()
            self.party = None
            try:
                import winsound
                winsound.PlaySound(None, 0)
            except Exception:
                pass
            self.say(st, "Best party ever!! 🪩💃 Again sometime?", 4)
            self.fun.react(st, "love", 2)
            self.coins(st, 3)

    def world(self) -> dict:
        d = self.life.d
        goal = int(d.get("water_goal", 8))
        return {"coins": int(d.get("coins", 0)), "owned": list(d["owned"]),
                "shop": [{"id": k, "name": v[0], "price": v[1], "kind": v[2]} for k, v in SHOP.items()],
                "todos": list(d["todos"]), "water": int(self.life.today().get("water", 0)), "water_goal": goal,
                "countdowns": sorted(d["countdowns"], key=lambda c: c["date"]),
                "gemini": bool(getattr(self.pet, "gemini_key", ""))}
