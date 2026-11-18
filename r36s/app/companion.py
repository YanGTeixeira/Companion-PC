#!/usr/bin/env python3
"""R36S PC Companion - cliente para o R36S (pygame, 640x480).

Abas: Painel, Mídia, Atalhos, Controle, Sistema.
L1/R1 trocam de aba. Segure SELECT + START para sair.
"""
import asyncio
import base64
import io
import json
import os
import queue
import sys
import threading
import time
from collections import deque
from pathlib import Path

os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
import pygame  # noqa: E402
from websockets.asyncio.client import connect  # noqa: E402

BASE = Path(__file__).resolve().parent
CFG = {"host": "10.55.0.1", "port": 8765, "token": ""}
try:
    CFG.update(json.loads((BASE / "config.json").read_text(encoding="utf-8")))
except (OSError, ValueError):
    pass
CFG["port"] = int(os.environ.get("COMPANION_PORT", CFG["port"]))

W, H = 640, 480
AUTO_TABS = (0, 1, 2)   # Painel, Tocando, Games
AUTO_SECONDS = 30       # troca de aba após este tempo sem apertar nada
NO_BOOT_FLAG = Path.home() / ".config" / ".NO_BOOT_COMPANION"
FPS = 60

# Botões do GO-Super Gamepad (mapeamento do EmulationStation)
BTN_B, BTN_A, BTN_X, BTN_Y = 0, 1, 2, 3
BTN_L1, BTN_R1, BTN_L2, BTN_R2 = 4, 5, 6, 7
BTN_UP, BTN_DOWN, BTN_LEFT, BTN_RIGHT = 8, 9, 10, 11
BTN_SELECT, BTN_START, BTN_L3, BTN_R3 = 12, 13, 14, 15

# Teclado do PC como alternativa (testes)
KEYMAP = {
    pygame.K_UP: BTN_UP, pygame.K_DOWN: BTN_DOWN, pygame.K_LEFT: BTN_LEFT, pygame.K_RIGHT: BTN_RIGHT,
    pygame.K_z: BTN_A, pygame.K_x: BTN_B, pygame.K_a: BTN_Y, pygame.K_s: BTN_X,
    pygame.K_q: BTN_L1, pygame.K_w: BTN_R1, pygame.K_RETURN: BTN_START, pygame.K_BACKSPACE: BTN_SELECT,
}

C = {
    "bg": (16, 18, 24), "panel": (28, 31, 40), "panel2": (38, 42, 54), "line": (56, 61, 76),
    "text": (232, 234, 240), "dim": (150, 156, 172), "faint": (98, 104, 120),
    "accent": (88, 166, 255), "accent_dim": (40, 74, 120),
    "ok": (80, 200, 120), "warn": (240, 180, 70), "bad": (235, 87, 87),
}


# --------------------------------------------------------------------------
# Conexão (thread com asyncio)
# --------------------------------------------------------------------------
class Link(threading.Thread):
    def __init__(self):
        super().__init__(daemon=True)
        self.inbox: "queue.Queue[dict]" = queue.Queue()
        self.loop = None
        self.outq = None
        self.connected = False
        self.status = "Conectando…"
        self.welcome = {}
        self.next_id = 1

    def run(self):
        asyncio.run(self._main())

    async def _main(self):
        self.loop = asyncio.get_running_loop()
        self.outq = asyncio.Queue()
        url = f"ws://{CFG['host']}:{CFG['port']}"
        while True:
            try:
                async with connect(url, open_timeout=4, ping_interval=5, ping_timeout=8, max_queue=64, max_size=4_000_000) as ws:
                    await ws.send(json.dumps({"t": "hello", "token": CFG["token"], "client": "r36s"}))
                    welcome = json.loads(await asyncio.wait_for(ws.recv(), 5))
                    if welcome.get("t") != "welcome":
                        raise ConnectionError("resposta inesperada")
                    self.welcome, self.connected = welcome, True
                    self.status = f"Conectado a {welcome.get('host', 'PC')}"
                    self.inbox.put(welcome)
                    while not self.outq.empty():  # descarta comandos antigos
                        self.outq.get_nowait()
                    sender = asyncio.create_task(self._sender(ws))
                    try:
                        async for raw in ws:
                            self.inbox.put(json.loads(raw))
                    finally:
                        sender.cancel()
            except Exception as e:  # noqa: BLE001
                code = getattr(getattr(e, "rcvd", None), "code", None)
                self.status = "Token recusado pelo PC" if code == 4001 else "Sem conexão com o PC"
            self.connected = False
            self.inbox.put({"t": "down"})
            await asyncio.sleep(2)

    async def _sender(self, ws):
        while True:
            await ws.send(json.dumps(await self.outq.get()))

    def send(self, action, params=None, want_reply=True):
        if not self.connected or not self.loop:
            return None
        msg = {"t": "req", "a": action, "p": params or {}}
        if want_reply:
            msg["id"] = self.next_id
            self.next_id += 1
        self.loop.call_soon_threadsafe(self.outq.put_nowait, msg)
        return msg.get("id")


# --------------------------------------------------------------------------
# Utilidades de desenho
# --------------------------------------------------------------------------
def font(size, bold=False):
    for name in ("/usr/share/fonts/truetype/freefont/FreeSansBold.ttf" if bold else
                 "/usr/share/fonts/truetype/freefont/FreeSans.ttf",):
        if os.path.exists(name):
            return pygame.font.Font(name, size)
    return pygame.font.SysFont("sans", size, bold=bold)


def human_bytes(n, rate=False):
    n = float(n or 0)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024 or unit == "TB":
            s = f"{n:.0f} {unit}" if unit in ("B", "KB") else f"{n:.1f} {unit}"
            return s + ("/s" if rate else "")
        n /= 1024
    return ""


def human_uptime(s):
    d, s = divmod(int(s or 0), 86400)
    h, s = divmod(s, 3600)
    m = s // 60
    return f"{d}d {h}h {m:02d}m" if d else f"{h}h {m:02d}m"


def level_color(pct):
    return C["ok"] if pct < 60 else C["warn"] if pct < 85 else C["bad"]


def r36s_battery():
    for base in ("/sys/class/power_supply/battery", "/sys/class/power_supply/bat"):
        try:
            cap = int(open(f"{base}/capacity").read().strip())
            st = open(f"{base}/status").read().strip()
            return cap, st in ("Charging", "Full")
        except (OSError, ValueError):
            continue
    return None, False


class UI:
    def __init__(self, screen):
        self.s = screen
        self.f_small = font(14)
        self.f = font(17)
        self.f_b = font(17, True)
        self.f_big = font(24, True)
        self.f_big2 = font(30, True)
        self.f_huge = font(40, True)

    def text(self, txt, pos, f=None, color=None, anchor="topleft", maxw=None):
        f = f or self.f
        txt = str(txt)
        if maxw:
            while txt and f.size(txt)[0] > maxw:
                txt = txt[:-2] + "…" if len(txt) > 2 else ""
        surf = f.render(txt, True, color or C["text"])
        rect = surf.get_rect(**{anchor: pos})
        self.s.blit(surf, rect)
        return rect

    def panel(self, rect, color=None, radius=10, border=None):
        pygame.draw.rect(self.s, color or C["panel"], rect, border_radius=radius)
        if border:
            pygame.draw.rect(self.s, border, rect, 2, border_radius=radius)

    def bar(self, rect, pct, color=None):
        rect = pygame.Rect(rect)
        pygame.draw.rect(self.s, C["panel2"], rect, border_radius=rect.h // 2)
        w = int(rect.w * max(0, min(100, pct)) / 100)
        if w > 0:
            pygame.draw.rect(self.s, color or level_color(pct), (rect.x, rect.y, max(w, rect.h), rect.h), border_radius=rect.h // 2)

    def spark(self, rect, values, color):
        rect = pygame.Rect(rect)
        if len(values) < 2:
            return
        n = len(values)
        pts = [(rect.x + i * (rect.w - 1) / (n - 1), rect.bottom - 1 - (v / 100) * (rect.h - 2)) for i, v in enumerate(values)]
        poly = [(rect.x, rect.bottom)] + pts + [(rect.right - 1, rect.bottom)]
        fill = pygame.Surface(rect.size, pygame.SRCALPHA)
        pygame.draw.polygon(fill, (*color, 50), [(x - rect.x, y - rect.y) for x, y in poly])
        self.s.blit(fill, rect.topleft)
        pygame.draw.lines(self.s, color, False, pts, 2)

    def hint(self, items, y=H - 26, center=None):
        x = 14
        if center is not None:
            total = sum(max(22, self.f_small.size(b)[0] + 12) + 6 + self.f_small.size(l)[0] + 14 for b, l in items) - 14
            x = center - total // 2
        for btn, label in items:
            bw = max(22, self.f_small.size(btn)[0] + 12)
            pygame.draw.rect(self.s, C["panel2"], (x, y, bw, 20), border_radius=10)
            self.text(btn, (x + bw // 2, y + 10), self.f_small, C["text"], "center")
            r = self.text(label, (x + bw + 6, y + 10), self.f_small, C["dim"], "midleft")
            x = r.right + 14


# --------------------------------------------------------------------------
# Abas
# --------------------------------------------------------------------------
class Tab:
    name = ""

    def __init__(self, app):
        self.app = app

    def on_button(self, btn, down):
        pass

    def update(self, dt):
        pass

    def draw(self, ui):
        pass

    def hints(self):
        return []

    def leave(self):
        pass


class GridTab(Tab):
    """Grade de botões navegável com o direcional."""
    cols = 3
    items: list = []

    def __init__(self, app):
        super().__init__(app)
        self.sel = 0

    def get_items(self):
        return self.items

    def on_button(self, btn, down):
        items = self.get_items()
        if not down or not items:
            return
        n = len(items)
        if btn == BTN_RIGHT:
            self.sel = (self.sel + 1) % n
        elif btn == BTN_LEFT:
            self.sel = (self.sel - 1) % n
        elif btn == BTN_DOWN:
            self.sel = min(n - 1, self.sel + self.cols) if self.sel + self.cols < n else self.sel % self.cols
        elif btn == BTN_UP:
            self.sel = self.sel - self.cols if self.sel - self.cols >= 0 else min(n - 1, self.sel + self.cols * ((n - 1 - self.sel) // self.cols))
        elif btn == BTN_A:
            self.activate(items[self.sel])

    def activate(self, item):
        pass

    def draw_grid(self, ui, top, cell_h, items, labels):
        gap = 12
        cw = (W - 28 - gap * (self.cols - 1)) // self.cols
        for i, item in enumerate(items):
            r, c = divmod(i, self.cols)
            rect = pygame.Rect(14 + c * (cw + gap), top + r * (cell_h + gap), cw, cell_h)
            sel = i == self.sel
            ui.panel(rect, C["accent_dim"] if sel else C["panel"], 12, C["accent"] if sel else None)
            big, small = labels(item)
            if small:
                ui.text(big, (rect.centerx, rect.centery - 11), ui.f_big, C["text"], "center", rect.w - 16)
                ui.text(small, (rect.centerx, rect.centery + 18), ui.f_small, C["dim"], "center", rect.w - 16)
            else:
                ui.text(big, rect.center, ui.f_b, C["text"], "center", rect.w - 16)


class DashboardTab(Tab):
    name = "Painel"

    def __init__(self, app):
        super().__init__(app)
        self.cpu_hist = deque(maxlen=40)
        self.ram_hist = deque(maxlen=40)
        self.gpu_hist = deque(maxlen=40)

    def on_stats(self, d):
        self.cpu_hist.append(d["cpu"])
        self.ram_hist.append(d["ram_pct"])
        if d.get("gpu"):
            self.gpu_hist.append(d["gpu"]["util"])

    def draw(self, ui):
        d = self.app.stats
        if not d:
            ui.text("Aguardando dados do PC…", (W // 2, 230), ui.f_big, C["dim"], "center")
            return
        # Linha 1: CPU, memória e GPU
        cards = [
            ("CPU", d["cpu"], f"{d['cpu_mhz']} MHz" if d.get("cpu_mhz") else "", self.cpu_hist, C["accent"]),
            ("Memória", d["ram_pct"], f"{human_bytes(d['ram_used'])} / {human_bytes(d['ram_total'])}", self.ram_hist, (170, 130, 255)),
        ]
        g = d.get("gpu")
        if g:
            cards.append(("GPU", g["util"], f"{g['temp']:.0f}°C · {human_bytes(g['mem_used'])} / {human_bytes(g['mem_total'])}",
                          self.gpu_hist, (80, 200, 120)))
        cw = (W - 28 - 12 * (len(cards) - 1)) // len(cards)
        for i, (label, pct, sub, hist, color) in enumerate(cards):
            rect = pygame.Rect(14 + i * (cw + 12), 52, cw, 128)
            ui.panel(rect)
            ui.text(label, (rect.x + 12, rect.y + 10), ui.f, C["dim"])
            ui.text(f"{pct:.0f}%", (rect.right - 12, rect.y + 4), ui.f_huge if len(cards) == 2 else ui.f_big2, level_color(pct), "topright")
            ui.text(sub, (rect.x + 12, rect.y + 36), ui.f_small, C["faint"], maxw=rect.w - 24)
            ui.spark((rect.x + 12, rect.y + 62, rect.w - 24, 54), list(hist), color)

        # Linha 2: discos e rede
        rect = pygame.Rect(14, 192, 300, 128)
        ui.panel(rect)
        ui.text("Discos", (rect.x + 14, rect.y + 10), ui.f, C["dim"])
        for j, disk in enumerate(d["disks"][:3]):
            y = rect.y + 38 + j * 29
            ui.text(disk["name"], (rect.x + 14, y), ui.f_b)
            ui.bar((rect.x + 50, y + 5, 150, 10), disk["pct"])
            ui.text(f"{human_bytes(disk['total'] - disk['used'])} livres", (rect.right - 12, y + 1), ui.f_small, C["dim"], "topright")

        rect = pygame.Rect(326, 192, 300, 128)
        ui.panel(rect)
        ui.text("Rede", (rect.x + 14, rect.y + 10), ui.f, C["dim"])
        ui.text("↓", (rect.x + 14, rect.y + 40), ui.f_big, C["ok"])
        ui.text(human_bytes(d["net_down"], True), (rect.x + 40, rect.y + 42), ui.f_big)
        ui.text("↑", (rect.x + 14, rect.y + 78), ui.f_big, C["accent"])
        ui.text(human_bytes(d["net_up"], True), (rect.x + 40, rect.y + 80), ui.f_big)

        # Linha 3: janela ativa e processos
        rect = pygame.Rect(14, 332, 612, 112)
        ui.panel(rect)
        ui.text("Janela ativa", (rect.x + 14, rect.y + 8), ui.f_small, C["faint"])
        ui.text(d.get("window") or "—", (rect.x + 14, rect.y + 24), ui.f_b, C["text"], maxw=rect.w - 28)
        ui.text("Processos (CPU)", (rect.x + 14, rect.y + 52), ui.f_small, C["faint"])
        for j, p in enumerate(d["procs"][:4]):
            x = rect.x + 14 + (j % 2) * 300
            y = rect.y + 70 + (j // 2) * 20
            ui.text(p["name"].removesuffix(".exe"), (x, y), ui.f_small, C["text"], maxw=170)
            ui.text(f"{p['cpu']:.1f}%  {human_bytes(p['mem'])}", (x + 285, y), ui.f_small, C["dim"], "topright")

    def hints(self):
        up = human_uptime(self.app.stats["uptime_s"]) if self.app.stats else "—"
        return [("L1/R1", "Abas"), ("PC ligado", up)]


def fmt_time(sec):
    sec = int(max(0, sec or 0))
    return f"{sec // 3600}:{sec % 3600 // 60:02d}:{sec % 60:02d}" if sec >= 3600 else f"{sec // 60}:{sec % 60:02d}"


class MediaTab(Tab):
    name = "Tocando"
    BUTTONS = [("media.prev", "prev"), ("media.play_pause", "play"), ("media.next", "next"),
               ("volume.change", "vol-"), ("media.mute", "mute"), ("volume.change", "vol+")]

    def __init__(self, app):
        super().__init__(app)
        self.sel = 1

    def press(self, idx):
        action, kind = self.BUTTONS[idx]
        params = {"delta": -5} if kind == "vol-" else {"delta": 5} if kind == "vol+" else None
        self.app.do(action, params, quiet=True)
        self.app.flash(idx)

    def on_button(self, btn, down):
        if not down:
            return
        if btn == BTN_LEFT:
            self.sel = (self.sel - 1) % len(self.BUTTONS)
        elif btn == BTN_RIGHT:
            self.sel = (self.sel + 1) % len(self.BUTTONS)
        elif btn == BTN_A:
            self.press(self.sel)
        elif btn == BTN_Y:
            self.press(1)
        elif btn == BTN_X:
            self.press(4)
        elif btn == BTN_UP:
            self.press(5)
        elif btn == BTN_DOWN:
            self.press(3)
        elif btn in (BTN_L2, BTN_R2):
            m = self.app.now.get("media") or {}
            if m.get("can_seek"):
                self.app.do("media.seek", {"delta": -10 if btn == BTN_L2 else 10}, quiet=True)
            else:
                self.app.toast("Este player não permite avançar", C["warn"])

    def draw(self, ui):
        m = self.app.now.get("media")
        vol = self.app.now.get("volume")
        # Capa
        art_rect = pygame.Rect(14, 54, 200, 200)
        art = self.app.art.get(m.get("art")) if m else None
        if art:
            ui.s.blit(art, art_rect)
            pygame.draw.rect(ui.s, C["line"], art_rect, 1, border_radius=4)
        else:
            ui.panel(art_rect, C["panel"], 12)
            pygame.draw.circle(ui.s, C["panel2"], art_rect.center, 60)
            pygame.draw.circle(ui.s, C["line"], art_rect.center, 14)
            ui.text("♪", art_rect.center, ui.f_huge, C["faint"], "center")

        x, w = 232, W - 232 - 14
        if not m:
            ui.text("Nada tocando", (x, 90), ui.f_big, C["text"])
            ui.text("Abra o Spotify, YouTube ou outro player", (x, 126), ui.f, C["dim"])
            ui.text("no PC e ele aparece aqui.", (x, 148), ui.f, C["dim"])
        else:
            status = {"playing": ("Tocando", C["ok"]), "paused": ("Pausado", C["warn"])}.get(m["status"], ("Parado", C["dim"]))
            chip = ui.text(m["app"], (x + 10, 66), ui.f_small, C["text"], "midleft")
            pygame.draw.rect(ui.s, C["panel2"], (x, 56, chip.w + 20, 22), border_radius=11)
            ui.text(m["app"], (x + 10, 67), ui.f_small, C["text"], "midleft")
            ui.text(status[0], (x + chip.w + 32, 67), ui.f_small, status[1], "midleft")
            ui.text(m["title"] or "Sem título", (x, 92), ui.f_big, C["text"], maxw=w)
            ui.text(m["artist"], (x, 126), ui.f_b, C["dim"], maxw=w)
            ui.text(m["album"], (x, 150), ui.f, C["faint"], maxw=w)
            # Progresso (interpolado localmente enquanto toca)
            pos, dur = m["pos"], m["dur"]
            if m["status"] == "playing":
                pos = min(dur or pos, pos + (time.monotonic() - self.app.now_t))
            if dur > 0:
                ui.bar((x, 204, w, 8), pos / dur * 100, C["accent"])
                ui.text(fmt_time(pos), (x, 218), ui.f_small, C["dim"])
                ui.text(fmt_time(dur), (x + w, 218), ui.f_small, C["dim"], "topright")

        # Botões
        gap, top, bh = 10, 272, 84
        bw = (W - 28 - gap * 5) // 6
        playing = bool(m and m["status"] == "playing")
        for i, (_a, kind) in enumerate(self.BUTTONS):
            rect = pygame.Rect(14 + i * (bw + gap), top, bw, bh)
            sel = i == self.sel
            flash = self.app.flash_idx == i and time.monotonic() - self.app.flash_t < 0.18
            ui.panel(rect, C["accent"] if flash else C["accent_dim"] if sel else C["panel"], 12, C["accent"] if sel else None)
            self._icon(ui, kind, rect.center, playing, bool(vol and vol["muted"]))

        # Volume
        vy = 374
        ui.panel(pygame.Rect(14, vy, W - 28, 52))
        if vol:
            muted = vol["muted"]
            ui.text("Volume", (30, vy + 26), ui.f_b, C["dim"], "midleft")
            ui.bar((112, vy + 21, W - 220, 10), vol["level"], C["faint"] if muted else C["accent"])
            ui.text("Mudo" if muted else f"{vol['level']}%", (W - 30, vy + 26), ui.f_b, C["warn"] if muted else C["text"], "midright")
        else:
            ui.text("Volume indisponível", (W // 2, vy + 26), ui.f, C["faint"], "center")

    @staticmethod
    def _icon(ui, kind, center, playing, muted):
        x, y = center
        col = C["text"]
        if kind == "play":
            if playing:
                pygame.draw.rect(ui.s, col, (x - 12, y - 14, 8, 28))
                pygame.draw.rect(ui.s, col, (x + 4, y - 14, 8, 28))
            else:
                pygame.draw.polygon(ui.s, col, [(x - 9, y - 15), (x - 9, y + 15), (x + 14, y)])
        elif kind == "next":
            pygame.draw.polygon(ui.s, col, [(x - 14, y - 12), (x - 14, y + 12), (x + 4, y)])
            pygame.draw.rect(ui.s, col, (x + 6, y - 12, 5, 24))
        elif kind == "prev":
            pygame.draw.polygon(ui.s, col, [(x + 14, y - 12), (x + 14, y + 12), (x - 4, y)])
            pygame.draw.rect(ui.s, col, (x - 11, y - 12, 5, 24))
        else:
            # alto-falante
            pygame.draw.rect(ui.s, col, (x - 16, y - 6, 7, 12))
            pygame.draw.polygon(ui.s, col, [(x - 9, y - 6), (x, y - 14), (x, y + 14), (x - 9, y + 6)])
            if kind == "mute":
                c2 = C["warn"] if muted else col
                pygame.draw.line(ui.s, c2, (x + 5, y - 7), (x + 17, y + 7), 3)
                pygame.draw.line(ui.s, c2, (x + 5, y + 7), (x + 17, y - 7), 3)
            elif kind == "vol+":
                pygame.draw.line(ui.s, col, (x + 5, y), (x + 17, y), 3)
                pygame.draw.line(ui.s, col, (x + 11, y - 6), (x + 11, y + 6), 3)
            else:
                pygame.draw.line(ui.s, col, (x + 5, y), (x + 17, y), 3)

    def hints(self):
        return [("A", "Executar"), ("Y", "Play"), ("↑↓", "Volume"), ("L2/R2", "−/+10s"), ("X", "Mudo")]


def human_dur(sec):
    sec = int(max(0, sec or 0))
    if sec < 60:
        return f"{sec}s"
    h, m = divmod(sec // 60, 60)
    return f"{h}h {m:02d}m" if h else f"{m} min"


def human_ago(sec):
    sec = int(max(0, sec or 0))
    if sec < 120:
        return "agora"
    if sec < 3600:
        return f"há {sec // 60} min"
    if sec < 86400:
        return f"há {sec // 3600} h"
    days = sec // 86400
    return "ontem" if days == 1 else f"há {days} dias"


class GamesTab(Tab):
    name = "Games"
    BUTTONS = [("discord.mute", "Mutar"), ("discord.deafen", "Ensurdecer"), ("discord.open", "Abrir")]
    STORE_COLORS = {"Steam": (102, 192, 244), "Epic": (220, 220, 220), "Riot": (235, 87, 87),
                    "GOG": (170, 130, 255), "EA": (240, 120, 80), "Ubisoft": (88, 166, 255)}

    def __init__(self, app):
        super().__init__(app)
        self.sel = 0

    def on_button(self, btn, down):
        if not down:
            return
        if btn == BTN_LEFT:
            self.sel = (self.sel - 1) % len(self.BUTTONS)
        elif btn == BTN_RIGHT:
            self.sel = (self.sel + 1) % len(self.BUTTONS)
        elif btn == BTN_A:
            action, label = self.BUTTONS[self.sel]
            self.app.do(action, label={"Mutar": "Discord: mutar/desmutar", "Ensurdecer": "Discord: ensurdecer",
                                       "Abrir": "Abrindo Discord"}[label])
            self.app.flash(self.sel)

    def draw(self, ui):
        d = self.app.games
        g = d.get("game")
        since = time.monotonic() - self.app.games_t

        # Card do jogo atual
        card = pygame.Rect(14, 52, W - 28, 166)
        ui.panel(card)
        art_rect = pygame.Rect(card.x + 12, card.y + 13, 300, 140)
        art = self.app.gameart.get(g.get("art")) if g else None
        if art:
            ui.s.blit(art, art_rect)
        else:
            pygame.draw.rect(ui.s, C["panel2"], art_rect, border_radius=8)
            self._pad_icon(ui, art_rect.center, C["accent"] if g else C["faint"])
            if g:
                ui.text(g["name"][:1].upper(), (art_rect.right - 22, art_rect.bottom - 22), ui.f_big, C["dim"], "center")

        x, w = art_rect.right + 16, card.right - art_rect.right - 28
        if g:
            col = self.STORE_COLORS.get(g["store"], C["dim"])
            chip_w = ui.f_small.size(g["store"])[0] + 18
            pygame.draw.rect(ui.s, C["panel2"], (x, card.y + 14, chip_w, 20), border_radius=10)
            ui.text(g["store"], (x + chip_w // 2, card.y + 24), ui.f_small, col, "center")
            pygame.draw.circle(ui.s, C["ok"], (x + chip_w + 12, card.y + 24), 4)
            ui.text("jogando", (x + chip_w + 20, card.y + 24), ui.f_small, C["ok"], "midleft")
            ui.text(g["name"], (x, card.y + 42), ui.f_b, C["text"], maxw=w)
            ui.text(human_dur(g["elapsed"] + since), (x, card.y + 66), ui.f_huge, C["text"])
            extra = [f"Hoje: {human_dur(g['today_s'] + since)}"]
            if g.get("total_h"):
                extra.append(f"Total: {g['total_h']:.0f} h")
            ui.text(" · ".join(extra), (x, card.y + 132), ui.f_small, C["dim"], maxw=w)
        else:
            ui.text("Nenhum jogo aberto", (x, card.y + 40), ui.f_big, C["text"], maxw=w)
            today = d.get("today_s") or 0
            ui.text(f"Hoje: {human_dur(today)} jogando" if today else "Abra um jogo no PC", (x, card.y + 78), ui.f, C["dim"], maxw=w)
            ui.text("Steam, Epic, GOG, Riot, EA, Ubisoft", (x, card.y + 104), ui.f_small, C["faint"], maxw=w)

        # Recentes
        rect = pygame.Rect(14, 230, 300, 216)
        ui.panel(rect)
        ui.text("Recentes", (rect.x + 14, rect.y + 10), ui.f, C["dim"])
        recent = d.get("recent") or []
        if not recent:
            ui.text("Nenhuma sessão ainda", (rect.x + 14, rect.y + 44), ui.f_small, C["faint"])
        for i, r in enumerate(recent[:4]):
            y = rect.y + 40 + i * 43
            ui.text(r["name"], (rect.x + 14, y), ui.f_b, C["text"], maxw=rect.w - 28)
            ui.text(f"{human_dur(r['dur'])} · {human_ago(r['ago'] + since)}", (rect.x + 14, y + 20), ui.f_small, C["faint"])

        # Discord
        rect = pygame.Rect(326, 230, 300, 216)
        ui.panel(rect)
        dc = d.get("discord") or {}
        on = dc.get("running")
        pygame.draw.circle(ui.s, (88, 101, 242) if on else C["faint"], (rect.x + 22, rect.y + 21), 7)
        ui.text("Discord", (rect.x + 36, rect.y + 10), ui.f_b, C["text"])
        ui.text("aberto" if on else "fechado", (rect.right - 14, rect.y + 12), ui.f_small, C["ok"] if on else C["faint"], "topright")
        if on and (dc.get("channel") or dc.get("server")):
            ui.text(dc.get("channel") or "", (rect.x + 14, rect.y + 44), ui.f_b, C["text"], maxw=rect.w - 28)
            ui.text(dc.get("server") or "Mensagem direta", (rect.x + 14, rect.y + 68), ui.f_small, C["dim"], maxw=rect.w - 28)
        elif on:
            ui.text("Nenhum canal aberto", (rect.x + 14, rect.y + 48), ui.f_small, C["dim"])
        else:
            ui.text("Abra o Discord no PC", (rect.x + 14, rect.y + 48), ui.f_small, C["dim"])
        gap, bw, bh = 8, (rect.w - 28 - 16) // 3, 70
        for i, (_a, label) in enumerate(self.BUTTONS):
            b = pygame.Rect(rect.x + 14 + i * (bw + gap), rect.bottom - bh - 14, bw, bh)
            sel = i == self.sel
            flash = self.app.flash_idx == i and time.monotonic() - self.app.flash_t < 0.18
            ui.panel(b, C["accent"] if flash else C["accent_dim"] if sel else C["panel2"], 10, C["accent"] if sel else None)
            self._dc_icon(ui, label, (b.centerx, b.y + 26))
            ui.text(label, (b.centerx, b.bottom - 16), ui.f_small, C["text"], "center", bw - 6)

    @staticmethod
    def _pad_icon(ui, center, col):
        x, y = center
        pygame.draw.rect(ui.s, col, (x - 38, y - 18, 76, 36), border_radius=18)
        pygame.draw.rect(ui.s, C["panel2"], (x - 26, y - 3, 16, 6))
        pygame.draw.rect(ui.s, C["panel2"], (x - 21, y - 8, 6, 16))
        pygame.draw.circle(ui.s, C["panel2"], (x + 18, y - 4), 4)
        pygame.draw.circle(ui.s, C["panel2"], (x + 26, y + 4), 4)

    @staticmethod
    def _dc_icon(ui, label, center):
        x, y = center
        col = C["text"]
        if label == "Mutar":  # microfone riscado
            pygame.draw.rect(ui.s, col, (x - 5, y - 13, 10, 18), border_radius=5)
            pygame.draw.arc(ui.s, col, (x - 10, y - 8, 20, 18), 3.4, 6.0, 2)
            pygame.draw.line(ui.s, col, (x, y + 9), (x, y + 13), 2)
            pygame.draw.line(ui.s, C["bad"], (x - 11, y - 13), (x + 11, y + 11), 3)
        elif label == "Ensurdecer":  # fone riscado
            pygame.draw.arc(ui.s, col, (x - 12, y - 13, 24, 24), 0, 3.14, 3)
            pygame.draw.rect(ui.s, col, (x - 13, y - 1, 7, 12), border_radius=3)
            pygame.draw.rect(ui.s, col, (x + 6, y - 1, 7, 12), border_radius=3)
            pygame.draw.line(ui.s, C["bad"], (x - 13, y - 13), (x + 13, y + 11), 3)
        else:  # abrir
            pygame.draw.rect(ui.s, col, (x - 12, y - 10, 22, 22), 2, border_radius=4)
            pygame.draw.line(ui.s, col, (x - 2, y + 1), (x + 12, y - 13), 3)
            pygame.draw.lines(ui.s, col, False, [(x + 3, y - 13), (x + 12, y - 13), (x + 12, y - 4)], 3)

    def hints(self):
        return [("←→", "Discord"), ("A", "Executar"), ("L1/R1", "Abas")]


class ShortcutsTab(Tab):
    name = "Atalhos"

    def __init__(self, app):
        super().__init__(app)
        self.sel = 0
        self.scroll = 0

    def items(self):
        return self.app.link.welcome.get("shortcuts", [])

    def on_button(self, btn, down):
        items = self.items()
        if not down or not items:
            return
        if btn == BTN_DOWN:
            self.sel = (self.sel + 1) % len(items)
        elif btn == BTN_UP:
            self.sel = (self.sel - 1) % len(items)
        elif btn == BTN_A:
            it = items[self.sel]
            self.app.do("app.launch", {"id": it["id"]}, label=f"Abrindo {it['name']}")

    def draw(self, ui):
        items = self.items()
        if not items:
            ui.text("Nenhum atalho configurado no PC.", (W // 2, 200), ui.f_big, C["dim"], "center")
            ui.text("Edite \"shortcuts\" no config.json do servidor.", (W // 2, 236), ui.f, C["faint"], "center")
            return
        row_h, top, visible = 50, 54, 7
        self.scroll = max(min(self.scroll, self.sel), self.sel - visible + 1)
        for i, it in enumerate(items[self.scroll:self.scroll + visible]):
            idx = i + self.scroll
            rect = pygame.Rect(14, top + i * (row_h + 6), W - 28, row_h)
            sel = idx == self.sel
            ui.panel(rect, C["accent_dim"] if sel else C["panel"], 10, C["accent"] if sel else None)
            badge = pygame.Rect(rect.x + 10, rect.y + 9, 32, 32)
            pygame.draw.rect(ui.s, C["accent"] if sel else C["panel2"], badge, border_radius=8)
            ui.text(it["name"][:1].upper(), badge.center, ui.f_b, C["bg"] if sel else C["text"], "center")
            ui.text(it["name"], (rect.x + 56, rect.centery), ui.f_b, C["text"], "midleft", rect.w - 70)
        if len(items) > visible:
            ui.text(f"{self.sel + 1}/{len(items)}", (W - 16, top - 22), ui.f_small, C["faint"], "topright")

    def hints(self):
        return [("A", "Abrir"), ("↑↓", "Escolher"), ("L1/R1", "Abas")]


class ControlTab(Tab):
    name = "Controle"
    DEAD = 0.14

    def __init__(self, app):
        super().__init__(app)
        self.acc = [0.0, 0.0]
        self.scroll_acc = [0.0, 0.0]
        self.alt_held = False
        self.last_alt_tab = 0
        self.dragging = False
        self.pressed = set()

    def curve(self, v):
        a = abs(v)
        if a < self.DEAD:
            return 0.0
        a = (a - self.DEAD) / (1 - self.DEAD)
        return (a ** 2.2) * (1 if v > 0 else -1)

    def update(self, dt):
        js = self.app.joy
        if not js or not self.app.link.connected:
            return
        lx, ly = self.curve(js.get_axis(0)), self.curve(js.get_axis(1))
        rx, ry = (self.curve(js.get_axis(2)), self.curve(js.get_axis(3))) if js.get_numaxes() >= 4 else (0, 0)
        speed = 1400.0
        if js.get_button(BTN_R2):
            speed *= 2.2
        if js.get_button(BTN_L2):
            speed *= 0.3
        self.acc[0] += lx * speed * dt
        self.acc[1] += ly * speed * dt
        dx, dy = int(self.acc[0]), int(self.acc[1])
        if dx or dy:
            self.acc[0] -= dx
            self.acc[1] -= dy
            self.app.link.send("mouse.move", {"dx": dx, "dy": dy}, want_reply=False)
        self.scroll_acc[0] += rx * 1600 * dt
        self.scroll_acc[1] += -ry * 1600 * dt
        sx, sy = int(self.scroll_acc[0] / 40) * 40, int(self.scroll_acc[1] / 40) * 40
        if sx or sy:
            self.scroll_acc[0] -= sx
            self.scroll_acc[1] -= sy
            self.app.link.send("mouse.scroll", {"dx": sx, "dy": sy}, want_reply=False)
        if self.alt_held and time.monotonic() - self.last_alt_tab > 1.2:
            self.app.link.send("key.up", {"key": "alt"}, want_reply=False)
            self.alt_held = False

    def on_button(self, btn, down):
        link = self.app.link
        (self.pressed.add if down else self.pressed.discard)(btn)
        if btn == BTN_A:
            link.send("mouse.button", {"button": "left", "state": "down" if down else "up"}, want_reply=False)
            return
        if not down:
            return
        if btn == BTN_B:
            link.send("mouse.button", {"button": "right"}, want_reply=False)
        elif btn == BTN_L3:
            link.send("mouse.button", {"button": "middle"}, want_reply=False)
        elif btn == BTN_Y:
            if not self.alt_held:
                link.send("key.down", {"key": "alt"}, want_reply=False)
                self.alt_held = True
            link.send("key.press", {"keys": "tab"}, want_reply=False)
            self.last_alt_tab = time.monotonic()
        elif btn == BTN_X:
            link.send("key.press", {"keys": "win"}, want_reply=False)
        elif btn in (BTN_UP, BTN_DOWN, BTN_LEFT, BTN_RIGHT):
            key = {BTN_UP: "up", BTN_DOWN: "down", BTN_LEFT: "left", BTN_RIGHT: "right"}[btn]
            link.send("key.press", {"keys": key}, want_reply=False)
        elif btn == BTN_R3:
            link.send("key.press", {"keys": "space"}, want_reply=False)

    def on_tap(self, btn):
        """Select/Start sozinhos (sem combo de saída)."""
        if btn == BTN_START:
            self.app.link.send("key.press", {"keys": "enter"}, want_reply=False)
        elif btn == BTN_SELECT:
            self.app.link.send("key.press", {"keys": "esc"}, want_reply=False)

    def leave(self):
        if self.alt_held:
            self.app.link.send("key.up", {"key": "alt"}, want_reply=False)
            self.alt_held = False
        if BTN_A in self.pressed:
            self.app.link.send("mouse.button", {"button": "left", "state": "up"}, want_reply=False)
        self.pressed.clear()

    def draw(self, ui):
        js = self.app.joy
        # Indicadores dos analógicos
        for i, (label, ax) in enumerate((("Mouse", (0, 1)), ("Rolagem", (2, 3)))):
            cx, cy = 120 + i * 200, 150
            pygame.draw.circle(ui.s, C["panel"], (cx, cy), 62)
            pygame.draw.circle(ui.s, C["line"], (cx, cy), 62, 2)
            pygame.draw.circle(ui.s, C["line"], (cx, cy), int(62 * self.DEAD), 1)
            vx = js.get_axis(ax[0]) if js and js.get_numaxes() > ax[1] else 0
            vy = js.get_axis(ax[1]) if js and js.get_numaxes() > ax[1] else 0
            active = abs(vx) > self.DEAD or abs(vy) > self.DEAD
            pygame.draw.circle(ui.s, C["accent"] if active else C["dim"], (int(cx + vx * 48), int(cy + vy * 48)), 14)
            ui.text(label, (cx, cy + 74), ui.f_b, C["text"], "center")
            ui.text("analógico " + ("esq." if i == 0 else "dir."), (cx, cy + 96), ui.f_small, C["faint"], "center")

        rect = pygame.Rect(436, 52, 190, 392)
        ui.panel(rect)
        rows = [("A", "Clique / arrastar"), ("B", "Clique direito"), ("L3", "Clique do meio"),
                ("X", "Tecla Windows"), ("Y", "Alt+Tab"), ("✚", "Setas"), ("R3", "Espaço"),
                ("START", "Enter"), ("SELECT", "Esc"), ("R2", "Mouse rápido"), ("L2", "Mouse preciso")]
        for j, (b, d) in enumerate(rows):
            y = rect.y + 14 + j * 34
            bw = max(26, ui.f_small.size(b)[0] + 12)
            pygame.draw.rect(ui.s, C["panel2"], (rect.x + 12, y, bw, 22), border_radius=11)
            ui.text(b, (rect.x + 12 + bw // 2, y + 11), ui.f_small, C["text"], "center")
            ui.text(d, (rect.x + 20 + bw, y + 11), ui.f_small, C["dim"], "midleft", rect.right - (rect.x + 26 + bw))

        ui.panel(pygame.Rect(14, 290, 410, 154))
        ui.text("Modo controle ativo", (30, 306), ui.f_b, C["ok"] if self.app.link.connected else C["bad"])
        ui.text("O R36S está controlando o mouse e o teclado", (30, 334), ui.f_small, C["dim"])
        ui.text("do PC. Troque de aba (L1/R1) para parar.", (30, 354), ui.f_small, C["dim"])
        ui.text("Segure SELECT + START para sair do app.", (30, 384), ui.f_small, C["faint"])

    def hints(self):
        return [("L1/R1", "Abas"), ("SELECT+START", "Sair")]


class SystemTab(GridTab):
    name = "Sistema"
    cols = 2

    def get_items(self):
        items = [
            ("key", {"keys": "win+d"}, "Mostrar área de trabalho", False),
            ("key", {"keys": "win+shift+s"}, "Captura de tela", False),
            ("key", {"keys": "alt+f4"}, "Fechar janela ativa", True),
            ("power", {"action": "lock"}, "Bloquear o PC", False),
        ]
        if self.app.link.welcome.get("power"):
            items += [
                ("power", {"action": "monitor_off"}, "Desligar monitor", False),
                ("power", {"action": "sleep"}, "Suspender", True),
                ("power", {"action": "restart"}, "Reiniciar", True),
                ("power", {"action": "shutdown"}, "Desligar", True),
                ("power", {"action": "cancel"}, "Cancelar desligamento", False),
            ]
        boot_on = not NO_BOOT_FLAG.exists()
        items += [
            ("local", "boot", f"Iniciar no Companion: {'sim' if boot_on else 'não'}", False),
            ("local", "exit", "Sair para o EmulationStation", False),
        ]
        return items

    def activate(self, item):
        kind, params, label, confirm = item
        if kind == "local":
            if params == "exit":
                self.app.running = False
            elif NO_BOOT_FLAG.exists():
                NO_BOOT_FLAG.unlink()
                self.app.toast("O R36S vai abrir no Companion", C["ok"])
            else:
                NO_BOOT_FLAG.parent.mkdir(parents=True, exist_ok=True)
                NO_BOOT_FLAG.touch()
                self.app.toast("O R36S vai abrir no EmulationStation", C["ok"])
            return
        action = "key.press" if kind == "key" else "power"
        run = lambda: self.app.do(action, params, label=label)  # noqa: E731
        if confirm:
            self.app.confirm(f"{label}?", run)
        else:
            run()

    def draw(self, ui):
        items = self.get_items()
        self.sel = min(self.sel, len(items) - 1)
        gap, top, cell_h = 8, 52, 56
        cw = (W - 28 - gap) // 2
        for i, (kind, _p, label, confirm) in enumerate(items):
            r, c = divmod(i, 2)
            rect = pygame.Rect(14 + c * (cw + gap), top + r * (cell_h + gap), cw, cell_h)
            sel = i == self.sel
            ui.panel(rect, C["accent_dim"] if sel else C["panel"], 12, C["accent"] if sel else None)
            dot = C["warn"] if confirm else C["dim"] if kind == "local" else (C["accent"] if kind == "power" else C["ok"])
            pygame.draw.circle(ui.s, dot, (rect.x + 20, rect.centery), 6)
            ui.text(label, (rect.x + 36, rect.centery), ui.f_b, C["text"], "midleft", rect.w - 46)

    def hints(self):
        return [("A", "Executar"), ("✚", "Escolher"), ("L1/R1", "Abas")]


# --------------------------------------------------------------------------
# Aplicativo
# --------------------------------------------------------------------------
class App:
    def __init__(self, shot_dir=None):
        pygame.init()
        pygame.joystick.init()
        flags = 0 if shot_dir else pygame.FULLSCREEN
        self.screen = pygame.display.set_mode((W, H), flags)
        pygame.display.set_caption("PC Companion")
        pygame.mouse.set_visible(False)
        # analógicos oscilam e geram eventos sem parar; a aba Controle lê o estado direto
        pygame.event.set_blocked([pygame.JOYAXISMOTION, pygame.JOYBALLMOTION, pygame.MOUSEMOTION])
        self.ui = UI(self.screen)
        self.clock = pygame.time.Clock()
        self.joy = pygame.joystick.Joystick(0) if pygame.joystick.get_count() else None
        self.link = Link()
        self.link.start()
        self.stats = None
        self.now = {}
        self.now_t = 0.0
        self.art = {}
        self.games, self.games_t, self.gameart = {}, 0.0, {}
        self.toasts = deque(maxlen=3)
        self.pending = {}
        self.dialog = None
        self.flash_idx, self.flash_t = None, 0.0
        self.tabs = [DashboardTab(self), MediaTab(self), GamesTab(self), ShortcutsTab(self), ControlTab(self), SystemTab(self)]
        self.tab = 0
        self.held = set()
        self.combo_used = False
        self.exit_t = None
        self.shot_dir = shot_dir
        self.running = True
        self.dirty = True
        self.last_draw = 0.0
        self.last_activity = time.monotonic()

    # -- ações --
    def do(self, action, params=None, label=None, quiet=False):
        if not self.link.connected:
            self.toast("Sem conexão com o PC", C["bad"])
            return
        rid = self.link.send(action, params)
        self.pending[rid] = (label or action, quiet)

    def toast(self, msg, color=None):
        self.dirty = True
        self.toasts.append((msg, color or C["text"], time.monotonic()))

    def flash(self, idx):
        self.flash_idx, self.flash_t = idx, time.monotonic()

    def confirm(self, question, on_yes):
        self.dialog = (question, on_yes)

    def switch_tab(self, delta):
        self.tabs[self.tab].leave()
        self.tab = (self.tab + delta) % len(self.tabs)

    # -- entrada --
    def button(self, btn, down):
        self.dirty = True
        self.last_activity = time.monotonic()
        (self.held.add if down else self.held.discard)(btn)
        if BTN_SELECT in self.held and BTN_START in self.held:
            self.combo_used = True
            if self.exit_t is None:
                self.exit_t = time.monotonic()
            return
        self.exit_t = None

        if self.dialog:
            if down and btn == BTN_A:
                _q, fn = self.dialog
                self.dialog = None
                fn()
            elif down and btn == BTN_B:
                self.dialog = None
            return

        if btn in (BTN_SELECT, BTN_START):
            if not down:
                if not self.combo_used and not (self.held & {BTN_SELECT, BTN_START}):
                    tab = self.tabs[self.tab]
                    if hasattr(tab, "on_tap"):
                        tab.on_tap(btn)
                if not (self.held & {BTN_SELECT, BTN_START}):
                    self.combo_used = False
            return
        if down and btn == BTN_L1:
            self.switch_tab(-1)
            return
        if down and btn == BTN_R1:
            self.switch_tab(1)
            return
        self.tabs[self.tab].on_button(btn, down)

    def events(self):
        for e in pygame.event.get():
            if e.type == pygame.QUIT:
                self.running = False
            elif e.type in (pygame.JOYBUTTONDOWN, pygame.JOYBUTTONUP):
                self.button(e.button, e.type == pygame.JOYBUTTONDOWN)
            elif e.type in (pygame.KEYDOWN, pygame.KEYUP):
                if e.key == pygame.K_ESCAPE:
                    self.running = False
                elif e.key in KEYMAP:
                    self.button(KEYMAP[e.key], e.type == pygame.KEYDOWN)
            elif e.type == pygame.JOYDEVICEADDED and not self.joy:
                self.joy = pygame.joystick.Joystick(e.device_index)

    def network(self):
        while True:
            try:
                m = self.link.inbox.get_nowait()
            except queue.Empty:
                break
            t = m.get("t")
            self.dirty = True
            if t == "stats":
                self.stats = m["d"]
                self.tabs[0].on_stats(m["d"])
            elif t == "now":
                self.now, self.now_t = m["d"], time.monotonic()
            elif t == "art":
                try:
                    img = pygame.image.load(io.BytesIO(base64.b64decode(m["jpg"])), "capa.jpg").convert()
                    self.art = {m["id"]: pygame.transform.smoothscale(img, (200, 200))}
                except (pygame.error, ValueError):
                    pass
            elif t == "games":
                self.games, self.games_t = m["d"], time.monotonic()
            elif t == "gameart":
                try:
                    img = pygame.image.load(io.BytesIO(base64.b64decode(m["jpg"])), "jogo.jpg").convert()
                    self.gameart = {m["id"]: pygame.transform.smoothscale(img, (300, 140))}
                except (pygame.error, ValueError):
                    pass
            elif t == "welcome":
                self.toast(f"Conectado a {m.get('host')}", C["ok"])
            elif t == "down":
                self.stats = None
                self.now = {}
                self.games = {}
            elif t == "res":
                label, quiet = self.pending.pop(m.get("id"), (m.get("a"), False))
                if not m.get("ok"):
                    self.toast(f"Falhou: {m.get('e', label)}", C["bad"])
                elif not quiet:
                    self.toast(label, C["ok"])

    # -- desenho --
    def draw(self):
        ui = self.ui
        self.screen.fill(C["bg"])
        # cabeçalho com abas
        x = 10
        for i, tab in enumerate(self.tabs):
            w = ui.f_b.size(tab.name)[0] + 16
            rect = pygame.Rect(x, 8, w, 32)
            if i == self.tab:
                pygame.draw.rect(self.screen, C["accent"], rect, border_radius=16)
                ui.text(tab.name, rect.center, ui.f_b, C["bg"], "center")
            else:
                ui.text(tab.name, rect.center, ui.f, C["dim"], "center")
            x += w
        # status: conexão + bateria + hora
        connected = self.link.connected
        clock = ui.text(self.stats["time"][:5] if self.stats else time.strftime("%H:%M"), (W - 12, 24), ui.f_b, C["text"], "midright")
        x = clock.left - 10
        cap, charging = r36s_battery()
        if cap is not None:
            x = ui.text(f"{cap}%{'+' if charging else ''}", (x, 24), ui.f_small, C["dim"], "midright").left - 10
        pygame.draw.circle(self.screen, C["ok"] if connected else C["bad"], (x - 4, 24), 5)

        offline_ok = self.tab == 0 or isinstance(self.tabs[self.tab], SystemTab)
        if connected or offline_ok:
            self.tabs[self.tab].draw(ui)
        if not connected and not isinstance(self.tabs[self.tab], SystemTab):
            self.offline_overlay()

        pygame.draw.line(self.screen, C["line"], (0, H - 34), (W, H - 34))
        ui.hint(self.tabs[self.tab].hints() if connected else [("SELECT+START", "Sair")])

        # toasts
        now = time.monotonic()
        y = H - 74
        for msg, color, t0 in reversed(self.toasts):
            if now - t0 > 2.5:
                continue
            w = min(W - 40, ui.f.size(msg)[0] + 30)
            rect = pygame.Rect((W - w) // 2, y, w, 32)
            ui.panel(rect, C["panel2"], 16, color)
            ui.text(msg, rect.center, ui.f, C["text"], "center", w - 20)
            y -= 38

        if self.dialog:
            self.draw_dialog()
        if self.exit_t is not None:
            left = max(0.0, 1.0 - (time.monotonic() - self.exit_t))
            ui.panel(pygame.Rect(170, 200, 300, 70), C["panel2"], 14, C["warn"])
            ui.text("Saindo…", (W // 2, 222), ui.f_b, C["warn"], "center")
            ui.bar((190, 244, 260, 8), (1 - left) * 100, C["warn"])
            if left <= 0:
                self.running = False
        pygame.display.flip()

    def offline_overlay(self):
        ui = self.ui
        if self.tab == 0 and self.stats:
            return
        rect = pygame.Rect(80, 140, 480, 170)
        ui.panel(rect, C["panel"], 16, C["line"])
        ui.text(self.link.status, (W // 2, rect.y + 36), ui.f_big, C["bad"] if "Token" in self.link.status else C["text"], "center")
        dots = "." * (int(time.monotonic() * 2) % 4)
        ui.text(f"Procurando {CFG['host']}:{CFG['port']}{dots}", (W // 2, rect.y + 76), ui.f, C["dim"], "center")
        ui.text("Verifique o cabo na porta OTG e se o servidor", (W // 2, rect.y + 112), ui.f_small, C["faint"], "center")
        ui.text("está aberto no Windows. SELECT+START: EmulationStation", (W // 2, rect.y + 132), ui.f_small, C["faint"], "center")

    def draw_dialog(self):
        ui = self.ui
        shade = pygame.Surface((W, H), pygame.SRCALPHA)
        shade.fill((0, 0, 0, 160))
        self.screen.blit(shade, (0, 0))
        rect = pygame.Rect(110, 150, 420, 160)
        ui.panel(rect, C["panel"], 16, C["warn"])
        ui.text(self.dialog[0], (W // 2, rect.y + 46), ui.f_big, C["text"], "center", rect.w - 30)
        ui.text("Esta ação afeta o PC.", (W // 2, rect.y + 80), ui.f, C["dim"], "center")
        ui.hint([("A", "Confirmar"), ("B", "Cancelar")], y=rect.bottom - 40, center=W // 2)

    # -- laço --
    def run(self):
        last = time.monotonic()
        while self.running:
            now = time.monotonic()
            dt, last = now - last, now
            self.events()
            self.network()
            if not self.shot_dir:
                self.auto_rotate()
            if not self.dialog:
                self.tabs[self.tab].update(dt)
            now = time.monotonic()
            busy = self.busy()
            if self.dirty or busy or now - self.last_draw > 1.0:
                self.draw()
                self.dirty, self.last_draw = False, now
            if self.shot_dir and self.screenshot_step():
                break
            self.clock.tick(FPS if busy else 30)
        self.tabs[self.tab].leave()
        time.sleep(0.1)
        pygame.quit()

    def auto_rotate(self):
        """Sem botões por AUTO_SECONDS: alterna entre Painel, Tocando e Games.
        Só gira se já estiver numa dessas abas (não tira você de Atalhos/Controle/Sistema)."""
        now = time.monotonic()
        if self.dialog or self.tab not in AUTO_TABS or now - self.last_activity < AUTO_SECONDS:
            return
        self.tab = AUTO_TABS[(AUTO_TABS.index(self.tab) + 1) % len(AUTO_TABS)]
        self.last_activity = now  # próxima troca em mais AUTO_SECONDS
        self.dirty = True

    def busy(self):
        """Precisa de quadro a quadro: aba Controle, animação de saída ou de botão."""
        return isinstance(self.tabs[self.tab], ControlTab) or self.exit_t is not None or \
            time.monotonic() - self.flash_t < 0.25

    def screenshot_step(self):
        """Modo de teste: espera dados, salva uma imagem de cada aba e sai."""
        if not hasattr(self, "_shot_t0"):
            self._shot_t0 = time.monotonic()
        if time.monotonic() - self._shot_t0 < 12:
            return False
        os.makedirs(self.shot_dir, exist_ok=True)
        for i in range(len(self.tabs)):
            self.tab = i
            self.draw()
            pygame.image.save(self.screen, os.path.join(self.shot_dir, f"{i}-{self.tabs[i].name}.png"))
        self.tab = len(self.tabs) - 1
        self.dialog = ("Desligar?", lambda: None)
        self.draw()
        pygame.image.save(self.screen, os.path.join(self.shot_dir, "5-confirmar.png"))
        return True


if __name__ == "__main__":
    shot = sys.argv[sys.argv.index("--shots") + 1] if "--shots" in sys.argv else None
    App(shot).run()
