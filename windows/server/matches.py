"""Acompanha as partidas de CS2 e Dota 2 (pelos dados do GSI) e guarda o histórico.

CS2: cada round fechado (map.round_wins) vira uma linha com quem ganhou, como, e os seus abates,
headshots e dano naquele round. Quando você morre o GSI passa a mandar o jogador que você está
assistindo, então os seus números vêm do último estado em que o jogador era você.

Dota 2: guarda uma amostra por minuto (ouro, GPM, XPM, last hits, nível) para os gráficos,
os eventos (Roshan, Aegis) e as marcações feitas pelo celular.

Partidas terminadas vão para matches.db (SQLite).
"""
import json
import logging
import sqlite3
import threading
import time

log = logging.getLogger("companion")

CS_REASON = {"elimination": "E", "bomb": "B", "defuse": "D", "time": "T", "hostage": "R", "surrender": "S"}


# --------------------------------------------------------------------------
# Banco
# --------------------------------------------------------------------------
class Store:
    def __init__(self, path):
        self.lock = threading.Lock()
        self.db = sqlite3.connect(str(path), check_same_thread=False)
        self.db.execute("""CREATE TABLE IF NOT EXISTS matches (
            id INTEGER PRIMARY KEY, game TEXT, key TEXT UNIQUE, ended REAL, title TEXT, win INTEGER, data TEXT)""")
        self.db.commit()

    def add(self, game, key, title, win, data):
        with self.lock:
            self.db.execute("INSERT OR REPLACE INTO matches (game, key, ended, title, win, data) VALUES (?,?,?,?,?,?)",
                            (game, key, time.time(), title, None if win is None else int(bool(win)),
                             json.dumps(data, ensure_ascii=False)))
            self.db.commit()
        log.info("partida salva: %s %s (%s)", game, title, {True: "vitória", False: "derrota", None: "empate"}[win])

    def report(self, game, limit=15):
        with self.lock:
            rows = self.db.execute("SELECT ended, title, win, data FROM matches WHERE game=? ORDER BY ended DESC LIMIT 500",
                                   (game,)).fetchall()
        recent, by = [], {}
        for ended, title, win, data in rows:
            d = json.loads(data)
            d.update(ended=ended, title=title, win=None if win is None else bool(win))
            if len(recent) < limit:
                recent.append(d)
            g = by.setdefault(title, {"name": title, "n": 0, "wins": 0, "k": 0, "d": 0, "a": 0, "x": 0.0, "xn": 0, "y": 0.0, "yn": 0})
            g["n"] += 1
            g["wins"] += 1 if win else 0
            for f in ("k", "d", "a"):
                g[f] += d.get(f) or 0
            # x/y: CS = HS% e ADR; Dota = GPM e XPM
            x, y = (d.get("hs_pct"), d.get("adr")) if game == "cs2" else (d.get("gpm"), d.get("xpm"))
            if x is not None:
                g["x"] += x; g["xn"] += 1
            if y is not None:
                g["y"] += y; g["yn"] += 1
        groups = []
        for g in sorted(by.values(), key=lambda g: -g["n"]):
            n = g["n"]
            groups.append({"name": g["name"], "n": n, "winrate": round(100 * g["wins"] / n),
                           "k": round(g["k"] / n, 1), "d": round(g["d"] / n, 1), "a": round(g["a"] / n, 1),
                           "x": round(g["x"] / g["xn"]) if g["xn"] else None, "y": round(g["y"] / g["yn"]) if g["yn"] else None})
        total = len(rows)
        wins = sum(1 for r in rows if r[2])
        return {"game": game, "recent": recent, "groups": groups[:12], "total": total,
                "winrate": round(100 * wins / total) if total else None}


# --------------------------------------------------------------------------
# CS2
# --------------------------------------------------------------------------
def _winner(reason):
    r = str(reason or "")
    return "CT" if r.startswith("ct_") else "T" if r.startswith("t_") else None


def _reason(reason):
    r = str(reason or "")
    for k, v in CS_REASON.items():
        if r.endswith(k):
            return v
    return "?"


class CsTracker:
    def __init__(self, store):
        self.store = store
        self._reset(None)

    def _reset(self, key):
        self.key, self.started = key, time.time()
        self.rounds = {}        # n -> {n, win, side, r, k, hs, dmg}
        self.mine = None        # último estado em que o jogador era você
        self.saved = False
        self.last_rn = 0

    def feed(self, d, s):
        mp, p = d.get("map") or {}, d.get("player") or {}
        me = (d.get("provider") or {}).get("steamid")
        if not mp:
            return self.decorate(s)
        key = f'{mp.get("name")}|{mp.get("mode")}'
        rn = int(mp.get("round") or 0)
        if key != self.key or rn < self.last_rn or (mp.get("phase") == "warmup" and self.rounds):
            self._reset(key)
            first = True
        else:
            first = False
        self.last_rn = rn
        if p.get("steamid") and p.get("steamid") == me:
            self.mine = {"team": p.get("team"), "state": dict(p.get("state") or {}), "ms": dict(p.get("match_stats") or {}),
                         "weapon": s.get("weapon")}
        wins = mp.get("round_wins") or {}
        for k in sorted(wins, key=lambda x: int(x) if str(x).isdigit() else 0):
            if not str(k).isdigit():
                continue
            n = int(k)
            if n in self.rounds:
                continue
            side = _winner(wins[k])
            entry = {"n": n, "side": side, "r": _reason(wins[k]), "win": None, "k": None, "hs": None, "dmg": None}
            # rounds que já tinham acabado quando o app começou a acompanhar ficam sem os seus números
            if not first and self.mine:
                st = self.mine["state"]
                entry.update(win=side == self.mine["team"] if side else None,
                             k=st.get("round_kills"), hs=st.get("round_killhs"), dmg=st.get("round_totaldmg"))
            self.rounds[n] = entry
        if mp.get("phase") == "gameover" and not self.saved and self.rounds:
            self.saved = True
            self._save(mp, s)
        return self.decorate(s)

    def _stats(self):
        played = [r for r in self.rounds.values() if r["dmg"] is not None]
        kills = sum(r["k"] or 0 for r in played)
        hs = sum(r["hs"] or 0 for r in played)
        return {"hs_pct": round(100 * hs / kills) if kills else None,
                "adr": round(sum(r["dmg"] or 0 for r in played) / len(played)) if played else None}

    def decorate(self, s):
        if self.mine and s.get("spectating"):
            # morto: o GSI manda quem você assiste; os seus números vêm do último estado seu
            ms, st = self.mine["ms"], self.mine["state"]
            s.update(k=ms.get("kills"), d=ms.get("deaths"), a=ms.get("assists"), mvp=ms.get("mvps"), score=ms.get("score"),
                     money=st.get("money"), equip=st.get("equip_value"), dmg=st.get("round_totaldmg"), team=self.mine["team"])
        s["rounds"] = [self.rounds[n] for n in sorted(self.rounds)]
        s.update(self._stats())
        return s

    def _save(self, mp, s):
        team = (self.mine or {}).get("team") or s.get("team")
        ct, t = (mp.get("team_ct") or {}).get("score") or 0, (mp.get("team_t") or {}).get("score") or 0
        mine, theirs = (ct, t) if team == "CT" else (t, ct)
        ms = (self.mine or {}).get("ms") or {}
        data = {"map": s.get("map"), "mode": mp.get("mode"), "mine": mine, "theirs": theirs, "team": team,
                "k": ms.get("kills"), "d": ms.get("deaths"), "a": ms.get("assists"), "mvp": ms.get("mvps"), "score": ms.get("score"),
                "rounds": len(self.rounds), "dur": round(time.time() - self.started), **self._stats()}
        win = None if mine == theirs else mine > theirs
        self.store.add("cs2", f"cs2:{int(self.started)}", s.get("map") or mp.get("name") or "?", win, data)


# --------------------------------------------------------------------------
# Dota 2
# --------------------------------------------------------------------------
class DotaTracker:
    def __init__(self, store):
        self.store = store
        self.events_seen = set()   # tipos de evento já registrados no log (para aprender os nomes)
        self._reset(None)

    def _reset(self, mid):
        self.mid = mid
        self.samples = {}       # minuto -> amostra
        self.marks = {}         # "rosh"/"aegis"/"torm" -> relógio da partida em que aconteceu
        self.ev_done = set()
        self.saved = False
        self.clock = None

    def mark(self, what, clear=False):
        if what not in ("rosh", "torm", "aegis"):
            raise ValueError("marcação inválida")
        if clear:
            self.marks.pop(what, None)
        elif self.clock is not None:
            self.marks[what] = self.clock
            if what == "rosh":
                self.marks["aegis"] = self.clock

    def feed(self, d, s):
        mp, pl, he = d.get("map") or {}, d.get("player") or {}, d.get("hero") or {}
        mid = str(mp.get("matchid") or "")
        if not mid or mid == "0":
            return self.decorate(s)
        if mid != self.mid:
            self._reset(mid)
        clock = mp.get("clock_time")
        self.clock = clock
        if s.get("raw_state") == "DOTA_GAMERULES_STATE_GAME_IN_PROGRESS" and isinstance(clock, int) and clock >= 0:
            minute = clock // 60
            if minute not in self.samples:
                self.samples[minute] = {"m": minute, "gold": pl.get("gold"), "gpm": pl.get("gpm"), "xpm": pl.get("xpm"),
                                        "lh": pl.get("last_hits"), "dn": pl.get("denies"), "lvl": he.get("level")}
        evs = d.get("events")
        for ev in evs if isinstance(evs, list) else []:
            et, gt = str(ev.get("event_type") or ""), ev.get("game_time")
            if et and et not in self.events_seen:
                self.events_seen.add(et)
                log.info("Dota GSI: evento '%s' %s", et, json.dumps(ev, ensure_ascii=False)[:200])
            k = (et, gt)
            if k in self.ev_done:
                continue
            self.ev_done.add(k)
            # game_time conta desde antes do relógio zerar; converte para o relógio da partida
            at = clock - (mp.get("game_time", 0) - gt) if isinstance(gt, (int, float)) and isinstance(clock, int) else clock
            if "roshan" in et and ("kill" in et or "death" in et):
                self.marks["rosh"] = self.marks["aegis"] = int(at)
            elif "aegis" in et and "pick" in et:
                self.marks["aegis"] = int(at)
        if not self.saved and (mp.get("win_team") not in (None, "none", "") or s.get("raw_state") == "DOTA_GAMERULES_STATE_POST_GAME"):
            self.saved = True
            self._save(mp, pl, he, s)
        return self.decorate(s)

    def decorate(self, s):
        s["series"] = [self.samples[m] for m in sorted(self.samples)]
        s["marks"] = dict(self.marks)
        return s

    def _save(self, mp, pl, he, s):
        win_team, team = mp.get("win_team"), pl.get("team_name")
        win = None if win_team in (None, "none", "") or not team else win_team == team
        data = {"hero": s.get("hero"), "k": pl.get("kills"), "d": pl.get("deaths"), "a": pl.get("assists"),
                "lh": pl.get("last_hits"), "dn": pl.get("denies"), "gpm": pl.get("gpm"), "xpm": pl.get("xpm"),
                "lvl": he.get("level"), "dur": mp.get("clock_time"), "team": team,
                "items": [it["name"] for it in s.get("items") or [] if it.get("slot", "").startswith("slot")]}
        self.store.add("dota2", f"dota2:{self.mid}", s.get("hero") or "?", win, data)
