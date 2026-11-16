"""
The safety word: a secret word YOU choose, which BOT asks for before anything that deletes,
sends, shares, posts, uploads, pays or uninstalls. Only a salted hash is stored (in config.json),
never the word itself.
"""
from __future__ import annotations

import hashlib
import hmac
import os

from matcher import longest, normalize, _norm_all

# Words that make a request "sensitive" (English whole words; Indian-language word stems).
SENSITIVE = _norm_all([
    # English
    "delete", "deleting", "remove", "erase", "wipe", "trash", "empty the recycle bin", "format",
    "uninstall", "send", "sending", "share", "sharing", "post", "upload", "forward", "reply",
    "tweet", "publish", "pay", "payment", "buy", "purchase", "order", "transfer", "checkout",
    # Hindi
    "डिलीट", "हटा", "मिटा", "भेज", "शेयर", "पोस्ट", "अपलोड", "फॉरवर्ड", "रिप्लाई", "जवाब",
    "खरीद", "पेमेंट", "भुगतान", "ऑर्डर", "अनइंस्टॉल", "फॉर्मेट", "ट्रांसफर",
    # Kannada
    "ಡಿಲೀಟ್", "ಅಳಿಸ", "ತೆಗೆದುಹಾಕ", "ಕಳುಹಿಸ", "ಕಳಿಸ", "ಶೇರ್", "ಹಂಚಿಕೊ", "ಪೋಸ್ಟ್", "ಅಪ್‌ಲೋಡ್",
    "ಫಾರ್ವರ್ಡ್", "ಖರೀದಿ", "ಪೇಮೆಂಟ್", "ಪಾವತಿ", "ಆರ್ಡರ್", "ಅನ್‌ಇನ್‌ಸ್ಟಾಲ್", "ಫಾರ್ಮ್ಯಾಟ್",
    # Telugu
    "డిలీట్", "తొలగించ", "తీసేయ", "పంప", "షేర్", "పోస్ట్", "అప్‌లోడ్", "ఫార్వర్డ్", "కొను", "కొన",
    "పేమెంట్", "చెల్లించ", "ఆర్డర్", "అన్‌ఇన్‌స్టాల్", "ఫార్మాట్",
])


def is_sensitive(text: str) -> bool:
    return bool(longest(normalize(text), SENSITIVE))


def is_set(cfg: dict) -> bool:
    return bool(cfg.get("safety_word_hash") and cfg.get("safety_word_salt"))


def _hash(word: str, salt_hex: str) -> str:
    return hashlib.pbkdf2_hmac("sha256", normalize(word).encode("utf-8"), bytes.fromhex(salt_hex), 200_000).hex()


def verify(cfg: dict, word: str) -> bool:
    if not is_set(cfg) or not normalize(word):
        return False
    return hmac.compare_digest(_hash(word, cfg["safety_word_salt"]), cfg["safety_word_hash"])


def set_word(cfg: dict, new: str, old: str = "") -> tuple[bool, str]:
    """Set or change the safety word (changing needs the current one). Caller saves cfg."""
    if len(normalize(new).replace(" ", "")) < 3:
        return False, "Pick a safety word with at least 3 letters."
    if is_set(cfg) and not verify(cfg, old):
        return False, "Your current safety word is wrong."
    salt = os.urandom(16).hex()
    cfg["safety_word_salt"] = salt
    cfg["safety_word_hash"] = _hash(new, salt)
    return True, "Safety word saved. I'll ask for it before deleting, sending, sharing or paying."
