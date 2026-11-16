"""
Turns a spoken sentence (English / Hindi / Kannada / Telugu) into a Match.
Pure logic with no side effects, so it can be unit-tested.
"""
from __future__ import annotations

import difflib
import re
import unicodedata
from dataclasses import dataclass
from functools import lru_cache

import phrases as P

_DROP = {0x200C: None, 0x200D: None, 0xFEFF: None}  # zero-width joiners / BOM
_NUKTA = "़"
_CHANDRABINDU, _ANUSVARA = "ँ", "ं"


def normalize(text: str) -> str:
    """Lowercase, unify Unicode spellings, turn punctuation into spaces."""
    text = unicodedata.normalize("NFC", text).translate(_DROP)
    text = text.replace(_NUKTA, "").replace(_CHANDRABINDU, _ANUSVARA).lower()
    text = "".join(" " if unicodedata.category(ch)[0] in "PSZC" else ch for ch in text)
    return " ".join(text.split())


def _norm_all(words) -> list[str]:
    out = []
    for w in words:
        n = normalize(w)
        if n and n not in out:
            out.append(n)
    return out


@lru_cache(maxsize=None)
def _pattern(kw: str) -> re.Pattern:
    # English: whole words. Indian scripts: match at the start of a word (stems).
    tail = r"(?=\s|$)" if kw.isascii() else r"\S*"
    return re.compile(r"(?:^|\s)" + re.escape(kw) + tail)


def has(text: str, kw: str) -> bool:
    return _pattern(kw).search(text) is not None


def longest(text: str, kws) -> str:
    best = ""
    for kw in kws:
        if len(kw) > len(best) and has(text, kw):
            best = kw
    return best


def strip_stems(text: str, kws) -> str:
    """Remove keywords (and, for Indian scripts, the rest of the word they start)."""
    for kw in sorted(kws, key=len, reverse=True):
        text = _pattern(kw).sub(" ", text)
    return " ".join(text.split())


def strip_words(text: str, words) -> str:
    drop = set(words)
    return " ".join(t for t in text.split() if t not in drop)


# ---- pre-normalised vocabulary ------------------------------------------------
OPEN = _norm_all(P.OPEN)
CLOSE = _norm_all(P.CLOSE)
SEARCH = _norm_all(P.SEARCH)
PLAY = _norm_all(P.PLAY)
TYPE = _norm_all(P.TYPE)
FILLERS = _norm_all(P.FILLERS)
TYPE_FILLERS = _norm_all(P.TYPE_FILLERS)
MUSIC = _norm_all(P.MUSIC)
APP_NAMES = {k: _norm_all(v["names"]) for k, v in P.APPS.items()}
SITE_NAMES = {k: _norm_all(v["names"]) for k, v in P.SITES.items()}
SIMPLE = [
    {
        "intent": s["intent"],
        "confirm": s.get("confirm", False),
        "priority": s.get("priority", 0),
        "rules": [[_norm_all(group) for group in rule] for rule in s["rules"]],
    }
    for s in P.SIMPLE
]
CONFIRM_INTENTS = {s["intent"] for s in SIMPLE if s["confirm"]}

# Ways people ask BOT to type something (English). First match wins; group 1 is the text.
_TYPE_EN = [
    # "type here is it done" / "write hello" / "say hello" / "enter my name"
    re.compile(r"^\s*(?:please\s+)?(?:type|write|enter|say)\s+(?:(?:here|there|this|it)\s*[:,]?\s+)?(.+)$", re.I | re.S),
    # "in the chat text box say is it done" / "in the search bar type cats"
    re.compile(r"^\s*(?:please\s+)?(?:in|into|on)\s+(?:the\s+)?(?:\w+\s+){0,2}(?:box|textbox|field|bar|area)"
               r"\s*,?\s*(?:say|type|write|enter|put)?\s+(.+)$", re.I | re.S),
    # "give a prompt saying is it done" / "reply to ram saying ok" / "a message that says hi"
    re.compile(r"\b(?:saying|that says|which says)\s+(.+)$", re.I | re.S),
]
NEW_TAB = _norm_all(["new tab", "नया टैब", "न्यू टैब", "ಹೊಸ ಟ್ಯಾಬ್", "ನ್ಯೂ ಟ್ಯಾಬ್", "కొత్త ట్యాబ్", "న్యూ ట్యాబ్"])
ALL_WORDS = _norm_all(["all", "every", "everything", "सब", "सारे", "सभी", "ಎಲ್ಲಾ", "ಎಲ್ಲ", "అన్ని", "అన్నీ"])
PRONOUNS = set(_norm_all(["it", "this", "that", "here", "there", "इसे", "उसे", "यह", "वह", "ಇದನ್ನು", "ಅದನ್ನು",
                          "ಇದು", "ಅದು", "దీన్ని", "దాన్ని", "ఇది", "అది"]))
LITTLE = _norm_all(["a little", "little", "a bit", "bit", "slightly", "thoda", "थोड़ा", "थोडा", "ಸ್ವಲ್ಪ", "కొంచెం"])
A_LOT = _norm_all(["a lot", "lot", "more", "much", "full", "बहुत", "ज्यादा", "ತುಂಬಾ", "ಜಾಸ್ತಿ", "చాలా", "ఎక్కువ"])
_DOMAIN = re.compile(r"((?:https?://)?(?:[a-z0-9-]+\.)+[a-z]{2,}(?:/\S*)?)", re.I)


@dataclass
class Match:
    intent: str
    arg: str = ""
    target: str = ""  # key into phrases.APPS / phrases.SITES

    @property
    def needs_confirm(self) -> bool:
        return self.intent in CONFIRM_INTENTS


def find_target(text: str, fuzzy: bool = True):
    """Find an app or website name. Returns (kind, key, matched_text) or None."""
    best = None
    # also try without English plurals: "close all notepads" -> notepad
    singular = " ".join(w[:-1] if len(w) > 4 and w.endswith("s") and w.isascii() else w for w in text.split())
    for kind, table in (("app", APP_NAMES), ("site", SITE_NAMES)):
        for key, names in table.items():
            for name in names:
                if (best is None or len(name) > len(best[2])) and (has(text, name) or has(singular, name)):
                    best = (kind, key, name)
    if best or not fuzzy:
        return best

    # Fuzzy fallback for Indian-script spellings ("ಯುಟ್ಯೂಬ್" vs "ಯೂಟ್ಯೂಬ್").
    toks = text.split()
    grams = {" ".join(toks[i:i + n]) for n in (1, 2, 3) for i in range(len(toks) - n + 1)}
    best_ratio = 0.0
    for kind, table in (("app", APP_NAMES), ("site", SITE_NAMES)):
        for key, names in table.items():
            for name in names:
                if name.isascii() or len(name) < 4:
                    continue
                for g in grams:
                    if g.isascii() or abs(len(g) - len(name)) > 3:
                        continue
                    r = difflib.SequenceMatcher(None, g, name).ratio()
                    if r >= 0.8 and r > best_ratio:
                        best_ratio, best = r, (kind, key, g)
    return best


def _clean(text: str, stems, words=()) -> str:
    return strip_words(strip_stems(text, stems), list(words))


# ---- matching steps (tried in order) -----------------------------------------

def _m_type(raw: str, t: str):
    for pattern in _TYPE_EN:
        m = pattern.search(raw)
        if m and m.group(1).strip(" ,.:"):
            return Match("type_text", arg=m.group(1).strip().strip('"“”'))
    if longest(t, TYPE):
        return Match("type_text", arg=_clean(t, TYPE, TYPE_FILLERS))
    return None


def _m_url(raw: str, t: str):
    m = _DOMAIN.search(raw)
    if not m:
        return None
    rest = _clean(normalize(raw.replace(m.group(1), " ")), OPEN, FILLERS + ["go"])
    if longest(t, OPEN) or not rest:
        url = m.group(1)
        if not url.lower().startswith("http"):
            url = "https://" + url
        return Match("open_url", arg=url)
    return None


def _m_youtube(raw: str, t: str):
    yt = SITE_NAMES["youtube"]
    if not longest(t, yt) or not (longest(t, SEARCH) or longest(t, PLAY)):
        return None
    q = _clean(t, yt + SEARCH + PLAY + OPEN, FILLERS)
    return Match("youtube_search", arg=q) if q else None


def _m_search(raw: str, t: str):
    google = SITE_NAMES["google"]
    first = t.split()[0]
    google_verb = any(has(first, g) for g in google) and len(t.split()) > 1 and not longest(t, OPEN)
    if not (longest(t, SEARCH) or google_verb):
        return None
    q = _clean(t, SEARCH + google + OPEN, FILLERS)
    return Match("google_search", arg=q) if q else None


def _m_close(raw: str, t: str):
    if not longest(t, CLOSE):
        return None
    found = find_target(t)
    if not found:
        return None
    kind, key, _ = found
    if kind == "site":
        return Match("close_tab", target=key)
    if P.APPS[key].get("process"):
        # "close notepad" closes one window; "close all notepads" closes every one
        return Match("close_app", target=key, arg="all" if longest(t, ALL_WORDS) else "")
    return Match("close_window", target=key)


def _m_new_tab(raw: str, t: str):
    # "open a new tab in notepad" means ctrl+T, not "open notepad again"
    return Match("new_tab") if longest(t, NEW_TAB) else None


def _m_open(raw: str, t: str):
    if not longest(t, OPEN):
        return None
    found = find_target(t)
    if not found:
        return None
    kind, key, _ = found
    return Match("open_app" if kind == "app" else "open_site", target=key)


def _m_play_query(raw: str, t: str):
    if not longest(t, PLAY):
        return None
    simple = match_simple(t)
    if simple and simple.intent != "play_pause":
        return None
    if not _clean(t, PLAY, FILLERS + MUSIC):
        return None  # just "play" / "play music" -> press play
    return Match("youtube_search", arg=_clean(t, PLAY, FILLERS))


def match_simple(t: str):
    best, best_score = None, None
    for spec in SIMPLE:
        for rule in spec["rules"]:
            total = 0
            for group in rule:
                hit = longest(t, group)
                if not hit:
                    break
                total += len(hit)
            else:
                score = (len(rule), spec["priority"], total)
                if best_score is None or score > best_score:
                    best, best_score = spec, score
    return Match(best["intent"]) if best else None


def _m_open_unknown(t: str):
    if not longest(t, OPEN):
        return None
    left = _clean(t, OPEN, FILLERS)
    if not left:
        return None
    if left in PRONOUNS:  # "open it" / "open that" = open the selected thing
        return Match("enter")
    return Match("start_menu" if left.isascii() else "unknown_app", arg=left)


def _m_bare(t: str):
    found = find_target(t, fuzzy=False)
    if not found:
        return None
    kind, key, name = found
    if _clean(t, [name], FILLERS):
        return None
    return Match("open_app" if kind == "app" else "open_site", target=key)


def match(raw: str) -> Match | None:
    t = normalize(raw)
    if not t:
        return None
    for step in (_m_type, _m_url, _m_new_tab, _m_youtube, _m_search, _m_close, _m_open, _m_play_query):
        m = step(raw, t)
        if m:
            return m
    m = match_simple(t) or _m_open_unknown(t) or _m_bare(t)
    if m and m.intent in ("scroll_up", "scroll_down"):  # "come down a little" / "scroll down a lot"
        m.arg = "little" if longest(t, LITTLE) else "lot" if longest(t, A_LOT) else ""
    if m and m.intent in KEY_ACTIONS:
        # Only short commands: "send it" presses Enter, but "send a mail to rahul" is a different task.
        if len(t.split()) > 4:
            return None
        if m.intent == "delete_key" and longest(t, PERMANENT):
            m.arg = "permanent"
    return m


KEY_ACTIONS = {"send_enter", "delete_key"}
PERMANENT = _norm_all(["permanently", "forever", "permanent", "हमेशा के लिए", "ಶಾಶ್ವತವಾಗಿ", "శాశ్వతంగా"])
