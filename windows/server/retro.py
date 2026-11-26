"""Retrospectiva do mês (estilo "Wrapped"): o mês em números, com uma "personalidade" no fim.

Junta os resumos diários de conquistas.db (tela por hora, foco, metas, XP, voz, partidas), o tempo por app do
mês (screentime) e os nomes das partidas (herói do Dota / mapa do CS2, de matches.db). O celular mostra como
"stories" e gera o cartão para compartilhar; aqui só sai o dicionário com os números.
"""
from datetime import date, timedelta

from conquistas import _kda, level_of

MONTHS = ["janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho", "agosto", "setembro", "outubro",
          "novembro", "dezembro"]
WEEKDAYS = ["segunda", "terça", "quarta", "quinta", "sexta", "sábado", "domingo"]
H, M = 3600, 60


def month_bounds(month):
    first = date.fromisoformat(month + "-01")
    nxt = (first + timedelta(days=32)).replace(day=1)
    return first, nxt - timedelta(days=1)


def prev_month(month):
    first, _ = month_bounds(month)
    return (first - timedelta(days=1)).isoformat()[:7]


def persona(hours, cats, total, focus_min, matches):
    """Um rótulo divertido para o mês, com o porquê. A primeira regra que bate vence."""
    if not total:
        return {"name": "Fantasma", "why": "o PC quase não foi ligado"}
    share = lambda keys: sum(cats.get(k, 0) for k in keys) / total  # noqa: E731
    night = (sum(hours[22:]) + sum(hours[:5])) / total
    early = sum(hours[5:8]) / total
    rules = [
        (night >= 0.25, "Coruja", f"{round(night * 100)}% do seu tempo foi entre 22h e 5h"),
        (share(["Jogos"]) >= 0.4, "Gamer de carteirinha", f"{round(share(['Jogos']) * 100)}% do tempo de tela foi jogando"),
        (focus_min >= 20 * 60, "Monge do foco", f"{round(focus_min / 60)} h de foco no mês"),
        (early >= 0.12, "Madrugador", f"{round(early * 100)}% do tempo foi entre 5h e 8h"),
        (share(["Trabalho", "Criação"]) >= 0.5, "Workaholic", f"{round(share(['Trabalho', 'Criação']) * 100)}% foi trabalho"),
        (share(["Social", "Entretenimento"]) >= 0.35, "Rolador de feed",
         f"{round(share(['Social', 'Entretenimento']) * 100)}% foi rede social e vídeo"),
        (matches >= 60, "Viciado em ranqueada", f"{matches} partidas no mês"),
    ]
    for ok, name, why in rules:
        if ok:
            return {"name": name, "why": why}
    return {"name": "Equilibrado", "why": "nenhuma categoria dominou o seu mês"}


def build(month, days, xp_before, conq, apps_report, matches, prev_days=None, today=None):
    """days: [(dia, facts, metas, xp)] do mês; conq: conquistas ganhas no mês; apps_report: ScreenTime.report("month");
    matches: [(fim, jogo, título, vitória, dados)] do mês; prev_days: os mesmos dias do mês anterior (comparação)."""
    today = today or date.today().isoformat()
    first, last = month_bounds(month)
    used = [(d, f) for d, f, _m, _x in days if f.get("scr", 0) > 0]
    hours = [0] * 24
    by_wd = [0] * 7
    for d, f in used:
        for h, s in enumerate(f.get("hrs") or []):
            hours[h] += s
        by_wd[date.fromisoformat(d).weekday()] += f.get("scr", 0)
    total = sum(f.get("scr", 0) for _d, f in used)
    best = max(used, key=lambda x: x[1].get("scr", 0), default=None)
    cats = {}
    for _d, f in used:
        for c, s in (f.get("cats") or {}).items():
            cats[c] = cats.get(c, 0) + s
    prev_total = sum(f.get("scr", 0) for _d, f, *_ in prev_days or [])

    # foco e metas
    focus = sum(f.get("foc", 0) for _d, f, _m, _x in days)
    best_focus = max(days, key=lambda x: x[1].get("foc", 0), default=None)
    metas_done = sum(1 for _d, _f, ms, _x in days for m in ms if m["status"] == "done")
    metas_total = sum(len(ms) for _d, _f, ms, _x in days)
    streak = best_streak = perfect = 0
    for _d, _f, ms, _x in days:
        done = sum(1 for m in ms if m["status"] == "done")
        streak = streak + 1 if done >= 2 else 0
        best_streak = max(best_streak, streak)
        perfect += done == len(ms) == 3

    # jogos e partidas
    game_apps = [a for a in apps_report.get("apps") or [] if a.get("cat") == "Jogos"]
    ms_all = [(e, g, t, w, dt) for e, g, t, w, dt in matches]
    wins = sum(1 for m in ms_all if m[3] == 1)
    losses = sum(1 for m in ms_all if m[3] == 0)
    fav = {}
    for g in ("dota2", "cs2"):
        cnt = {}
        for _e, gg, t, w, _dt in ms_all:
            if gg == g and t and t != "?":
                n, v = cnt.get(t, (0, 0))
                cnt[t] = (n + 1, v + (w == 1))
        if cnt:
            t, (n, v) = max(cnt.items(), key=lambda x: (x[1][0], x[1][1]))
            fav[g] = {"title": t, "n": n, "w": v}
    top = max(ms_all, key=lambda m: (_kda({"k": m[4].get("k"), "d": m[4].get("d"), "a": m[4].get("a")}), m[3] == 1), default=None)
    best_match = None
    if top:
        e, g, t, w, dt = top
        best_match = {"game": g, "title": t, "win": w, "k": dt.get("k"), "d": dt.get("d"), "a": dt.get("a"),
                      "kda": round(_kda(dt), 1), "day": date.fromtimestamp(e).isoformat()}

    talk = {}
    for _d, f, _m, _x in days:
        for k, s in (f.get("talk") or {}).items():
            talk[k] = talk.get(k, 0) + s

    month_xp = sum(x for *_r, x in days) + sum(c["xp"] for c in conq)
    lvl_a, lvl_b = level_of(xp_before)[0], level_of(xp_before + month_xp)[0]
    peak = max(range(24), key=lambda h: hours[h]) if total else None
    wd = max(range(7), key=lambda i: by_wd[i]) if total else None
    return {
        "month": month, "label": f"{MONTHS[first.month - 1]} de {first.year}", "partial": today <= last.isoformat(),
        "days_used": len(used), "days_in_month": last.day,
        "screen": {"total": total, "avg": round(total / len(used)) if used else 0, "prev_total": prev_total,
                   "best_day": {"day": best[0], "secs": best[1].get("scr", 0)} if best else None,
                   "peak_hour": peak, "weekday": WEEKDAYS[wd] if wd is not None else None, "hours": hours},
        "cats": [{"cat": c, "secs": s, "pct": round(s * 100 / total) if total else 0}
                 for c, s in sorted(cats.items(), key=lambda x: -x[1]) if s >= 60],
        "apps": [{"name": a["name"], "secs": a["secs"], "cat": a.get("cat")} for a in (apps_report.get("apps") or [])[:5]],
        "focus": {"min": focus, "best_day": {"day": best_focus[0], "min": best_focus[1].get("foc", 0)}
                  if best_focus and best_focus[1].get("foc") else None,
                  "metas_done": metas_done, "metas_total": metas_total, "best_streak": best_streak, "perfect": perfect},
        "games": {"secs": cats.get("Jogos", 0), "top": [{"name": a["name"], "secs": a["secs"]} for a in game_apps[:3]],
                  "matches": len(ms_all), "wins": wins, "losses": losses,
                  "winrate": round(wins * 100 / (wins + losses)) if wins + losses else None, "fav": fav, "best": best_match},
        "talk": {"total": round(sum(talk.values())), "meet": round(talk.get("meet", 0)), "game": round(talk.get("game", 0))},
        "xp": {"month": month_xp, "level_start": lvl_a, "level_end": lvl_b},
        "conq": conq,
        "persona": persona(hours, cats, total, focus, len(ms_all)),
    }
