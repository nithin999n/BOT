"""Captures the main monitor as small JPEG frames for the phone's live screen view."""
from __future__ import annotations

import hashlib
import io

import mss
from PIL import Image

# quality name -> (max width px, JPEG quality, max frames per second)
QUALITY = {
    "low": (640, 40, 4),      # good for mobile data
    "medium": (960, 55, 8),
    "high": (1280, 70, 12),
}


def grab(quality: str, last_digest: bytes | None = None):
    """Returns (jpeg_bytes or None if unchanged, (left, top, width, height), digest)."""
    max_w, jpeg_q, _ = QUALITY.get(quality, QUALITY["medium"])
    with mss.mss() as sct:  # one per call: mss objects can't be shared between threads
        mon = sct.monitors[1]
        shot = sct.grab(mon)
    img = Image.frombytes("RGB", shot.size, shot.bgra, "raw", "BGRX")
    if img.width > max_w:
        img = img.resize((max_w, max(1, round(img.height * max_w / img.width))), Image.BILINEAR)
    digest = hashlib.blake2b(img.tobytes(), digest_size=8).digest()
    geom = (mon["left"], mon["top"], mon["width"], mon["height"])
    if digest == last_digest:
        return None, geom, digest
    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=jpeg_q)
    return buf.getvalue(), geom, digest
