"""
Reads the words on the main monitor with Windows' built-in OCR (free, offline, ~0.3 s).
Every word comes back with its position in real screen pixels, so BOT can click it.
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass

import mss
from PIL import Image
from winrt.windows.graphics.imaging import BitmapPixelFormat, SoftwareBitmap
from winrt.windows.media.ocr import OcrEngine
from winrt.windows.storage.streams import DataWriter

_MSS = getattr(mss, "MSS", None) or mss.mss
_engine = None


@dataclass
class Word:
    text: str
    x: float  # left, in real screen pixels
    y: float  # top
    w: float
    h: float


@dataclass
class Screen:
    lines: list[list[Word]]
    left: int
    top: int
    width: int
    height: int


def _get_engine():
    global _engine
    if _engine is None:
        _engine = OcrEngine.try_create_from_user_profile_languages()
        if _engine is None:
            raise RuntimeError("Windows OCR is not available on this PC")
    return _engine


async def _recognize(bmp):
    return await _get_engine().recognize_async(bmp)


def read_screen(upscale: float = 1.0) -> Screen:
    """OCR the main monitor. upscale > 1 helps with tiny text (slower)."""
    with _MSS() as sct:
        mon = sct.monitors[1]
        shot = sct.grab(mon)
    w, h = shot.size
    data = shot.bgra
    if upscale != 1.0:
        img = Image.frombytes("RGBA", (w, h), shot.bgra, "raw", "BGRA")
        w, h = round(w * upscale), round(h * upscale)
        img = img.resize((w, h), Image.LANCZOS)
        data = img.tobytes("raw", "BGRA")
    writer = DataWriter()
    writer.write_bytes(data)
    bmp = SoftwareBitmap.create_copy_from_buffer(writer.detach_buffer(), BitmapPixelFormat.BGRA8, w, h)
    result = asyncio.run(_recognize(bmp))
    k = 1.0 / upscale
    lines = []
    for line in result.lines:
        words = []
        for word in line.words:
            r = word.bounding_rect
            words.append(Word(word.text, mon["left"] + r.x * k, mon["top"] + r.y * k, r.width * k, r.height * k))
        if words:
            lines.append(words)
    return Screen(lines, mon["left"], mon["top"], mon["width"], mon["height"])
