"""Ajuda no draft e builds do Dota 2, com as estatísticas públicas do STRATZ (precisa da chave grátis).

- Draft: você marca os heróis inimigos (e, se quiser, os aliados) no celular e recebe os heróis da sua
  posição ordenados por vantagem contra eles. O GSI do jogador não mostra o time inimigo, por isso é na mão.
- Build: itens iniciais, botas, itens principais com o minuto médio, ordem de skills e talentos mais
  escolhidos para o herói na sua posição e faixa de rank. Abre sozinha com o herói que o GSI informa.

Vantagem ("synergy" do STRATZ): quanto o herói ganha a mais (em pontos de % de vitória) contra aquele
inimigo do que o esperado pelas forças dos dois. É quase simétrica: A contra B ≈ -(B contra A).
Tudo fica em cache no disco (horas/dias): as estatísticas mudam devagar e o STRATZ limita as chamadas.
"""
import json
import logging
import time
from pathlib import Path

import dota_stats

log = logging.getLogger("companion")

BRACKETS = ("HERALD_GUARDIAN", "CRUSADER_ARCHON", "LEGEND_ANCIENT", "DIVINE_IMMORTAL")
BRACKET_NAME = {"HERALD_GUARDIAN": "Arauto–Guardião", "CRUSADER_ARCHON": "Cruzado–Arconte",
                "LEGEND_ANCIENT": "Lenda–Ancestral", "DIVINE_IMMORTAL": "Divino–Imortal"}
DEFAULT_BRACKET = "LEGEND_ANCIENT"
TALENT_LEVELS = (10, 15, 20, 25)
MIN_SHARE = 0.008        # heróis com menos de 0,8% das partidas na posição ficam fora das sugestões
MIN_MATCHUP_GAMES = 40   # matchup com menos partidas que isso é ruído: conta como 0

HOUR = 3600
TTL = {"heroes": 7 * 86400, "items": 7 * 86400, "pos": 12 * HOUR, "mu": 24 * HOUR, "build": 12 * HOUR, "player": 6 * HOUR}


def bracket_of(season_rank):
    """seasonRank do STRATZ (ex.: 54 = Lenda 4, 80 = Imortal) -> faixa usada nas estatísticas."""
    try:
        tier = int(season_rank) // 10
    except (TypeError, ValueError):
        return None
    return {1: BRACKETS[0], 2: BRACKETS[0], 3: BRACKETS[1], 4: BRACKETS[1],
            5: BRACKETS[2], 6: BRACKETS[2], 7: BRACKETS[3], 8: BRACKETS[3]}.get(tier)


def median_rank(ranks):
    """Mediana dos ranks (ex.: 22 = Guardião 2) das partidas, ignorando as sem rank (0/None)."""
    r = sorted(int(x) for x in ranks if isinstance(x, (int, float)) and x > 0)
    return r[len(r) // 2] if r else None


def check_pos(pos):
    try:
        p = int(pos)
    except (TypeError, ValueError):
        raise ValueError("posição inválida") from None
    if not 1 <= p <= 5:
        raise ValueError("posição inválida")
    return p


def check_heroes(ids, limit):
    out = []
    for h in ids or []:
        try:
            h = int(h)
        except (TypeError, ValueError):
            raise ValueError("herói inválido") from None
        if not 0 < h < 1000:
            raise ValueError("herói inválido")
        if h not in out:
            out.append(h)
    if len(out) > limit:
        raise ValueError("heróis demais")
    return out


# --------------------------------------------------------------------------
# Contas puras (testadas sem rede)
# --------------------------------------------------------------------------
def suggest(pos, enemies, allies, pos_stats, mu, heroes, mine=None, prefer=()):
    """Heróis da posição ordenados por vantagem contra os inimigos (+ sinergia com aliados + força no meta).

    pos_stats: {pos: {hero: [partidas, vitórias]}}; mu: {hero: {"vs": {h2: [vantagem, wr, n]}, "with": {...}}}
    (vantagem/wr do ponto de vista de `hero`); mine: {hero: [partidas, vitórias]} do jogador;
    prefer: heróis que você planejou jogar (entram mesmo pouco jogados na posição, marcados com "fav").
    """
    rows = pos_stats.get(pos) or pos_stats.get(str(pos)) or {}
    total = sum(n for n, _ in rows.values()) or 1
    taken = set(enemies) | set(allies)
    out = []
    for hid, (n, w) in rows.items():
        hid = int(hid)
        fav = hid in prefer
        if hid in taken or (n / total < MIN_SHARE and not fav):
            continue
        vs = []
        for e in enemies:
            # do ponto de vista do inimigo: vantagem dele contra o candidato, com o sinal trocado
            adv, wr, cnt = (mu.get(e) or {}).get("vs", {}).get(hid) or (0, None, 0)
            ok = cnt >= MIN_MATCHUP_GAMES
            vs.append([e, round(-adv, 1) if ok else 0, round(100 - wr * 100, 1) if ok and wr is not None else None])
        wi = []
        for a in allies:
            syn, _, cnt = (mu.get(a) or {}).get("with", {}).get(hid) or (0, None, 0)
            wi.append([a, round(syn, 1) if cnt >= MIN_MATCHUP_GAMES else 0])
        adv = sum(v[1] for v in vs) + 0.5 * sum(v[1] for v in wi)
        wr = w / n * 100 if n else 50
        my = (mine or {}).get(hid)
        out.append({"id": hid, "n": (heroes.get(hid) or {}).get("n") or f"herói {hid}",
                    "score": round(adv + (wr - 50), 1), "adv": round(adv, 1), "wr": round(wr, 1),
                    "share": round(n / total * 100, 1), "vs": vs, "with": wi,
                    "mine": [my[0], round(my[1] / my[0] * 100)] if my and my[0] else None, "fav": fav})
    out.sort(key=lambda x: (-x["score"], -x["share"]))
    return out


def ban_suggestions(prefer, pos_stats, mu, heroes, top=5, min_pick=0.03):
    """Heróis que mais atrapalham os seus preferidos (bons para banir), entre os que aparecem em pelo menos 3% das partidas.

    Vem da lista "vs" de cada preferido: vantagem negativa dele contra X = X é counter dele.
    """
    count = {}
    for rows in pos_stats.values():
        for h, (n, _) in rows.items():
            count[int(h)] = count.get(int(h), 0) + n
    matches = sum(count.values()) / 10 or 1   # cada partida tem 10 heróis
    out = []
    for hid, n in count.items():
        if hid in prefer or n / matches < min_pick:
            continue
        hurt = []
        for p in prefer:
            adv, _, cnt = (mu.get(p) or {}).get("vs", {}).get(hid) or (0, None, 0)
            if cnt >= MIN_MATCHUP_GAMES and adv < 0:
                hurt.append([p, round(adv, 1)])
        if hurt:
            out.append({"id": hid, "n": (heroes.get(hid) or {}).get("n") or f"herói {hid}", "score": round(-sum(a for _, a in hurt), 1),
                        "vs": sorted(hurt, key=lambda x: x[1]), "pick": round(n / matches * 100)})
    out.sort(key=lambda x: -x["score"])
    return out[:top]


def hero_positions(pos_stats, hero):
    """{pos: fração das partidas do herói} na faixa."""
    got = {int(p): (rows.get(hero) or rows.get(str(hero)) or [0, 0])[0] for p, rows in pos_stats.items()}
    total = sum(got.values())
    return {p: n / total for p, n in got.items()} if total else {}


def _item(items, iid):
    it = items.get(iid) or items.get(str(iid)) or {}
    return it.get("n") or f"item {iid}", it.get("c") or 0


def make_build(raw, items, total):
    """Resposta crua do STRATZ (já filtrada por herói/posição/faixa) -> build resumida."""
    # itens iniciais: instance 0 = primeira unidade, 1 = segunda...
    start = {}
    for r in raw.get("start") or []:
        if r.get("wasGiven"):
            continue
        s = start.setdefault(r["itemId"], {"n": 0, "q": 0, "first": 0})
        if r.get("instance", 0) == 0 or not s["first"]:
            s["first"] = max(s["first"], r["matchCount"])
        s["q"] = max(s["q"], (r.get("instance") or 0) + 1 if r["matchCount"] >= 0.4 * max(s["first"], 1) else 0)
    first_n = max([s["first"] for s in start.values()] or [1])
    start_out = sorted(({"name": _item(items, i)[0], "q": max(1, s["q"]), "pct": round(s["first"] / first_n * 100)}
                        for i, s in start.items() if s["first"] >= 0.25 * first_n), key=lambda x: -x["pct"])[:8]

    boots_ids, boots = set(), []
    bt = sum(r["matchCount"] for r in raw.get("boots") or []) or 1
    for r in sorted(raw.get("boots") or [], key=lambda r: -r["matchCount"]):
        boots_ids.add(r["itemId"])
        if r["matchCount"] / bt >= 0.05 and len(boots) < 3:
            boots.append({"name": _item(items, r["itemId"])[0], "min": round((r.get("timeAverage") or 0) / 60),
                          "pct": round(r["matchCount"] / bt * 100), "wr": round((r.get("winAverage") or 0) * 100)})

    # as compras vêm de uma amostra maior que a contagem de partidas; quase todo mundo compra botas,
    # então a soma das botas é o melhor denominador para "% das partidas"
    total = max(total or 0, sum(r["matchCount"] for r in raw.get("boots") or []), 1)
    agg = {}
    for r in raw.get("full") or []:
        a = agg.setdefault(r["itemId"], [0, 0.0, 0.0])
        n = r["matchCount"]
        a[0] += n
        a[1] += (r.get("winsAverage") or 0) * n
        a[2] += (r.get("time") or 0) * n
    core, early, situ = [], [], []
    for iid, (n, wins, tsum) in agg.items():
        if iid in boots_ids or not n:
            continue
        name, cost = _item(items, iid)
        row = {"name": name, "min": round(tsum / n), "pct": round(n / total * 100), "wr": round(wins / n * 100)}
        share = n / total
        if cost >= 1800 and share >= 0.15:
            core.append(row)
        elif cost >= 1800 and share >= 0.03:
            situ.append(row)
        elif 200 <= cost < 1800 and share >= 0.3 and row["min"] <= 15:
            early.append(row)
    core.sort(key=lambda x: x["min"])
    early.sort(key=lambda x: x["min"])
    situ.sort(key=lambda x: -x["pct"])

    names = {a["abilityId"]: a for a in raw.get("abilities") or []}
    modal = {}
    for r in raw.get("maxlvl") or []:
        aid = r["abilityId"]
        if aid in names and r["matchCount"] > modal.get(aid, (0, 0))[1]:
            modal[aid] = (r["level"], r["matchCount"])
    skills = [{"name": names[a]["name"], "max": lvl, "ult": names[a]["ult"]}
              for a, (lvl, _) in sorted(modal.items(), key=lambda kv: kv[1][0])]

    tal = {r["abilityId"]: r for r in raw.get("talent") or []}
    talents = []
    for i, lvl in enumerate(TALENT_LEVELS):
        pair = [t for t in raw.get("talents") or [] if t.get("slot") in (2 * i, 2 * i + 1)]
        counted = [(tal.get(t["abilityId"], {}).get("matchCount", 0), t) for t in pair]
        tot = sum(c for c, _ in counted)
        if not tot:
            continue
        c, best = max(counted, key=lambda x: x[0])
        other = next((t for t in pair if t is not best), None)
        talents.append({"lvl": lvl, "name": best.get("name") or "?", "pct": round(c / tot * 100),
                        "wr": round((tal[best["abilityId"]].get("winsAverage") or 0) * 100),
                        "alt": (other or {}).get("name")})
    return {"start": start_out, "boots": boots, "early": early[:5], "core": core[:8], "situ": situ[:6],
            "skills": skills, "talents": talents}


# --------------------------------------------------------------------------
# STRATZ + cache
# --------------------------------------------------------------------------
HEROES_Q = "{ constants { heroes { id displayName shortName } } }"
ITEMS_Q = "{ constants { items { id displayName stat { cost } } } }"
POS_Q = """query($b: [RankBracketBasicEnum]) { heroStats {
  stats(bracketBasicIds: $b, groupByPosition: true) { heroId position matchCount winCount } } }"""
MU_FIELDS = "advantage { heroId vs { heroId2 synergy winsAverage matchCount } with { heroId2 synergy winsAverage matchCount } }"
PLAYER_Q = """query($id: Long!) { player(steamAccountId: $id) { steamAccount { seasonRank }
  heroesPerformance(request: {take: 200}, take: 150) { heroId matchCount winCount }
  matches(request: {take: 20}) { rank } } }"""
BUILD_Q = """query($h: Short!, $b: [RankBracketBasicEnum], $p: [MatchPlayerPositionType]) {
  heroStats {
    st: stats(heroIds: [$h], bracketBasicIds: $b, positionIds: $p, groupByPosition: true) { matchCount winCount }
    start: itemStartingPurchase(heroId: $h, bracketBasicIds: $b, positionIds: $p) { itemId instance wasGiven matchCount winsAverage }
    boots: itemBootPurchase(heroId: $h, bracketBasicIds: $b, positionIds: $p) { itemId timeAverage matchCount winAverage }
    full: itemFullPurchase(heroId: $h, bracketBasicIds: $b, positionIds: $p) { itemId time matchCount winsAverage }
    talent(heroId: $h, bracketBasicIds: $b, positionIds: $p) { abilityId matchCount winsAverage }
    maxlvl: abilityMaxLevel(heroId: $h, bracketBasicIds: $b) { abilityId level matchCount position }
  }
  constants { hero(id: $h) { abilities { slot abilityId ability { language { displayName } stat { isUltimate } } } talents { slot abilityId } } }
}"""


class Draft:
    def __init__(self, token_fn, cache_dir):
        self.token_fn = token_fn
        self.dir = Path(cache_dir) / "dota-cache"
        self.mem = {}

    def sz(self):
        return dota_stats.Stratz(self.token_fn(), self.dir.parent)

    def _get(self, name, kind, build):
        """Memória -> disco (dentro do prazo) -> STRATZ. Se o STRATZ falhar, usa o disco mesmo vencido."""
        now = time.time()
        hit = self.mem.get(name)
        if hit and now - hit[0] < TTL[kind]:
            return hit[1]
        path = self.dir / (name + ".json")
        old = None
        try:
            old = json.loads(path.read_text(encoding="utf-8"))
            if now - path.stat().st_mtime < TTL[kind]:
                self.mem[name] = (path.stat().st_mtime, old)
                return old
        except (OSError, ValueError):
            pass
        try:
            got = build()
        except dota_stats.ApiError:
            if old is not None:
                log.warning("STRATZ fora do ar: usando o cache vencido de %s", name)
                return old
            raise
        # ida e volta pelo JSON: as chaves viram texto igual ao que volta do disco
        got = json.loads(json.dumps(got, ensure_ascii=False))
        try:
            self.dir.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(got, ensure_ascii=False), encoding="utf-8")
        except OSError:
            pass
        self.mem[name] = (now, got)
        return got

    # ---- tabelas
    def heroes(self):
        d = self._get("heroes", "heroes", lambda: {
            h["id"]: {"n": h.get("displayName") or "", "s": h.get("shortName") or ""}
            for h in self.sz().gql(HEROES_Q)["constants"]["heroes"] if h.get("id")})
        return {int(k): v for k, v in d.items()}

    def items(self):
        d = self._get("items", "items", lambda: {
            i["id"]: {"n": i.get("displayName") or "", "c": (i.get("stat") or {}).get("cost") or 0}
            for i in self.sz().gql(ITEMS_Q)["constants"]["items"] if i.get("id")})
        return {int(k): v for k, v in d.items()}

    def pos_stats(self, bracket):
        def build():
            out = {str(p): {} for p in range(1, 6)}
            for r in self.sz().gql(POS_Q, {"b": [bracket]})["heroStats"]["stats"] or []:
                p = dota_stats.POSITION.get(r.get("position"))
                if p:
                    out[str(p)][r["heroId"]] = [r["matchCount"], r["winCount"]]
            return out
        d = self._get(f"pos-{bracket}", "pos", build)
        return {p: {int(h): v for h, v in rows.items()} for p, rows in d.items()}

    def matchups(self, hero_ids, bracket):
        """{herói: {"vs": {h2: [vantagem, wr, n]}, "with": {...}}}; busca de uma vez os que faltam no cache."""
        out, missing = {}, []
        for h in hero_ids:
            hit = self._peek(f"mu-{bracket}-{h}", "mu")
            if hit is None:
                missing.append(h)
            else:
                out[h] = hit
        if missing:
            q = "query($b: [RankBracketBasicEnum]) { heroStats { " + " ".join(
                f"h{h}: heroVsHeroMatchup(heroId: {int(h)}, bracketBasicIds: $b) {{ {MU_FIELDS} }}" for h in missing) + " } }"
            data = self.sz().gql(q, {"b": [bracket]}).get("heroStats") or {}
            for h in missing:
                adv = ((data.get(f"h{h}") or {}).get("advantage") or [{}])[0]
                got = {k: {r["heroId2"]: [r.get("synergy") or 0, r.get("winsAverage"), r.get("matchCount") or 0]
                           for r in adv.get(k) or []} for k in ("vs", "with")}
                out[h] = self._get(f"mu-{bracket}-{h}", "mu", lambda got=got: got)
        return {h: {k: {int(x): v for x, v in m.items()} for k, m in d.items()} for h, d in out.items()}

    def _peek(self, name, kind):
        try:
            return self._get(name, kind, self._miss)
        except _Miss:
            return None

    @staticmethod
    def _miss():
        raise _Miss()

    def player(self, acc):
        if not acc:
            return None

        def build():
            p = self.sz().gql(PLAYER_Q, {"id": int(acc)}).get("player") or {}
            rank, src = (p.get("steamAccount") or {}).get("seasonRank"), "medal"
            if not rank:   # sem medalha (não calibrado / sem ranked na temporada): rank médio das suas partidas
                rank, src = median_rank([m.get("rank") for m in p.get("matches") or []]), "matches"
            return {"rank": rank, "src": src if rank else None,
                    "heroes": {r["heroId"]: [r["matchCount"], r["winCount"]] for r in p.get("heroesPerformance") or []}}
        try:
            d = self._get(f"player-{int(acc)}", "player", build)
        except dota_stats.ApiError as e:
            log.info("STRATZ: perfil do jogador indisponível (%s)", e)
            return None
        return {"rank": d.get("rank"), "src": d.get("src"), "heroes": {int(h): v for h, v in (d.get("heroes") or {}).items()}}

    def bracket(self, want, acc):
        """Faixa pedida pelo celular, ou "auto": a do seu rank no STRATZ (perfil público), senão Lenda–Ancestral."""
        if want in BRACKETS:
            return want, False
        me = self.player(acc) or {}
        b = bracket_of(me.get("rank"))
        return (b, me.get("src") or True) if b else (DEFAULT_BRACKET, False)

    # ---- respostas para o celular
    def hero_list(self):
        return sorted(({"id": h, "n": v["n"]} for h, v in self.heroes().items()), key=lambda x: x["n"])

    def draft(self, pos, enemies, allies, want_bracket, acc, prefer=()):
        pos = check_pos(pos) if pos else None
        enemies, allies, prefer = check_heroes(enemies, 5), check_heroes(allies, 4), check_heroes(prefer, Plan.MAX_HEROES)
        bracket, auto = self.bracket(want_bracket, acc)
        need = list(dict.fromkeys(enemies + allies + prefer))
        mu = self.matchups(need, bracket) if need else {}
        me = self.player(acc)
        stats, heroes = self.pos_stats(bracket), self.heroes()
        rows = suggest(pos, enemies, allies, stats, mu, heroes, (me or {}).get("heroes"), prefer) if pos else []
        # banir: só faz sentido antes de ver o time inimigo, e sem tirar quem já está no jogo
        bans = [b for b in ban_suggestions(prefer, stats, mu, heroes, top=8) if b["id"] not in enemies + allies][:5] if prefer else []
        return {"pos": pos, "bracket": bracket, "bname": BRACKET_NAME[bracket], "auto": auto,
                "enemies": enemies, "allies": allies, "prefer": prefer, "list": rows, "bans": bans}

    def build(self, hero, pos, want_bracket, acc, enemies=()):
        hero = check_heroes([hero], 1)[0]
        enemies = check_heroes(enemies, 5)
        bracket, auto = self.bracket(want_bracket, acc)
        heroes = self.heroes()
        if hero not in heroes:
            raise ValueError("herói desconhecido")
        shares = hero_positions(self.pos_stats(bracket), hero)
        asked = check_pos(pos) if pos else None
        moved = False
        if shares and (asked is None or shares.get(asked, 0) < 0.05):
            moved = asked is not None
            asked = max(shares, key=shares.get)
        pos = asked or 1

        def fetch():
            d = self.sz().gql(BUILD_Q, {"h": hero, "b": [bracket], "p": [f"POSITION_{pos}"]})
            hs, h = d.get("heroStats") or {}, ((d.get("constants") or {}).get("hero") or {})
            talents = h.get("talents") or []
            names = {}
            if talents:
                q = "{ constants { " + " ".join(f"t{t['abilityId']}: ability(id: {int(t['abilityId'])}) {{ language {{ displayName }} }}"
                                                for t in talents) + " } }"
                c = self.sz().gql(q).get("constants") or {}
                names = {t["abilityId"]: ((c.get(f"t{t['abilityId']}") or {}).get("language") or {}).get("displayName")
                         for t in talents}
            maxlvl = [r for r in hs.get("maxlvl") or [] if r.get("position") in (None, f"POSITION_{pos}")] or hs.get("maxlvl") or []
            st = (hs.get("st") or [{}])[0] if hs.get("st") else {}
            return {"total": st.get("matchCount") or 0, "wins": st.get("winCount") or 0,
                    "start": hs.get("start"), "boots": hs.get("boots"), "full": hs.get("full"), "talent": hs.get("talent"),
                    "maxlvl": maxlvl,
                    "abilities": [{"abilityId": a["abilityId"], "slot": a.get("slot"),
                                   "name": ((a.get("ability") or {}).get("language") or {}).get("displayName") or "?",
                                   "ult": bool(((a.get("ability") or {}).get("stat") or {}).get("isUltimate"))}
                                  for a in h.get("abilities") or []],
                    "talents": [{"slot": t.get("slot"), "abilityId": t["abilityId"], "name": names.get(t["abilityId"])} for t in talents]}
        raw = self._get(f"build-{bracket}-{hero}-{pos}", "build", fetch)
        out = make_build(raw, self.items(), raw.get("total"))
        vs = []
        if enemies:
            # do ponto de vista de cada inimigo (o mesmo cache e os mesmos números do draft), com o sinal trocado
            mu = self.matchups(enemies, bracket)
            for e in enemies:
                adv, wr, n = (mu.get(e) or {}).get("vs", {}).get(hero) or (0, None, 0)
                ok = n >= MIN_MATCHUP_GAMES
                vs.append({"id": e, "n": heroes.get(e, {}).get("n") or f"herói {e}",
                           "adv": round(-adv, 1) if ok else None, "wr": round(100 - wr * 100, 1) if ok and wr is not None else None})
        return {"hero": hero, "name": heroes[hero]["n"], "pos": pos, "moved": moved,
                "pos_share": {p: round(s * 100) for p, s in shares.items()},
                "bracket": bracket, "bname": BRACKET_NAME[bracket], "auto": auto,
                "games": raw.get("total") or 0, "wr": round(raw["wins"] / raw["total"] * 100, 1) if raw.get("total") else None,
                "vs": vs, **out}


class _Miss(Exception):
    pass


class Plan:
    """O que você combinou consigo mesmo para a próxima partida (escolhido na fila): posição e heróis preferidos.

    Fica no servidor (todos os aparelhos veem o mesmo) e num arquivo (sobrevive a reinício); zera quando a partida
    termina e é salva.
    """
    MAX_HEROES = 6

    def __init__(self, path):
        self.path = Path(path)
        self.d = {"pos": None, "heroes": [], "t": 0}
        try:
            d = json.loads(self.path.read_text(encoding="utf-8"))
            self.d = {"pos": check_pos(d["pos"]) if d.get("pos") else None,
                      "heroes": check_heroes(d.get("heroes"), self.MAX_HEROES), "t": float(d.get("t") or 0)}
        except (OSError, ValueError, KeyError, TypeError):
            pass

    def state(self):
        return dict(self.d)

    def set(self, p):
        d = dict(self.d)
        if "pos" in p:
            d["pos"] = check_pos(p["pos"]) if p["pos"] else None
        if "heroes" in p:
            d["heroes"] = check_heroes(p["heroes"], self.MAX_HEROES)
        d["t"] = time.time()
        self.d = d
        self._save()
        return self.state()

    def reset(self):
        self.d = {"pos": None, "heroes": [], "t": time.time()}
        self._save()
        return self.state()

    def _save(self):
        try:
            self.path.write_text(json.dumps(self.d), encoding="utf-8")
        except OSError as e:
            log.warning("plano do Dota: não deu para gravar (%s)", e)
