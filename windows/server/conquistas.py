"""Conquistas, metas do dia, XP e nível: gamifica o uso do PC com o que já fica gravado.

O servidor entrega um "resumo do dia" (facts) montado de screentime.db, focus.json, matches.db e voz.db:
    {"scr": s de tela, "cats": {categoria: s}, "hrs": [s por hora, 24], "foc": min de foco,
     "talk": {"meet"|"game"|"other": s falando}, "m": [{"g", "w", "k", "d", "a", "lh", "dur", "hs", "mvp", "t"}]}
Os resumos ficam guardados em conquistas.db (os dias que passaram não mudam mais: o focus.json só guarda 60 dias).
Metas, XP, nível e sequência são recalculados desses resumos (sempre dão o mesmo resultado); só a data em que
cada conquista foi desbloqueada é gravada. summary() é o resumo que o ranking online recebe.

1.18: desafios e chefão da semana, congelamento de sequência, multiplicador pela sequência, dia de XP em dobro,
recompensas por nível/conquista (título, moldura, som, tema) e conquistas secretas. Essas regras valem do dia em que
a 1.18 rodou pela 1ª vez (kv "rules2") em diante; o XP dos dias anteriores fica como era.
"""
import json
import logging
import random
import sqlite3
import threading
import time
from datetime import date, timedelta

import colecao

log = logging.getLogger("companion")

TIER_XP = {"bronze": 50, "prata": 150, "ouro": 400}
META_XP, ALL_METAS_XP = 50, 50
FOCUS_XP_MIN, FOCUS_XP_MAX = 2, 300      # 2 XP por minuto de foco, até 300 por dia
MATCH_XP, WIN_XP = 10, 20
BASE_DAYS = 14                           # as metas se ajustam à sua média desses dias
STREAK_METAS = 2                         # metas cumpridas para o dia contar na sequência
BACKFILL_DAYS = 180
H, M = 3600, 60


level_of = colecao.level_of   # 1.21: curva 17·N·(N−1), até o nível 30 (o resto é prestígio)


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




def _done(metas):
    return sum(1 for m in metas if m["status"] == "done")


# ---------------------------------------------------------------- sequência, congelamento e multiplicador (1.18)
# As regras da 1.18 valem do dia em que ela rodou pela 1ª vez ("since"): o XP do passado não muda (o ranking
# recusaria um salto grande). A cada FREEZE_EVERY dias seguidos ganha um congelamento (guarda até FREEZE_MAX);
# um dia perdido gasta um e a sequência continua.
FREEZE_EVERY, FREEZE_MAX = 7, 2
MULT = [(30, 1.5), (14, 1.35), (7, 1.2), (3, 1.1)]     # sequência no começo do dia -> multiplicador do XP do dia
X2_ODDS = 7                                          # ~1 dia em 7 é de XP em dobro


def streak_mult(streak):
    return next((m for n, m in MULT if streak >= n), 1.0)


def is_x2(day):
    """Dia de XP em dobro: sorteado pela data (o mesmo dia sempre dá o mesmo)."""
    return random.Random("x2:" + day).randrange(X2_ODDS) == 0


def streak_sim(days, today, since):
    """days: [(dia, facts, metas)] em ordem, um por data. Devolve um dict com: per {dia: (sequência no começo do
    dia, congelado?)}, streak (atual), freezes, best, used (congelamentos gastos), phoenix, run (dias para o próximo)."""
    per, streak, freezes, run, best, used, phoenix, broke7 = {}, 0, 0, 0, 0, 0, 0, False
    for k, _f, metas in days:
        before, frozen = streak, False
        if _done(metas) >= STREAK_METAS:
            streak += 1
            if k >= since:
                run += 1
                if run % FREEZE_EVERY == 0 and freezes < FREEZE_MAX:
                    freezes += 1
            if broke7 and streak >= 7:
                phoenix = 1
        elif k == today:
            pass                         # hoje ainda dá tempo: não quebra
        elif k >= since and freezes and streak:
            freezes -= 1
            used += 1
            frozen = True
        else:
            broke7 = broke7 or streak >= 7
            streak, run = 0, 0
        best = max(best, streak)
        per[k] = (before, frozen)
    return {"per": per, "streak": streak, "freezes": freezes, "best": best, "used": used, "phoenix": phoenix,
            "next": None if freezes >= FREEZE_MAX else FREEZE_EVERY - run % FREEZE_EVERY}


# ---------------------------------------------------------------- desafios e chefão da semana (1.18)
QUEST_XP, ALL_QUESTS_XP, BOSS_XP = 150, 100, 300
QUESTS_WEEK = 3
BASE_WEEK_DAYS = 28


def _light_days(w, b, today):
    return sum(1 for k, f, _m in w if k < today and 30 * M <= f.get("scr", 0) < b["scr"])


# (id, texto, unidade, valor(dias da semana, média, hoje), alvo(média), vale?(média))
QUESTS = [
    ("foco", "Foco na semana: {t}", "min", lambda w, b, t: sum(f.get("foc", 0) for _k, f, _m in w),
     lambda b: min(900, max(120, _r(b["foc"] * 7 * 1.15, 15))), lambda b: True),
    ("dias", "{t} dias com 2 metas cumpridas", "n", lambda w, b, t: sum(1 for *_x, m in w if _done(m) >= STREAK_METAS),
     lambda b: 5, lambda b: True),
    ("perfeito", "{t} dias perfeitos (as 3 metas)", "n", lambda w, b, t: sum(1 for *_x, m in w if _done(m) == METAS_DAY),
     lambda b: 2, lambda b: True),
    ("vitorias", "Vencer {t} partidas", "n", lambda w, b, t: sum(_wins(f) for _k, f, _m in w),
     lambda b: max(3, min(15, round(b["wins"] * 7 * 1.1))), lambda b: b["match_days"] > 0),
    ("leve", "{t} dias com menos tela que a sua média", "n", _light_days, lambda b: 4, lambda b: b["scr"] > 2 * H),
    ("trabalho", "Trabalho na semana: {t}", "dur", lambda w, b, t: sum(_work(f) for _k, f, _m in w),
     lambda b: min(30 * H, max(2 * H, _r(b["work"] * 5 * 1.1, 30 * M))), lambda b: b["work"] > 30 * M),
]
BOSSES = [("Procrastinador", "🦥"), ("Dragão da Distração", "🐉"), ("Hidra das Abas", "🐍"),
          ("Kraken das Notificações", "🐙"), ("Golem da Preguiça", "🗿"), ("Fantasma do Prazo", "👻"),
          ("Lich do Scroll Infinito", "💀"), ("Ogro da Segunda-feira", "👹")]
BOSS_META, BOSS_WIN = 15, 20      # dano: 1 por minuto de foco, 15 por meta, 20 por vitória


def monday(day):
    d = date.fromisoformat(day)
    return (d - timedelta(days=d.weekday())).isoformat()


def week_id(day):
    y, w, _d = date.fromisoformat(day).isocalendar()
    return f"{y}-W{w:02d}"


def boss_dmg(f, metas):
    return f.get("foc", 0) + BOSS_META * _done(metas) + BOSS_WIN * _wins(f)


def week_base(prev):
    """Média dos dias antes da semana (prev: [(dia, facts, metas)])."""
    b = baseline([f for _k, f, _m in prev])
    used = [m for _k, f, m in prev if f.get("scr", 0) > 0] or [[]]
    used_f = [f for _k, f, _m in prev if f.get("scr", 0) > 0] or [{}]
    b["metas"] = sum(_done(m) for m in used) / len(used)
    b["wins"] = sum(_wins(f) for f in used_f) / len(used_f)
    return b


def eval_week(mon, wdays, prev, today):
    """Desafios e chefão de uma semana. wdays: [(dia, facts, metas)] da semana até hoje; prev: dias antes dela."""
    base = week_base(prev[-BASE_WEEK_DAYS:])
    ok = [q for q in QUESTS if q[5](base)]
    rest = [q for q in ok if q[0] != "foco"]
    picks = [QUESTS[0]] + random.Random("w:" + mon).sample(rest, min(QUESTS_WEEK - 1, len(rest)))
    sunday = (date.fromisoformat(mon) + timedelta(days=6)).isoformat()
    ended = sunday < today
    quests, xp = [], {}
    for qid, text, unit, value, target, _ok in picks:
        t = target(base)
        done_day = next((wdays[i][0] for i in range(len(wdays)) if value(wdays[: i + 1], base, today) >= t), None)
        quests.append({"id": qid, "text": text, "unit": unit, "value": round(value(wdays, base, today), 2), "target": t,
                       "status": "done" if done_day else "failed" if ended else "open", "day": done_day, "xp": QUEST_XP})
        if done_day:
            xp[done_day] = xp.get(done_day, 0) + QUEST_XP
    if len(quests) == QUESTS_WEEK and all(q["day"] for q in quests):
        last = max(q["day"] for q in quests)
        xp[last] = xp.get(last, 0) + ALL_QUESTS_XP
    daily = base["foc"] + BOSS_META * base["metas"] + BOSS_WIN * base["wins"]
    hp = min(1500, max(200, _r(daily * 7 * 1.2, 10)))
    name, icon = BOSSES[random.Random("b:" + mon).randrange(len(BOSSES))]
    dmg, dead = 0, None
    for k, f, metas in wdays:
        dmg += boss_dmg(f, metas)
        if dead is None and dmg >= hp:
            dead = k
    if dead:
        xp[dead] = xp.get(dead, 0) + BOSS_XP
    boss = {"name": name, "icon": icon, "hp": hp, "dmg": round(dmg), "dead": dead, "xp": BOSS_XP, "escaped": ended and not dead,
            "today": round(sum(boss_dmg(f, m) for k, f, m in wdays if k == today))}
    return {"id": week_id(mon), "start": mon, "end": sunday, "quests": quests, "boss": boss, "xp": xp,
            "all": len(quests) == QUESTS_WEEK and all(q["day"] for q in quests)}


# ---------------------------------------------------------------- conquistas
# (id, nome, como ganhar, nível, valor(agregado), alvo[, secreta])
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
    # 1.18: desafios, chefões, séries e secretas
    ("des1", "Desafiante I", "Complete um desafio da semana", "bronze", lambda a: a["quests"], 1),
    ("des10", "Desafiante II", "Complete 10 desafios da semana", "prata", lambda a: a["quests"], 10),
    ("des50", "Desafiante III", "Complete 50 desafios da semana", "ouro", lambda a: a["quests"], 50),
    ("boss1", "Caçador I", "Derrote um chefão da semana", "bronze", lambda a: a["bosses"], 1),
    ("boss5", "Caçador II", "Derrote 5 chefões da semana", "prata", lambda a: a["bosses"], 5),
    ("boss20", "Caçador III", "Derrote 20 chefões da semana", "ouro", lambda a: a["bosses"], 20),
    ("semana", "Semana impecável", "Os 3 desafios e o chefão na mesma semana", "prata", lambda a: a["full_weeks"], 1),
    ("part50", "Rodado I", "Jogue 50 partidas de CS2 ou Dota 2", "bronze", lambda a: a["matches"], 50),
    ("part250", "Rodado II", "Jogue 250 partidas", "prata", lambda a: a["matches"], 250),
    ("part1000", "Rodado III", "Jogue 1000 partidas", "ouro", lambda a: a["matches"], 1000),
    ("voz10", "Locutor", "10 h falando no total (mesa de som)", "prata", lambda a: a["talk_total"], 600),
    ("fds", "Fim de semana produtivo", "2 h de foco no sábado e no domingo", "prata", lambda a: a["weekend"], 1),
    ("col25", "Colecionador", "Ganhe 25 conquistas", "prata", lambda a: a["unlocked"], 25),
    ("nv50", "Mito", "Chegue ao nível 30", "ouro", lambda a: a["level"], 30),
    ("duelo1", "Duelista", "Vença um duelo da semana no ranking", "bronze", lambda a: a["duels_won"], 1),
    ("x2", "Dobradinha", "Cumpra as 3 metas num dia de XP em dobro", "bronze", lambda a: a["x2_perfect"], 1, True),
    ("gelo", "Sangue frio", "Salve a sequência com um congelamento", "bronze", lambda a: a["freezes_used"], 1, True),
    ("fenix", "Fênix", "Perca uma sequência de 7+ dias e faça outra de 7", "prata", lambda a: a["phoenix"], 1, True),
    ("silencio", "Voto de silêncio", "Um dia com 4 h+ de PC sem redes sociais nem vídeos", "prata", lambda a: a["silent"], 1, True),
    # 1.21: prestígio
    ("prest1", "Recomeço", "Faça o seu primeiro prestígio", "ouro", lambda a: a["prestige"], 1),
    ("prest5", "Cinco estrelas", "Chegue ao prestígio 5", "ouro", lambda a: a["prestige"], 5),
    ("pmestre", "Mestre do Prestígio", "Chegue ao Mestre (depois do prestígio 10)", "ouro", lambda a: a["prestige"], 11),
    ("meianoite", "Meia-noite", "Vença uma partida entre meia-noite e 4h", "bronze", lambda a: a["midnight"], 1, True),
]
CONQ_VER = 3     # sobe quando entram conquistas novas: as que o histórico já merecia entram sem aviso


def aggregate(days, today=None):
    """days: [(dia, facts, metas)] em ordem. O agregado de tudo para as conquistas (menos o nível).
    today: o dia que ainda não acabou (não conta para "Detox")."""
    a = dict.fromkeys(["focus_total", "focus_day", "metas", "perfect", "best_streak", "early", "owl", "detox", "wins",
                       "win_streak", "matches_day", "kda", "deathless", "lh_min", "hs", "mvp", "talk_day", "matches",
                       "talk_total", "silent", "midnight", "weekend"], 0)
    streak, wins_row, wk_foc = 0, 0, {}
    for i, (day, f, metas) in enumerate(days):
        done = _done(metas)
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
        a["silent"] += day != today and f.get("scr", 0) >= 4 * H and bool(f.get("cats")) and _social(f) == 0
        try:
            wd = date.fromisoformat(day).weekday()
        except ValueError:
            wd = -1
        if wd >= 5 and f.get("foc", 0) >= 120:
            wk_foc.setdefault(monday(day), set()).add(wd)
        ms = f.get("m") or []
        a["matches"] += len(ms)
        a["matches_day"] = max(a["matches_day"], len(ms))
        talk = sum((f.get("talk") or {}).values()) / M
        a["talk_day"] = max(a["talk_day"], talk)
        a["talk_total"] += talk
        for m in sorted(ms, key=lambda m: m.get("t") or 0):
            if m.get("w") == 1:
                a["wins"] += 1
                wins_row += 1
                a["deathless"] += (m.get("d") or 0) == 0 and m.get("d") is not None
                a["midnight"] += bool(m.get("t")) and time.localtime(m["t"]).tm_hour < 4
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
    a["weekend"] = sum(1 for s in wk_foc.values() if len(s) == 2)
    return a


def current_streak(days, today):
    """Dias seguidos (até ontem, e hoje se já contar) com STREAK_METAS metas cumpridas (sem congelamentos)."""
    by = {d: _done(metas) for d, _f, metas in days}
    n, d = 0, date.fromisoformat(today)
    if by.get(today, 0) < STREAK_METAS:
        d -= timedelta(days=1)          # hoje ainda dá tempo: não quebra
    while by.get(d.isoformat(), 0) >= STREAK_METAS:
        n += 1
        d -= timedelta(days=1)
    return n


# ---------------------------------------------------------------- recompensas (1.18) e coleção (1.19)
# O catálogo, os créditos, a loja e os eventos ficam em colecao.py.
EQUIP_DEFAULT = colecao.EQUIP_DEFAULT


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

    @staticmethod
    def _kv(db, key, default=None):
        row = db.execute("SELECT v FROM kv WHERE k = ?", (key,)).fetchone()
        return row[0] if row else default

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
        """Recalcula tudo. Devolve (estado, eventos novos: conquistas, metas, desafios, chefão, nível, recompensas)."""
        today = today or date.today().isoformat()
        with self.lock, self._db() as db:
            raw = self._load_days(db, today)
            since = self._kv(db, "rules2")
            if since is None:
                since = today
                db.execute("INSERT INTO kv VALUES ('rules2', ?)", (since,))
            days = []
            for k, f, final in raw:
                base = baseline([x[1] for x in raw if x[0] < k][-BASE_DAYS:])
                days.append((k, f, eval_metas(k, f, base, bool(final))))
            sim = streak_sim(days, today, since)
            xp_days, bonus = {}, {}
            for k, f, metas in days:
                base_xp = day_xp(f, metas)
                if k >= since:
                    mult = streak_mult(sim["per"][k][0]) * (2 if is_x2(k) else 1)
                    xp_days[k] = int(round(base_xp * mult))
                    bonus[k] = (base_xp, mult)
                else:
                    xp_days[k] = base_xp
            # semanas (desde a da 1.18)
            weeks, mon = [], monday(since)
            while mon <= today:
                end = (date.fromisoformat(mon) + timedelta(days=6)).isoformat()
                wd = [x for x in days if mon <= x[0] <= end]
                weeks.append(eval_week(mon, wd, [x for x in days if x[0] < mon], today))
                mon = (date.fromisoformat(mon) + timedelta(days=7)).isoformat()
            for w in weeks:
                for k, v in w["xp"].items():
                    xp_days[k] = xp_days.get(k, 0) + v
            agg = aggregate(days, today)
            agg["best_streak"] = max(agg["best_streak"], sim["best"])
            agg.update(quests=sum(1 for w in weeks for q in w["quests"] if q["day"]),
                       bosses=sum(1 for w in weeks if w["boss"]["dead"]),
                       full_weeks=sum(1 for w in weeks if w["all"] and w["boss"]["dead"]),
                       freezes_used=sim["used"], phoenix=sim["phoenix"],
                       x2_perfect=sum(1 for k, _f, m in days if k >= since and is_x2(k) and _done(m) == METAS_DAY),
                       duels_won=len(json.loads(self._kv(db, "duels_won", "[]"))))
            unlocked = dict(db.execute("SELECT id, day FROM unlocks").fetchall())
            pres = json.loads(self._kv(db, "prestige", "[]"))        # 1.21: [{n, xp (o total na hora), extra, day}]
            prest = len(pres)
            base = pres[-1]["xp"] if pres else 0
            agg["prestige"] = prest
            first_run = self._kv(db, "init") is None
            silent = first_run or self._kv(db, "conq_ver") != str(CONQ_VER)
            new = []
            for _pass in range(3):          # o nível depende do XP das conquistas, e há conquistas de nível e de coleção
                xp = sum(xp_days.values()) + sum(TIER_XP[c[3]] for c in CONQ if c[0] in unlocked)
                agg["level"] = colecao.LEVEL_MAX if prest else level_of(max(0, xp - base))[0]
                agg["unlocked"] = sum(1 for c in CONQ if c[0] in unlocked)
                for c in CONQ:
                    cid, name, _desc, tier, val, goal = c[:6]
                    if cid not in unlocked and val(agg) >= goal:
                        unlocked[cid] = today
                        db.execute("INSERT INTO unlocks VALUES (?, ?, ?)", (cid, today, int(silent)))
                        if not silent:
                            new.append({"kind": "conq", "id": cid, "name": name, "tier": tier, "xp": TIER_XP[tier]})
            if first_run:
                db.execute("INSERT INTO kv VALUES ('init', ?)", (today,))
            if silent:
                db.execute("INSERT OR REPLACE INTO kv VALUES ('conq_ver', ?)", (str(CONQ_VER),))
            # 1.19: eventos sazonais (só a partir do dia em que a 1.19 rodou), compras e créditos
            since3 = self._kv(db, "rules3")
            if since3 is None:
                since3 = today
                db.execute("INSERT INTO kv VALUES ('rules3', ?)", (since3,))
            ev_done, event = colecao.events_eval(days, weeks, today, since3)
            for eid, d in ev_done.items():
                if "ev_" + eid not in unlocked:
                    unlocked["ev_" + eid] = d
                    db.execute("INSERT OR REPLACE INTO unlocks VALUES (?, ?, 0)", ("ev_" + eid, d))
                    new.append({"kind": "event", "id": eid, "name": next(e[1] for e in colecao.EVENTS if e[0] == eid),
                                "credits": colecao.CR_EVENT})
            events_done = {k[3:]: d for k, d in unlocked.items() if k.startswith("ev_")}
            bought = json.loads(self._kv(db, "bought", "[]"))
            xp = sum(xp_days.values()) + sum(TIER_XP[c[3]] for c in CONQ if c[0] in unlocked)
            conq_xp_today = sum(TIER_XP[c[3]] for c in CONQ if unlocked.get(c[0]) == today)
            equip = {**EQUIP_DEFAULT, **json.loads(self._kv(db, "equip", "{}"))}
        rel = max(0, xp - base)
        lvl, lo, hi = level_of(rel)
        lo, hi = lo + base, hi + base
        extra = (rel - colecao.XP_MAX_LEVEL) // colecao.EXTRA_XP if lvl == colecao.LEVEL_MAX else 0
        levels = (lvl - 1) + extra + sum(colecao.LEVEL_MAX - 1 + int(e.get("extra") or 0) for e in pres)
        conq_days = [(unlocked[c[0]], c[3]) for c in CONQ if c[0] in unlocked]
        owned = {b["id"] for b in bought}
        got = colecao.got_ids(lvl, unlocked, owned, prest)
        # 1.20: conjuntos completos (o dia fica gravado: os créditos não mudam se um item sair da coleção depois)
        new_sets = [sid for sid in colecao.sets_complete(got) if "set_" + sid not in unlocked]
        if new_sets:
            with self.lock, self._db() as db:
                for sid in new_sets:
                    unlocked["set_" + sid] = today
                    db.execute("INSERT OR REPLACE INTO unlocks VALUES (?, ?, 0)", ("set_" + sid, today))
            for sid in new_sets:
                st_ = next(x for x in colecao.SETS if x[0] == sid)
                new.append({"kind": "set", "id": sid, "name": st_[1], "icon": st_[2], "credits": colecao.set_credits(sid),
                            "reward": colecao.BY_ID[colecao.SET_REWARD[sid]][2]})
            got = colecao.got_ids(lvl, unlocked, owned, prest)
        sets_done = {k[4:]: d for k, d in unlocked.items() if k.startswith("set_")}
        cr_days = colecao.credits_by_day(days, weeks, sim["per"], conq_days, levels, events_done, sets_done)
        earned, spent = sum(cr_days.values()), sum(int(b.get("price") or 0) for b in bought)
        equip = self._fix_equip(equip, got, unlocked, lvl, prest)
        today_metas = days[-1][2] if days else []
        week0 = monday(today)
        base_xp, mult = bonus.get(today, (0, 1.0))
        cur_week = weeks[-1] if weeks else None
        shop = colecao.shop_pick(week_id(today), {b["id"] for b in bought if b.get("day", "") < week0}, prest)
        st = {
            "day": today, "level": lvl, "xp": xp, "lvl_lo": lo, "lvl_hi": hi,
            "today_xp": xp_days.get(today, 0) + conq_xp_today,
            "week_xp": sum(v for k, v in xp_days.items() if k >= week0) + sum(
                TIER_XP[c[3]] for c in CONQ if (unlocked.get(c[0]) or "") >= week0),
            "streak": sim["streak"], "best_streak": agg["best_streak"],
            "freezes": sim["freezes"], "freeze_max": FREEZE_MAX, "freeze_next": sim["next"],
            "frozen": sorted(k for k, (_b, fr) in sim["per"].items() if fr)[-5:],
            "mult": streak_mult(sim["per"][today][0] if today in sim["per"] else sim["streak"]),
            "x2": is_x2(today), "since": since,
            "x2_next": next((d for d in ((date.fromisoformat(today) + timedelta(days=i)).isoformat() for i in range(1, 15))
                             if is_x2(d)), None),
            "metas": today_metas,
            "week": cur_week and {k: cur_week[k] for k in ("id", "start", "end", "quests", "boss", "all")} | {
                "quest_xp": QUEST_XP, "all_xp": ALL_QUESTS_XP},
            "weeks_won": {"quests": agg["quests"], "bosses": agg["bosses"]},
            "conq": [self._conq_view(c, agg, unlocked) for c in CONQ],
            "rewards": [self._item_view(it, got, unlocked, owned) for it in colecao.ITEMS],
            "equip": equip,
            "show_max": colecao.show_max(lvl, prest),
            "show_next": None if prest else next((lv for lv, _n in reversed(colecao.SHOW_SLOTS) if lv > lvl), None),
            "level_max": colecao.LEVEL_MAX, "prestige": prest, "prestige_label": colecao.prestige_label(prest),
            "prestige_max": colecao.PRESTIGE_MAX,
            "can_prestige": lvl == colecao.LEVEL_MAX and prest < colecao.PRESTIGE_MAX,
            "prestige_next": [i[0] for i in colecao.ITEMS if i[4] == f"p:{prest + 1}"],
            "prestiges": [{"n": e["n"], "day": e.get("day")} for e in pres],
            "extra": {"xp": (rel - colecao.XP_MAX_LEVEL) % colecao.EXTRA_XP, "per": colecao.EXTRA_XP, "levels": extra}
            if lvl == colecao.LEVEL_MAX else None,
            "credits": {"bal": earned - spent, "earned": earned, "spent": spent, "today": cr_days.get(today, 0),
                        "week": sum(v for k, v in cr_days.items() if k >= week0),
                        "rules": {"meta": colecao.CR_META, "metas3": colecao.CR_ALL_METAS, "quest": colecao.CR_QUEST,
                                  "boss": colecao.CR_BOSS, "level": colecao.CR_LEVEL, "extra_xp": colecao.EXTRA_XP, "streak7": colecao.CR_STREAK7,
                                  "conq": colecao.CR_CONQ, "event": colecao.CR_EVENT, "set": colecao.CR_SET}},
            "shop": {"week": week_id(today), "end": (date.fromisoformat(week0) + timedelta(days=6)).isoformat(), "items": shop},
            "event": event,
            "events": [{"id": e[0], "name": e[1], "icon": e[2], "text": e[6], "done": e[0] in events_done} for e in colecao.EVENTS],
            "bought": [b["id"] for b in bought],
            "sets": [{"id": sid, "name": name, "icon": icon, "items": items, "have": sum(1 for i in items if i in got),
                      "done": sets_done.get(sid), "reward": colecao.SET_REWARD[sid], "credits": colecao.set_credits(sid)}
                     for sid, name, icon, items in colecao.SETS],
        }
        st["today_bonus"] = {"base": base_xp, "mult": mult}
        ev = self._events(st, new, weeks)
        self._state = st
        self._calc = {"days": [(k, f, metas, xp_days[k]) for k, f, metas in days], "unlocked": dict(unlocked),
                      "credits": cr_days, "bought": bought, "pxp": base,
                      "bosses": [w["boss"]["dead"] for w in weeks if w["boss"]["dead"]],
                      "quests": [q["day"] for w in weeks for q in w["quests"] if q["day"]]}
        return st, ev

    @staticmethod
    def _conq_view(c, agg, unlocked):
        cid, name, desc, tier, val, goal = c[:6]
        secret = len(c) > 6 and c[6]
        day = unlocked.get(cid)
        if secret and not day:
            return {"id": cid, "name": "???", "desc": "Conquista secreta. Continue jogando para descobrir.", "tier": tier,
                    "xp": TIER_XP[tier], "day": None, "cur": 0, "goal": 1, "secret": True}
        return {"id": cid, "name": name, "desc": desc, "tier": tier, "xp": TIER_XP[tier], "day": day,
                "cur": round(min(val(agg), goal), 1), "goal": goal, "secret": bool(secret)}

    @staticmethod
    def _item_view(it, got, unlocked, owned):
        rid, kind, name, rarity, req = it
        conq = None
        shop_p = colecao.shop_req(it)
        if isinstance(req, str) and shop_p is None and not req.startswith(("ev:", "set:", "p:")):
            conq = next((c[1] if c[0] in unlocked or not (len(c) > 6 and c[6]) else "???") for c in CONQ if c[0] == req)
        return {"id": rid, "kind": kind, "name": name, "rarity": rarity, "got": rid in got,
                "req": req if isinstance(req, int) else None, "conq": conq,
                "shop": shop_p is not None, "price": colecao.PRICE[rarity] if shop_p is not None else None,
                "shop_p": shop_p or None,
                "prestige": int(req[2:]) if isinstance(req, str) and req.startswith("p:") else None,
                "event": req[3:] if isinstance(req, str) and req.startswith("ev:") else None,
                "set": req[4:] if isinstance(req, str) and req.startswith("set:") else None,
                "anim": rid in colecao.ANIMATED}

    @staticmethod
    def _fix_equip(equip, got, unlocked, level=1, prestige=0):
        """O que está equipado continua valendo? (ex.: conquista perdida num banco apagado) Senão volta ao padrão."""
        out = dict(equip)
        for kind in colecao.EQUIP_KINDS:
            it = colecao.BY_ID.get(out.get(kind))
            if not it or it[1] != kind or out[kind] not in got:
                out[kind] = EQUIP_DEFAULT[kind]
        out["color"] = colecao.clean_color(out.get("color")) or EQUIP_DEFAULT["color"]
        out["bio"] = colecao.clean_bio(out.get("bio"))
        lay = out.get("lay")
        out["lay"] = colecao.clean_lay(lay) if isinstance(lay, list) else list(EQUIP_DEFAULT["lay"])
        out["show"] = [c for c in (out.get("show") or []) if c in unlocked and not c.startswith(("ev_", "set_"))][:colecao.show_max(level, prestige)]
        return out

    def _events(self, st, new, weeks):
        prev = self._state
        ev = list(new)
        if prev is None:
            return ev
        was = {m["id"] for m in prev["metas"] if m["status"] == "done"}
        for m in st["metas"]:
            if m["status"] == "done" and m["id"] not in was and m["kind"] == "min":
                ev.append({"kind": "meta", "id": m["id"], "text": m["text"], "target": m["target"], "unit": m["unit"], "xp": META_XP})
        pw, w = prev.get("week") or {}, st.get("week") or {}
        if w and pw.get("id") == w["id"]:
            pdone = {q["id"] for q in pw.get("quests") or [] if q["day"]}
            for q in w["quests"]:
                if q["day"] and q["id"] not in pdone:
                    ev.append({"kind": "quest", "id": q["id"], "text": q["text"], "target": q["target"], "unit": q["unit"], "xp": QUEST_XP})
            if w["all"] and not pw.get("all"):
                ev.append({"kind": "quests_all", "xp": ALL_QUESTS_XP})
            if w["boss"]["dead"] and not pw["boss"]["dead"]:
                ev.append({"kind": "boss", "name": w["boss"]["name"], "icon": w["boss"]["icon"], "xp": BOSS_XP})
        if st["prestige"] > prev.get("prestige", 0):
            ev.append({"kind": "prestige", "n": st["prestige"], "label": st["prestige_label"]})
        elif st["level"] > prev["level"]:
            ev.append({"kind": "level", "level": st["level"]})
        pgot = {r["id"] for r in prev["rewards"] if r["got"]}
        for r in st["rewards"]:
            if r["got"] and r["id"] not in pgot and not (r["shop"] or r["set"] or r["prestige"]):   # já teve aviso próprio
                ev.append({"kind": "reward", "id": r["id"], "type": r["kind"], "name": r["name"]})
        if prev["day"] != st["day"]:
            if st["x2"]:
                ev.append({"kind": "x2"})
            if st["frozen"] and st["frozen"][-1] not in prev["frozen"]:
                ev.append({"kind": "freeze", "day": st["frozen"][-1], "left": st["freezes"]})
        return ev

    def state(self):
        return self._state

    # ------------------------------------------------------------ equipar, vitrine, perfil e loja
    def _save_equip(self, **changes):
        with self.lock, self._db() as db:
            eq = {**EQUIP_DEFAULT, **json.loads(self._kv(db, "equip", "{}")), **changes}
            db.execute("INSERT OR REPLACE INTO kv VALUES ('equip', ?)", (json.dumps(eq),))
        self._state["equip"] = {**self._state["equip"], **changes}
        return self._state

    def equip(self, kind, rid):
        st = self._state or self.refresh()[0]
        if kind == "show":
            ids = [str(x) for x in (rid or [])]
            if len(ids) > st["show_max"]:
                raise ValueError(f"a vitrine tem {st['show_max']} lugares no seu nível")
            have = {c["id"] for c in st["conq"] if c["day"]}
            if any(i not in have for i in ids):
                raise ValueError("só dá para mostrar conquistas que você já ganhou")
            return self._save_equip(show=list(dict.fromkeys(ids)))
        r = next((r for r in st["rewards"] if r["id"] == rid and r["kind"] == kind), None)
        if kind not in colecao.EQUIP_KINDS or not r:
            raise ValueError("recompensa inválida")
        if not r["got"]:
            raise ValueError("ainda bloqueada")
        return self._save_equip(**{kind: rid})

    def set_profile(self, p):
        """Frase, ordem dos blocos do perfil e a cor livre (essa só com a recompensa)."""
        st = self._state or self.refresh()[0]
        ch = {}
        if "bio" in p:
            ch["bio"] = colecao.clean_bio(p["bio"])
        if "lay" in p:
            if not isinstance(p["lay"], list):
                raise ValueError("layout inválido")
            ch["lay"] = colecao.clean_lay(p["lay"])
        if "color" in p:
            c = colecao.clean_color(p["color"])
            if not c:
                raise ValueError("cor inválida (use #rrggbb)")
            if not next(r["got"] for r in st["rewards"] if r["id"] == "a_livre"):
                raise ValueError("a cor livre ainda está bloqueada")
            ch["color"] = c
        return self._save_equip(**ch) if ch else st

    def buy(self, rid, today=None):
        """Compra um item da loja da semana com créditos."""
        st = self._state or self.refresh(today)[0]
        r = next((r for r in st["rewards"] if r["id"] == rid), None)
        if not r or not r["shop"]:
            raise ValueError("esse item não é da loja")
        if r["got"]:
            raise ValueError("esse item já é seu")
        if rid not in st["shop"]["items"]:
            raise ValueError("esse item não está na loja desta semana")
        if st["credits"]["bal"] < r["price"]:
            raise ValueError(f"faltam {r['price'] - st['credits']['bal']} créditos")
        with self.lock, self._db() as db:
            bought = json.loads(self._kv(db, "bought", "[]"))
            if any(b["id"] == rid for b in bought):
                raise ValueError("esse item já é seu")
            bought.append({"id": rid, "price": r["price"], "day": today or date.today().isoformat()})
            db.execute("INSERT OR REPLACE INTO kv VALUES ('bought', ?)", (json.dumps(bought),))
        return self.refresh(today)

    def prestige(self, today=None):
        """Prestigiar (1.21): no nível 30, o nível volta a 1 e tudo o que já foi liberado fica."""
        st = self.refresh(today)[0]
        if not st["can_prestige"]:
            raise ValueError("o Mestre é o último prestígio" if st["prestige"] >= colecao.PRESTIGE_MAX
                             else f"chegue ao nível {colecao.LEVEL_MAX} para prestigiar")
        with self.lock, self._db() as db:
            pres = json.loads(self._kv(db, "prestige", "[]"))
            pres.append({"n": len(pres) + 1, "xp": st["xp"], "extra": (st["extra"] or {}).get("levels", 0),
                         "day": today or date.today().isoformat()})
            db.execute("INSERT OR REPLACE INTO kv VALUES ('prestige', ?)", (json.dumps(pres),))
        return self.refresh(today)

    def set_duels_won(self, ids):
        """Duelos vencidos no ranking (ids): guarda a união; conta para a conquista Duelista."""
        with self.lock, self._db() as db:
            have = set(json.loads(self._kv(db, "duels_won", "[]")))
            new = have | {str(i) for i in ids}
            if new != have:
                db.execute("INSERT OR REPLACE INTO kv VALUES ('duels_won', ?)", (json.dumps(sorted(new)),))
            return len(new) > len(have)

    def month_data(self, month):
        """Para a retrospectiva: (dias do mês [(dia, facts, metas, xp)], XP antes do mês,
        conquistas do mês [{id, name, tier, xp, day}], dias com dados de todos os meses)."""
        return self.range_data(month + "-01", month + "-31")

    def range_data(self, a, b):
        """O mesmo que month_data, para um período qualquer (dias "AAAA-MM-DD", inclusive)."""
        if self._calc is None:
            self.refresh()
        days, unlocked = self._calc["days"], self._calc["unlocked"]
        inside = [x for x in days if a <= x[0] <= b]
        conq = {c[0]: c for c in CONQ}
        xp_before = sum(x[3] for x in days if x[0] < a) + sum(TIER_XP[conq[c][3]] for c, d in unlocked.items()
                                                              if c in conq and d < a)
        got = [{"id": c, "name": conq[c][1], "tier": conq[c][3], "xp": TIER_XP[conq[c][3]], "day": d}
               for c, d in sorted(unlocked.items(), key=lambda x: x[1]) if c in conq and a <= d <= b]
        return inside, xp_before, got, [x[0] for x in days]

    def collection_data(self, a, b):
        """Para a retrospectiva do ano: créditos, chefões, desafios, conjuntos, eventos e compras do período,
        e a coleção de hoje (itens liberados)."""
        if self._calc is None:
            self.refresh()
        c, st = self._calc, self._state
        inn = lambda d: bool(d) and a <= d <= b  # noqa: E731
        sets = [s for s in colecao.SETS if inn(c["unlocked"].get("set_" + s[0]))]
        events = [e for e in colecao.EVENTS if inn(c["unlocked"].get("ev_" + e[0]))]
        return {"credits": sum(v for k, v in c["credits"].items() if inn(k)),
                "bosses": sum(1 for d in c["bosses"] if inn(d)), "quests": sum(1 for d in c["quests"] if inn(d)),
                "sets": [{"name": s[1], "icon": s[2]} for s in sets], "events": [{"name": e[1], "icon": e[2]} for e in events],
                "bought": sum(1 for x in c["bought"] if inn(x.get("day"))),
                "items": sum(1 for r in st["rewards"] if r["got"]), "items_total": len(st["rewards"]),
                "level": st["level"], "best_streak": st["best_streak"]}

    def flag(self, key, value=None):
        """Marcador simples guardado no banco (ex.: retrospectiva já avisada). Sem value: lê."""
        with self.lock, self._db() as db:
            if value is None:
                return self._kv(db, key)
            db.execute("INSERT OR REPLACE INTO kv VALUES (?, ?)", (key, str(value)))
            return value

    def summary(self):
        """O que o ranking online recebe (sem nada de tempo de tela ou apps)."""
        st = self._state or {}
        y, w, _d = date.today().isocalendar()
        eq = st.get("equip") or EQUIP_DEFAULT
        pf = {k: eq.get(k) for k in ("bg", "avatar", "effect", "accent", "bio", "lay")}
        if eq.get("accent") == "a_livre":
            pf["color"] = eq.get("color")
        return {k: st.get(k) for k in ("level", "xp", "week_xp", "streak", "best_streak")} | {
            "unlocked": sum(1 for c in st.get("conq") or [] if c["day"]), "week": f"{y}-W{w:02d}",   # semana ISO local
            "title": eq["title"], "frame": eq["frame"], "show": list(eq["show"]), "profile": pf,
            "prestige": st.get("prestige", 0), "pxp": (self._calc or {}).get("pxp", 0)}   # 1.21: o ranking confere
