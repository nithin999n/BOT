"""Things the desktop BOT holds or wears for a moment: popcorn, nerd glasses, umbrella, scarf, blanket,
a reminder note, festival things (diya, kite, cake, Holi colours, mango leaves) and a ball."""
from __future__ import annotations

import math
import random

INK = (22, 24, 38, 255)


def _star(cx, cy, r, points=5, inner=0.45, rot=-math.pi / 2):
    return [(cx + math.cos(rot + i * math.pi / points) * (r if i % 2 == 0 else r * inner),
             cy + math.sin(rot + i * math.pi / points) * (r if i % 2 == 0 else r * inner))
            for i in range(points * 2)]


def under(d, kind: str, x0, y0, bw, bh, ss, t) -> None:
    """Drawn on the body, before the face (paint on its skin)."""
    if kind == "holi":
        rnd = random.Random(7)
        for col in ((255, 80, 160), (255, 210, 60), (80, 220, 120), (120, 120, 255), (255, 140, 60)):
            for _ in range(2):
                cx, cy = x0 + bw * rnd.uniform(0.15, 0.85), y0 + bh * rnd.uniform(0.12, 0.9)
                if abs(cy - (y0 + bh * 0.5)) < bh * 0.12 and abs(cx - (x0 + bw / 2)) < bw * 0.3:
                    cy += bh * 0.25  # keep the eyes clean
                r = bw * rnd.uniform(0.05, 0.09)
                d.ellipse((cx - r, cy - r * 0.8, cx + r, cy + r * 0.8), fill=col + (150,))


def over(d, kind: str, x0, y0, bw, bh, eyes, er, ss, t, font=None, arg=None) -> None:
    """Drawn on top of BOT."""
    cx = x0 + bw / 2
    if kind == "glass":  # water glass standing next to BOT (fills up as you drink)
        gx0, gx1 = x0 - bw * 0.36, x0 - bw * 0.1
        gy0, gy1 = y0 + bh * 0.52, y0 + bh * 1.0
        fill = max(0.0, min(1.0, float(arg or 0)))
        d.polygon([(gx0, gy0), (gx1, gy0), (gx1 - bw * 0.03, gy1), (gx0 + bw * 0.03, gy1)],
                  outline=(200, 225, 245, 255), fill=(230, 245, 255, 70))
        if fill > 0:  # the water (drawn after the glass so it isn't covered)
            wy = gy1 - (gy1 - gy0) * 0.9 * fill
            d.polygon([(gx0 + bw * 0.025, wy), (gx1 - bw * 0.025, wy),
                       (gx1 - bw * 0.035, gy1 - bh * 0.02), (gx0 + bw * 0.035, gy1 - bh * 0.02)], fill=(110, 190, 255, 230))
        d.line([(gx0 + bw * 0.05, gy0 + bh * 0.06), (gx0 + bw * 0.06, gy1 - bh * 0.08)], fill=(255, 255, 255, 170),
               width=int(2 * ss))
        if font is not None and fill >= 1:
            d.text(((gx0 + gx1) / 2, gy0 - bh * 0.1), "🏆", font=font, anchor="mm", embedded_color=True)
        return
    if kind == "ears":  # little round ears pop out while you change the volume
        for side in (-1, 1):
            ex, ey = cx + side * bw * 0.36, y0 + bh * 0.04
            d.ellipse((ex - bw * 0.11, ey - bh * 0.13, ex + bw * 0.11, ey + bh * 0.1), fill=(98, 168, 255, 255),
                      outline=(40, 105, 210, 255), width=int(2 * ss))
            d.ellipse((ex - bw * 0.06, ey - bh * 0.07, ex + bw * 0.06, ey + bh * 0.05), fill=(255, 170, 205, 255))
        return
    if kind == "clipboard":
        if font is not None:
            d.text((x0 + bw * 1.0, y0 + bh * 0.62), "📋", font=font, anchor="mm", embedded_color=True)
        return
    if kind == "glasses":  # round nerd glasses
        for ex, ey in eyes:
            r = er * 1.5
            d.ellipse((ex - r, ey - r, ex + r, ey + r), outline=(150, 95, 50, 255), width=int(2.4 * ss))
            d.arc((ex - r * 0.75, ey - r * 0.75, ex + r * 0.75, ey + r * 0.75), 200, 250, fill=(255, 255, 255, 200),
                  width=int(1.6 * ss))
        (ax, ay), (bx, by) = eyes
        d.line([(ax + er * 1.5, ay - er * 0.2), (bx - er * 1.5, by - er * 0.2)], fill=(150, 95, 50, 255),
               width=int(2.4 * ss))
    elif kind == "popcorn":  # a striped bucket in front
        bx, by = x0 + bw * 0.72, y0 + bh * 0.72
        w, h = bw * 0.34, bh * 0.36
        d.polygon([(bx, by), (bx + w, by), (bx + w * 0.86, by + h), (bx + w * 0.14, by + h)], fill=(255, 255, 255, 255))
        for i in range(4):
            sx = bx + w * (0.06 + i * 0.25)
            d.polygon([(sx, by), (sx + w * 0.12, by), (sx + w * 0.1, by + h), (sx + w * 0.02, by + h)],
                      fill=(230, 50, 60, 255))
        for i, (ox, oy) in enumerate(((0.1, -0.05), (0.32, -0.12), (0.55, -0.06), (0.78, -0.1), (0.42, -0.2),
                                      (0.2, -0.17), (0.66, -0.2))):
            r = w * 0.13
            px, py = bx + w * ox, by + h * oy + math.sin(t * 3 + i) * h * 0.02
            d.ellipse((px - r, py - r, px + r, py + r), fill=(255, 246, 210, 255), outline=(240, 210, 140, 255))
    elif kind == "umbrella":
        hx = x0 + bw * 1.06
        top = y0 - bh * 0.42
        d.line([(hx, y0 + bh * 0.62), (hx, top + bh * 0.05)], fill=(90, 70, 60, 255), width=int(3 * ss))
        d.arc((hx - bw * 0.1, y0 + bh * 0.55, hx + bw * 0.02, y0 + bh * 0.72), 0, 180, fill=(90, 70, 60, 255), width=int(3 * ss))
        w = bw * 0.62
        d.chord((hx - w, top - bh * 0.25, hx + w, top + bh * 0.25), 180, 360, fill=(255, 210, 60, 255))
        for i in range(4):  # scallops
            sx = hx - w + i * w / 2
            d.chord((sx, top - bh * 0.06, sx + w / 2, top + bh * 0.06), 0, 180, fill=(255, 210, 60, 255))
        d.line([(hx, top - bh * 0.25), (hx, top - bh * 0.32)], fill=(90, 70, 60, 255), width=int(3 * ss))
        for i in range(3):  # rain drops around
            ph = (t * 1.3 + i / 3) % 1
            rx, ry = hx - w * 1.15 + i * w * 1.1, top + ph * bh * 1.3
            d.line([(rx, ry), (rx - bw * 0.02, ry + bh * 0.08)], fill=(120, 180, 255, int(220 * (1 - ph))), width=int(2 * ss))
    elif kind == "scarf":
        yy = y0 + bh * 0.8
        d.rounded_rectangle((x0 + bw * 0.06, yy, x0 + bw * 0.94, yy + bh * 0.12), radius=bh * 0.05, fill=(230, 60, 70, 255))
        for i in range(6):
            sx = x0 + bw * (0.12 + i * 0.14)
            d.line([(sx, yy + bh * 0.01), (sx + bw * 0.03, yy + bh * 0.11)], fill=(255, 255, 255, 200), width=int(2 * ss))
        d.polygon([(x0 + bw * 0.66, yy + bh * 0.08), (x0 + bw * 0.8, yy + bh * 0.08), (x0 + bw * 0.84, yy + bh * 0.3),
                   (x0 + bw * 0.7, yy + bh * 0.3)], fill=(210, 45, 55, 255))
    elif kind == "blanket":
        top = y0 + bh * 0.66
        d.rounded_rectangle((x0 - bw * 0.06, top, x0 + bw * 1.06, y0 + bh * 1.04), radius=bh * 0.12,
                            fill=(255, 180, 210, 255), outline=(230, 140, 180, 255), width=int(2 * ss))
        d.rounded_rectangle((x0 - bw * 0.06, top, x0 + bw * 1.06, top + bh * 0.1), radius=bh * 0.05, fill=(255, 245, 250, 255))
        for i in range(5):
            hx, hy = x0 + bw * (0.1 + i * 0.2), top + bh * 0.24
            from_heart = [(hx, hy + bw * 0.03), (hx - bw * 0.03, hy - bw * 0.005), (hx - bw * 0.015, hy - bw * 0.025),
                          (hx, hy - bw * 0.012), (hx + bw * 0.015, hy - bw * 0.025), (hx + bw * 0.03, hy - bw * 0.005)]
            d.polygon(from_heart, fill=(255, 255, 255, 200))
    elif kind == "note":  # a reminder note on a stick
        sx = x0 + bw * 1.02
        d.line([(sx, y0 + bh * 0.8), (sx, y0 + bh * 0.05)], fill=(150, 110, 70, 255), width=int(3 * ss))
        w, h = bw * 0.42, bh * 0.36
        d.rounded_rectangle((sx - w / 2, y0 - h * 0.35, sx + w / 2, y0 + h * 0.65), radius=bh * 0.04,
                            fill=(255, 240, 140, 255), outline=(220, 190, 80, 255), width=int(2 * ss))
        if font is not None:
            d.text((sx, y0 + h * 0.15 + math.sin(t * 4) * bh * 0.01), "⏰", font=font, anchor="mm", embedded_color=True)
    elif kind == "phone":  # holding up a phone sign (a call / a message)
        sx = x0 + bw * 1.02
        w, h = bw * 0.3, bh * 0.5
        wob = math.sin(t * 12) * bw * 0.01
        d.rounded_rectangle((sx - w / 2 + wob, y0 - h * 0.1, sx + w / 2 + wob, y0 + h * 0.9), radius=bw * 0.05,
                            fill=(40, 44, 60, 255))
        d.rounded_rectangle((sx - w * 0.4 + wob, y0, sx + w * 0.4 + wob, y0 + h * 0.75), radius=bw * 0.03,
                            fill=(130, 200, 255, 255))
        if font is not None:
            d.text((sx + wob, y0 + h * 0.38), "📞", font=font, anchor="mm", embedded_color=True)
    elif kind == "ball":  # carrying the ball in its mouth
        mx, my = cx, y0 + bh * 0.74
        r = bw * 0.12
        d.ellipse((mx - r, my - r, mx + r, my + r), fill=(255, 92, 120, 255))
        d.arc((mx - r * 1.6, my - r * 0.6, mx + r * 0.4, my + r * 1.6), 280, 360, fill=(255, 235, 120, 255), width=int(2.4 * ss))
    elif kind == "diya":  # a little Diwali lamp
        bx, by = x0 + bw * 0.08, y0 + bh * 0.98
        w = bw * 0.3
        d.chord((bx - w / 2, by - w * 0.45, bx + w / 2, by + w * 0.25), 0, 180, fill=(210, 110, 50, 255))
        d.ellipse((bx - w / 2, by - w * 0.18, bx + w / 2, by + w * 0.02), fill=(240, 150, 70, 255))
        fl = 1 + math.sin(t * 13) * 0.12
        d.ellipse((bx - w * 0.07, by - w * 0.48 * fl, bx + w * 0.07, by - w * 0.1), fill=(255, 200, 60, 255))
        d.ellipse((bx - w * 0.035, by - w * 0.33 * fl, bx + w * 0.035, by - w * 0.12), fill=(255, 250, 200, 255))
    elif kind == "kite":
        kx, ky = x0 - bw * 0.25 + math.sin(t * 1.5) * bw * 0.05, y0 - bh * 0.45 + math.cos(t * 1.2) * bh * 0.04
        s = bw * 0.2
        d.polygon([(kx, ky - s), (kx + s * 0.8, ky), (kx, ky + s * 1.1), (kx - s * 0.8, ky)], fill=(255, 90, 90, 255))
        d.polygon([(kx, ky - s), (kx + s * 0.8, ky), (kx, ky)], fill=(255, 210, 60, 255))
        d.line([(kx, ky + s * 1.1), (x0 + bw * 0.1, y0 + bh * 0.6)], fill=(90, 90, 90, 200), width=int(1.4 * ss))
        for i in range(3):
            tx, ty = kx - s * 0.2 * i, ky + s * (1.25 + 0.3 * i)
            d.polygon(_star(tx, ty, s * 0.15, points=4, inner=0.5), fill=(80, 200, 255, 255))
    elif kind == "cake":
        bx, by = x0 + bw * 0.92, y0 + bh * 1.0
        w, h = bw * 0.36, bh * 0.28
        d.rounded_rectangle((bx - w / 2, by - h, bx + w / 2, by), radius=bw * 0.03, fill=(255, 230, 240, 255))
        d.rounded_rectangle((bx - w / 2, by - h, bx + w / 2, by - h * 0.65), radius=bw * 0.03, fill=(255, 120, 170, 255))
        d.line([(bx, by - h), (bx, by - h * 1.45)], fill=(120, 190, 255, 255), width=int(3 * ss))
        fl = 1 + math.sin(t * 12) * 0.15
        d.ellipse((bx - w * 0.06, by - h * (1.45 + 0.3 * fl), bx + w * 0.06, by - h * 1.42), fill=(255, 200, 60, 255))
    elif kind == "toran":  # mango-leaf garland for Ugadi
        for i in range(7):
            lx = x0 - bw * 0.05 + i * bw * 0.185
            ly = y0 - bh * 0.18 + abs(i - 3) * bh * 0.02
            d.polygon([(lx, ly), (lx - bw * 0.04, ly + bh * 0.12), (lx, ly + bh * 0.2), (lx + bw * 0.04, ly + bh * 0.12)],
                      fill=(70, 170, 80, 255))
            if i % 2 == 0:
                d.ellipse((lx - bw * 0.025, ly - bh * 0.03, lx + bw * 0.025, ly + bh * 0.02), fill=(255, 150, 40, 255))
        d.line([(x0 - bw * 0.08, y0 - bh * 0.17), (x0 + bw * 1.08, y0 - bh * 0.17)], fill=(200, 60, 60, 255), width=int(2 * ss))
    elif kind == "modak":  # Ganesh Chaturthi sweet
        bx, by = x0 + bw * 0.9, y0 + bh * 0.98
        w = bw * 0.24
        d.polygon([(bx, by - w * 1.1), (bx + w / 2, by), (bx - w / 2, by)], fill=(250, 235, 200, 255))
        d.ellipse((bx - w / 2, by - w * 0.5, bx + w / 2, by + w * 0.1), fill=(250, 235, 200, 255))


def outfit(d, kind: str, x0, y0, bw, bh, ss, t) -> bool:
    """Outfits from badges and the shop. Returns True if it drew one."""
    if kind == "bunny":
        for side in (-1, 1):
            ex = x0 + bw * (0.5 + side * 0.2)
            tilt = side * bw * 0.06 + math.sin(t * 2 + side) * bw * 0.015
            d.ellipse((ex - bw * 0.09 + tilt, y0 - bh * 0.5, ex + bw * 0.09 + tilt, y0 + bh * 0.12), fill=(250, 250, 255, 255),
                      outline=(215, 215, 230, 255), width=int(2 * ss))
            d.ellipse((ex - bw * 0.045 + tilt, y0 - bh * 0.4, ex + bw * 0.045 + tilt, y0 + bh * 0.02), fill=(255, 170, 205, 255))
        return True
    if kind == "chef":
        cx = x0 + bw * 0.5
        d.rounded_rectangle((cx - bw * 0.24, y0 - bh * 0.05, cx + bw * 0.24, y0 + bh * 0.12), radius=bh * 0.03,
                            fill=(250, 250, 252, 255), outline=(215, 215, 225, 255), width=int(2 * ss))
        for ox, r in ((-0.17, 0.15), (0.0, 0.19), (0.17, 0.15)):
            d.ellipse((cx + bw * ox - bw * r, y0 - bh * 0.42, cx + bw * ox + bw * r, y0 + bh * 0.02), fill=(250, 250, 252, 255),
                      outline=(215, 215, 225, 255), width=int(2 * ss))
        d.rectangle((cx - bw * 0.235, y0 - bh * 0.06, cx + bw * 0.235, y0 + bh * 0.02), fill=(250, 250, 252, 255))
        return True
    if kind == "cowboy":
        cx = x0 + bw * 0.5
        d.ellipse((cx - bw * 0.5, y0 - bh * 0.02, cx + bw * 0.5, y0 + bh * 0.14), fill=(150, 95, 55, 255))
        d.rounded_rectangle((cx - bw * 0.24, y0 - bh * 0.3, cx + bw * 0.24, y0 + bh * 0.07), radius=bh * 0.1,
                            fill=(170, 110, 65, 255))
        d.rectangle((cx - bw * 0.24, y0 - bh * 0.04, cx + bw * 0.24, y0 + bh * 0.03), fill=(90, 55, 35, 255))
        return True
    if kind == "beret":
        cx = x0 + bw * 0.42
        d.ellipse((cx - bw * 0.36, y0 - bh * 0.2, cx + bw * 0.3, y0 + bh * 0.1), fill=(220, 50, 70, 255))
        d.line([(cx - bw * 0.02, y0 - bh * 0.2), (cx + bw * 0.02, y0 - bh * 0.28)], fill=(220, 50, 70, 255), width=int(4 * ss))
        return True
    if kind == "flower":  # flower crown
        for i in range(7):
            fx = x0 + bw * (0.14 + i * 0.12)
            fy = y0 + bh * 0.06 - math.sin(i / 6 * math.pi) * bh * 0.08
            col = [(255, 140, 190), (255, 220, 90), (190, 150, 255), (255, 170, 120)][i % 4]
            for a in range(5):
                ang = a * 2 * math.pi / 5 + t * 0.3
                px, py = fx + math.cos(ang) * bw * 0.035, fy + math.sin(ang) * bw * 0.035
                d.ellipse((px - bw * 0.03, py - bw * 0.03, px + bw * 0.03, py + bw * 0.03), fill=col + (255,))
            d.ellipse((fx - bw * 0.02, fy - bw * 0.02, fx + bw * 0.02, fy + bw * 0.02), fill=(255, 250, 220, 255))
        return True
    if kind == "grad":  # graduation cap
        cx, top = x0 + bw * 0.5, y0 - bh * 0.12
        d.polygon([(cx, top - bh * 0.12), (cx + bw * 0.42, top), (cx, top + bh * 0.12), (cx - bw * 0.42, top)], fill=(40, 40, 50, 255))
        d.rectangle((cx - bw * 0.2, top + bh * 0.03, cx + bw * 0.2, top + bh * 0.16), fill=(40, 40, 50, 255))
        sw = math.sin(t * 2) * bw * 0.02
        d.line([(cx, top), (cx + bw * 0.34, top + bh * 0.04), (cx + bw * 0.36 + sw, top + bh * 0.24)],
               fill=(255, 205, 60, 255), width=int(2.4 * ss))
        d.ellipse((cx + bw * 0.33 + sw, top + bh * 0.22, cx + bw * 0.39 + sw, top + bh * 0.3), fill=(255, 205, 60, 255))
        return True
    if kind == "halo":
        cx, cy = x0 + bw * 0.5, y0 - bh * 0.2 + math.sin(t * 2) * bh * 0.02
        d.ellipse((cx - bw * 0.3, cy - bh * 0.07, cx + bw * 0.3, cy + bh * 0.07), outline=(255, 220, 90, 255), width=int(4 * ss))
        d.ellipse((cx - bw * 0.27, cy - bh * 0.05, cx + bw * 0.27, cy + bh * 0.05), outline=(255, 245, 190, 200), width=int(1.5 * ss))
        return True
    return False
