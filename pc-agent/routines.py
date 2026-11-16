"""
Routines: one phrase runs several commands. "good night" -> close everything, lock.
Each step is written exactly like something you'd say to BOT. You can edit them in the app
(⋮ menu -> Routines); they're saved in config.json under "routines".
"""
from __future__ import annotations

from matcher import has, normalize

DEFAULT_ROUTINES = [
    {
        "name": "good night",
        "aliases": ["goodnight", "गुड नाइट", "शुभ रात्रि", "ಗುಡ್ ನೈಟ್", "ಶುಭ ರಾತ್ರಿ", "గుడ్ నైట్", "శుభ రాత్రి"],
        "steps": ["close everything", "lock the computer"],
    },
    {
        "name": "study mode",
        "aliases": ["study time", "स्टडी मोड", "पढ़ाई मोड", "ಸ್ಟಡಿ ಮೋಡ್", "ಓದುವ ಸಮಯ", "స్టడీ మోడ్", "చదువు సమయం"],
        "steps": ["close youtube", "open vs code"],
    },
]
TRIGGER_FILLERS = {"start", "run", "do", "begin", "activate", "routine", "please", "bot", "now", "the", "my",
                   "शुरू", "करो", "चालू", "ಶುರು", "ಮಾಡು", "ప్రారంభించు", "చేయి"}


def get(cfg: dict) -> list[dict]:
    routines = cfg.get("routines")
    if not isinstance(routines, list):
        routines = [dict(r) for r in DEFAULT_ROUTINES]
    return routines


def clean(items) -> list[dict]:
    """Validate routines sent from the app."""
    out = []
    for r in items if isinstance(items, list) else []:
        if not isinstance(r, dict):
            continue
        name = str(r.get("name", "")).strip()[:40]
        steps = [str(s).strip()[:200] for s in r.get("steps", []) if str(s).strip()][:15]
        aliases = [str(a).strip()[:40] for a in r.get("aliases", []) if str(a).strip()][:10]
        if name and steps:
            out.append({"name": name, "aliases": aliases, "steps": steps})
    return out[:20]


def match(cfg: dict, text: str) -> dict | None:
    """Is this the name of a routine? ("good night", "start study mode", "शुभ रात्रि")"""
    t = normalize(text)
    words = [w for w in t.split() if w not in TRIGGER_FILLERS]
    rest = " ".join(words)
    for r in get(cfg):
        for phrase in [r["name"], *r.get("aliases", [])]:
            p = normalize(phrase)
            if p and (rest == p or t == p or (has(t, p) and len(words) <= len(p.split()) + 1)):
                return r
    return None
