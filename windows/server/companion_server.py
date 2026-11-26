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
from pathlib import Path

import psutil
from websockets.asyncio.server import serve
from websockets.exceptions import ConnectionClosed

import devices
import extras
import conquistas
import retro
import ranking
import games
import gsi
import https_cert
import matches
import daily
import dota_stats
import dota_draft
import steam
import overlay
import pc_info
import screentime
import soundboard
import startapps
import updater
import voice
import watchers

VERSION = "1.17"
BASE = Path(__file__).resolve().parent
CFG_PATH = BASE / "config.json"
LOG_PATH = BASE / "companion-server.log"

DEFAULT_CFG = {
    "token": "",
    "allow_power": True,
    "shutdown_delay_s": 30,
    # App do celular. host "0.0.0.0" = rede local + cabo; "127.0.0.1" = só cabo (adb).
    "web": {"host": "0.0.0.0", "port": 8770, "adb_reverse": True, "adb_path": ""},
    # HTTPS na porta 8771 com o certificado do Tailscale (ou cert_file/key_file, ex.: mkcert; "host" = nome do link)
    "https": dict(https_cert.DEFAULT),
    # Relatório do Dota depois da partida (nota, lanes, placar): chave grátis em stratz.com/api
    "stratz": {"token": ""},
    # Atualização automática: confere o release.json do repositório a cada 6 h ("check": false desliga)
    "update": dict(updater.DEFAULT),
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
        # usados pelas macros da página padrão "Macros" (caminhos da instalação padrão de cada um)
        {"id": "vscode", "name": "VS Code", "open": "%LOCALAPPDATA%\\Programs\\Microsoft VS Code\\Code.exe"},
        {"id": "terminal", "name": "Terminal", "open": "wt.exe"},
        {"id": "opera", "name": "Opera", "open": "%LOCALAPPDATA%\\Programs\\Opera\\launcher.exe"},
        {"id": "discord", "name": "Discord", "open": "%LOCALAPPDATA%\\Discord\\Update.exe",
         "args": "--processStart Discord.exe"},
        {"id": "steam", "name": "Steam", "open": "steam://open/main"},
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
UPD = updater.Updater(VERSION, CFG.get("update"), BASE)
WEB = {**DEFAULT_CFG["web"], **(CFG.get("web") or {})}

# --------------------------------------------------------------------------
# Win32: teclado e mouse (win_input.py), energia e atalhos
# --------------------------------------------------------------------------
from win_input import (  # noqa: E402
    VK, focus_window_titled, foreground_app, foreground_title, modifier, mouse_button, mouse_move,
    mouse_scroll, press_combo, release_modifiers, type_text, user32, valid_combo,
)


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


START_APPS = startapps.StartApps()


def launch(shortcut_id):
    if str(shortcut_id).startswith("start:"):  # app do Menu Iniciar (voz): só o que está na lista do Windows
        appid = shortcut_id[6:]
        name = START_APPS.name_of(appid)
        if not name:
            raise ValueError("app não encontrado no Menu Iniciar")
        os.startfile("shell:AppsFolder\\" + appid)
        return name
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
LAYOUT_VIEWS = {"dash", "today", "conq", "games", "usage", "media", "mix", "mouse", "screen", "deck", "send", "power", "voz", "sys"}
LAYOUT_CARDS = {"cpu", "ram", "gpu", "net", "procs", "disks", "bat", "sys"}
SKINS = {"fallout", "synth", "minimal", "hud", "lcd", "paper", "pocket", "code", "rpg", "tac", "jp", "exec"}


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
    if isinstance(o.get("known"), list):
        out["known"] = [v for v in o["known"] if v in LAYOUT_VIEWS][:30]
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
    au = lay.get("auto")
    if isinstance(au, dict):
        ok_theme = lambda v: isinstance(v, str) and len(v) <= 30 and (v == "" or v.split(":")[0] in SKINS)  # noqa: E731
        ok_time = lambda v: isinstance(v, str) and re.fullmatch(r"\d{2}:\d{2}", v)  # noqa: E731
        t, g, out = au.get("time") or {}, au.get("game") or {}, {}
        if isinstance(t, dict):
            out["time"] = {"on": bool(t.get("on")), **{k: t[k] for k in ("day", "night") if ok_theme(t.get(k))},
                           **{k: t[k] for k in ("from", "to") if ok_time(t.get(k))}}
        if isinstance(g, dict):
            out["game"] = {"on": bool(g.get("on")), **{k: g[k] for k in ("dota2", "cs2") if ok_theme(g.get(k))}}
        clean["auto"] = out
    for k in ("portrait", "landscape"):
        o = _clean_orient(lay.get(k))
        if o:
            clean[k] = o
    tmp = LAYOUT_PATH.with_suffix(".tmp")
    tmp.write_text(json.dumps(clean, indent=2, ensure_ascii=False), encoding="utf-8")
    tmp.replace(LAYOUT_PATH)
    asyncio.get_running_loop().create_task(broadcast({"t": "layout", "d": clean}))
    return clean


def deck_sounds(deck):
    return {b["value"] for pg in deck.get("pages", []) for b in pg.get("buttons") or [] if b and b.get("type") == "sound"}


def deck_saved(data):
    try:
        BOARD.cleanup(deck_sounds(data))
    except Exception:  # noqa: BLE001
        log.exception("sons: limpeza")
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
    "snd.state": lambda p: _async(BOARD.state()),
    "snd.mics": lambda p: asyncio.to_thread(BOARD.mics),
    "snd.set": lambda p: asyncio.to_thread(BOARD.set, p),
    "snd.add": lambda p: asyncio.to_thread(BOARD.add, str(p["data"])),
    "snd.info": lambda p: asyncio.to_thread(BOARD.info, str(p["id"])),
    "snd.get": lambda p: asyncio.to_thread(BOARD.raw, str(p["id"])),
    "snd.play": lambda p: asyncio.to_thread(BOARD.play, str(p["id"]), int(p.get("vol", 100))),
    "snd.stop": lambda p: asyncio.to_thread(BOARD.stop),
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
    "day.summary": lambda p: asyncio.to_thread(day_summary, p),
    "conq.get": lambda p: _async(CONQ.state()),
    "retro.get": lambda p: asyncio.to_thread(retro_get, p),
    "rank.state": lambda p: _async(RANK.state()),
    "rank.join": lambda p: rank_join(p),
    "rank.nick": lambda p: rank_call(RANK.set_nick, str(p.get("nick") or "")),
    "rank.leave": lambda p: rank_call(RANK.leave),
    "rank.board": lambda p: rank_call(RANK.board, str(p.get("kind") or "week")),
    "steam.set": lambda p: steam_set(p),
    "steam.get": lambda p: _async({**STEAM_STATE, "steamid": STEAM.steamid()}),
    "stratz.get": lambda p: _async(stratz_public()),
    "update.get": lambda p: _async(UPD.state()),
    "update.check": lambda p: asyncio.to_thread(UPD.check),
    "update.install": lambda p: asyncio.to_thread(UPD.install),
    "stratz.set": lambda p: stratz_set(p),
    "dota.report": lambda p: dota_report_now(p),
    "dota.heroes": lambda p: dota_draft_call(DRAFT.hero_list),
    "dota.draft": lambda p: dota_draft_call(DRAFT.draft, p.get("pos"), p.get("enemies"), p.get("allies"), p.get("bracket"), dota_acc(), p.get("prefer") or (), p.get("turbo") is True),
    "dota.plan.get": lambda p: _async(DOTA_PLAN.state()),
    "dota.plan.set": lambda p: dota_plan_set(p),
    "dota.build": lambda p: dota_draft_call(DRAFT.build, p.get("hero"), p.get("pos"), p.get("bracket"), dota_acc(), p.get("enemies") or (), p.get("turbo") is True),
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
    elif t == "sound":
        await asyncio.to_thread(BOARD.play, v, b.get("vol", 100))
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
        "t": "welcome", "version": VERSION, "web": web_build(), "host": socket.gethostname(), "https": https_url(),
        "os": f"{platform.system()} {platform.release()}",
        "shortcuts": [{"id": s["id"], "name": s["name"]} for s in CFG["shortcuts"]],
        "power": bool(CFG.get("allow_power")), "layout": layout_get(), "update": UPD.state(),
        "features": {"media": pc_info.HAS_MEDIA, "volume": pc_info.HAS_VOLUME, "mixer": pc_info.HAS_VOLUME,
                     "screen": True, "clipboard": True, "files": True, "deck": True,
                     "mic": pc_info.HAS_VOLUME, "timer": True, "deck_auto": True, "macro": True,
                     "library": True, "ping": True, "notif": True, "fps": True, "voice": VOICE.available, "sounds": BOARD.available,
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
    await ws.send(json.dumps({"t": "steam", "d": STEAM_STATE}, ensure_ascii=False))
    if LAST_MATCH["d"] and time.time() - LAST_MATCH["d"]["t"] < 1800:
        await ws.send(json.dumps({"t": "match_end", "d": LAST_MATCH["d"]}, ensure_ascii=False))
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
                    lp = msg.get("p") or ""
                    if isinstance(lp, dict) and (lp.get("ics") or lp.get("key")):
                        lp = {**lp, **({"ics": "(oculto)"} if lp.get("ics") else {}), **({"key": "(oculta)"} if lp.get("key") else {})}
                    log.info("%s %s", action, lp)
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
QUIET_ACTIONS = {"conq.get", "retro.get", "rank.state", "rank.board", "snd.get", "snd.state", "snd.mics", "snd.add", "snd.info", "snd.play", "snd.stop", "layout.get", "dota.plan.get", "dota.heroes", "dota.draft", "dota.build", "day.summary", "steam.get", "stratz.get", "matches.get", "daily.get", "audio.profiles", "bat.refresh", "usage.get", "usage.app", "games.history", "games.library", "notif.sub", "mouse.move", "mouse.scroll", "key.text", "clip.set", "clip.get", "file.chunk",
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
    return voice.Catalog([(s["id"], s["name"]) for s in CFG["shortcuts"]], _voice_games[1], deck, START_APPS.get())


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


async def board_event(st):
    await broadcast({"t": "snd", "d": st})


def audio_refresh():
    """Reinicia o PortAudio (só assim ele vê um fone que conectou depois). A voz usa o PortAudio também:
    fecha o microfone dela antes e reabre depois. Chamado pela thread da mesa de som, já sem streams abertos."""
    import sounddevice as sd
    was = VOICE.pause()
    try:
        if was is False:  # a voz não soltou o microfone: reiniciar agora derrubaria o processo
            return False
        sd._terminate()
        sd._initialize()
        return True
    finally:
        if was is not None:
            VOICE._spawn()


BOARD = soundboard.Board(BASE, CFG.get("sounds"), lambda c: save_cfg_key("sounds", c), board_event, audio_refresh)
TALK = soundboard.TalkLog(BASE / "voz.db")
TALK_WATCH = soundboard.TalkWatch(time.monotonic())


def talk_flush(force=False):
    got = TALK_WATCH.take(time.monotonic(), force)
    if got:
        TALK.add(time.strftime("%Y-%m-%d"), got)


async def talk_loop():
    """Tempo de fala (Seu dia) e o aviso de "falando no mudo" (mesa de som ou Meet)."""
    while True:
        await asyncio.sleep(0.5)
        try:
            meet = MEET["state"] or {}
            in_call = bool(MEET["since"])
            ctx = "meet" if in_call else "game" if MON.state.get("game") else "other"
            mute = "mesa" if BOARD.muted else "meet" if in_call and meet.get("mic") is False else ""
            why = TALK_WATCH.step(time.monotonic(), BOARD.talk_secs, ctx, mute)
            if why:
                await broadcast({"t": "event", "kind": "talkwarn", "why": why})
            if TALK_WATCH.pend:
                await asyncio.to_thread(talk_flush)
        except Exception:  # noqa: BLE001
            log.exception("talk_loop")
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
            "city": c.get("city", ""), "has_ics": bool(c.get("ics")), "err": DAILY["err"],
            "busy_only": bool(c.get("ics")) and bool(DAILY["events"]) and all(e["title"] == "Ocupado" for e in DAILY["events"]),
            "meet_auto": c.get("meet_auto", True), "meet_open": bool(c.get("meet_open")), "meet_profile": c.get("meet_profile", "")}


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


MEET_PREP = set()


async def meet_prepare():
    """1 minuto antes de um compromisso: avisa o celular; se tiver link do Meet, aplica o perfil de áudio (e abre, se pedido)."""
    import datetime as _dt
    c = daily_cfg()
    if not c.get("meet_auto", True):
        return
    now = _dt.datetime.now()
    for e in DAILY["events"]:
        if e["all_day"]:
            continue
        key = e["start"] + e["title"]
        left = (_dt.datetime.fromisoformat(e["start"]) - now).total_seconds()
        if key in MEET_PREP or not 0 < left <= 75:
            continue
        MEET_PREP.add(key)
        applied = None
        if c.get("meet_profile") and e.get("link"):
            try:
                await audio_profile_apply({"name": c["meet_profile"]})
                applied = c["meet_profile"]
            except Exception as ex:  # noqa: BLE001
                log.warning("reunião: perfil %s: %s", c["meet_profile"], ex)
        if c.get("meet_open") and e.get("link"):
            try:
                daily_open({"link": e["link"]})
            except Exception as ex:  # noqa: BLE001
                log.warning("reunião: abrir: %s", ex)
        log.info("reunião em 1 min: %s (perfil: %s)", e["title"], applied or "nenhum")
        await broadcast({"t": "meet_soon", "d": {**e, "profile": applied, "opened": bool(c.get("meet_open") and e.get("link"))}})


async def daily_loop():
    while True:
        try:
            await daily_refresh()
            await meet_prepare()
        except Exception:  # noqa: BLE001
            log.exception("hoje")
        await asyncio.sleep(15)


async def daily_set(p):
    c = dict(daily_cfg())
    if "city" in p:
        city = str(p["city"] or "").strip()[:80]
        if city != c.get("city"):
            DAILY["weather"] = None
        c["city"] = city
    for k in ("meet_auto", "meet_open"):
        if k in p:
            c[k] = bool(p[k])
    if "meet_profile" in p:
        c["meet_profile"] = str(p["meet_profile"] or "")[:24]
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
        CONQ_KICK.set()
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


# --------------------------------------------------------------------------
# Pós-partida
# --------------------------------------------------------------------------
LAST_MATCH = {"d": None}


def match_saved(pm):
    LAST_MATCH["d"] = pm
    CONQ_KICK.set()
    loop = asyncio.get_running_loop()
    loop.create_task(broadcast({"t": "match_end", "d": pm}))
    if pm.get("game") == "dota2" and pm.get("key"):
        loop.create_task(dota_report_job(pm["key"], pm.get("data") or {}))
        loop.create_task(dota_plan_reset())   # o plano era para esta partida


MATCHES.on_saved = match_saved


# --------------------------------------------------------------------------
# Dota 2: relatório depois da partida (STRATZ, ou OpenDota sem chave) - dota_stats.py
# --------------------------------------------------------------------------
DOTA_JOBS = {}       # chave da partida -> task
STRATZ_STATE = {"err": None, "last": None}


def stratz_token():
    return str((CFG.get("stratz") or {}).get("token") or "").strip()


def stratz_public():
    return {"has_key": bool(stratz_token()), **STRATZ_STATE}


def stratz_import_file():
    """Chave colada em stratz-token.txt (antes do campo em Personalizar): passa para o config.json."""
    f = BASE / "stratz-token.txt"
    if stratz_token() or not f.is_file():
        return
    try:
        tok = f.read_text(encoding="utf-8-sig").strip()
    except OSError:
        return
    tok = tok[7:].strip() if tok.lower().startswith("bearer ") else tok
    if tok:
        save_cfg_key("stratz", {**(CFG.get("stratz") or {}), "token": tok})
        log.info("STRATZ: chave importada de stratz-token.txt (pode apagar o arquivo)")


async def stratz_set(p):
    tok = str(p.get("token") or "").strip()
    tok = tok[7:].strip() if tok.lower().startswith("bearer ") else tok
    if tok:   # testa antes de salvar
        try:
            await asyncio.to_thread(dota_stats.Stratz(tok, BASE).gql, "{ constants { gameVersions { id } } }")
        except dota_stats.ApiError as e:
            raise ValueError(str(e)) from e
    save_cfg_key("stratz", {**(CFG.get("stratz") or {}), "token": tok})
    STRATZ_STATE["err"] = None
    return stratz_public()


def dota_me(data):
    """(conta, herói) para achar você no relatório: a conta do GSI ou a do login da Steam."""
    acc = dota_stats.account_id(data.get("acc")) or dota_stats.account_id(STEAM.steamid())
    return acc, data.get("hero_id")


async def dota_report_push(key, rep):
    MATCHES.attach(key, "report", rep)
    if LAST_MATCH["d"] and LAST_MATCH["d"].get("key") == key:
        LAST_MATCH["d"]["report"] = rep
    await broadcast({"t": "match_report", "d": {"key": key, "report": rep}})


async def dota_report_job(key, data, delays=None):
    """Busca o relatório em segundo plano (uma tarefa por partida); cada versão melhor vai para o celular."""
    if key in DOTA_JOBS and not DOTA_JOBS[key].done():
        return
    DOTA_JOBS[key] = asyncio.current_task()
    mid, (acc, hero) = key.split(":", 1)[1], dota_me(data)

    async def push(rep, err):
        STRATZ_STATE["err"] = err if err and "STRATZ" in err else None
        STRATZ_STATE["last"] = {"match": mid, "src": rep["src"], "complete": rep["complete"], "t": rep["t"]}
        await dota_report_push(key, rep)
    try:
        await dota_stats.report_job(mid, stratz_token, BASE, acc, hero, push, delays)
    finally:
        DOTA_JOBS.pop(key, None)


async def dota_report_resume():
    """Servidor reiniciou no meio da espera: retoma as partidas das últimas 2 h sem relatório completo."""
    for key, data in MATCHES.pending("dota2", "report", time.time() - 7200):
        asyncio.create_task(dota_report_job(key, data, dota_stats.DELAYS[1:]))


# Draft e builds (estatísticas públicas do STRATZ) - dota_draft.py
DRAFT = dota_draft.Draft(stratz_token, BASE)


DOTA_PLAN = dota_draft.Plan(BASE / "dota-plan.json")
PLAN_WARM = {"task": None}


async def dota_plan_set(p):
    st = DOTA_PLAN.set(p)
    await broadcast({"t": "dota_plan", "d": st})
    # já deixa as builds dos preferidos no cache: na hora de escolher o herói elas abrem na hora
    if stratz_token() and st["heroes"] and (PLAN_WARM["task"] is None or PLAN_WARM["task"].done()):
        PLAN_WARM["task"] = asyncio.create_task(dota_plan_warm())
    return st


async def dota_plan_warm():
    await asyncio.sleep(3)   # espera terminar de escolher
    st = DOTA_PLAN.state()
    for h in st["heroes"]:
        try:
            await asyncio.to_thread(DRAFT.build, h, st["pos"], "auto", dota_acc(), (), st.get("turbo", False))
        except (ValueError, dota_stats.ApiError) as e:
            log.info("plano do Dota: build de %s não veio (%s)", h, e)
            return


async def dota_plan_reset():
    await broadcast({"t": "dota_plan", "d": DOTA_PLAN.reset(), "reset": True})


def dota_acc():
    """Sua conta do Dota: a da última partida salva pelo GSI, senão a do login da Steam."""
    d = LAST_MATCH["d"] or {}
    return dota_me((d.get("data") or {}) if d.get("game") == "dota2" else {})[0]


async def dota_draft_call(fn, *args):
    if not stratz_token():
        raise ValueError("Coloque a chave grátis do STRATZ em Personalizar > Dota 2 para ver draft e builds")
    try:
        return await asyncio.to_thread(fn, *args)
    except dota_stats.ApiError as e:
        raise ValueError(f"STRATZ: {e}") from None


async def dota_report_now(p):
    """Busca agora (botão no celular). key = "dota2:<id da partida>"."""
    key = str(p.get("key") or "")
    if not key.startswith("dota2:") or not key[6:].isdigit():
        raise ValueError("partida inválida")
    rows = [d for k, d in MATCHES.pending("dota2", "report", 0) if k == key]
    acc, hero = dota_me(rows[0] if rows else {})
    rep, err = await asyncio.to_thread(dota_stats.fetch, key[6:], stratz_token(), BASE, acc, hero, {})
    if not rep:
        raise ValueError(err or "a partida ainda não apareceu; tente daqui a alguns minutos")
    await dota_report_push(key, rep)
    return rep


# --------------------------------------------------------------------------
# Steam: downloads e amigos
# --------------------------------------------------------------------------
STEAM = steam.Steam(MON.catalog, CFG.setdefault("steam", {}))
STEAM_STATE = {"downloads": [], "friends": None, "err": None, "has_key": bool(CFG["steam"].get("key"))}


async def steam_loop():
    friends_next = 0.0
    while True:
        changed = False
        try:
            dls, finished = await asyncio.to_thread(STEAM.downloads)
            if dls != STEAM_STATE["downloads"]:
                STEAM_STATE["downloads"], changed = dls, True
            for name in finished:
                await broadcast({"t": "event", "kind": "steam_done", "name": name})
        except Exception:  # noqa: BLE001
            log.exception("steam downloads")
        if CFG["steam"].get("key") and time.monotonic() > friends_next:
            friends_next = time.monotonic() + 60
            try:
                fr = await asyncio.to_thread(STEAM.friends)
                if fr != STEAM_STATE["friends"] or STEAM_STATE["err"]:
                    STEAM_STATE.update(friends=fr, err=None)
                    changed = True
            except Exception as e:  # noqa: BLE001
                if STEAM_STATE["err"] != str(e)[:160]:
                    STEAM_STATE["err"], changed = str(e)[:160], True
                    log.warning("steam amigos: %s", e)
                friends_next = time.monotonic() + 300
        if changed:
            await broadcast({"t": "steam", "d": STEAM_STATE})
        await asyncio.sleep(5)


async def steam_set(p):
    key = str(p.get("key") or "").strip()
    if key and not steam.KEY_RE.fullmatch(key):
        raise ValueError("a chave da Steam tem 32 letras e números (copie de steamcommunity.com/dev/apikey)")
    c = dict(CFG["steam"]); c["key"] = key
    save_cfg_key("steam", c)
    STEAM.cfg = CFG["steam"]
    STEAM.friend_ids = []
    STEAM_STATE.update(has_key=bool(key), friends=None, err=None)
    if key:
        try:
            STEAM_STATE["friends"] = await asyncio.to_thread(STEAM.friends)
        except Exception as e:  # noqa: BLE001
            STEAM_STATE["err"] = str(e)[:160]
    await broadcast({"t": "steam", "d": STEAM_STATE})
    return {"has_key": bool(key), "friends": len(STEAM_STATE["friends"] or []), "err": STEAM_STATE["err"], "steamid": STEAM.steamid()}


# --------------------------------------------------------------------------
# Resumo do dia
# --------------------------------------------------------------------------
def day_summary(p=None):
    import datetime as _dt
    scr = SCREEN.report("day")
    midnight = time.mktime(time.localtime()[:3] + (0, 0, 0, 0, 0, -1))
    with MATCHES.lock:
        rows = MATCHES.db.execute("SELECT game, title, win FROM matches WHERE ended >= ?", (midnight,)).fetchall()
    games_today = MON.summary(1)
    today = _dt.date.today().isoformat()
    meets = [e for e in DAILY["events"] if not e["all_day"] and e["start"][:10] == today]
    mmin = sum((_dt.datetime.fromisoformat(e["end"]) - _dt.datetime.fromisoformat(e["start"])).total_seconds() / 60 for e in meets)
    return {"screen": scr.get("total", 0), "prev_avg": scr.get("prev_avg"),
            "cats": (scr.get("cats") or [])[:3], "apps": [{"name": a["name"], "secs": a["secs"]} for a in (scr.get("apps") or [])[:3]],
            "focus_min": focus_today(), "game_s": games_today["week_s"], "games": games_today["top"][:3],
            "matches": {"n": len(rows), "w": sum(1 for r in rows if r[2] == 1), "l": sum(1 for r in rows if r[2] == 0)},
            "meetings": {"n": len(meets), "min": round(mmin)},
            "talk": talk_today(today)}


def talk_today(today):
    """Minutos falando hoje por contexto (o que ainda não foi gravado também conta)."""
    secs = TALK.day(today)
    for k, v in dict(TALK_WATCH.pend).items():
        secs[k] = secs.get(k, 0) + v
    return {k: round(v / 60, 1) for k, v in secs.items()}


# --------------------------------------------------------------------------
# Conquistas, metas do dia e nível (conquistas.py)
# --------------------------------------------------------------------------
def _focus_log():
    try:
        return json.loads(FOCUS_LOG.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def conq_facts(day):
    import datetime as _dt
    start = time.mktime(_dt.date.fromisoformat(day).timetuple())
    end = start + 86400
    with MATCHES.lock:
        rows = MATCHES.db.execute("SELECT ended, game, win, data FROM matches WHERE ended >= ? AND ended < ?", (start, end)).fetchall()
    talk = TALK.day(day)
    if day == time.strftime("%Y-%m-%d"):
        for k, v in dict(TALK_WATCH.pend).items():
            talk[k] = talk.get(k, 0) + v
    return conquistas.build_facts(SCREEN.report("day", day), _focus_log().get(day, 0), talk,
                                  [(e, g, w, json.loads(d or "{}")) for e, g, w, d in rows])


def conq_first_day():
    days = list(_focus_log())
    try:
        with SCREEN._db() as db:
            days.append(db.execute("SELECT MIN(day) FROM usage").fetchone()[0])
    except Exception:  # noqa: BLE001
        pass
    with MATCHES.lock:
        first = MATCHES.db.execute("SELECT MIN(ended) FROM matches").fetchone()[0]
    if first:
        days.append(time.strftime("%Y-%m-%d", time.localtime(first)))
    days = [d for d in days if d]
    return min(days) if days else None


CONQ = conquistas.Conquistas(BASE / "conquistas.db", conq_facts, conq_first_day)
CONQ_KICK = asyncio.Event()
RANK = ranking.Ranking(CFG.setdefault("ranking", {}), lambda c: save_cfg_key("ranking", c))


async def rank_call(fn, *a):
    """Ações do ranking (rede): erro vira mensagem para o celular; o estado novo vai para todos."""
    try:
        res = await asyncio.to_thread(fn, *a)
    except ranking.RankError as e:
        raise ValueError(str(e)) from None
    await broadcast({"t": "rank", "d": RANK.state()})
    return res


async def rank_join(p):
    st = await rank_call(RANK.join, str(p.get("nick") or ""))
    await asyncio.to_thread(RANK.submit, CONQ.summary(), True)   # já aparece no ranking
    return st


async def conq_loop():
    """Recalcula a cada minuto (ou logo depois de uma partida ou um foco) e avisa os celulares."""
    sent = None
    while True:
        try:
            st, ev = await asyncio.to_thread(CONQ.refresh)
            for e in ev:
                log.info("conquistas: %s", e)
                await broadcast({"t": "event", "kind": "conq", "d": e})
            if clients:
                await retro_notice()
            await asyncio.to_thread(RANK.submit, CONQ.summary())     # a cada 15 min, se entrou no ranking
            key = json.dumps(st, sort_keys=True)
            if key != sent:
                sent = key
                await broadcast({"t": "conq", "d": st})
        except Exception:  # noqa: BLE001
            log.exception("conq_loop")
        try:
            await asyncio.wait_for(CONQ_KICK.wait(), 60)
        except asyncio.TimeoutError:
            pass
        CONQ_KICK.clear()
        await asyncio.sleep(2)   # junta vários avisos seguidos (partida + foco)


def retro_get(p):
    """Retrospectiva de um mês ("AAAA-MM"; padrão: o mês atual)."""
    import datetime as _dt
    month = str(p.get("month") or time.strftime("%Y-%m"))
    if not re.fullmatch(r"\d{4}-(0[1-9]|1[0-2])", month):
        raise ValueError("mês inválido")
    days, xp_before, conq, all_days = CONQ.month_data(month)
    first, last = retro.month_bounds(month)
    # comparação justa com o mês anterior: até o mesmo dia do mês, se este ainda não acabou
    today = _dt.date.today()
    upto = min(last, today).day
    prev = [x for x in CONQ.month_data(retro.prev_month(month))[0] if int(x[0][8:]) <= upto]
    start = time.mktime(first.timetuple())
    end = time.mktime((last + _dt.timedelta(days=1)).timetuple())
    with MATCHES.lock:
        rows = MATCHES.db.execute("SELECT ended, game, title, win, data FROM matches WHERE ended >= ? AND ended < ?",
                                  (start, end)).fetchall()
    out = retro.build(month, days, xp_before, conq, SCREEN.report("month", first.isoformat()),
                      [(e, g, t, w, json.loads(d or "{}")) for e, g, t, w, d in rows], prev)
    out["months"] = sorted({d[:7] for d in all_days}, reverse=True)
    return out


async def retro_notice():
    """No começo do mês, avisa uma vez que a retrospectiva do mês que acabou está pronta."""
    month = retro.prev_month(time.strftime("%Y-%m"))
    if CONQ.flag("retro_seen") == month or not any(d[:7] == month for d in CONQ.month_data(month)[3]):
        return
    CONQ.flag("retro_seen", month)
    await broadcast({"t": "event", "kind": "retro", "month": month, "label": retro.month_bounds(month)[0].strftime("%m/%Y")})


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


NET = {"web": False, "https": False, "adb": []}
HTTPS = https_cert.Https(BASE, CFG.get("https"))


def lan_ip():
    """IP do PC na rede local (não envia nada: UDP connect só escolhe a rota)."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("192.168.255.255", 1))
            return s.getsockname()[0]
    except OSError:
        return None


def https_url():
    """https://<nome do certificado>:<porta>/ quando o HTTPS está no ar (mkcert sem "host": IP da rede)."""
    if not NET["https"]:
        return None
    host = HTTPS.host or lan_ip()
    return f"https://{host}:{HTTPS.port}/" if host else None


def phone_links():
    """Links para abrir o app no celular (o token vai no #, que não é enviado na rede)."""
    port, tok = WEB["port"], CFG["token"]
    links = {"cabo": f"http://localhost:{port}/#t={tok}"}
    ip = lan_ip()
    if ip and WEB["host"] not in ("127.0.0.1", "localhost"):
        links["wifi"] = f"http://{ip}:{port}/#t={tok}"
    if https_url():
        links["https"] = f"{https_url()}#t={tok}"
    return links


def status():
    """Estado para o ícone da bandeja/painel."""
    kinds = [client_kind.get(ws) for ws in list(clients)]
    game = (MON.state.get("game") or {}).get("name")
    n = kinds.count("celular")
    parts = ["aparelho conectado" if n == 1 else f"{n} aparelhos conectados"] if n else []
    phone = {"web": NET["web"], "adb": list(NET["adb"]), "port": WEB["port"],
             "links": phone_links() if NET["web"] or NET["https"] else {},
             "https": {**HTTPS.state(), "on": NET["https"]} if HTTPS.enabled else None}
    vs = VOICE.state()
    if parts:
        return {"state": "ok", "text": " + ".join(parts), "game": game, "phone": phone, "voice": vs}
    text = "Aguardando conexão na rede local" if NET["web"] else "Porta do app indisponível (veja o log)"
    return {"state": "wait" if NET["web"] else "off", "text": text, "game": game, "phone": phone, "voice": vs}


# --------------------------------------------------------------------------
# Celular: app web + adb reverse
# --------------------------------------------------------------------------
from web_static import serve_static, web_build  # noqa: E402

SERVE_KW = dict(process_request=serve_static, ping_interval=5, ping_timeout=10, max_size=4 * 2**20, max_queue=64)


async def web_main():
    host, port = WEB["host"], int(os.environ.get("COMPANION_WEB_PORT", WEB["port"]))
    while True:
        try:
            async with serve(web_handler, host, port, **SERVE_KW) as server:
                NET["web"] = True
                for name, url in phone_links().items():
                    log.info("celular (%s): %s", name, url.split("#")[0])
                await server.serve_forever()
        except OSError as e:
            NET["web"] = False
            log.warning("app do celular: não consegui escutar em %s:%s: %s", host, port, e)
            await asyncio.sleep(10)


async def https_main():
    """O mesmo app com HTTPS numa segunda porta (certificado do Tailscale ou cert/key do config)."""
    if not HTTPS.enabled:
        return
    while not await asyncio.to_thread(HTTPS.refresh):
        await asyncio.sleep(600)   # Tailscale desligado/sem HTTPS: tenta de novo daqui a pouco
    asyncio.create_task(https_renew())
    while True:
        try:
            async with serve(web_handler, WEB["host"], HTTPS.port, ssl=HTTPS.ctx, **SERVE_KW) as server:
                NET["https"] = True
                log.info("celular (https): %s", https_url())
                await server.serve_forever()
        except OSError as e:
            NET["https"] = False
            log.warning("HTTPS: não consegui escutar na porta %s: %s", HTTPS.port, e)
            await asyncio.sleep(10)


async def https_renew():
    while True:
        await asyncio.sleep(3600)
        if HTTPS.due():
            await asyncio.to_thread(HTTPS.refresh)


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
    asyncio.create_task(talk_loop())
    asyncio.create_task(conq_loop())
    asyncio.create_task(daily_loop())
    asyncio.create_task(focus_loop())
    asyncio.create_task(steam_loop())
    stratz_import_file()
    asyncio.create_task(dota_report_resume())
    asyncio.create_task(GSI.serve())
    asyncio.create_task(adb_loop())
    asyncio.create_task(downloads_loop())
    asyncio.create_task(web_watch())
    loop = asyncio.get_running_loop()
    UPD.on_change = lambda st: asyncio.run_coroutine_threadsafe(broadcast({"t": "update", "d": st}), loop)
    updater.run_detached_check(UPD)
    asyncio.create_task(asyncio.to_thread(START_APPS.get))  # já deixa a lista do Menu Iniciar pronta para a voz
    VOICE.start(asyncio.get_running_loop())
    BOARD.start(asyncio.get_running_loop())
    asyncio.create_task(https_main())
    await web_main()


def stop_server():
    release_modifiers()
    SCREEN.flush()
    talk_flush(force=True)


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
                 voice_set=VOICE.set, updater=UPD).run()


if __name__ == "__main__":
    try:
        if "--console" in sys.argv:
            asyncio.run(main())
        else:
            run_with_tray()
    except KeyboardInterrupt:
        pass
