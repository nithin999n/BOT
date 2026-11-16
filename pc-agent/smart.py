"""
Free "smart mode": no AI needed.

  * Click anything by its name: "select Gmail", "click Sign in", "Gmail पर क्लिक करो".
    BOT reads the screen (Windows OCR), finds the words, and the bubble glides there and clicks.
  * Position hints: "go to the top right and select Gmail" picks the Gmail in the top-right area.
  * Chains: "open chrome and go to gmail and click compose" runs the steps one by one.
"""
from __future__ import annotations

import difflib
import re
import threading
import time
import unicodedata
from dataclasses import dataclass, field

import actions
import matcher
import win_input
from matcher import Match, _clean, _norm_all, find_target, longest, normalize
from overlay import BUBBLE
import phrases as P

# ---- vocabulary --------------------------------------------------------------------
POSITIONS = {
    "top_right": ["top right", "upper right", "top right corner", "ऊपर दाएं", "ऊपर दाईं", "दाएं ऊपर",
                  "ಮೇಲೆ ಬಲ", "ಬಲ ಮೇಲೆ", "ಮೇಲಿನ ಬಲ", "పైన కుడి", "కుడి పైన"],
    "top_left": ["top left", "upper left", "top left corner", "ऊपर बाएं", "ऊपर बाईं", "बाएं ऊपर",
                 "ಮೇಲೆ ಎಡ", "ಎಡ ಮೇಲೆ", "ಮೇಲಿನ ಎಡ", "పైన ఎడమ", "ఎడమ పైన"],
    "bottom_right": ["bottom right", "lower right", "नीचे दाएं", "नीचे दाईं", "ಕೆಳಗೆ ಬಲ", "ಕೆಳಗಿನ ಬಲ",
                     "కింద కుడి", "క్రింద కుడి"],
    "bottom_left": ["bottom left", "lower left", "नीचे बाएं", "नीचे बाईं", "ಕೆಳಗೆ ಎಡ", "ಕೆಳಗಿನ ಎಡ",
                    "కింద ఎడమ", "క్రింద ఎడమ"],
    "top": ["top", "at the top", "ऊपर", "ಮೇಲೆ", "ಮೇಲ್ಭಾಗ", "పైన", "పై భాగం"],
    "bottom": ["bottom", "at the bottom", "नीचे", "ಕೆಳಗೆ", "ಕೆಳಭಾಗ", "కింద", "క్రింద"],
    "left": ["left", "left side", "बाएं", "बाईं", "ಎಡ", "ಎಡಭಾಗ", "ఎడమ"],
    "right": ["right", "right side", "दाएं", "दाईं", "ಬಲ", "ಬಲಭಾಗ", "కుడి"],
    "center": ["center", "centre", "middle", "बीच", "बीच में", "ಮಧ್ಯ", "ಮಧ್ಯದಲ್ಲಿ", "మధ్య", "మధ్యలో"],
}
CLICK = ["click", "click on", "tap", "tap on", "press", "select", "choose", "hit", "open the",
         "क्लिक", "चुन", "सेलेक्ट", "दबा", "ಕ್ಲಿಕ್", "ಆಯ್ಕೆ", "ಸೆಲೆಕ್ಟ್", "ಒತ್ತ", "క్లిక్", "ఎంచుకో", "ఎంచుక",
         "సెలెక్ట్", "నొక్క"]
DOUBLE = ["double click", "double tap", "डबल क्लिक", "ಡಬಲ್ ಕ್ಲಿಕ್", "డబుల్ క్లిక్"]
RIGHT = ["right click", "राइट क्लिक", "ರೈಟ್ ಕ್ಲಿಕ್", "రైట్ క్లిక్"]
GO = ["go to", "goto", "navigate to", "move to", "जाओ", "पर जाओ", "में जाओ", "ಗೆ ಹೋಗು", "ಹೋಗು",
      "కి వెళ్ళు", "కు వెళ్ళు", "వెళ్ళు"]
TARGET_FILLERS = ["the", "a", "an", "on", "button", "link", "tab", "option", "icon", "word", "text",
                  "corner", "side", "at", "pe",
                  "पर", "को", "का", "की", "के", "में", "बटन", "लिंक", "करो", "कर", "दो", "वाले", "वाला",
                  "ಮೇಲೆ", "ಬಟನ್", "ಲಿಂಕ್", "ಮಾಡು", "ಮಾಡಿ", "ಅನ್ನು", "ನ್ನು", "ನಲ್ಲಿ",
                  "పై", "మీద", "బటన్", "లింక్", "చేయి", "చేయండి", "ని", "ను", "లో"]
# Split a sentence into steps on these words.
SPLITTERS = ["and then", "then", "and", "after that", "और फिर", "उसके बाद", "और", "फिर", "ಮತ್ತು", "ನಂತರ", "ಆಮೇಲೆ",
             "మరియు", "ఆ తర్వాత", "ఆపై"]

_POS_N = {k: _norm_all(v) for k, v in POSITIONS.items()}
_ALL_POS = [p for v in _POS_N.values() for p in v]
_CLICK_N, _DOUBLE_N, _RIGHT_N, _GO_N = (_norm_all(x) for x in (CLICK, DOUBLE, RIGHT, GO))
_FILL_N = _norm_all(TARGET_FILLERS)
_SPLIT_RE = re.compile(r"\s*(?:,\s*)?\b(?:" + "|".join(re.escape(s) for s in sorted(
    [s for s in SPLITTERS if s.isascii()], key=len, reverse=True)) + r")\b\s*"
    + "|" + r"\s+(?:" + "|".join(re.escape(s) for s in sorted(
        [s for s in SPLITTERS if not s.isascii()], key=len, reverse=True)) + r")\s+", re.I)
POINTER_INTENTS = {"click", "double_click", "right_click"}
FREE_TEXT = {"google_search", "youtube_search", "type_text"}


# ---- steps -------------------------------------------------------------------------
@dataclass
class ClickStep:
    names: list[str]          # what to look for on screen (Latin text), e.g. ["gmail"]
    said: str                 # what the user said, for messages
    kind: str = "left"        # left | double | right
    hint: str | None = None   # top_right, top, left, ...


@dataclass
class HintStep:
    hint: str                 # "go to the top right" (applies to the next click)


@dataclass
class Plan:
    steps: list = field(default_factory=list)

    @property
    def is_single_builtin(self) -> bool:
        return len(self.steps) == 1 and isinstance(self.steps[0], Match)


def translit(text: str) -> str:
    """Rough Hindi/Kannada/Telugu -> Latin ("साइन इन" -> "sain in") to match English screen text."""
    out: list[str] = []
    for ch in unicodedata.normalize("NFC", text):
        try:
            name = unicodedata.name(ch)
        except ValueError:
            out.append(ch)
            continue
        parts = name.split()
        if "VOWEL SIGN" in name:
            if out and out[-1].endswith("a"):
                out[-1] = out[-1][:-1]
            out.append(parts[-1].lower())
        elif "VIRAMA" in name:
            if out and out[-1].endswith("a"):
                out[-1] = out[-1][:-1]
        elif "ANUSVARA" in name or "CANDRABINDU" in name:
            out.append("n")
        elif "LETTER" in parts and parts[0] in ("DEVANAGARI", "KANNADA", "TELUGU"):
            out.append(parts[-1].lower())
        elif parts[0] in ("DEVANAGARI", "KANNADA", "TELUGU"):
            continue  # nukta, visarga, signs
        else:
            out.append(ch)
    s = "".join(out)
    s = re.sub(r"a\b", "", s)  # Hindi drops the final 'a' (kamal, not kamala)
    for a, b in (("aa", "a"), ("ii", "i"), ("uu", "u"), ("ee", "e"), ("oo", "o")):
        s = s.replace(a, b)
    return s


def _names_for(target: str) -> tuple[list[str], bool]:
    """Screen words to look for. Returns (names, exact_spelling_known)."""
    if target.isascii():
        return [target], True
    found = find_target(target, fuzzy=True)  # known app/site said in an Indian script, e.g. "जीमेल"
    if found:
        kind, key, _ = found
        table = P.APPS if kind == "app" else P.SITES
        latin = [n for n in table[key]["names"] if n.isascii()]
        if latin:
            return latin, True
    return [translit(target)], False


def parse_click(part: str):
    """'select gmail' / 'go to the top right' / 'Gmail पर क्लिक करो' -> ClickStep / HintStep / None."""
    t = normalize(part)
    hint = None
    found: list[str] = []
    for key, words in _POS_N.items():  # corners are listed first, so "top right" beats "top"
        w = longest(t, words)
        if w:
            if hint is None:
                hint = key
            found.append(w)
    kind = "double" if longest(t, _DOUBLE_N) else "right" if longest(t, _RIGHT_N) else "left"
    has_click = bool(longest(t, _CLICK_N) or kind != "left")
    has_go = bool(longest(t, _GO_N))
    if not (has_click or has_go):
        return None
    target = _clean(t, _DOUBLE_N + _RIGHT_N + _CLICK_N + _GO_N + found, _FILL_N)
    if not target:
        return HintStep(hint) if hint else None
    if has_go and not has_click:
        found = find_target(target, fuzzy=False)
        if found and normalize(_clean(target, [found[2]], _FILL_N)) == "":
            kind_, key, _ = found
            return Match("open_app" if kind_ == "app" else "open_site", target=key)
    names, _ = _names_for(target)
    return ClickStep(names=names, said=target, kind=kind, hint=hint)


# When you say "click/select/go to <something>", a built-in command only wins if it's one of these
# harmless ones ("select all", "go to desktop", "click new tab"...). Never restart/shutdown/lock etc.
BUILTIN_BEATS_CLICK = {
    "select_all", "enter", "scroll_up", "scroll_down", "show_desktop", "new_tab", "close_tab", "copy",
    "paste", "undo", "refresh", "go_back", "open_app", "open_site", "open_url", "type_text",
    "google_search", "youtube_search", "bubble_on", "bubble_off",
}


def parse_step(part: str):
    part = part.strip(" ,.")
    if not part:
        return None
    m = matcher.match(part)
    c = parse_click(part)
    if isinstance(c, ClickStep):
        if c.said in matcher.PRONOUNS:  # "click that" / "click here" = click where the mouse is
            return Match({"double": "double_click", "right": "right_click"}.get(c.kind, "click"))
        if m is None or m.intent not in BUILTIN_BEATS_CLICK:
            return c
        return m
    if m is not None and m.intent not in POINTER_INTENTS:
        return m
    return c or m


def split_steps(text: str) -> list[str]:
    return [p for p in _SPLIT_RE.split(text) if p and p.strip(" ,.")]


def plan(text: str) -> Plan | None:
    """Turn a sentence into steps, or None if any part isn't understood."""
    parts = split_steps(text)
    steps: list = []
    raw: list[str] = []
    for part in parts:
        step = parse_step(part)
        if step is None and raw:
            # "search cats and dogs": 'dogs' alone means nothing -> glue it back to a search/type step
            merged = f"{raw[-1]} and {part}"
            step = parse_step(merged)
            if not (isinstance(step, Match) and step.intent in FREE_TEXT):
                return None
            steps[-1], raw[-1] = step, merged
            continue
        if step is None:
            return None
        steps.append(step)
        raw.append(part)
    # Position hints apply to the click that follows them.
    out: list = []
    pending = None
    for step in steps:
        if isinstance(step, HintStep):
            pending = step.hint
            continue
        if isinstance(step, ClickStep) and step.hint is None and pending:
            step.hint = pending
        pending = None
        # "open youtube and search X" -> search on YouTube
        if (isinstance(step, Match) and step.intent == "google_search" and out
                and isinstance(out[-1], Match) and out[-1].target == "youtube"):
            step = Match("youtube_search", arg=step.arg)
        out.append(step)
    if pending and not out:
        out.append(HintStep(pending))
    return Plan(out) if out else None


# ---- finding text on screen ------------------------------------------------------
def _norm_word(s: str) -> str:
    return re.sub(r"[^\w\s]", "", s.lower()).strip()


def _in_region(cx: float, cy: float, scr, hint: str | None) -> bool:
    if not hint:
        return True
    x = (cx - scr.left) / scr.width
    y = (cy - scr.top) / scr.height
    checks = {
        "top": y < 0.4, "bottom": y > 0.6, "left": x < 0.45, "right": x > 0.55,
        "center": 0.2 < x < 0.8 and 0.2 < y < 0.8,
    }
    return all(checks[p] for p in hint.split("_"))


def find_on_screen(scr, names: list[str], hint: str | None, exact_known: bool = True):
    """Candidates [(score, cx, cy, text)], best first."""
    threshold = 0.8 if exact_known else 0.65
    found = []
    for line in scr.lines:
        texts = [_norm_word(w.text) for w in line]
        for name in names:
            n_words = max(1, len(name.split()))
            for i in range(len(line) - n_words + 1):
                phrase = " ".join(t for t in texts[i:i + n_words] if t)
                if not phrase:
                    continue
                if phrase == name:
                    score = 1.0
                elif len(name) >= 4 and name in phrase.split():
                    score = 0.95
                else:
                    score = difflib.SequenceMatcher(None, phrase, name).ratio()
                if score < threshold:
                    continue
                span = line[i:i + n_words]
                x0 = min(w.x for w in span)
                y0 = min(w.y for w in span)
                x1 = max(w.x + w.w for w in span)
                y1 = max(w.y + w.h for w in span)
                cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
                if _in_region(cx, cy, scr, hint):
                    found.append((score, cx, cy, " ".join(w.text for w in span)))
    corner = None
    if hint:
        fx = 1.0 if "right" in hint else 0.0 if "left" in hint else 0.5
        fy = 0.0 if "top" in hint else 1.0 if "bottom" in hint else 0.5
        corner = (scr.left + fx * scr.width, scr.top + fy * scr.height)

    def key(c):
        score, cx, cy, _ = c
        dist = ((cx - corner[0]) ** 2 + (cy - corner[1]) ** 2) ** 0.5 if corner else cy * 3 + cx
        return (-round(score, 2), dist)
    return sorted(found, key=key)


# ---- running a plan --------------------------------------------------------------
class Stopped(Exception):
    pass


class Runner:
    """Runs one smart plan at a time; stoppable."""

    def __init__(self):
        self.busy = False
        self.owner = None
        self._stop = threading.Event()

    def stop(self) -> None:
        self._stop.set()

    def run(self, p: Plan, progress, owner=None) -> tuple[bool, str]:
        self.busy, self.owner = True, owner
        self._stop.clear()
        done: list[str] = []
        try:
            for i, step in enumerate(p.steps):
                if self._stop.is_set():
                    raise Stopped("Stopped.")
                if isinstance(step, Match):
                    progress(f"Step {i + 1}/{len(p.steps)}: {step.intent.replace('_', ' ')}…")
                    ok, msg = actions.execute(step)
                    if step.intent in ("open_app", "open_site", "open_url", "start_menu", "new_tab"):
                        self._sleep(1.5)  # give it a moment to open
                elif isinstance(step, ClickStep):
                    ok, msg = self.click_text(step, progress)
                elif isinstance(step, HintStep):
                    ok, msg = self.move_to_area(step.hint)
                else:
                    ok, msg = False, "I don't know how to do that step."
                if not ok:
                    prefix = f"Step {i + 1} of {len(p.steps)}: " if len(p.steps) > 1 else ""
                    return False, prefix + msg
                done.append(msg)
            return True, " → ".join(done) if len(done) > 1 else (done[0] if done else "Done.")
        except Stopped as exc:
            BUBBLE.pop("Stopped", ok=False, hold=1.5)
            return False, str(exc)
        finally:
            self.busy, self.owner = False, None

    def _sleep(self, seconds: float) -> None:
        end = time.monotonic() + seconds
        while time.monotonic() < end:
            if self._stop.is_set() or win_input.esc_pressed():
                raise Stopped("Stopped.")
            time.sleep(0.1)

    def click_text(self, step: ClickStep, progress, timeout: float = 8.0) -> tuple[bool, str]:
        import ocr  # Windows OCR (only needed for this)
        where = f" ({step.hint.replace('_', ' ')})" if step.hint else ""
        progress(f"Looking for “{step.said}”{where}…")
        BUBBLE.pop(f"Looking for {step.names[0]}", hold=1.5)
        exact = step.names != [step.said] or step.said.isascii()
        deadline = time.monotonic() + timeout
        attempt = 0
        while True:
            if self._stop.is_set() or win_input.esc_pressed():
                raise Stopped("Stopped.")
            scale = 1.0 if attempt % 2 == 0 else 1.6  # alternate: normal / zoomed-in read (tiny text)
            scr = ocr.read_screen(upscale=scale)
            hits = find_on_screen(scr, step.names, step.hint, exact)
            if hits:
                _, cx, cy, text = hits[0]
                label = {"double": "Double-clicking", "right": "Right-clicking"}.get(step.kind, "Clicking")
                if not BUBBLE.glide_to(cx, cy, f"{label} {text}"):
                    raise Stopped("You took over the mouse, so I stopped.")
                win_input.move_to(cx, cy)
                if step.kind == "right":
                    win_input.click("right")
                else:
                    win_input.click("left", double=step.kind == "double")
                BUBBLE.pulse()
                more = f" (there were {len(hits)}; say 'top right', 'bottom left'… to pick another)" \
                    if len(hits) > 1 and not step.hint else ""
                return True, f"Clicked “{text}”{more}"
            attempt += 1
            if time.monotonic() > deadline:
                BUBBLE.pop(f"Can't find {step.names[0]}", ok=False, hold=2)
                return False, f"I couldn't find “{step.said}”{where} on the screen."
            self._sleep(0.5)

    def move_to_area(self, hint: str) -> tuple[bool, str]:
        left, top, w, h = win_input.primary_screen()
        fx = 0.9 if "right" in hint else 0.1 if "left" in hint else 0.5
        fy = 0.1 if "top" in hint else 0.9 if "bottom" in hint else 0.5
        x, y = left + fx * w, top + fy * h
        if not BUBBLE.glide_to(x, y, hint.replace("_", " ")):
            raise Stopped("You took over the mouse, so I stopped.")
        win_input.move_to(x, y)
        return True, f"Moved to the {hint.replace('_', ' ')}"


RUNNER = Runner()
