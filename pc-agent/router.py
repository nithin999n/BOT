"""
Decides who handles what you said:
  * the quick built-in commands (instant, free, offline), or
  * the AI brain (any task, step by step, needs an Anthropic API key).
"""
from __future__ import annotations

from matcher import Match, longest, normalize, _norm_all

# Built-in commands whose argument is free text ("search <anything>"): keep them built-in.
FREE_TEXT_INTENTS = {"google_search", "youtube_search", "type_text"}

# Words that mean "several steps" -> let the AI plan it.
# "then"-words always do; a plain "and" is fine inside a search ("search cats and dogs").
THEN = _norm_all(["then", "and then", "after that", "फिर", "उसके बाद", "ನಂತರ", "ಆಮೇಲೆ", "ఆ తర్వాత", "ఆపై"])
AND = _norm_all(["and", "और", "ಮತ್ತು", "మరియు"])

# Words that mean "find something on the screen and act on it" -> AI.
ON_SCREEN = _norm_all([
    "select", "choose", "click on", "click the", "go to", "navigate", "find", "fill", "top right",
    "top left", "bottom right", "bottom left", "button", "link", "icon", "menu", "tab named",
    "सेलेक्ट", "चुनो", "चुनें", "पर क्लिक", "ढूंढो", "बटन", "ಆಯ್ಕೆ", "ಸೆಲೆಕ್ಟ್", "ಮೇಲೆ ಕ್ಲಿಕ್", "ಬಟನ್",
    "ఎంచుకో", "సెలెక్ట్", "పై క్లిక్", "బటన్",
])

STOP_WORDS = set(_norm_all([
    "stop", "cancel", "stop it", "stop stop", "abort", "रुको", "रोको", "बस", "स्टॉप", "ನಿಲ್ಲಿಸು", "ಸಾಕು",
    "ಸ್ಟಾಪ್", "ఆపు", "ఆపండి", "చాలు", "స్టాప్",
]))


def is_stop(text: str) -> bool:
    return normalize(text) in STOP_WORDS


def prefer_builtin(text: str, m: Match) -> bool:
    """True if the quick built-in command is clearly enough for what was said."""
    t = normalize(text)
    if m.intent == "type_text":
        return True  # whatever follows "type" is the text itself
    if longest(t, THEN):
        return False
    if m.intent in FREE_TEXT_INTENTS:
        return True
    if longest(t, AND) or longest(t, ON_SCREEN):
        return False
    return len(t.split()) <= 6
