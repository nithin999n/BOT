"""
Little typing windows on the PC (tkinter, all on one UI thread):
* ask_text(): "What's one good thing that happened today?" -> a cute box with a text field
* open_chat(): "Talk to BOT" chat window
"""
from __future__ import annotations

import ctypes
import queue
import threading

BG, CARD, BLUE, INK, SOFT = "#EEF5FF", "#FFFFFF", "#3A8DFF", "#1E2440", "#6B7896"
_q: queue.Queue = queue.Queue()
_thread: threading.Thread | None = None
_chat: dict = {}


def _ensure() -> None:
    global _thread
    if _thread is None:
        _thread = threading.Thread(target=_run, name="bot-ui", daemon=True)
        _thread.start()


def _run() -> None:
    import tkinter as tk
    root = tk.Tk()
    root.withdraw()
    try:
        dpi = ctypes.windll.user32.GetDpiForSystem()
        root.tk.call("tk", "scaling", dpi / 72)
    except Exception:
        pass
    root._bot_font = ("Segoe UI", 11)

    def pump():
        try:
            while True:
                fn = _q.get_nowait()
                try:
                    fn(root)
                except Exception:
                    pass
        except queue.Empty:
            pass
        root.after(80, pump)

    pump()
    root.mainloop()


def _center(win, w: int, h: int) -> None:
    win.update_idletasks()
    sw, sh = win.winfo_screenwidth(), win.winfo_screenheight()
    win.geometry(f"{w}x{h}+{(sw - w) // 2}+{(sh - h) // 3}")


def ask_text(title: str, prompt: str, on_done, initial: str = "", secret: bool = False) -> None:
    """Shows a small box; calls on_done(text or None) from the UI thread."""
    _ensure()

    def make(root):
        import tkinter as tk
        win = tk.Toplevel(root, bg=BG)
        win.title(title)
        win.attributes("-topmost", True)
        win.resizable(False, False)
        done = {"v": False}

        def finish(value):
            if done["v"]:
                return
            done["v"] = True
            win.destroy()
            on_done(value)

        tk.Label(win, text=prompt, bg=BG, fg=INK, font=("Segoe UI", 12), wraplength=420, justify="left").pack(
            padx=18, pady=(16, 8), anchor="w")
        entry = tk.Entry(win, font=("Segoe UI", 12), relief="flat", bg=CARD, fg=INK, insertbackground=INK,
                         show="•" if secret else "")
        entry.pack(fill="x", padx=18, ipady=6)
        entry.insert(0, initial)
        entry.focus_force()
        row = tk.Frame(win, bg=BG)
        row.pack(fill="x", padx=18, pady=14)
        tk.Button(row, text="Save 💙", command=lambda: finish(entry.get().strip() or None), bg=BLUE, fg="white",
                  relief="flat", font=("Segoe UI", 11, "bold"), padx=14, pady=4, cursor="hand2").pack(side="right")
        tk.Button(row, text="Cancel", command=lambda: finish(None), bg=BG, fg=SOFT, relief="flat",
                  font=("Segoe UI", 11), padx=10, cursor="hand2").pack(side="right", padx=6)
        entry.bind("<Return>", lambda _e: finish(entry.get().strip() or None))
        win.bind("<Escape>", lambda _e: finish(None))
        win.protocol("WM_DELETE_WINDOW", lambda: finish(None))
        _center(win, 470, 190)
        win.lift()
        win.after(50, entry.focus_force)

    _q.put(make)


def open_chat(get_reply, on_reply=None) -> None:
    """The "Talk to BOT" window. get_reply(text, history) runs on a worker thread."""
    _ensure()

    def make(root):
        import tkinter as tk
        old = _chat.get("win")
        if old is not None:
            try:
                old.deiconify()
                old.lift()
                old.focus_force()
                return
            except Exception:
                pass
        win = tk.Toplevel(root, bg=BG)
        win.title("💬 Talk to BOT")
        win.attributes("-topmost", True)
        _chat["win"] = win
        history: list = []
        tk.Label(win, text="💬 Talk to BOT", bg=BG, fg=INK, font=("Segoe UI", 14, "bold")).pack(
            padx=16, pady=(12, 4), anchor="w")
        box = tk.Text(win, wrap="word", bg=CARD, fg=INK, relief="flat", font=("Segoe UI Emoji", 11), padx=10, pady=8,
                      state="disabled", height=16)
        box.tag_configure("you", foreground=SOFT, justify="right", rmargin=6, spacing3=8)
        box.tag_configure("bot", foreground=INK, spacing3=8)
        box.pack(fill="both", expand=True, padx=14)
        row = tk.Frame(win, bg=BG)
        row.pack(fill="x", padx=14, pady=12)
        entry = tk.Entry(row, font=("Segoe UI", 12), relief="flat", bg=CARD, fg=INK, insertbackground=INK)
        entry.pack(side="left", fill="x", expand=True, ipady=6)

        def add(text, who):
            box.configure(state="normal")
            box.insert("end", ("" if who == "bot" else "") + text + "\n", who)
            box.configure(state="disabled")
            box.see("end")

        def send(_e=None):
            text = entry.get().strip()
            if not text:
                return
            entry.delete(0, "end")
            add(text, "you")
            history.append(("user", text))

            def work():
                try:
                    reply = get_reply(text, list(history))
                except Exception:
                    reply = "Hmm, my brain got a little fuzzy 🥴 Say that again?"
                history.append(("bot", reply))
                _q.put(lambda _r: add("BOT: " + reply, "bot"))
                if on_reply:
                    on_reply(reply)

            threading.Thread(target=work, daemon=True).start()

        tk.Button(row, text="Send", command=send, bg=BLUE, fg="white", relief="flat", font=("Segoe UI", 11, "bold"),
                  padx=12, cursor="hand2").pack(side="right", padx=(8, 0))
        entry.bind("<Return>", send)

        def close():
            _chat.pop("win", None)
            win.destroy()

        win.protocol("WM_DELETE_WINDOW", close)
        add("BOT: Hiii! 💙 Talk to me about anything. I'm all ears 🥰", "bot")
        _center(win, 420, 520)
        win.lift()
        win.after(60, entry.focus_force)

    _q.put(make)
