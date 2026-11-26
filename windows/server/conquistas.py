"""Conquistas, metas do dia, XP e nível: gamifica o uso do PC com o que já fica gravado.

O servidor entrega um "resumo do dia" (facts) montado de screentime.db, focus.json, matches.db e voz.db:
    {"scr": s de tela, "cats": {categoria: s}, "hrs": [s por hora, 24], "foc": min de foco,
     "talk": {"meet"|"game"|"other": s falando}, "m": [{"g", "w", "k", "d", "a", "lh", "dur", "hs", "mvp", "t"}]}
Os resumos ficam guardados em conquistas.db (os dias que passaram não mudam mais: o focus.json só guarda 60 dias).
Metas, XP, nível e sequência são recalculados desses resumos (sempre dão o mesmo resultado); só a data em que
cada conquista foi desbloqueada é gravada. summary() é o resumo que um ranking online usaria.
"""
import json
import logging
import random
import sqlite3
import threading
from datetime import date, timedelta

log = logging.getLogger("companion")

TIER_XP = {"bronze": 50, "prata": 150, "ouro": 400}
META_XP, ALL_METAS_XP = 50, 50
FOCUS_XP_MIN, FOCUS_XP_MAX = 2, 300      # 2 XP por minuto de foco, até 300 por dia
MATCH_XP, WIN_XP = 10, 20
BASE_DAYS = 14                           # as metas se ajustam à sua média desses dias
STREAK_METAS = 2                         # metas cumpridas para o dia contar na sequência
BACKFILL_DAYS = 180
H, M = 3600, 60


def level_of(xp):
    """Nível e a faixa de XP dele: o nível N começa em 50·N·(N−1) (100, 300, 600, 1000...)."""
    n = 1
    while 50 * (n + 1) * n <= xp:
        n += 1
    return n, 50 * n * (n - 1), 50 * (n + 1) * n


def _r(x, step):
    return int(round(x / step) * step)


def _social(f):
    c = f.get("cats") or {}
    return c.get("Social", 0) + c.get("Entretenimento", 0)


def _work(f):
    c = f.get("cats") or {}
    return c.get("Trabalho", 0) + c.get("Criação", 0)


def _games(f):
    return (f.get("cats") or {}).get("Jogos", 0)


def _kda(m):
    return ((m.get("k") or 0) + (m.get("a") or 0)) / max(1, m.get("d") or 0)


def _wins(f):
    return sum(1 for m in f.get("m") or [] if m.get("w") == 1)


def build_facts(report, focus_min, talk, matches):
    """Monta o resumo do dia. report: ScreenTime.report("day", dia); talk: {ctx: s};
    matches: [(fim em epoch, jogo, vitória 1/0/None, dados)] das partidas que acabaram no dia."""
    cats = {c["cat"]: c["secs"] for c in report.get("cats") or []}
    ms = []
    for ended, game, win, d in matches:
        ms.append({"g": game, "w": win, "t": int(ended), "k": d.get("k"), "d": d.get("d"), "a": d.get("a"),
                   "lh": d.get("lh"), "dur": d.get("dur"), "hs": d.get("hs_pct"), "mvp": d.get("mvp")})
    return {"scr": report.get("total", 0), "cats": cats, "hrs": report.get("hours") or [0] * 24,
            "foc": focus_min or 0, "talk": {k: round(v) for k, v in (talk or {}).items()}, "m": ms}


# ---------------------------------------------------------------- metas do dia
# (id, tipo, unidade, texto, valor(facts), alvo(média), vale?(média)). "min": chegar ao alvo; "max": não passar
# dele (só fica cumprida quando o dia acaba, e só se o PC foi usado ao menos 30 min).
METAS = [
    ("foco", "min", "min", "Foco: {t}", lambda f: f.get("foc", 0),
     lambda b: min(180, max(25, _r(b["foc"] * 1.2, 5))), lambda b: True),
    ("tela", "max", "dur", "Tela abaixo de {t}", lambda f: f.get("scr", 0),
     lambda b: max(H, _r(b["scr"] * 0.9, 15 * M)), lambda b: b["scr"] > 2 * H),
    ("social", "max", "dur", "Redes e vídeos: no máximo {t}", _social,
     lambda b: max(15 * M, _r(b["social"] * 0.8, 15 * M)), lambda b: b["social"] > 20 * M),
    ("trabalho", "min", "dur", "Trabalho: {t}", _work,
     lambda b: min(6 * H, max(30 * M, _r(b["work"] * 1.1, 15 * M))), lambda b: b["work"] > 30 * M),
    ("jogo", "max", "dur", "Jogar no máximo {t}", _games,
     lambda b: max(H, _r(b["games"] * 0.85, 15 * M)), lambda b: b["games"] > H),
    ("vitorias", "min", "n", "Vencer {t} partida(s)", _wins,
     lambda b: 2 if b["matches"] >= 2 else 1, lambda b: b["match_days"] > 0),
    ("kda", "min", "kda", "Uma partida com KDA {t}+", lambda f: max([_kda(m) for m in f.get("m") or []] or [0]),
     lambda b: 3, lambda b: b["match_days"] > 0),
]
METAS_DAY = 3


def baseline(days):
    """Médias dos dias anteriores em que o PC foi usado (lista de facts)."""
    used = [f for f in days if f.get("scr", 0) > 0] or [{}]
    n = len(used)
    avg = lambda fn: sum(fn(f) for f in used) / n  # noqa: E731
    return {"scr": avg(lambda f: f.get("scr", 0)), "foc": avg(lambda f: f.get("foc", 0)), "social": avg(_social),
            "work": avg(_work), "games": avg(_games), "matches": avg(lambda f: len(f.get("m") or [])),
            "match_days": sum(1 for f in days if f.get("m"))}


def pick_metas(day, base):
    """As metas do dia: sorteadas com a data como semente (o mesmo dia sempre tem as mesmas), foco sempre entra."""
    ok = [m for m in METAS if m[6](base)]
    rest = [m for m in ok if m[0] != "foco"]
    rng = random.Random(day)
    return [METAS[0]] + rng.sample(rest, min(METAS_DAY - 1, len(rest)))


def eval_metas(day, facts, base, final):
    out = []
    for mid, kind, unit, text, value, target, _ok in pick_metas(day, base):
        v, t = value(facts), target(base)
        if kind == "min":
            status = "done" if v >= t else "open"
        elif v > t:
            status = "failed"
        elif final:
            status = "done" if facts.get("scr", 0) >= 30 * M else "skip"
        else:
            status = "ok"           # até agora dentro; só vale quando o dia acaba
        out.append({"id": mid, "kind": kind, "unit": unit, "text": text, "value": round(v, 2), "target": t, "status": status})
    return out


def day_xp(facts, metas):
    done = sum(1 for m in metas if m["status"] == "done")
    ms = facts.get("m") or []
    xp = min(facts.get("foc", 0) * FOCUS_XP_MIN, FOCUS_XP_MAX) + MATCH_XP * len(ms) + WIN_XP * _wins(facts)
    xp += META_XP * done + (ALL_METAS_XP if metas and done == len(metas) == METAS_DAY else 0)
    return int(xp)


# ---------------------------------------------------------------- conquistas
# (id, nome, como ganhar, nível, valor(agregado), alvo)
CONQ = [
    ("foco1", "Primeiro foco", "Termine um foco", "bronze", lambda a: a["focus_total"], 1),
    ("foco3h", "Maratona de foco", "3 h de foco num dia", "prata", lambda a: a["focus_day"], 180),
    ("foco100", "Monge", "100 h de foco no total", "ouro", lambda a: a["focus_total"], 6000),
    ("meta1", "Primeira meta", "Cumpra uma meta do dia", "bronze", lambda a: a["metas"], 1),
    ("meta3", "Dia perfeito", "Cumpra as 3 metas de um dia", "bronze", lambda a: a["perfect"], 1),
    ("meta100", "Centenário", "100 metas cumpridas", "ouro", lambda a: a["metas"], 100),
    ("seq7", "Semana firme", "7 dias seguidos cumprindo 2 metas", "prata", lambda a: a["best_streak"], 7),
    ("seq30", "Hábito formado", "30 dias seguidos cumprindo 2 metas", "ouro", lambda a: a["best_streak"], 30),
    ("cedo", "Madrugador", "Usar o PC entre 5h e 7h", "bronze", lambda a: a["early"], 1),
    ("coruja", "Coruja", "Usar o PC entre 2h e 5h", "bronze", lambda a: a["owl"], 1),
    ("detox", "Detox", "Um dia com menos de 2 h de tela", "bronze", lambda a: a["detox"], 1),
    ("vit1", "Primeira vitória", "Vença uma partida de CS2 ou Dota 2", "bronze", lambda a: a["wins"], 1),
    ("vit5", "Embalado", "5 vitórias seguidas", "prata", lambda a: a["win_streak"], 5),
    ("vit10", "Imparável", "10 vitórias seguidas", "ouro", lambda a: a["win_streak"], 10),
    ("maratona", "Só mais uma", "10 partidas num dia", "prata", lambda a: a["matches_day"], 10),
    ("kda10", "Carregou o time", "KDA 10 ou mais numa partida", "prata", lambda a: a["kda"], 10),
    ("imortal", "Imortal", "Vencer uma partida sem morrer", "ouro", lambda a: a["deathless"], 1),
    ("farm", "Fazendeiro", "Dota 2: 8 last hits por minuto (partida de 15 min ou mais)", "prata", lambda a: a["lh_min"], 8),
    ("hs", "Mira de laser", "CS2: 60% de headshots com 10 abates ou mais", "prata", lambda a: a["hs"], 60),
    ("mvp", "Estrela", "CS2: 5 MVPs numa partida", "bronze", lambda a: a["mvp"], 5),
    ("fala", "Tagarela", "1 h falando num dia (mesa de som)", "bronze", lambda a: a["talk_day"], 60),
    ("nv10", "Veterano", "Chegue ao nível 10", "prata", lambda a: a["level"], 10),
    ("nv25", "Lenda", "Chegue ao nível 25", "ouro", lambda a: a["level"], 25),
]


def aggregate(days, today=None):
    """days: [(dia, facts, metas)] em ordem. O agregado de tudo para as conquistas (menos o nível).
    today: o dia que ainda não acabou (não conta para "Detox")."""
    a = dict.fromkeys(["focus_total", "focus_day", "metas", "perfect", "best_streak", "early", "owl", "detox", "wins",
                       "win_streak", "matches_day", "kda", "deathless", "lh_min", "hs", "mvp", "talk_day"], 0)
    streak, wins_row = 0, 0
    for i, (day, f, metas) in enumerate(days):
        done = sum(1 for m in metas if m["status"] == "done")
        a["focus_total"] += f.get("foc", 0)
        a["focus_day"] = max(a["focus_day"], f.get("foc", 0))
        a["metas"] += done
        a["perfect"] += done == len(metas) == METAS_DAY
        streak = streak + 1 if done >= STREAK_METAS else 0
        a["best_streak"] = max(a["best_streak"], streak)
        hrs = f.get("hrs") or [0] * 24
        a["early"] += hrs[5] + hrs[6] >= 10 * M
        a["owl"] += hrs[2] + hrs[3] + hrs[4] >= 15 * M
        # o 1º dia com dados costuma estar pela metade (o registro começou no meio dele)
        a["detox"] += i > 0 and day != today and 30 * M <= f.get("scr", 0) < 2 * H
        ms = f.get("m") or []
        a["matches_day"] = max(a["matches_day"], len(ms))
        a["talk_day"] = max(a["talk_day"], sum((f.get("talk") or {}).values()) / M)
        for m in sorted(ms, key=lambda m: m.get("t") or 0):
            if m.get("w") == 1:
                a["wins"] += 1
                wins_row += 1
                a["deathless"] += (m.get("d") or 0) == 0 and m.get("d") is not None
            elif m.get("w") == 0:
                wins_row = 0
            a["win_streak"] = max(a["win_streak"], wins_row)
            a["kda"] = max(a["kda"], _kda(m))
            if m.get("g") == "dota2" and (m.get("dur") or 0) >= 15 * M and m.get("lh") is not None:
                a["lh_min"] = max(a["lh_min"], m["lh"] / (m["dur"] / M))
            if m.get("g") == "cs2":
                if (m.get("k") or 0) >= 10 and m.get("hs") is not None:
                    a["hs"] = max(a["hs"], m["hs"])
                a["mvp"] = max(a["mvp"], m.get("mvp") or 0)
    return a


def current_streak(days, today):
    """Dias seguidos (até ontem, e hoje se já contar) com STREAK_METAS metas cumpridas."""
    by = {d: sum(1 for m in metas if m["status"] == "done") for d, _f, metas in days}
    n, d = 0, date.fromisoformat(today)
    if by.get(today, 0) < STREAK_METAS:
        d -= timedelta(days=1)          # hoje ainda dá tempo: não quebra
    while by.get(d.isoformat(), 0) >= STREAK_METAS:
        n += 1
        d -= timedelta(days=1)
    return n


class Conquistas:
    def __init__(self, path, facts_fn, first_day_fn=None):
        """facts_fn(dia) -> resumo do dia; first_day_fn() -> primeiro dia com algum dado ('AAAA-MM-DD' ou None)."""
        self.path = str(path)
        self.facts_fn = facts_fn
        self.first_day_fn = first_day_fn or (lambda: None)
        self.lock = threading.Lock()
        self._state = None
        self._calc = None
        with self._db() as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS days (day TEXT PRIMARY KEY, facts TEXT, final INT);
                CREATE TABLE IF NOT EXISTS unlocks (id TEXT PRIMARY KEY, day TEXT, retro INT);
                CREATE TABLE IF NOT EXISTS kv (k TEXT PRIMARY KEY, v TEXT);
            """)

    def _db(self):
        return sqlite3.connect(self.path, timeout=5)

    # ------------------------------------------------------------ resumos dos dias
    def _load_days(self, db, today):
        """Garante o resumo de cada dia desde o primeiro com dados (os passados ficam fixos) e devolve todos."""
        rows = {d: (json.loads(f), fin) for d, f, fin in db.execute("SELECT day, facts, final FROM days")}
        first = self.first_day_fn()
        t = date.fromisoformat(today)
        start = max(date.fromisoformat(first) if first else t, t - timedelta(days=BACKFILL_DAYS))
        if rows:
            start = min(start, date.fromisoformat(min(rows)))
        d = start
        while d <= t:
            k = d.isoformat()
            if k not in rows or not rows[k][1]:
                final = int(d < t)
                facts = self.facts_fn(k)
                db.execute("INSERT OR REPLACE INTO days VALUES (?, ?, ?)", (k, json.dumps(facts), final))
                rows[k] = (facts, final)
            d += timedelta(days=1)
        return [(k, rows[k][0], rows[k][1]) for k in sorted(rows)]

    # ------------------------------------------------------------ cálculo
    def refresh(self, today=None):
        """Recalcula tudo. Devolve (estado, eventos novos: conquistas, metas cumpridas, nível)."""
        today = today or date.today().isoformat()
        with self.lock, self._db() as db:
            raw = self._load_days(db, today)
            days, hist = [], []
            for k, f, final in raw:
                base = baseline([x[1] for x in raw if x[0] < k][-BASE_DAYS:])
                metas = eval_metas(k, f, base, bool(final))
                days.append((k, f, metas))
            xp_days = {k: day_xp(f, metas) for k, f, metas in days}
            agg = aggregate(days, today)
            unlocked = dict(db.execute("SELECT id, day FROM unlocks").fetchall())
            first_run = db.execute("SELECT v FROM kv WHERE k = 'init'").fetchone() is None
            new = []
            for _pass in range(2):          # o nível depende do XP das conquistas, e há conquistas de nível
                xp = sum(xp_days.values()) + sum(TIER_XP[c[3]] for c in CONQ if c[0] in unlocked)
                agg["level"] = level_of(xp)[0]
                for cid, name, _desc, tier, val, goal in CONQ:
                    if cid not in unlocked and val(agg) >= goal:
                        unlocked[cid] = today
                        db.execute("INSERT INTO unlocks VALUES (?, ?, ?)", (cid, today, int(first_run)))
                        if not first_run:
                            new.append({"kind": "conq", "id": cid, "name": name, "tier": tier, "xp": TIER_XP[tier]})
            if first_run:
                db.execute("INSERT INTO kv VALUES ('init', ?)", (today,))
            xp = sum(xp_days.values()) + sum(TIER_XP[c[3]] for c in CONQ if c[0] in unlocked)
            conq_xp_today = sum(TIER_XP[c[3]] for c in CONQ if unlocked.get(c[0]) == today)
        lvl, lo, hi = level_of(xp)
        today_metas = days[-1][2] if days else []
        week0 = (date.fromisoformat(today) - timedelta(days=date.fromisoformat(today).weekday())).isoformat()
        st = {
            "level": lvl, "xp": xp, "lvl_lo": lo, "lvl_hi": hi,
            "today_xp": xp_days.get(today, 0) + conq_xp_today,
            "week_xp": sum(v for k, v in xp_days.items() if k >= week0) + sum(
                TIER_XP[c[3]] for c in CONQ if (unlocked.get(c[0]) or "") >= week0),
            "streak": current_streak(days, today), "best_streak": agg["best_streak"],
            "metas": today_metas,
            "conq": [{"id": cid, "name": name, "desc": desc, "tier": tier, "xp": TIER_XP[tier], "day": unlocked.get(cid),
                      "cur": round(min(val(agg), goal), 1), "goal": goal} for cid, name, desc, tier, val, goal in CONQ],
        }
        ev = self._events(st, new)
        self._state = st
        self._calc = {"days": [(k, f, metas, xp_days[k]) for k, f, metas in days], "unlocked": dict(unlocked)}
        return st, ev

    def _events(self, st, new):
        prev = self._state
        ev = list(new)
        if prev is None:
            return ev
        was = {m["id"] for m in prev["metas"] if m["status"] == "done"}
        for m in st["metas"]:
            if m["status"] == "done" and m["id"] not in was and m["kind"] == "min":
                ev.append({"kind": "meta", "id": m["id"], "text": m["text"], "target": m["target"], "unit": m["unit"], "xp": META_XP})
        if st["level"] > prev["level"]:
            ev.append({"kind": "level", "level": st["level"]})
        return ev

    def state(self):
        return self._state

    def month_data(self, month):
        """Para a retrospectiva: (dias do mês [(dia, facts, metas, xp)], XP antes do mês,
        conquistas do mês [{id, name, tier, xp, day}], dias com dados de todos os meses)."""
        if self._calc is None:
            self.refresh()
        days, unlocked = self._calc["days"], self._calc["unlocked"]
        start = month + "-01"
        inside = [x for x in days if x[0][:7] == month]
        conq = {c[0]: c for c in CONQ}
        xp_before = sum(x[3] for x in days if x[0] < start) + sum(TIER_XP[conq[c][3]] for c, d in unlocked.items()
                                                                  if c in conq and d < start)
        got = [{"id": c, "name": conq[c][1], "tier": conq[c][3], "xp": TIER_XP[conq[c][3]], "day": d}
               for c, d in sorted(unlocked.items(), key=lambda x: x[1]) if c in conq and d[:7] == month]
        return inside, xp_before, got, [x[0] for x in days]

    def flag(self, key, value=None):
        """Marcador simples guardado no banco (ex.: retrospectiva já avisada). Sem value: lê."""
        with self.lock, self._db() as db:
            if value is None:
                row = db.execute("SELECT v FROM kv WHERE k = ?", (key,)).fetchone()
                return row[0] if row else None
            db.execute("INSERT OR REPLACE INTO kv VALUES (?, ?)", (key, str(value)))
            return value

    def summary(self):
        """O que um ranking online receberia (sem nada de tempo de tela ou apps)."""
        st = self._state or {}
        y, w, _d = date.today().isocalendar()
        return {k: st.get(k) for k in ("level", "xp", "week_xp", "streak", "best_streak")} | {
            "unlocked": sum(1 for c in st.get("conq") or [] if c["day"]), "week": f"{y}-W{w:02d}"}   # semana ISO local
