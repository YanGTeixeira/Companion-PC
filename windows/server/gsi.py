"""Game State Integration (recurso oficial da Valve) para CS2 e Dota 2.

O jogo lê um .cfg na pasta dele e manda o estado da partida por HTTP POST para
http://127.0.0.1:<porta>/ com um token. Aqui: instala os .cfg, recebe os POSTs e
resume o estado em um dicionário pequeno para o celular.

Dota 2 só manda se tiver a opção de inicialização -gamestateintegration na Steam.
"""
import asyncio
import json
import logging
import os
import time

log = logging.getLogger("companion")

CFG_NAME = "gamestate_integration_companionpc.cfg"
GAMES = {
    "730": ("cs2", os.path.join("game", "csgo", "cfg")),
    "570": ("dota2", os.path.join("game", "dota", "cfg", "gamestate_integration")),
}
DATA = {
    "cs2": ["provider", "map", "round", "player_id", "player_state", "player_weapons", "player_match_stats",
            "phase_countdowns", "map_round_wins"],
    "dota2": ["provider", "map", "player", "hero", "abilities", "items", "buildings", "events", "roshan", "neutralitems"],
}
STALE_S = 30  # sem POST há mais que isso: dados velhos (jogo fechado ou no menu)


def cfg_text(game, port, token):
    data = "\n".join(f'    "{k}" "1"' for k in DATA[game])
    return f'''"Companion PC"
{{
  "uri" "http://127.0.0.1:{port}/"
  "timeout" "5.0"
  "buffer" "0.1"
  "throttle" "0.5"
  "heartbeat" "10.0"
  "auth"
  {{
    "token" "{token}"
  }}
  "data"
  {{
{data}
  }}
}}
'''


def install(roots, port, token):
    """roots: [(pasta_do_jogo, info)] do catálogo. Escreve o .cfg de CS2/Dota 2 se faltar ou mudou."""
    done = []
    for path, info in roots:
        hit = GAMES.get(str(info.get("appid") or ""))
        if not hit:
            continue
        game, sub = hit
        folder = os.path.join(path, sub)
        if not os.path.isdir(os.path.dirname(folder)):
            continue
        try:
            os.makedirs(folder, exist_ok=True)
            f = os.path.join(folder, CFG_NAME)
            text = cfg_text(game, port, token)
            old = open(f, encoding="utf-8").read() if os.path.exists(f) else None
            if old != text:
                with open(f, "w", encoding="utf-8") as fh:
                    fh.write(text)
                log.info("GSI: configuração instalada para %s (%s)", info.get("name"), f)
            done.append(game)
        except OSError as e:
            log.warning("GSI: não consegui instalar em %s: %s", folder, e)
    return done


# --------------------------------------------------------------------------
# Resumo do estado
# --------------------------------------------------------------------------
def _pretty(name, prefix):
    n = (name or "").removeprefix(prefix).replace("_", " ").strip()
    return n.title() if n else ""


CS_WEAPONS = {"ak47": "AK-47", "m4a1": "M4A4", "m4a1_silencer": "M4A1-S", "awp": "AWP", "deagle": "Desert Eagle",
              "usp_silencer": "USP-S", "hkp2000": "P2000", "glock": "Glock-18", "p250": "P250", "fiveseven": "Five-SeveN",
              "tec9": "Tec-9", "cz75a": "CZ75-Auto", "revolver": "R8", "elite": "Dual Berettas", "mac10": "MAC-10",
              "mp9": "MP9", "mp7": "MP7", "mp5sd": "MP5-SD", "ump45": "UMP-45", "p90": "P90", "bizon": "PP-Bizon",
              "galilar": "Galil AR", "famas": "FAMAS", "sg556": "SG 553", "aug": "AUG", "ssg08": "SSG 08",
              "scar20": "SCAR-20", "g3sg1": "G3SG1", "nova": "Nova", "xm1014": "XM1014", "mag7": "MAG-7",
              "sawedoff": "Sawed-Off", "m249": "M249", "negev": "Negev", "taser": "Zeus", "c4": "C4",
              "hegrenade": "HE", "flashbang": "Flash", "smokegrenade": "Smoke", "molotov": "Molotov",
              "incgrenade": "Incendiária", "decoy": "Decoy"}


def summarize_cs2(d):
    me = (d.get("provider") or {}).get("steamid")
    p = d.get("player") or {}
    mp, rd = d.get("map") or {}, d.get("round") or {}
    st, ms = p.get("state") or {}, p.get("match_stats") or {}
    spectating = bool(me and p.get("steamid") and p.get("steamid") != me)
    weapon = None
    for w in (p.get("weapons") or {}).values():
        if w.get("state") == "active":
            raw = (w.get("name") or "").removeprefix("weapon_")
            nm = "Faca" if raw.startswith(("knife", "bayonet")) else CS_WEAPONS.get(raw) or _pretty(raw, "")
            weapon = {"name": nm, "clip": w.get("ammo_clip"), "max": w.get("ammo_clip_max"),
                      "reserve": w.get("ammo_reserve"), "type": w.get("type")}
    team = p.get("team")
    ct, t = (mp.get("team_ct") or {}).get("score"), (mp.get("team_t") or {}).get("score")
    return {
        "g": "cs2", "map": _pretty(mp.get("name"), "de_") or mp.get("name"), "mode": mp.get("mode"), "phase": mp.get("phase"),
        "round": (mp.get("round") or 0) + (1 if rd.get("phase") in ("live", "freezetime") else 0),
        "rphase": rd.get("phase"), "bomb": rd.get("bomb"), "win": rd.get("win_team"),
        "ct": ct, "t": t, "team": team, "menu": p.get("activity") == "menu" or not mp,
        "spectating": spectating, "name": p.get("name"),
        "hp": st.get("health"), "armor": st.get("armor"), "helmet": st.get("helmet"), "money": st.get("money"),
        "flashed": st.get("flashed"), "rk": st.get("round_kills"), "rhs": st.get("round_killhs"),
        "k": ms.get("kills"), "d": ms.get("deaths"), "a": ms.get("assists"), "mvp": ms.get("mvps"), "score": ms.get("score"),
        "weapon": weapon, "equip": st.get("equip_value"), "dmg": st.get("round_totaldmg"),
        "losses": ((mp.get("team_ct") if team == "CT" else mp.get("team_t")) or {}).get("consecutive_round_losses"),
        "cd": _countdown(d.get("phase_countdowns")),
    }


def _countdown(pc):
    """Contagem da fase (bomba plantada, desarmando, compra...) em segundos."""
    if not isinstance(pc, dict) or pc.get("phase_ends_in") is None:
        return None
    try:
        return {"phase": pc.get("phase"), "ends": round(float(pc["phase_ends_in"]), 1)}
    except (TypeError, ValueError):
        return None


DOTA_STATES = {
    "DOTA_GAMERULES_STATE_HERO_SELECTION": "Escolha de heróis", "DOTA_GAMERULES_STATE_STRATEGY_TIME": "Estratégia",
    "DOTA_GAMERULES_STATE_PRE_GAME": "Pré-jogo", "DOTA_GAMERULES_STATE_GAME_IN_PROGRESS": "Em jogo",
    "DOTA_GAMERULES_STATE_POST_GAME": "Fim de jogo", "DOTA_GAMERULES_STATE_WAIT_FOR_PLAYERS_TO_LOAD": "Carregando",
    "DOTA_GAMERULES_STATE_TEAM_SHOWCASE": "Apresentação", "DOTA_GAMERULES_STATE_WAIT_FOR_MAP_TO_LOAD": "Carregando",
}


def summarize_dota(d):
    mp, pl, he = d.get("map") or {}, d.get("player") or {}, d.get("hero") or {}
    items = []
    for slot in [f"slot{i}" for i in range(6)] + ["neutral0"]:
        it = (d.get("items") or {}).get(slot) or {}
        if it.get("name") and it["name"] != "empty":
            items.append({"name": _pretty(it["name"], "item_"), "cd": it.get("cooldown") or 0, "charges": it.get("charges"),
                          "slot": slot})
    abil = []
    for k, a in sorted((d.get("abilities") or {}).items()):
        if a.get("name") and not a["name"].startswith(("generic_hidden", "plus_")) and a.get("level", 0) >= 0:
            abil.append({"name": _pretty(a["name"], _hero_prefix(he.get("name"))), "lvl": a.get("level"), "cd": a.get("cooldown") or 0,
                         "ult": bool(a.get("ultimate")), "ready": bool(a.get("can_cast"))})
    return {
        "g": "dota2", "state": DOTA_STATES.get(mp.get("game_state"), mp.get("game_state")), "raw_state": mp.get("game_state"),
        "clock": mp.get("clock_time"), "day": mp.get("daytime"), "paused": mp.get("paused"), "win": mp.get("win_team"),
        "rad": mp.get("radiant_score"), "dire": mp.get("dire_score"), "team": pl.get("team_name"),
        "menu": not mp, "hero": _pretty(he.get("name"), "npc_dota_hero_"), "hero_id": he.get("id") or None, "level": he.get("level"),
        "alive": he.get("alive"), "respawn": he.get("respawn_seconds"), "hp": he.get("health"), "hpmax": he.get("max_health"),
        "mana": he.get("mana"), "manamax": he.get("max_mana"), "buyback": he.get("buyback_cost"), "bbcd": he.get("buyback_cooldown"),
        "k": pl.get("kills"), "d": pl.get("deaths"), "a": pl.get("assists"), "lh": pl.get("last_hits"), "dn": pl.get("denies"),
        "gold": pl.get("gold"), "gpm": pl.get("gpm"), "xpm": pl.get("xpm"), "streak": pl.get("kill_streak"),
        "items": items, "abilities": abil[:6],
    }


def _hero_prefix(hero):
    h = (hero or "").removeprefix("npc_dota_hero_")
    return h + "_" if h else ""


# --------------------------------------------------------------------------
# Servidor HTTP mínimo (o servidor de WebSocket não aceita POST)
# --------------------------------------------------------------------------
class GSI:
    def __init__(self, port, token, on_update, trackers=None):
        self.port, self.token, self.on_update = port, token, on_update
        self.trackers = trackers or {}   # jogo -> objeto com feed(raw, resumo) (matches.py)
        self.state = {}       # jogo -> resumo
        self.seen = {}        # jogo -> time.time() do último POST
        self.running = False

    def refresh(self, game):
        """Recalcula o resumo depois de uma marcação manual (ex.: Roshan) e manda de novo."""
        tr, s = self.trackers.get(game), self.state.get(game)
        if tr and s:
            self.state[game] = tr.decorate(dict(s))
            self.on_update(game, self.state[game])

    def current(self, game=None):
        """Resumo mais recente (do jogo pedido, ou o último a mandar algo), se não estiver velho."""
        now = time.time()
        live = {g: s for g, s in self.state.items() if now - self.seen.get(g, 0) < STALE_S}
        if game:
            return live.get(game)
        if not live:
            return None
        return live[max(live, key=lambda g: self.seen[g])]

    async def _handle(self, reader, writer):
        try:
            head = await asyncio.wait_for(reader.readuntil(b"\r\n\r\n"), 5)
            lines = head.decode("latin-1").split("\r\n")
            method = lines[0].split(" ")[0]
            length = 0
            for ln in lines[1:]:
                if ln.lower().startswith("content-length:"):
                    length = int(ln.split(":", 1)[1].strip() or 0)
            body = await asyncio.wait_for(reader.readexactly(length), 5) if 0 < length < 2_000_000 else b""
            writer.write(b"HTTP/1.1 200 OK\r\nContent-Length: 0\r\nConnection: close\r\n\r\n")
            await writer.drain()
            if method == "POST" and body:
                self._ingest(json.loads(body))
        except (asyncio.TimeoutError, asyncio.IncompleteReadError, ValueError, ConnectionError):
            pass
        finally:
            writer.close()

    def _ingest(self, d):
        if (d.get("auth") or {}).get("token") != self.token:
            return
        app = str((d.get("provider") or {}).get("appid") or "")
        game = GAMES.get(app, (None,))[0]
        if not game:
            return
        s = summarize_cs2(d) if game == "cs2" else summarize_dota(d)
        tr = self.trackers.get(game)
        if tr:
            try:
                s = tr.feed(d, s)
            except Exception:  # noqa: BLE001  (o resumo básico continua chegando)
                log.exception("GSI: falha ao acompanhar a partida de %s", game)
        changed = s != self.state.get(game)
        self.state[game], self.seen[game] = s, time.time()
        if changed:
            self.on_update(game, s)

    async def serve(self):
        try:
            srv = await asyncio.start_server(self._handle, "127.0.0.1", self.port)
        except OSError as e:
            log.warning("GSI: porta %s indisponível: %s", self.port, e)
            return
        self.running = True
        log.info("GSI (CS2/Dota 2) em http://127.0.0.1:%s/", self.port)
        async with srv:
            await srv.serve_forever()
