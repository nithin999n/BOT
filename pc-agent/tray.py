"""
BOT in the Windows system tray (the ^ area next to the clock).

Left-click: show / hide the desktop BOT.
Right-click: menu (desktop BOT, bring BOT here, BOT cursor, walk-away lock,
start with Windows, show PIN, open received files, quit).
"""
from __future__ import annotations

import ctypes
import logging
import os
import threading

import pystray
from PIL import Image, ImageDraw

log = logging.getLogger("bot")


def make_icon(color=(79, 195, 255), size=64) -> Image.Image:
    """A tiny BOT face for the tray."""
    s = size * 4
    img = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.line([(s / 2, s * 0.06), (s / 2, s * 0.2)], fill=(60, 80, 140, 255), width=s // 18)
    d.ellipse((s / 2 - s * 0.07, s * 0.0, s / 2 + s * 0.07, s * 0.14), fill=color + (255,))
    d.rounded_rectangle((s * 0.06, s * 0.18, s * 0.94, s * 0.94), radius=s * 0.26, fill=(26, 40, 86, 255),
                        outline=color + (255,), width=s // 20)
    d.rounded_rectangle((s * 0.16, s * 0.28, s * 0.84, s * 0.84), radius=s * 0.18, fill=(7, 12, 32, 255))
    light = tuple(int(c + (255 - c) * 0.6) for c in color)
    for ex in (0.36, 0.64):
        d.rounded_rectangle((s * (ex - 0.07), s * 0.38, s * (ex + 0.07), s * 0.62), radius=s * 0.07,
                            fill=light + (255,))
    d.arc((s * 0.4, s * 0.58, s * 0.6, s * 0.74), 20, 160, fill=light + (255,), width=s // 22)
    for cx in (0.27, 0.73):
        d.ellipse((s * (cx - 0.06), s * 0.64, s * (cx + 0.06), s * 0.7), fill=(255, 126, 182, 150))
    return img.resize((size, size), Image.LANCZOS)


class Tray:
    """Callbacks are plain functions; they run on the tray's own thread."""

    def __init__(self, *, pet, bubble, cfg: dict, toggle_pet, toggle_bubble, toggle_walkaway,
                 bring_pet, autostart_on, set_autostart, open_files, quit_bot):
        self.pet, self.bubble, self.cfg = pet, bubble, cfg
        self._cb = dict(toggle_pet=toggle_pet, toggle_bubble=toggle_bubble, toggle_walkaway=toggle_walkaway,
                        bring_pet=bring_pet, autostart_on=autostart_on, set_autostart=set_autostart,
                        open_files=open_files, quit_bot=quit_bot)
        self.icon: pystray.Icon | None = None

    def _safe(self, name):
        def run(*_args):
            try:
                self._cb[name]()
            except Exception:
                log.exception("tray action %s failed", name)
            self.refresh()
        return run

    def _show_pin(self, *_args) -> None:
        name = self.cfg.get("style", {}).get("name", "BOT")
        ctypes.windll.user32.MessageBoxW(
            None, f"PIN: {self.cfg.get('pin')}\n\nType it in the {name} app on your phone to connect.",
            f"{name} PIN", 0x40 | 0x40000)  # info icon, topmost

    def _menu(self) -> pystray.Menu:
        M = pystray.MenuItem
        name = self.cfg.get("style", {}).get("name", "BOT")
        return pystray.Menu(
            M(lambda _i: f"{'Hide' if self.pet.wanted else 'Show'} desktop {name}",
              self._safe("toggle_pet"), default=True),       # left-click
            M(f"Bring {name} here", self._safe("bring_pet"), enabled=lambda _i: self.pet.wanted),
            pystray.Menu.SEPARATOR,
            M("Desktop BOT", self._safe("toggle_pet"), checked=lambda _i: self.pet.wanted),
            M("BOT cursor (blue bubble)", self._safe("toggle_bubble"), checked=lambda _i: self.bubble.wanted),
            M("Walk-away lock", self._safe("toggle_walkaway"),
              checked=lambda _i: bool(self.cfg.get("walkaway", {}).get("enabled"))),
            M("Start with Windows", self._safe("set_autostart"), checked=lambda _i: self._cb["autostart_on"]()),
            pystray.Menu.SEPARATOR,
            M("Show PIN", self._show_pin),
            M("Open received files", self._safe("open_files")),
            pystray.Menu.SEPARATOR,
            M(f"Quit {name}", self._safe("quit_bot")),
        )

    def start(self) -> None:
        name = self.cfg.get("style", {}).get("name", "BOT")
        self.icon = pystray.Icon("BOT", make_icon(self._color()), f"{name} is running", self._menu())
        threading.Thread(target=self._run, name="tray", daemon=True).start()

    def _run(self) -> None:
        try:
            self.icon.run()
        except Exception as exc:
            log.warning("Tray icon unavailable: %s", exc)

    def _color(self):
        h = str(self.cfg.get("style", {}).get("color", "#4FC3FF")).lstrip("#")
        try:
            return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))
        except ValueError:
            return (79, 195, 255)

    def refresh(self) -> None:
        """Call after anything changed (checkmarks, name, colour)."""
        if not self.icon:
            return
        try:
            name = self.cfg.get("style", {}).get("name", "BOT")
            self.icon.icon = make_icon(self._color())
            self.icon.title = f"{name} is running"
            self.icon.menu = self._menu()
            self.icon.update_menu()
        except Exception:
            pass

    def stop(self) -> None:
        if self.icon:
            try:
                self.icon.stop()
            except Exception:
                pass


def open_folder(path: str) -> None:
    os.makedirs(path, exist_ok=True)
    os.startfile(path)
