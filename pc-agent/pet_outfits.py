"""Little outfits for the desktop BOT, drawn with Pillow on top of its body."""
from __future__ import annotations

import math

HAT_HEIGHT = 0.45  # how far above the body (in body heights) the tallest hat reaches


def _star(cx, cy, r, points=5, inner=0.45, rot=-math.pi / 2):
    return [(cx + math.cos(rot + i * math.pi / points) * (r if i % 2 == 0 else r * inner),
             cy + math.sin(rot + i * math.pi / points) * (r if i % 2 == 0 else r * inner))
            for i in range(points * 2)]


def draw(d, kind: str, x0: float, y0: float, bw: float, bh: float, eyes: list, er: float, ss: float, t: float):
    """d: ImageDraw (RGBA). (x0, y0, bw, bh): the body box. eyes: [(x, y), (x, y)]."""
    if kind == "party":
        tip = (x0 + bw * 0.6, y0 - bh * 0.4)
        base_l, base_r = (x0 + bw * 0.36, y0 + bh * 0.07), (x0 + bw * 0.84, y0 + bh * 0.02)
        d.polygon([tip, base_l, base_r], fill=(180, 120, 255, 255))
        for k in (0.35, 0.65):  # stripes
            a = (tip[0] + (base_l[0] - tip[0]) * k, tip[1] + (base_l[1] - tip[1]) * k)
            b = (tip[0] + (base_r[0] - tip[0]) * k, tip[1] + (base_r[1] - tip[1]) * k)
            d.line([a, b], fill=(255, 225, 90, 255), width=int(3 * ss))
        r = bw * 0.06
        d.ellipse((tip[0] - r, tip[1] - r, tip[0] + r, tip[1] + r), fill=(255, 225, 90, 255))
    elif kind == "santa":
        tip = (x0 + bw * 0.96, y0 - bh * 0.12 + math.sin(t * 2) * bh * 0.02)
        d.polygon([(x0 + bw * 0.18, y0 + bh * 0.1), (x0 + bw * 0.5, y0 - bh * 0.32), tip,
                   (x0 + bw * 0.82, y0 + bh * 0.06)], fill=(230, 50, 60, 255))
        d.rounded_rectangle((x0 + bw * 0.12, y0 + bh * 0.02, x0 + bw * 0.88, y0 + bh * 0.17), radius=bh * 0.07,
                            fill=(255, 255, 255, 255))
        r = bw * 0.075
        d.ellipse((tip[0] - r, tip[1] - r, tip[0] + r, tip[1] + r), fill=(255, 255, 255, 255))
    elif kind == "cap":  # sleeping nightcap
        tip = (x0 + bw * 0.05, y0 + bh * 0.05 + math.sin(t * 1.5) * bh * 0.02)
        d.polygon([(x0 + bw * 0.2, y0 + bh * 0.1), (x0 + bw * 0.45, y0 - bh * 0.3), tip,
                   (x0 + bw * 0.8, y0 + bh * 0.08)], fill=(110, 90, 210, 255))
        d.line([(x0 + bw * 0.3, y0 - bh * 0.05), (x0 + bw * 0.62, y0 - bh * 0.02)], fill=(250, 220, 120, 255),
               width=int(3 * ss))
        d.rounded_rectangle((x0 + bw * 0.15, y0 + bh * 0.03, x0 + bw * 0.85, y0 + bh * 0.15), radius=bh * 0.06,
                            fill=(245, 240, 255, 255))
        r = bw * 0.065
        d.ellipse((tip[0] - r, tip[1] - r, tip[0] + r, tip[1] + r), fill=(250, 220, 120, 255))
    elif kind == "crown":
        bx0, bx1, by = x0 + bw * 0.28, x0 + bw * 0.72, y0 + bh * 0.06
        top = y0 - bh * 0.2
        pts = [(bx0, by), (bx0, top + bh * 0.08), (bx0 + (bx1 - bx0) * 0.25, top + bh * 0.16),
               (bx0 + (bx1 - bx0) * 0.5, top), (bx0 + (bx1 - bx0) * 0.75, top + bh * 0.16),
               (bx1, top + bh * 0.08), (bx1, by)]
        d.polygon(pts, fill=(255, 205, 60, 255), outline=(220, 160, 30, 255))
        for k, col in ((0.25, (255, 80, 120, 255)), (0.5, (90, 170, 255, 255)), (0.75, (255, 80, 120, 255))):
            r = bw * 0.03
            cx, cy = bx0 + (bx1 - bx0) * k, by - bh * 0.07
            d.ellipse((cx - r, cy - r, cx + r, cy + r), fill=col)
    elif kind == "bow":
        cx, cy = x0 + bw * 0.78, y0 + bh * 0.08
        s = bw * 0.14
        d.polygon([(cx, cy), (cx - s, cy - s * 0.7), (cx - s, cy + s * 0.7)], fill=(255, 110, 170, 255))
        d.polygon([(cx, cy), (cx + s, cy - s * 0.7), (cx + s, cy + s * 0.7)], fill=(255, 110, 170, 255))
        r = s * 0.32
        d.ellipse((cx - r, cy - r, cx + r, cy + r), fill=(255, 70, 140, 255))
    elif kind == "headband":  # focus mode
        y = y0 + bh * 0.13
        d.rounded_rectangle((x0 + bw * 0.07, y, x0 + bw * 0.93, y + bh * 0.09), radius=bh * 0.04,
                            fill=(235, 60, 70, 255))
        tx, ty = x0 + bw * 0.9, y + bh * 0.045
        wave = math.sin(t * 6) * bh * 0.04
        d.polygon([(tx, ty), (tx + bw * 0.16, ty - bh * 0.05 + wave), (tx + bw * 0.14, ty + bh * 0.03 + wave)],
                  fill=(235, 60, 70, 255))
        d.polygon([(tx, ty), (tx + bw * 0.12, ty + bh * 0.1 - wave), (tx + bw * 0.06, ty + bh * 0.12 - wave)],
                  fill=(210, 45, 55, 255))
    elif kind == "sunglasses":
        for ex, ey in eyes:
            w, h = er * 1.45, er * 1.05
            d.rounded_rectangle((ex - w, ey - h, ex + w, ey + h), radius=h * 0.6, fill=(20, 22, 32, 255))
            d.line([(ex - w * 0.5, ey - h * 0.4), (ex - w * 0.1, ey - h * 0.75)], fill=(255, 255, 255, 170),
                   width=int(2.5 * ss))
        (ax, ay), (bx, by) = eyes
        d.line([(ax + er * 1.3, ay - er * 0.3), (bx - er * 1.3, by - er * 0.3)], fill=(20, 22, 32, 255),
               width=int(3 * ss))


def has_hat(kind: str) -> bool:
    return kind in ("party", "santa", "cap", "crown", "bow")
