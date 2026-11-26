"""Aviso flutuante no canto da tela do PC para os comandos de voz e (1.18) conquistas, nível e desafios.

"PC" ouvido -> "Ouvindo..."; comando feito -> o que ele entendeu e o resultado.
Janela sem borda, sempre por cima, que não rouba o foco (não atrapalha o
jogo nem o que você estiver digitando) e some sozinha.
Jogo em tela cheia exclusiva fica por cima dela; aí só o bipe avisa.
"""
import ctypes
import logging
import queue
import threading
from ctypes import wintypes

log = logging.getLogger("companion")

BG, TEXT, DIM = "#14171c", "#e8ecf1", "#8a94a3"
ACCENT = {"wake": "#3498db", "ok": "#2ecc71", "err": "#e74c3c", "trophy": "#f0b446", "level": "#a66bff", "quest": "#ff7a45"}
HEAD = {"wake": "PC  OUVINDO", "ok": "PC", "err": "PC  NÃO DEU", "trophy": "CONQUISTA", "level": "JOGADOR", "quest": "DESAFIO DA SEMANA"}

GWL_EXSTYLE = -20
WS_EX_TOOLWINDOW, WS_EX_NOACTIVATE, WS_EX_TOPMOST, WS_EX_TRANSPARENT, WS_EX_LAYERED = 0x80, 0x08000000, 0x8, 0x20, 0x80000
SW_HIDE, SW_SHOWNOACTIVATE = 0, 4
HWND_TOPMOST = -1
SWP_NOACTIVATE, SWP_NOSIZE, SWP_NOMOVE, SWP_SHOWWINDOW = 0x10, 0x1, 0x2, 0x40


class Overlay:
    def __init__(self):
        self.q = queue.Queue()
        self._thread = None

    def show(self, kind, title, body="", secs=3.5):
        if self._thread is None:
            self._thread = threading.Thread(target=self._run, daemon=True, name="aviso-voz")
            self._thread.start()
        self.q.put((kind, title, body, secs))

    def _run(self):
        try:
            import tkinter as tk
            from tkinter import font as tkfont
        except Exception:  # noqa: BLE001
            log.warning("aviso de voz: sem tkinter")
            return
        u = ctypes.windll.user32
        u.GetParent.restype = wintypes.HWND
        u.GetWindowLongW.restype = ctypes.c_long
        u.SetWindowPos.argtypes = [wintypes.HWND, wintypes.HWND, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, wintypes.UINT]

        root = tk.Tk()
        root.withdraw()
        win = tk.Toplevel(root, bg=BG)
        win.overrideredirect(True)
        win.attributes("-topmost", True)
        win.attributes("-alpha", 0.96)
        base = tkfont.nametofont("TkDefaultFont").actual("family")
        bar = tk.Frame(win, width=6, bg=ACCENT["ok"])
        bar.pack(side="left", fill="y")
        box = tk.Frame(win, bg=BG)
        box.pack(side="left", fill="both", expand=True, padx=(14, 18), pady=12)
        head = tk.Label(box, text="PC", font=(base, 9, "bold"), fg=DIM, bg=BG, anchor="w")
        head.pack(fill="x")
        title = tk.Label(box, font=(base, 13, "bold"), fg=TEXT, bg=BG, anchor="w", justify="left", wraplength=340)
        title.pack(fill="x", pady=(2, 0))
        body = tk.Label(box, font=(base, 10), fg=DIM, bg=BG, anchor="w", justify="left", wraplength=340)
        body.pack(fill="x")
        win.update_idletasks()
        hwnd = u.GetParent(win.winfo_id()) or win.winfo_id()
        ex = u.GetWindowLongW(hwnd, GWL_EXSTYLE)
        u.SetWindowLongW(hwnd, GWL_EXSTYLE, ex | WS_EX_TOOLWINDOW | WS_EX_NOACTIVATE | WS_EX_TOPMOST
                         | WS_EX_TRANSPARENT | WS_EX_LAYERED)  # clique passa direto
        u.ShowWindow(hwnd, SW_HIDE)
        state = {"hide": None}

        def hide():
            state["hide"] = None
            u.ShowWindow(hwnd, SW_HIDE)

        def poll():
            try:
                while True:
                    kind, t, b, secs = self.q.get_nowait()
                    bar.configure(bg=ACCENT.get(kind, ACCENT["ok"]))
                    head.configure(text=HEAD.get(kind, "PC"), fg=ACCENT[kind] if kind in ("trophy", "level", "quest") else DIM)
                    title.configure(text=t)
                    body.configure(text=b)
                    if b:
                        body.pack(fill="x")
                    else:
                        body.pack_forget()
                    win.update_idletasks()
                    w, h = max(260, win.winfo_reqwidth()), win.winfo_reqheight()
                    rc = wintypes.RECT()
                    ctypes.windll.user32.SystemParametersInfoW(0x30, 0, ctypes.byref(rc), 0)  # área sem a barra de tarefas
                    x, y = rc.right - w - 24, rc.bottom - h - 24
                    win.geometry(f"{w}x{h}+{x}+{y}")
                    win.update_idletasks()
                    u.SetWindowPos(hwnd, HWND_TOPMOST, x, y, 0, 0, SWP_NOACTIVATE | SWP_NOSIZE | SWP_SHOWWINDOW)
                    u.ShowWindow(hwnd, SW_SHOWNOACTIVATE)
                    if state["hide"]:
                        root.after_cancel(state["hide"])
                    state["hide"] = root.after(int(secs * 1000), hide)
            except queue.Empty:
                pass
            except Exception:  # noqa: BLE001
                log.exception("aviso de voz")
            root.after(80, poll)

        poll()
        root.mainloop()
