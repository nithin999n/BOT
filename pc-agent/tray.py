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
    """A tiny blue blob BOT with round black eyes, for the tray."""
    s = size * 4
    img = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    d = ImageDraw.Draw(img, "RGBA")
    light = tuple(int(c + (255 - c) * 0.35) for c in color)
    dark = tuple(int(c * 0.78) for c in color)
    d.rounded_rectangle((s * 0.04, s * 0.08, s * 0.96, s * 0.92), radius=s * 0.4, fill=light + (255,),
                        outline=dark + (255,), width=s // 22)
    d.ellipse((s * 0.2, s * 0.14, s * 0.56, s * 0.3), fill=(255, 255, 255, 110))  # gloss
    for ex in (0.33, 0.67):  # round black eyes with a sparkle
        d.ellipse((s * (ex - 0.12), s * 0.38, s * (ex + 0.12), s * 0.62), fill=(22, 24, 38, 255))
        d.ellipse((s * (ex - 0.08), s * 0.41, s * (ex - 0.0), s * 0.49), fill=(255, 255, 255, 255))
    for cx in (0.2, 0.8):
        d.ellipse((s * (cx - 0.08), s * 0.6, s * (cx + 0.08), s * 0.7), fill=(255, 126, 182, 170))
    q = s * 0.06
    d.arc((s * 0.5 - 2 * q, s * 0.66 - q, s * 0.5, s * 0.66 + q), 0, 180, fill=(22, 24, 38, 255), width=s // 26)
    d.arc((s * 0.5, s * 0.66 - q, s * 0.5 + 2 * q, s * 0.66 + q), 0, 180, fill=(22, 24, 38, 255), width=s // 26)
    return img.resize((size, size), Image.LANCZOS)


class Tray:
    """Callbacks are plain functions; they run on the tray's own thread."""

    def __init__(self, *, pet, bubble, cfg: dict, toggle_pet, toggle_bubble, toggle_walkaway,
                 bring_pet, autostart_on, set_autostart, open_files, quit_bot, extras=()):
        self.pet, self.bubble, self.cfg = pet, bubble, cfg
        self.extras = list(extras)  # [(label, callback)] for the "BOT fun" section
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

    def _wrap(self, fn):
        def run(*_args):
            try:
                fn()
            except Exception:
                log.exception("tray extra failed")
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
            *[M(label, self._wrap(fn)) for label, fn in self.extras],
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
        return (58, 141, 255)  # same blue as the desktop BOT

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
