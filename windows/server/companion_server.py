"""Companion PC - painel de dados pessoais e atalhos do PC, pela rede local.

Serve o app web (PWA) + WebSocket na porta "web" (8770) - acessível de qualquer
aparelho da rede local ou pelo cabo USB do celular (adb reverse, automático).
Exige token e executa apenas ações de uma lista fechada (ACTIONS). Atalhos de
programas vêm do config.json.

Uso:  pythonw companion_server.py      (ícone na bandeja, sem janela)
      py -3 companion_server.py --console  (no terminal, sem ícone)
"""
import asyncio
import ctypes
import json
import logging
import os
import platform
import re
import secrets
import socket
import subprocess
import sys
import time
from ctypes import wintypes
from http import HTTPStatus
from pathlib import Path

import psutil
from websockets.asyncio.server import serve
from websockets.datastructures import Headers
from websockets.http11 import Response
from websockets.exceptions import ConnectionClosed

import devices
import extras
import games
import gsi
import matches
import daily
import overlay
import pc_info
import screentime
import voice
import watchers

VERSION = "1.9"
BASE = Path(__file__).resolve().parent
CFG_PATH = BASE / "config.json"
LOG_PATH = BASE / "companion-server.log"
WEB_DIR = BASE / "web"

DEFAULT_CFG = {
    "token": "",
    "allow_power": True,
    "shutdown_delay_s": 30,
    # App do celular. host "0.0.0.0" = rede local + cabo; "127.0.0.1" = só cabo (adb).
    "web": {"host": "0.0.0.0", "port": 8770, "adb_reverse": True, "adb_path": ""},
    "upload_dir": "%USERPROFILE%\\Downloads\\Companion PC",  # arquivos enviados pelo celular
    "downloads_dir": "%USERPROFILE%\\Downloads",               # avisa no celular quando um download termina
    # Teclas que o servidor aperta para o Discord. Configure as MESMAS como
    # atalhos globais no Discord (Configurações > Atalhos de teclado).
    "discord": {"mute_keys": "ctrl+shift+f9", "deafen_keys": "ctrl+shift+f10"},
    "games_ignore": games.DEFAULT_IGNORE,
    "game_folders": [],
    "shortcuts": [
        {"id": "explorer", "name": "Explorador de Arquivos", "open": "explorer.exe"},
        {"id": "downloads", "name": "Pasta Downloads", "open": "%USERPROFILE%\\Downloads"},
        {"id": "calc", "name": "Calculadora", "open": "calc.exe"},
        {"id": "notepad", "name": "Bloco de Notas", "open": "notepad.exe"},
        {"id": "taskmgr", "name": "Gerenciador de Tarefas", "open": "taskmgr.exe"},
        {"id": "settings", "name": "Configurações do Windows", "open": "ms-settings:"},
        {"id": "youtube", "name": "YouTube", "open": "https://www.youtube.com"},
    ],
}

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    handlers=[logging.FileHandler(LOG_PATH, encoding="utf-8")]
    + ([logging.StreamHandler(sys.stdout)] if sys.stdout else []),  # pythonw: sem stdout
)
log = logging.getLogger("companion")


def load_config():
    cfg = dict(DEFAULT_CFG)
    if CFG_PATH.exists():
        cfg.update(json.loads(CFG_PATH.read_text(encoding="utf-8")))
    if not cfg.get("token"):
        cfg["token"] = secrets.token_urlsafe(24)
        CFG_PATH.write_text(json.dumps(cfg, indent=2, ensure_ascii=False), encoding="utf-8")
        log.info("token novo gerado em %s", CFG_PATH)
    elif not CFG_PATH.exists():
        CFG_PATH.write_text(json.dumps(cfg, indent=2, ensure_ascii=False), encoding="utf-8")
    return cfg


CFG = load_config()
WEB = {**DEFAULT_CFG["web"], **(CFG.get("web") or {})}

# --------------------------------------------------------------------------
# Win32: teclado, mouse, energia
# --------------------------------------------------------------------------
user32 = ctypes.windll.user32
user32.keybd_event.argtypes = [wintypes.BYTE, wintypes.BYTE, wintypes.DWORD, ctypes.c_size_t]
user32.mouse_event.argtypes = [wintypes.DWORD, wintypes.DWORD, wintypes.DWORD, wintypes.DWORD, ctypes.c_size_t]
user32.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
user32.PostMessageW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
user32.MapVirtualKeyW.argtypes = [wintypes.UINT, wintypes.UINT]
user32.MapVirtualKeyW.restype = wintypes.UINT

KEYEVENTF_EXTENDEDKEY, KEYEVENTF_KEYUP = 0x1, 0x2
VK = {
    "enter": 0x0D, "esc": 0x1B, "tab": 0x09, "space": 0x20, "backspace": 0x08,
    "delete": 0x2E, "home": 0x24, "end": 0x23, "pageup": 0x21, "pagedown": 0x22,
    "up": 0x26, "down": 0x28, "left": 0x25, "right": 0x27,
    "win": 0x5B, "alt": 0x12, "ctrl": 0x11, "shift": 0x10,
    **{f"f{i}": 0x6F + i for i in range(1, 13)},
    **{chr(c): c - 32 for c in range(ord("a"), ord("z") + 1)},  # VK das letras = ASCII maiúsculo
    **{str(d): 0x30 + d for d in range(10)},
    "insert": 0x2D, "printscreen": 0x2C, "menu": 0x5D, "plus": 0xBB, "minus": 0xBD,
    "comma": 0xBC, "period": 0xBE,
    "play_pause": 0xB3, "next": 0xB0, "prev": 0xB1, "stop": 0xB2,
    "vol_mute": 0xAD, "vol_down": 0xAE, "vol_up": 0xAF,
}
EXTENDED = {"delete", "home", "end", "pageup", "pagedown", "up", "down", "left", "right", "win",
            "insert", "printscreen", "menu",
            "play_pause", "next", "prev", "stop", "vol_mute", "vol_down", "vol_up"}
MODIFIERS = {"alt", "ctrl", "shift", "win"}
held_modifiers: set[str] = set()


def _key(name, up=False):
    flags = (KEYEVENTF_EXTENDEDKEY if name in EXTENDED else 0) | (KEYEVENTF_KEYUP if up else 0)
    # Scan code junto com o VK: apps que leem o teclado em baixo nível (atalhos
    # globais do Discord) ignoram eventos com scan code 0.
    scan = user32.MapVirtualKeyW(VK[name], 0) & 0xFF  # MAPVK_VK_TO_VSC
    user32.keybd_event(VK[name], scan, flags, 0)


def valid_combo(combo: str):
    keys = [k.strip().lower() for k in str(combo).split("+") if k.strip()]
    if not keys or any(k not in VK for k in keys):
        raise ValueError(f"tecla não permitida: {combo}")
    return keys


def press_combo(combo: str):
    keys = valid_combo(combo)
    # Pequenas pausas: o Discord não reconhece um atalho pressionado e solto
    # no mesmo instante.
    for k in keys:
        _key(k)
        time.sleep(0.02)
    time.sleep(0.05)
    for k in reversed(keys):
        _key(k, up=True)
        time.sleep(0.01)


class _KEYBDINPUT(ctypes.Structure):
    _fields_ = [("wVk", wintypes.WORD), ("wScan", wintypes.WORD), ("dwFlags", wintypes.DWORD),
                ("time", wintypes.DWORD), ("dwExtraInfo", ctypes.c_size_t)]


class _INPUT(ctypes.Structure):
    class _U(ctypes.Union):
        # MOUSEINPUT é o maior membro da união: reserva o tamanho certo
        _fields_ = [("ki", _KEYBDINPUT), ("_pad", ctypes.c_byte * 32)]
    _anonymous_ = ("u",)
    _fields_ = [("type", wintypes.DWORD), ("u", _U)]


user32.SendInput.argtypes = [wintypes.UINT, ctypes.POINTER(_INPUT), ctypes.c_int]
KEYEVENTF_UNICODE = 0x4


def type_text(text: str):
    """Digita texto qualquer (acentos, emoji) como eventos Unicode.
    "\\n" vira Enter e "\\b" vira Backspace."""
    inputs = []

    def flush():
        if inputs:
            _send(inputs)
            inputs.clear()

    for ch in str(text)[:1000].replace("\r\n", "\n"):
        if ch in "\n\b":
            flush()
            press_combo("enter" if ch == "\n" else "backspace")
            continue
        data = ch.encode("utf-16-le")
        for i in range(0, len(data), 2):  # emoji = par substituto (2 unidades)
            unit = int.from_bytes(data[i:i + 2], "little")
            for flags in (KEYEVENTF_UNICODE, KEYEVENTF_UNICODE | KEYEVENTF_KEYUP):
                inp = _INPUT(type=1)  # INPUT_KEYBOARD
                inp.ki = _KEYBDINPUT(0, unit, flags, 0, 0)
                inputs.append(inp)
    flush()


def _send(inputs):
    arr = (_INPUT * len(inputs))(*inputs)
    user32.SendInput(len(inputs), arr, ctypes.sizeof(_INPUT))


def modifier(name, down):
    """Segura/solta Alt, Ctrl, Shift ou Win (ex.: Alt segurado para Alt+Tab)."""
    if name not in MODIFIERS:
        raise ValueError("só modificadores podem ser segurados")
    _key(name, up=not down)
    (held_modifiers.add if down else held_modifiers.discard)(name)


def release_modifiers():
    for k in list(held_modifiers):
        _key(k, up=True)
    held_modifiers.clear()


MOUSE = {"left": (0x2, 0x4), "right": (0x8, 0x10), "middle": (0x20, 0x40)}


def _u32(v):
    return int(v) & 0xFFFFFFFF


def mouse_move(dx, dy):
    dx, dy = max(-400, min(400, int(dx))), max(-400, min(400, int(dy)))
    user32.mouse_event(0x1, _u32(dx), _u32(dy), 0, 0)


def mouse_button(button="left", state="click"):
    down, up = MOUSE[button]
    if state in ("click", "down"):
        user32.mouse_event(down, 0, 0, 0, 0)
    if state in ("click", "up"):
        user32.mouse_event(up, 0, 0, 0, 0)


def mouse_scroll(dy=0, dx=0):
    if dy:
        user32.mouse_event(0x800, 0, 0, _u32(max(-1200, min(1200, int(dy)))), 0)
    if dx:
        user32.mouse_event(0x1000, 0, 0, _u32(max(-1200, min(1200, int(dx)))), 0)


def foreground_title():
    hwnd = user32.GetForegroundWindow()
    buf = ctypes.create_unicode_buffer(256)
    user32.GetWindowTextW(hwnd, buf, 256)
    return buf.value


_WNDENUM = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)


def focus_window_titled(part, exe=None):
    """Traz para a frente a primeira janela visível cujo título contém `part`.
    O Windows só deixa trocar o foco depois de uma tecla: um Alt solto antes destrava."""
    found = []

    def cb(h, _):
        if user32.IsWindowVisible(h):
            buf = ctypes.create_unicode_buffer(256)
            user32.GetWindowTextW(h, buf, 256)
            if part.lower() in buf.value.lower():
                pid = ctypes.c_ulong()
                user32.GetWindowThreadProcessId(h, ctypes.byref(pid))
                try:
                    ok = not exe or psutil.Process(pid.value).name().lower() == exe
                except psutil.Error:
                    ok = False
                if ok:
                    found.append(h)
                    return False
        return True
    user32.EnumWindows(_WNDENUM(cb), 0)
    if not found:
        return False
    h = found[0]
    if user32.IsIconic(h):
        user32.ShowWindow(h, 9)  # SW_RESTORE
    user32.keybd_event(0x12, 0, 0, 0)
    user32.keybd_event(0x12, 0, 2, 0)
    user32.SetForegroundWindow(h)
    return True


def foreground_app():
    """(nome do exe em minúsculas, caminho, pid) do programa em foco."""
    pid = ctypes.c_ulong()
    user32.GetWindowThreadProcessId(user32.GetForegroundWindow(), ctypes.byref(pid))
    try:
        p = psutil.Process(pid.value)
        return p.name().lower(), p.exe(), pid.value
    except (psutil.Error, OSError):
        return "", None, 0


def power(action):
    if not CFG.get("allow_power"):
        raise PermissionError("ações de energia desativadas no config.json")
    delay = str(int(CFG.get("shutdown_delay_s", 30)))

    def run(*args):
        subprocess.run(["shutdown", *args], creationflags=pc_info.NO_WINDOW, capture_output=True)

    if action == "lock":
        user32.LockWorkStation()
    elif action == "monitor_off":
        user32.PostMessageW(0xFFFF, 0x0112, 0xF170, 2)
    elif action == "sleep":
        ctypes.windll.powrprof.SetSuspendState(0, 1, 0)
    elif action == "shutdown":
        run("/s", "/t", delay, "/c", "Desligamento pedido pelo Companion PC")
    elif action == "restart":
        run("/r", "/t", delay, "/c", "Reinício pedido pelo Companion PC")
    elif action == "cancel":
        run("/a")
    else:
        raise ValueError(f"ação de energia inválida: {action}")


def launch(shortcut_id):
    sc = next((s for s in CFG["shortcuts"] if s.get("id") == shortcut_id), None)
    if not sc:
        raise ValueError("atalho não configurado")
    target = os.path.expandvars(sc["open"])
    if sc.get("appx"):  # app da Microsoft Store (WhatsApp, Spotify, Terminal...)
        os.startfile("shell:AppsFolder\\" + sc["appx"])
        return sc["name"]
    kw = {}
    if sc.get("args"):
        kw["arguments"] = sc["args"]
    if target.lower().endswith(".exe") and os.path.isabs(target):
        kw["cwd"] = os.path.dirname(target)  # OBS e outros só abrem a partir da própria pasta
    os.startfile(target, **kw)
    return sc["name"]


# --------------------------------------------------------------------------
# Estatísticas
# --------------------------------------------------------------------------
class Stats:
    def __init__(self):
        psutil.cpu_percent(None)
        self.cores = psutil.cpu_count() or 1
        self.last_net = psutil.net_io_counters()
        self.last_t = time.monotonic()
        self.pcache: dict[int, psutil.Process] = {}  # cache próprio (não usa o do process_iter)
        self.slow: set[int] = set()  # processos protegidos: psutil cai num caminho lento (~5 ms cada)
        self._top_procs()

    def _app(self):
        name, exe, self._fg_pid = foreground_app()
        game = False
        if exe and name not in ("explorer.exe", "applicationframehost.exe"):
            try:
                game = bool(MON.catalog.match(exe))
            except Exception:  # noqa: BLE001
                game = False
        self.fg_pid = self._fg_pid if game else 0
        return {"app": name, "app_game": game}

    def _top_procs(self):
        procs, pids = [], set(psutil.pids())
        for pid in list(self.pcache):
            if pid not in pids:
                del self.pcache[pid]
        self.slow &= pids
        for pid in pids:
            if pid == 0 or pid in self.slow:
                continue
            t0 = time.perf_counter()
            p = self.pcache.get(pid)
            try:
                if p is None:
                    p = self.pcache[pid] = psutil.Process(pid)
                    p.cached_name = p.name()  # nome não muda; ler uma vez só
                with p.oneshot():
                    cpu = p.cpu_percent(None) / self.cores
                    procs.append((cpu, p.memory_info().rss, p.cached_name))
                if time.perf_counter() - t0 > 0.003 and pid in self.pcache and hasattr(p, "seen"):
                    self.slow.add(pid)
                p.seen = True
            except psutil.Error:
                self.pcache.pop(pid, None)
        procs.sort(reverse=True)
        return procs

    def collect(self):
        now = time.monotonic()
        net = psutil.net_io_counters()
        dt = max(now - self.last_t, 0.001)
        up = (net.bytes_sent - self.last_net.bytes_sent) / dt
        down = (net.bytes_recv - self.last_net.bytes_recv) / dt
        self.last_net, self.last_t = net, now

        vm = psutil.virtual_memory()
        disks = []
        for part in psutil.disk_partitions(all=False):
            if "cdrom" in part.opts or not part.fstype:
                continue
            try:
                u = psutil.disk_usage(part.mountpoint)
            except OSError:
                continue
            disks.append({"name": part.mountpoint.rstrip("\\"), "used": u.used, "total": u.total, "pct": u.percent})

        procs = self._top_procs()

        bat = psutil.sensors_battery()
        freq = psutil.cpu_freq()
        return {
            "time": time.strftime("%H:%M:%S"),
            "date": time.strftime("%d/%m/%Y"),
            "uptime_s": int(time.time() - psutil.boot_time()),
            "cpu": psutil.cpu_percent(None),
            "cpu_mhz": int(freq.current) if freq else 0,
            "ram_used": vm.used, "ram_total": vm.total, "ram_pct": vm.percent,
            "disks": disks,
            "net_up": up, "net_down": down,
            "battery": {"pct": bat.percent, "plugged": bat.power_plugged} if bat else None,
            "window": foreground_title(),
            **self._app(),
            "gpu": pc_info.gpu(),
            "procs": [{"name": n, "cpu": round(c, 1), "mem": m} for c, m, n in procs[:5]],
            "sensors": pc_info.sensors(),
        }


# --------------------------------------------------------------------------
# Ações permitidas
# --------------------------------------------------------------------------
ACTIONS = {
    "media.vol_up": lambda p: press_combo("vol_up"),
    "media.vol_down": lambda p: press_combo("vol_down"),
    "key.press": lambda p: press_combo(p["keys"]),
    "key.text": lambda p: type_text(p.get("text", "")),
    "key.down": lambda p: modifier(p["key"], down=True),
    "key.up": lambda p: modifier(p["key"], down=False),
    "mouse.move": lambda p: mouse_move(p.get("dx", 0), p.get("dy", 0)),
    "mouse.button": lambda p: mouse_button(p.get("button", "left"), p.get("state", "click")),
    "mouse.scroll": lambda p: mouse_scroll(p.get("dy", 0), p.get("dx", 0)),
    "app.launch": lambda p: launch(p["id"]),
    "power": lambda p: power(p["action"]),
    "discord.mute": lambda p: press_combo(CFG["discord"]["mute_keys"]),
    "discord.deafen": lambda p: press_combo(CFG["discord"]["deafen_keys"]),
    "discord.open": lambda p: open_discord(),
    # celular: deck, área de transferência, arquivos
    "deck.get": lambda p: deck_payload(),
    "deck.save": lambda p: deck_saved(DECK.save(p["deck"], valid_combo, shortcut_map())),
    "deck.reset": lambda p: deck_payload(DECK.reset()),
    "clip.set": lambda p: clip_set(p),
    "file.begin": lambda p: UPLOADS.begin(p["name"], p["size"]),
    "file.chunk": lambda p: UPLOADS.chunk(p["id"], p["data"]),
    "file.end": lambda p: UPLOADS.end(p["id"]),
    "file.cancel": lambda p: UPLOADS.cancel(p["id"]),
    "file.open_folder": lambda p: UPLOADS.open_folder(),
}

DECK = extras.Deck(BASE)
UPLOADS = extras.Uploads(CFG.get("upload_dir") or DEFAULT_CFG["upload_dir"])
DOWNLOADS = extras.DownloadWatcher(CFG.get("downloads_dir") or DEFAULT_CFG["downloads_dir"])


LAYOUT_PATH = BASE / "layout.json"
LAYOUT_VIEWS = {"dash", "today", "games", "usage", "media", "mix", "mouse", "screen", "deck", "send", "power", "voz", "sys"}
LAYOUT_CARDS = {"cpu", "ram", "gpu", "net", "procs", "disks", "bat", "sys"}
SKINS = {"fallout", "synth", "minimal", "hud", "lcd", "paper"}


def layout_get():
    try:
        return json.loads(LAYOUT_PATH.read_text(encoding="utf-8")) if LAYOUT_PATH.exists() else {}
    except (OSError, ValueError):
        return {}


def _clean_orient(o):
    """Menu (seções com abas) e cartões do Status de uma orientação; ignora o que não existe."""
    if not isinstance(o, dict):
        return None
    out = {}
    if isinstance(o.get("nav"), list):
        nav, seen = [], set()
        for sec in o["nav"][:8]:
            if not isinstance(sec, dict):
                continue
            views = [v for v in sec.get("views") or [] if v in LAYOUT_VIEWS and v not in seen]
            seen.update(views)
            if views:
                nav.append({"id": str(sec.get("id") or f"s{len(nav)}")[:20], "label": str(sec.get("label") or "")[:14], "views": views})
        if nav:
            out["nav"] = nav
    if isinstance(o.get("dash"), list):
        dash = []
        for d in o["dash"][:12]:
            if isinstance(d, dict) and d.get("id") in LAYOUT_CARDS:
                dash.append({"id": d["id"], "span": max(1, min(4, int(d.get("span") or 1))), "hidden": bool(d.get("hidden"))})
        if dash:
            out["dash"] = dash
    if isinstance(o.get("blocks"), dict):
        blocks = {}
        for view, lst in o["blocks"].items():
            if view not in LAYOUT_VIEWS | {"play", "meet"} or not isinstance(lst, list):
                continue
            items, seen = [], set()
            for d in lst[:40]:
                bid = d.get("id") if isinstance(d, dict) else None
                if isinstance(bid, str) and re.fullmatch(r"[a-z0-9-]{1,20}", bid) and bid not in seen:
                    seen.add(bid)
                    items.append({"id": bid, "hidden": bool(d.get("hidden")), "wide": bool(d.get("wide"))})
            if items:
                blocks[view] = items
        if blocks:
            out["blocks"] = blocks
    return out or None


def layout_set(p):
    lay = p.get("layout")
    if not isinstance(lay, dict):
        raise ValueError("layout inválido")
    clean = {}
    if lay.get("skin") in SKINS:
        clean["skin"] = lay["skin"]
    if isinstance(lay.get("theme"), str):
        clean["theme"] = lay["theme"][:16]
    if isinstance(lay.get("crt"), bool):
        clean["crt"] = lay["crt"]
    for k in ("portrait", "landscape"):
        o = _clean_orient(lay.get(k))
        if o:
            clean[k] = o
    tmp = LAYOUT_PATH.with_suffix(".tmp")
    tmp.write_text(json.dumps(clean, indent=2, ensure_ascii=False), encoding="utf-8")
    tmp.replace(LAYOUT_PATH)
    asyncio.get_running_loop().create_task(broadcast({"t": "layout", "d": clean}))
    return clean


def deck_saved(data):
    payload = deck_payload(data)
    asyncio.get_running_loop().create_task(broadcast({"t": "deck", "d": payload}))
    return payload


def shortcut_map():
    """Programas do config.json por id e por nome (minúsculos), para as macros."""
    m = {}
    for s in CFG["shortcuts"]:
        m[s["name"].lower()] = s["id"]
        m[s["id"].lower()] = s["id"]
    return m


def deck_payload(deck=None):
    return {"deck": deck or DECK.get(), "actions": {k: v[0] for k, v in extras.DECK_ACTIONS.items()},
            "keys": sorted(VK)}


def clip_set(p):
    extras.clip_set_text(p.get("text", ""))
    if p.get("paste"):
        time.sleep(0.05)
        press_combo("ctrl+v")


def open_discord():
    upd = os.path.expandvars(r"%LOCALAPPDATA%\Discord\Update.exe")
    if not os.path.exists(upd):
        raise FileNotFoundError("Discord não encontrado")
    subprocess.Popen([upd, "--processStart", "Discord.exe"], creationflags=pc_info.NO_WINDOW)


async def media_action(name, p):
    """Controla o player atual; se não houver sessão de mídia, usa a tecla de mídia."""
    if name == "seek":
        if not await pc_info.MEDIA.control("seek", float(p.get("delta", 0))):
            raise RuntimeError("nada tocando")
    elif not await pc_info.MEDIA.control(name):
        press_combo({"play_pause": "play_pause", "next": "next", "prev": "prev", "stop": "stop"}[name])
    await push_now()


async def volume_action(p):
    if "delta" in p:
        cur = await pc_info.volume_get() or {"level": 50}
        res = await pc_info.volume_set(level=cur["level"] + float(p["delta"]))
    elif "level" in p:
        res = await pc_info.volume_set(level=float(p["level"]))
    elif p.get("toggle_mute"):
        cur = await pc_info.volume_get() or {"muted": False}
        res = await pc_info.volume_set(muted=not cur["muted"])
    else:
        raise ValueError("parâmetro de volume inválido")
    await push_now()
    return res


ASYNC_ACTIONS = {
    "media.play_pause": lambda p: media_action("play_pause", p),
    "media.next": lambda p: media_action("next", p),
    "media.prev": lambda p: media_action("prev", p),
    "media.stop": lambda p: media_action("stop", p),
    "media.seek": lambda p: media_action("seek", p),
    "media.mute": lambda p: volume_action({"toggle_mute": True}),
    "volume.change": volume_action,
    "volume.set": volume_action,
    "mixer.get": lambda p: pc_info.mixer_get(),
    "mixer.set": lambda p: pc_info.mixer_set(str(p["key"]), p.get("level"), p.get("muted")),
    "audio.set_output": lambda p: output_action(p.get("id")),
    "audio.cycle": lambda p: output_action(cycle=True),
    "deck.press": lambda p: deck_press(p),
    "clip.get": lambda p: asyncio.to_thread(extras.clip_get),
    "screen.shot": lambda p: asyncio.to_thread(extras.screen_shot, p.get("mon", 0), p.get("w", 1280),
                                               p.get("q", 60), p.get("sid")),
    "screen.click": lambda p: screen_click(p),
    "mic.set": lambda p: pc_info.mic_set(p.get("muted", "toggle")),
    "timer.start": lambda p: TIMER.start(p.get("action"), p.get("minutes")),
    "timer.cancel": lambda p: timer_cancel(),
    "games.library": lambda p: asyncio.to_thread(MON.library),
    "games.history": lambda p: asyncio.to_thread(MON.summary),
    "games.launch": lambda p: asyncio.to_thread(MON.launch, str(p.get("id"))),
    "notif.sub": lambda p: notif_sub(p),
    "voice.set": lambda p: asyncio.to_thread(VOICE.set, p),
    "voice.devices": lambda p: asyncio.to_thread(VOICE.devices),
    "voice.help": lambda p: voice_help(),
    "voice.try": lambda p: voice_try(p),
    "bat.refresh": lambda p: asyncio.to_thread(BAT.refresh),
    "meet.cmd": lambda p: meet_cmd(p),
    "layout.get": lambda p: _async(layout_get()),
    "matches.get": lambda p: asyncio.to_thread(matches_get, p),
    "daily.get": lambda p: _async(daily_public()),
    "daily.set": lambda p: daily_set(p),
    "daily.open": lambda p: _async(daily_open(p)),
    "focus.start": lambda p: focus_start(p),
    "focus.stop": lambda p: focus_stop(p),
    "audio.profiles": lambda p: _async(audio_profiles()),
    "audio.profile_save": lambda p: audio_profile_save(p),
    "audio.profile_apply": lambda p: audio_profile_apply(p),
    "audio.profile_del": lambda p: _async(audio_profile_del(p)),
    "dota.mark": lambda p: _async(dota_mark(p)),
    "layout.set": lambda p: _async(layout_set(p)),
    "usage.get": lambda p: asyncio.to_thread(SCREEN.report, p.get("range", "day"), p.get("day")),
    "usage.app": lambda p: asyncio.to_thread(SCREEN.app_report, str(p["app"]), int(p.get("days", 7))),
    "usage.cat": lambda p: asyncio.to_thread(screen_cat, p),
}


# --------------------------------------------------------------------------
# Timer de energia: "desligar/suspender daqui a X minutos"
# --------------------------------------------------------------------------
class PowerTimer:
    ACTIONS = {"shutdown": "Desligar", "sleep": "Suspender", "monitor_off": "Desligar monitor", "lock": "Bloquear"}

    def __init__(self):
        self.task, self.action, self.at = None, None, 0.0

    def state(self):
        if not self.task:
            return None
        return {"action": self.action, "label": self.ACTIONS[self.action], "left": max(0, round(self.at - time.time()))}

    async def start(self, action, minutes):
        if action not in self.ACTIONS:
            raise ValueError("ação do timer inválida")
        if not CFG.get("allow_power"):
            raise PermissionError("ações de energia desativadas no config.json")
        minutes = float(minutes)
        if not 1 <= minutes <= 720:
            raise ValueError("escolha entre 1 minuto e 12 horas")
        self.cancel()
        self.action, self.at = action, time.time() + minutes * 60
        self.task = asyncio.create_task(self._run())
        log.info("timer: %s em %d min", action, minutes)
        return self.state()

    async def _run(self):
        try:
            await asyncio.sleep(max(0, self.at - time.time()))
        except asyncio.CancelledError:
            return
        action, self.task, self.action = self.action, None, None
        log.info("timer: executando %s", action)
        try:
            await asyncio.to_thread(power, action)
        except Exception:  # noqa: BLE001
            log.exception("timer")

    def cancel(self):
        if self.task:
            self.task.cancel()
            log.info("timer cancelado")
        self.task, self.action = None, None
        return None


TIMER = PowerTimer()


async def timer_cancel():
    return TIMER.cancel()


async def output_action(dev_id=None, cycle=False):
    name = await pc_info.set_output(dev_id, cycle)
    asyncio.create_task(push_now())
    return name


async def screen_click(p):
    await asyncio.to_thread(extras.screen_point, p.get("mon", 0), p["x"], p["y"])
    if p.get("button"):
        mouse_button(p["button"], p.get("state", "click"))
        if p.get("double"):
            mouse_button(p["button"])


async def run_deck_action(v):
    _label, action, params = extras.DECK_ACTIONS[v]
    fn = ACTIONS.get(action) or ASYNC_ACTIONS.get(action)
    res = fn(dict(params))
    if asyncio.iscoroutine(res):
        res = await res
    return res


async def deck_press(p):
    b = DECK.button(p.get("page"), p.get("index"))
    t, v = b["type"], b["value"]
    if t == "keys":
        press_combo(v)
    elif t == "text":
        type_text(v)
    elif t == "shortcut":
        return launch(v)
    elif t == "action":
        return await run_deck_action(v)
    elif t == "macro":
        for kind, arg in extras.parse_macro(v, valid_combo, shortcut_map()):
            if kind == "keys":
                press_combo(arg)
            elif kind == "text":
                type_text(arg)
            elif kind == "wait":
                await asyncio.sleep(arg / 1000)
            elif kind == "open":
                launch(arg)
            elif kind == "action":
                await run_deck_action(arg)
            await asyncio.sleep(0.04)  # dá tempo de o Windows processar cada passo
    return None


# --------------------------------------------------------------------------
# Ping, notificações do Windows e FPS (watchers.py)
# --------------------------------------------------------------------------
PING = watchers.Ping()
NOTIF = watchers.WinNotifications()
FPS = watchers.Fps(CFG.get("presentmon_path", ""))
notif_subs: set = set()


def notif_sub(p):
    ws = p.get("_ws")
    if ws is None:
        raise ValueError("sem conexão")
    (notif_subs.add if p.get("on") else notif_subs.discard)(ws)
    return {"available": NOTIF.available}


async def push_notif(n):
    if FOCUS["state"]:
        return  # modo foco: as notificações do PC não vão para o celular
    msg = json.dumps({"t": "event", "kind": "notif", **n}, ensure_ascii=False)
    for ws in list(notif_subs):
        try:
            await ws.send(msg)
        except ConnectionClosed:
            notif_subs.discard(ws)


def phone_connected():
    return any(k == "celular" for k in client_kind.values())


def fps_wanted():
    st = STATS_REF[0]
    return getattr(st, "fg_pid", 0) if st and phone_connected() else 0


STATS_REF = [None]




# --------------------------------------------------------------------------
# WebSocket
# --------------------------------------------------------------------------
clients = set()
client_kind: dict = {}  # ws -> "celular"


async def web_handler(ws):
    """Conexão de um aparelho (rede local ou cabo via adb reverse): só o token."""
    peer = ws.remote_address[0] if ws.remote_address else "?"
    await session(ws, "cabo USB" if peer in ("127.0.0.1", "::1") else peer, "celular")


async def session(ws, peer, kind):
    try:
        hello = json.loads(await asyncio.wait_for(ws.recv(), 5))
    except Exception:
        await ws.close(4001, "hello")
        return
    if hello.get("t") == "hello" and hello.get("kind") == "meet":
        origin = (ws.request.headers.get("Origin") or "") if ws.request else ""
        # só a extensão do navegador, no próprio PC (página nenhuma consegue mandar esse Origin)
        if peer == "cabo USB" and origin.startswith(("chrome-extension://", "extension://", "moz-extension://")):
            await meet_session(ws)
        else:
            log.warning("recusado: extensão de reunião de %s (origem %s)", peer, origin)
            await ws.close(4001, "origin")
        return
    if hello.get("t") != "hello" or not secrets.compare_digest(str(hello.get("token", "")), CFG["token"]):
        log.warning("recusado: token inválido de %s", peer)
        await ws.close(4001, "token")
        return

    await ws.send(json.dumps({
        "t": "welcome", "version": VERSION, "web": web_build(), "host": socket.gethostname(),
        "os": f"{platform.system()} {platform.release()}",
        "shortcuts": [{"id": s["id"], "name": s["name"]} for s in CFG["shortcuts"]],
        "power": bool(CFG.get("allow_power")), "layout": layout_get(),
        "features": {"media": pc_info.HAS_MEDIA, "volume": pc_info.HAS_VOLUME, "mixer": pc_info.HAS_VOLUME,
                     "screen": True, "clipboard": True, "files": True, "deck": True,
                     "mic": pc_info.HAS_VOLUME, "timer": True, "deck_auto": True, "macro": True,
                     "library": True, "ping": True, "notif": True, "fps": True, "voice": VOICE.available,
                     "battery": devices.hid is not None, "usage": True, "meet": True},
    }))
    if hello.get("role") in ("editor", "preview") and peer == "cabo USB":
        kind = hello["role"]  # editor no PC e as prévias dele: não contam como aparelho
    clients.add(ws)
    client_kind[ws] = kind
    sent_art[ws] = None
    sent_gameart[ws] = None
    await send_games(ws, MON.state)
    if MEET["state"]:
        await ws.send(json.dumps({"t": "meet", "d": MEET["state"]}, ensure_ascii=False))
    if GSI.current():
        await ws.send(json.dumps({"t": "gsi", "d": GSI.current()}, ensure_ascii=False))
    await ws.send(json.dumps({"t": "daily", "d": daily_public()}, ensure_ascii=False))
    await ws.send(json.dumps({"t": "focus", "d": focus_state()}, ensure_ascii=False))
    await push_now(only=ws)
    if kind == "celular":
        log.info("conectado: %s (%s) tela %s", kind, peer, str(hello.get("screen", "?"))[:120])
    try:
        async for raw in ws:
            try:
                msg = json.loads(raw)
            except ValueError:
                continue
            if msg.get("t") != "req":
                continue
            action, rid = msg.get("a"), msg.get("id")
            fn = ACTIONS.get(action) or ASYNC_ACTIONS.get(action)
            try:
                if not fn:
                    raise ValueError(f"ação não permitida: {action}")
                params = msg.get("p") or {}
                if action == "notif.sub":  # precisa saber qual conexão está pedindo
                    params = {**params, "_ws": ws}
                data = fn(params)
                if asyncio.iscoroutine(data):
                    data = await data
                res = {"t": "res", "id": rid, "a": action, "ok": True, "d": data if isinstance(data, (str, int, float, dict, list)) else None}
                if action not in QUIET_ACTIONS:
                    log.info("%s %s", action, msg.get("p") or "")
            except Exception as e:  # noqa: BLE001
                log.warning("falha %s: %s", action, e)
                res = {"t": "res", "id": rid, "a": action, "ok": False, "e": str(e)}
            if rid is not None:
                await ws.send(json.dumps(res))
    except ConnectionClosed:
        pass
    finally:
        clients.discard(ws)
        client_kind.pop(ws, None)
        notif_subs.discard(ws)
        sent_art.pop(ws, None)
        sent_gameart.pop(ws, None)
        release_modifiers()
        user32.mouse_event(0x4, 0, 0, 0, 0)  # solta botão esquerdo se ficou preso (drag)
        if kind == "celular":
            log.info("desconectado: %s (%s)", kind, peer)


sent_art: dict = {}


# --------------------------------------------------------------------------
# Reunião: extensão do Edge no Google Meet (windows/edge-extension)
# --------------------------------------------------------------------------
MEET = {"ws": None, "state": None, "since": None}
MEET_CMDS = {"mic", "cam", "hand", "share", "leave", "join", "captions", "chat", "focus", "sharePrep"}


async def _async(value):
    return value


async def broadcast(obj):
    msg = json.dumps(obj, ensure_ascii=False)
    for w in list(clients):
        try:
            await w.send(msg)
        except ConnectionClosed:
            clients.discard(w)


async def meet_set(state):
    if state and state.get("inCall"):
        if not MEET["since"]:
            MEET["since"] = time.time()
            log.info("reunião começou: %s", state.get("app"))
        state["since"] = int(MEET["since"])
    elif MEET["since"]:
        log.info("reunião terminou")
        MEET["since"] = None
    MEET["state"] = state
    await broadcast({"t": "meet", "d": state})


async def meet_session(ws):
    if MEET["ws"] is not None:
        try:
            await MEET["ws"].close()
        except Exception:  # noqa: BLE001
            pass
    MEET["ws"] = ws
    log.info("extensão de reunião conectada")
    try:
        async for raw in ws:
            try:
                m = json.loads(raw)
            except ValueError:
                continue
            if m.get("t") == "meet":
                d = m.get("d")
                await meet_set(d if isinstance(d, dict) else None)
    except ConnectionClosed:
        pass
    finally:
        if MEET["ws"] is ws:
            MEET["ws"] = None
            await meet_set(None)
        log.info("extensão de reunião desconectada")


async def meet_cmd(p):
    cmd = str(p.get("cmd"))
    if cmd not in MEET_CMDS:
        raise ValueError("comando de reunião inválido")
    if not MEET["ws"]:
        raise ValueError("nenhuma reunião aberta no navegador")
    msg = {"t": "meet.cmd", "cmd": cmd}
    if isinstance(p.get("arg"), bool):
        msg["arg"] = p["arg"]
    st = MEET["state"] or {}
    if cmd == "share" and not st.get("sharing"):
        # o navegador só abre a escolha de tela com uma tecla/clique de verdade: traz o Meet para
        # frente, a extensão foca o botão "Apresentar" e aqui apertamos Enter (só se o Meet estiver em foco)
        await MEET["ws"].send(json.dumps({"t": "meet.cmd", "cmd": "focus"}))  # aba do Meet ativa
        await asyncio.sleep(0.3)
        await asyncio.to_thread(focus_window_titled, "Meet", "msedge.exe")
        await MEET["ws"].send(json.dumps({"t": "meet.cmd", "cmd": "sharePrep"}))
        for _ in range(10):
            await asyncio.sleep(0.15)
            if "meet" in foreground_title().lower() and foreground_app()[0] == "msedge.exe":
                await asyncio.sleep(0.15)
                await asyncio.to_thread(press_combo, "enter")
                return "escolha a tela no PC"
        raise ValueError("não consegui trazer o Meet para a frente")
    await MEET["ws"].send(json.dumps(msg))
# não vão para o log: repetitivas ou com conteúdo pessoal (texto digitado/copiado)
QUIET_ACTIONS = {"layout.get", "matches.get", "daily.get", "audio.profiles", "bat.refresh", "usage.get", "usage.app", "games.history", "games.library", "notif.sub", "mouse.move", "mouse.scroll", "key.text", "clip.set", "clip.get", "file.chunk",
                 "screen.shot", "mixer.get", "deck.get", "voice.devices", "voice.help", "voice.try"}


async def now_payload():
    media = await pc_info.MEDIA.info()
    vol = await pc_info.volume_get()
    return {"media": media, "volume": vol}


async def send_now(ws, payload):
    msg = json.dumps({"t": "now", "d": payload}, ensure_ascii=False)
    try:
        await ws.send(msg)
        art = (payload.get("media") or {}).get("art")
        if art and sent_art.get(ws) != art and pc_info.MEDIA.art_b64:
            await ws.send(json.dumps({"t": "art", "id": art, "jpg": pc_info.MEDIA.art_b64}))
            sent_art[ws] = art
    except ConnectionClosed:
        clients.discard(ws)


async def push_now(only=None):
    """Envia mídia/volume já (após uma ação), sem esperar o próximo ciclo."""
    if not clients:
        return
    await asyncio.sleep(0.25)  # dá tempo do player reagir
    payload = await now_payload()
    for ws in ([only] if only else list(clients)):
        await send_now(ws, payload)


async def stats_loop(stats: Stats):
    while True:
        try:
            if clients:
                data = await asyncio.to_thread(stats.collect)
                data["mic"] = await pc_info.mic_get()
                data["timer"] = TIMER.state()
                data["ping"] = PING.state()
                data["fps"] = FPS.state(getattr(stats, "fg_pid", 0))
                data["voice"] = VOICE.state()
                data["bat"] = BAT.state()
                msg = json.dumps({"t": "stats", "d": data}, ensure_ascii=False)
                for ws in list(clients):
                    try:
                        await ws.send(msg)
                    except ConnectionClosed:
                        clients.discard(ws)
        except Exception:  # noqa: BLE001
            log.exception("stats_loop")
        await asyncio.sleep(1)


MON = games.GameMonitor(CFG, BASE)
sent_gameart: dict = {}


# --------------------------------------------------------------------------
# Comandos de voz (voice.py): "PC, próxima música"
# --------------------------------------------------------------------------
def save_cfg_key(key, value):
    """Grava uma chave do config.json sem mexer no resto do arquivo."""
    CFG[key] = value
    try:
        cur = json.loads(CFG_PATH.read_text(encoding="utf-8")) if CFG_PATH.exists() else {}
        cur[key] = value
        CFG_PATH.write_text(json.dumps(cur, indent=2, ensure_ascii=False), encoding="utf-8")
    except Exception:  # noqa: BLE001
        log.exception("salvar config (%s)", key)


def voice_save_cfg(vcfg):
    save_cfg_key("voice", vcfg)


_voice_games = [0.0, []]


def voice_catalog():
    if time.monotonic() - _voice_games[0] > 60:
        try:
            _voice_games[:] = [time.monotonic(), MON.launchable()]
        except Exception:  # noqa: BLE001
            log.exception("voz: catálogo de jogos")
    deck = []
    try:
        for pi, page in enumerate(DECK.get().get("pages", [])):
            for bi, b in enumerate(page.get("buttons", [])):
                if b and b.get("label") and not b.get("confirm"):
                    deck.append((pi, bi, b["label"]))
    except Exception:  # noqa: BLE001
        log.exception("voz: deck")
    return voice.Catalog([(s["id"], s["name"]) for s in CFG["shortcuts"]], _voice_games[1], deck)


async def voice_run(it):
    a, p = it["action"], dict(it.get("p") or {})
    if a in ("media.pause", "media.play", "media.what"):
        info = await pc_info.MEDIA.info()
        if a == "media.what":
            if not info or not info.get("title"):
                return "Nada tocando agora"
            return f"{info['title']}" + (f", de {info['artist']}" if info.get("artist") else "")
        playing = bool(info and info.get("status") == "playing")
        if playing == (a == "media.play"):
            return "Já está tocando" if playing else "Já está pausado"
        a = "media.play_pause"
    elif a == "deck.press":
        await deck_press(p)
        return it.get("say")
    fn = ACTIONS.get(a) or ASYNC_ACTIONS.get(a)
    if not fn:
        raise ValueError(f"ação desconhecida: {a}")
    res = fn(p)
    if asyncio.iscoroutine(res):
        res = await res
    if a == "games.launch" and isinstance(res, str):
        return f"Abrindo {res}"
    if a in ("mic.set",) and isinstance(res, dict) and "muted" in res:
        return "Microfone no mudo" if res["muted"] else "Microfone ligado"
    return it.get("say")


OVERLAY = overlay.Overlay()


async def voice_help():
    """O que dá para falar: atalhos (com apelidos), jogos e botões do deck do usuário."""
    cat = await asyncio.to_thread(voice_catalog)
    apps = [{"name": name, "say": [a for a in voice.APP_ALIASES.get(sid, []) if a != voice.norm(name)][:4]}
            for sid, name in cat.apps]
    return {"apps": apps, "games": sorted({n for _g, n in cat.games}, key=str.lower),
            "deck": list(dict.fromkeys(label for _p, _i, label in cat.deck))}


async def voice_try(p):
    """Comando escrito no app (como se tivesse falado "PC, ...")."""
    text = str(p.get("text", ""))[:200]
    cat = await asyncio.to_thread(voice_catalog)
    _w, _cmd, it = voice.interpret(text, cat, following=True)
    if not it:
        raise ValueError("não entendi esse comando")
    if it.get("error"):
        raise ValueError(it["error"])
    msg = await voice_run(it)
    log.info("voz (escrito): \"%s\" -> %s", text, it["action"])
    return {"msg": msg or it.get("say") or "Feito", "action": it["action"]}


async def voice_event(ev):
    if ev.get("phase") == "done":
        log.info("voz: %s", ev.get("msg"))
    if VOICE.cfg.get("overlay"):
        try:
            if ev.get("phase") == "wake":
                OVERLAY.show("wake", "Ouvindo...", "Diga o comando", ev.get("secs", 6))
            elif ev.get("phase") == "done":
                OVERLAY.show("ok" if ev.get("ok") else "err", ev.get("msg") or "", f"\u201c{ev.get('text', '')}\u201d", 4)
        except Exception:  # noqa: BLE001
            log.exception("aviso de voz")
    msg = json.dumps(ev, ensure_ascii=False)
    for ws in list(clients):
        try:
            await ws.send(msg)
        except ConnectionClosed:
            clients.discard(ws)


VOICE = voice.Voice(CFG.get("voice"), BASE, voice_save_cfg, voice_catalog, voice_run, voice_event,
                    mic_fn=lambda: pc_info.mic_get())


async def send_games(ws, state):
    try:
        await ws.send(json.dumps({"t": "games", "d": state}, ensure_ascii=False))
        art = (state.get("game") or {}).get("art")
        if art and sent_gameart.get(ws) != art and MON.art.get(art):
            await ws.send(json.dumps({"t": "gameart", "id": art, "jpg": MON.art[art]}))
            sent_gameart[ws] = art
    except ConnectionClosed:
        clients.discard(ws)


async def downloads_loop():
    """Avisa os celulares quando aparece um arquivo novo (completo) em Downloads."""
    while True:
        try:
            for f in await asyncio.to_thread(DOWNLOADS.poll):
                log.info("download concluído: %s", f["name"])
                msg = json.dumps({"t": "event", "kind": "download", **f}, ensure_ascii=False)
                for ws in [w for w in list(clients) if client_kind.get(w) == "celular"]:
                    try:
                        await ws.send(msg)
                    except ConnectionClosed:
                        pass
        except Exception:  # noqa: BLE001
            log.exception("downloads_loop")
        await asyncio.sleep(3)


BAT = devices.Batteries(CFG.get("batteries"))
_media_playing = [False]
SCREEN = screentime.ScreenTime(BASE, CFG.setdefault("screentime", {}), match_game=lambda exe: MON.catalog.match(exe),
                               media_playing=lambda: _media_playing[0])


async def screentime_loop():
    while True:
        try:
            if screentime.idle_seconds() > screentime.IDLE_S - 5:
                # parado: só conta se algo estiver tocando (vídeo, música com a janela em foco)
                m = await pc_info.MEDIA.info() if pc_info.MEDIA else None
                _media_playing[0] = bool(m and m.get("status") == "playing")
            await asyncio.to_thread(SCREEN.tick)
        except Exception:  # noqa: BLE001
            log.exception("screentime_loop")
        await asyncio.sleep(2)


def screen_cat(p):
    cat = SCREEN.set_category(str(p["app"]), str(p["cat"]))
    save_cfg_key("screentime", SCREEN.cfg)
    return cat


async def battery_loop():
    while True:
        try:
            await asyncio.to_thread(BAT.poll)
        except Exception:  # noqa: BLE001
            log.exception("battery_loop")
        await asyncio.sleep(5)


def gsi_token():
    if not CFG.get("gsi_token"):
        save_cfg_key("gsi_token", secrets.token_urlsafe(16))
    return CFG["gsi_token"]


def gsi_update(game, summary):
    asyncio.get_running_loop().create_task(broadcast({"t": "gsi", "d": summary}))


MATCHES = matches.Store(BASE / "matches.db")
GSI = gsi.GSI(int(CFG.get("gsi_port", 8772)), gsi_token(), gsi_update,
              trackers={"cs2": matches.CsTracker(MATCHES), "dota2": matches.DotaTracker(MATCHES)})


# --------------------------------------------------------------------------
# Hoje: clima e agenda
# --------------------------------------------------------------------------
DAILY = {"weather": None, "events": [], "err": {}, "wT": 0.0, "cT": 0.0}


def daily_cfg():
    return CFG.setdefault("daily", {"city": "", "ics": ""})


def daily_public():
    c = daily_cfg()
    return {"weather": DAILY["weather"] if c.get("city") else None, "events": DAILY["events"] if c.get("ics") else [],
            "city": c.get("city", ""), "has_ics": bool(c.get("ics")), "err": DAILY["err"]}


async def daily_refresh(force=False):
    c, now, changed = daily_cfg(), time.monotonic(), False
    if c.get("city") and (force or now - DAILY["wT"] > 1800):
        DAILY["wT"] = now
        try:
            DAILY["weather"] = await asyncio.to_thread(daily.weather, c["city"])
            DAILY["err"].pop("weather", None)
        except Exception as e:  # noqa: BLE001
            DAILY["err"]["weather"] = str(e)[:120]
            DAILY["wT"] = now - 1500  # tenta de novo em 5 min
            log.warning("clima: %s", e)
        changed = True
    if c.get("ics") and (force or now - DAILY["cT"] > 600):
        DAILY["cT"] = now
        try:
            DAILY["events"] = await asyncio.to_thread(daily.calendar, c["ics"])
            DAILY["err"].pop("calendar", None)
        except Exception as e:  # noqa: BLE001
            DAILY["err"]["calendar"] = str(e)[:120]
            DAILY["cT"] = now - 480
            log.warning("agenda: %s", e)
        changed = True
    if changed:
        await broadcast({"t": "daily", "d": daily_public()})


async def daily_loop():
    while True:
        try:
            await daily_refresh()
        except Exception:  # noqa: BLE001
            log.exception("hoje")
        await asyncio.sleep(30)


async def daily_set(p):
    c = dict(daily_cfg())
    if "city" in p:
        c["city"] = str(p["city"] or "").strip()[:80]
        DAILY["weather"] = None
    if "ics" in p:
        ics = str(p["ics"] or "").strip()
        if ics and not ics.startswith(("https://", "webcal://")):
            raise ValueError("cole o endereço secreto no formato iCal (começa com https://)")
        c["ics"] = ics[:600]
        DAILY["events"] = []
    save_cfg_key("daily", c)
    DAILY["err"] = {}
    await daily_refresh(force=True)
    return daily_public()


def daily_open(p):
    link = str(p.get("link") or "")
    if not daily.MEET_RE.fullmatch(link) or link not in {e.get("link") for e in DAILY["events"]}:
        raise ValueError("link de reunião desconhecido")
    subprocess.Popen(["cmd", "/c", "start", "", "msedge", link], creationflags=0x08000000)
    return True


# --------------------------------------------------------------------------
# Modo foco (cronômetro tipo Pomodoro; segura as notificações do PC no celular)
# --------------------------------------------------------------------------
FOCUS = {"state": None}
FOCUS_LOG = BASE / "focus.json"


def focus_today():
    try:
        return json.loads(FOCUS_LOG.read_text(encoding="utf-8")).get(time.strftime("%Y-%m-%d"), 0)
    except (OSError, ValueError):
        return 0


def _focus_add(minutes):
    try:
        data = json.loads(FOCUS_LOG.read_text(encoding="utf-8")) if FOCUS_LOG.exists() else {}
    except ValueError:
        data = {}
    day = time.strftime("%Y-%m-%d")
    data[day] = data.get(day, 0) + minutes
    data = dict(sorted(data.items())[-60:])
    FOCUS_LOG.write_text(json.dumps(data), encoding="utf-8")


def focus_state():
    f = FOCUS["state"]
    return {"on": bool(f), "end": f["end"] if f else None, "min": f["min"] if f else None,
            "left": max(0, round(f["end"] - time.time())) if f else None, "today": focus_today()}


async def focus_start(p):
    minutes = int(p.get("minutes") or 25)
    if not 1 <= minutes <= 240:
        raise ValueError("tempo de foco inválido")
    FOCUS["state"] = {"start": time.time(), "end": time.time() + minutes * 60, "min": minutes}
    await broadcast({"t": "focus", "d": focus_state()})
    return focus_state()


async def focus_stop(p=None, done=False):
    f = FOCUS["state"]
    if f:
        FOCUS["state"] = None
        _focus_add(round((min(time.time(), f["end"]) - f["start"]) / 60))
    st = focus_state()
    await broadcast({"t": "focus", "d": {**st, "done": done}})
    return st


async def focus_loop():
    while True:
        await asyncio.sleep(2)
        f = FOCUS["state"]
        if f and time.time() >= f["end"]:
            await focus_stop(done=True)


# --------------------------------------------------------------------------
# Perfis de áudio (saída + volume + microfone + volume dos apps)
# --------------------------------------------------------------------------
def audio_profiles():
    return CFG.setdefault("audio_profiles", [])


async def audio_profile_save(p):
    name = str(p.get("name") or "").strip()[:24]
    if not name:
        raise ValueError("dê um nome ao perfil")
    mx = await pc_info.mixer_get()
    mic = await pc_info.mic_get()
    out = next((o for o in mx.get("outputs") or [] if o.get("default")), None)
    prof = {"name": name, "out_id": out and out["id"], "out_name": out and out["name"],
            "level": (mx.get("master") or {}).get("level"), "mic_muted": (mic or {}).get("muted"),
            "apps": {a["key"]: a["level"] for a in mx.get("apps") or [] if a["key"] != "_system"}}
    profs = [x for x in audio_profiles() if x["name"].lower() != name.lower()] + [prof]
    save_cfg_key("audio_profiles", profs[-8:])
    return audio_profiles()


async def audio_profile_apply(p):
    prof = next((x for x in audio_profiles() if x["name"] == p.get("name")), None)
    if not prof:
        raise ValueError("perfil não existe")
    msgs = []
    if prof.get("out_id"):
        try:
            await pc_info.set_output(prof["out_id"])
        except Exception:  # noqa: BLE001
            msgs.append(f"{prof.get('out_name')} não está conectado")
    if prof.get("level") is not None:
        await pc_info.volume_set(level=float(prof["level"]))
    if prof.get("mic_muted") is not None:
        await pc_info.mic_set(bool(prof["mic_muted"]))
    for key, level in (prof.get("apps") or {}).items():
        try:
            await pc_info.mixer_set(key, level)
        except ValueError:
            pass  # app fechado agora
    await push_now()
    return {"name": prof["name"], "warn": msgs}


def audio_profile_del(p):
    save_cfg_key("audio_profiles", [x for x in audio_profiles() if x["name"] != p.get("name")])
    return audio_profiles()


def matches_get(p):
    game = p.get("game")
    if game not in ("cs2", "dota2"):
        raise ValueError("jogo inválido")
    return MATCHES.report(game)


def dota_mark(p):
    GSI.trackers["dota2"].mark(str(p.get("what")), bool(p.get("clear")))
    GSI.refresh("dota2")


async def games_loop():
    gsi_next = 0.0
    while True:
        try:
            state = await asyncio.to_thread(MON.poll)
            if time.monotonic() > gsi_next and MON.catalog.roots and CFG.get("gsi_install", True):
                gsi_next = time.monotonic() + 600
                await asyncio.to_thread(gsi.install, list(MON.catalog.roots), GSI.port, GSI.token)
            for ws in list(clients):
                await send_games(ws, state)
        except Exception:  # noqa: BLE001
            log.exception("games_loop")
        await asyncio.sleep(3)


async def now_loop():
    while True:
        try:
            if clients:
                payload = await now_payload()
                for ws in list(clients):
                    await send_now(ws, payload)
        except Exception:  # noqa: BLE001
            log.exception("now_loop")
        await asyncio.sleep(1)


NET = {"web": False, "adb": []}


def lan_ip():
    """IP do PC na rede local (não envia nada: UDP connect só escolhe a rota)."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("192.168.255.255", 1))
            return s.getsockname()[0]
    except OSError:
        return None


def phone_links():
    """Links para abrir o app no celular (o token vai no #, que não é enviado na rede)."""
    port, tok = WEB["port"], CFG["token"]
    links = {"cabo": f"http://localhost:{port}/#t={tok}"}
    ip = lan_ip()
    if ip and WEB["host"] not in ("127.0.0.1", "localhost"):
        links["wifi"] = f"http://{ip}:{port}/#t={tok}"
    return links


def status():
    """Estado para o ícone da bandeja/painel."""
    kinds = [client_kind.get(ws) for ws in list(clients)]
    game = (MON.state.get("game") or {}).get("name")
    n = kinds.count("celular")
    parts = ["aparelho conectado" if n == 1 else f"{n} aparelhos conectados"] if n else []
    phone = {"web": NET["web"], "adb": list(NET["adb"]), "port": WEB["port"],
             "links": phone_links() if NET["web"] else {}}
    vs = VOICE.state()
    if parts:
        return {"state": "ok", "text": " + ".join(parts), "game": game, "phone": phone, "voice": vs}
    text = "Aguardando conexão na rede local" if NET["web"] else "Porta do app indisponível (veja o log)"
    return {"state": "wait" if NET["web"] else "off", "text": text, "game": game, "phone": phone, "voice": vs}


# --------------------------------------------------------------------------
# Celular: app web + adb reverse
# --------------------------------------------------------------------------
MIME = {".html": "text/html; charset=utf-8", ".js": "text/javascript; charset=utf-8",
        ".css": "text/css; charset=utf-8", ".json": "application/json",
        ".webmanifest": "application/manifest+json", ".png": "image/png", ".svg": "image/svg+xml", ".mp4": "video/mp4", ".webm": "video/webm",
        ".woff2": "font/woff2", ".txt": "text/plain; charset=utf-8"}


def web_build():
    """Muda quando algum arquivo do app web muda: o celular recarrega a página sozinho."""
    try:
        return int(max(f.stat().st_mtime for f in WEB_DIR.rglob("*") if f.is_file()))
    except (OSError, ValueError):
        return 0


def serve_static(connection, request):
    """Requisições HTTP comuns recebem os arquivos de web/; WebSocket segue normal."""
    if "websocket" in request.headers.get("Upgrade", "").lower():
        return None
    path = request.path.split("?", 1)[0].split("#", 1)[0]
    if path.startswith("/dl/"):  # arquivo do PC liberado por clip.get (link temporário)
        got = extras.dl_fetch(path)
        if not got:
            return connection.respond(HTTPStatus.NOT_FOUND, "link expirado\n")
        name, body, ctype = got
        from urllib.parse import quote
        headers = Headers([("Content-Type", ctype), ("Content-Length", str(len(body))),
                           ("Content-Disposition", f"attachment; filename*=UTF-8''{quote(name)}"),
                           ("Cache-Control", "no-store")])
        return Response(200, "OK", headers, body)
    name = "index.html" if path in ("/", "") else "editor.html" if path.rstrip("/") == "/editor" else path.lstrip("/")
    f = (WEB_DIR / name).resolve()
    if WEB_DIR.resolve() not in f.parents or not f.is_file() or f.suffix not in MIME:
        return connection.respond(HTTPStatus.NOT_FOUND, "não encontrado\n")
    body = f.read_bytes()
    headers = Headers([("Content-Type", MIME[f.suffix]), ("Content-Length", str(len(body))),
                       ("Cache-Control", "no-cache"), ("X-Content-Type-Options", "nosniff")])
    return Response(200, "OK", headers, body)


async def web_main():
    host, port = WEB["host"], int(os.environ.get("COMPANION_WEB_PORT", WEB["port"]))
    while True:
        try:
            async with serve(web_handler, host, port, process_request=serve_static,
                             ping_interval=5, ping_timeout=10, max_size=4 * 2**20,
                             max_queue=64) as server:
                NET["web"] = True
                for name, url in phone_links().items():
                    log.info("celular (%s): %s", name, url.split("#")[0])
                await server.serve_forever()
        except OSError as e:
            NET["web"] = False
            log.warning("app do celular: não consegui escutar em %s:%s: %s", host, port, e)
            await asyncio.sleep(10)


def find_adb():
    cands = [WEB.get("adb_path") or "", "adb",
             os.path.expandvars(r"%LOCALAPPDATA%\Android\Sdk\platform-tools\adb.exe"),
             os.path.expandvars(r"%LOCALAPPDATA%\Microsoft\WinGet\Links\adb.exe"),
             os.path.expandvars(r"%USERPROFILE%\companion-pc\platform-tools\adb.exe")]
    import glob
    import shutil
    cands += glob.glob(os.path.expandvars(
        r"%LOCALAPPDATA%\Microsoft\WinGet\Packages\Google.PlatformTools*\platform-tools\adb.exe"))
    for c in cands:
        if c and (shutil.which(c) or os.path.isfile(c)):
            return shutil.which(c) or c
    return None


def adb(path, *args, timeout=8):
    return subprocess.run([path, *args], capture_output=True, text=True, timeout=timeout,
                          creationflags=pc_info.NO_WINDOW)


def adb_open_on_phone(serial=None):
    """Abre o app no celular conectado pelo cabo (já com o token)."""
    path = find_adb()
    if not path:
        raise RuntimeError("adb não encontrado (rode windows\\setup-network.ps1)")
    serials = [serial] if serial else list(NET["adb"])
    if not serials:
        raise RuntimeError("nenhum celular com depuração USB conectado")
    for sr in serials:
        adb(path, "-s", sr, "shell", "am", "start", "-a", "android.intent.action.VIEW",
            "-d", f"'{phone_links()['cabo']}'")


async def adb_loop():
    """Com o celular no cabo (depuração USB), mapeia localhost:8770 do celular para o PC."""
    if not WEB.get("adb_reverse", True):
        return
    port = int(os.environ.get("COMPANION_WEB_PORT", WEB["port"]))
    path, warned = None, False
    while True:
        try:
            path = path or await asyncio.to_thread(find_adb)
            if not path:
                if not warned:
                    log.info("adb não encontrado: cabo no celular desativado (Wi-Fi continua funcionando)")
                    warned = True
                await asyncio.sleep(30)
                continue
            out = (await asyncio.to_thread(adb, path, "devices")).stdout
            ready = [ln.split()[0] for ln in out.splitlines()[1:] if ln.strip().endswith("\tdevice")]
            for ln in out.splitlines()[1:]:
                if "unauthorized" in ln and ln.split()[0] not in NET.setdefault("unauth", set()):
                    NET["unauth"].add(ln.split()[0])
                    log.info("celular %s: aceite a 'depuração USB' na tela do celular", ln.split()[0])
            for sr in ready:
                if sr not in NET["adb"]:
                    r = await asyncio.to_thread(adb, path, "-s", sr, "reverse", f"tcp:{port}", f"tcp:{port}")
                    if r.returncode == 0:
                        NET["adb"].append(sr)
                        log.info("celular %s no cabo: abra http://localhost:%s", sr, port)
                    else:
                        log.warning("adb reverse falhou (%s): %s", sr, (r.stderr or r.stdout).strip())
            for sr in list(NET["adb"]):
                if sr not in ready:
                    NET["adb"].remove(sr)
                    log.info("celular %s desconectado do cabo", sr)
        except Exception as e:  # noqa: BLE001
            log.warning("adb: %s", e)
            path = None
        await asyncio.sleep(4)


async def web_watch():
    """Página do app mudou no PC: avisa os aparelhos conectados (eles recarregam)."""
    last = web_build()
    while True:
        await asyncio.sleep(3)
        cur = await asyncio.to_thread(web_build)
        if cur != last:
            last = cur
            log.info("app web atualizado - recarregando os aparelhos")
            for ws in list(clients):
                try:
                    await ws.send(json.dumps({"t": "welcome", "web": cur}))
                except Exception:  # noqa: BLE001
                    pass


async def main():
    log.info("Companion PC %s", VERSION)
    pc_info.MEDIA = pc_info.Media()
    st = STATS_REF[0] = Stats()
    asyncio.create_task(stats_loop(st))
    asyncio.create_task(PING.loop(lambda: bool(clients)))
    asyncio.create_task(NOTIF.loop(lambda: bool(notif_subs), push_notif,
                                   lambda: {a.lower() for a in CFG.get("notif_ignore", [])}))
    await asyncio.to_thread(watchers.kill_orphans)
    asyncio.create_task(FPS.loop(fps_wanted))
    asyncio.create_task(now_loop())
    asyncio.create_task(games_loop())
    asyncio.create_task(battery_loop())
    asyncio.create_task(screentime_loop())
    asyncio.create_task(daily_loop())
    asyncio.create_task(focus_loop())
    asyncio.create_task(GSI.serve())
    asyncio.create_task(adb_loop())
    asyncio.create_task(downloads_loop())
    asyncio.create_task(web_watch())
    VOICE.start(asyncio.get_running_loop())
    await web_main()


def stop_server():
    release_modifiers()
    SCREEN.flush()


def run_with_tray():
    import threading
    import tray

    if not tray.acquire_single_instance(wait_s=15 if "--restart" in sys.argv else 0):
        tray.signal_running_instance()  # já está rodando: só mostra o painel
        return
    try:
        import pystray  # noqa: F401
    except ImportError:
        log.warning("pystray não instalado - rodando sem ícone na bandeja")
        asyncio.run(main())
        return

    def server_thread():
        try:
            asyncio.run(main())
        except Exception:  # noqa: BLE001
            log.exception("servidor parou")
    threading.Thread(target=server_thread, daemon=True, name="server").start()
    tray.TrayApp(status, LOG_PATH, BASE, VERSION, stop_server, open_on_phone=adb_open_on_phone,
                 voice_set=VOICE.set).run()


if __name__ == "__main__":
    try:
        if "--console" in sys.argv:
            asyncio.run(main())
        else:
            run_with_tray()
    except KeyboardInterrupt:
        pass
