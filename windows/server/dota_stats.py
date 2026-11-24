"""Relatório da partida de Dota 2 depois que ela acaba: STRATZ (com chave) ou OpenDota (sem chave).

O GSI só manda os seus dados durante a partida. Aqui, minutos depois do fim, vem o placar dos 10,
a nota de desempenho (IMP, só STRATZ), a posição, o resultado de cada lane e a vantagem de ouro.

STRATZ: chave grátis em stratz.com/api (login com a Steam). A partida aparece lá alguns minutos depois
do fim; quando não aparece, pedimos o download (retryMatchDownload). O IMP sai depois da análise.
OpenDota: sem chave; sem IMP e sem resultado de lane.
"""
import asyncio
import json
import logging
import time
import urllib.error
import urllib.request
from pathlib import Path

log = logging.getLogger("companion")

STRATZ_URL = "https://api.stratz.com/graphql"
OPENDOTA = "https://api.opendota.com/api"
STEAM64_BASE = 76561197960265728

MATCH_QUERY = """query($id: Long!) { match(id: $id) {
  id didRadiantWin durationSeconds parsedDateTime statsDateTime analysisOutcome
  bottomLaneOutcome midLaneOutcome topLaneOutcome radiantNetworthLeads
  players { steamAccountId isRadiant isVictory heroId hero { displayName } steamAccount { name }
    kills deaths assists numLastHits numDenies goldPerMinute experiencePerMinute networth level
    heroDamage towerDamage heroHealing lane position imp award
    item0Id item1Id item2Id item3Id item4Id item5Id neutral0Id }
} }"""
ITEMS_QUERY = "{ constants { items { id displayName } } }"

LANE = {"SAFE_LANE": "safe", "MID_LANE": "mid", "OFF_LANE": "off", "JUNGLE": "jungle", "ROAMING": "roam"}
OD_LANE_ROLE = {1: "safe", 2: "mid", 3: "off", 4: "jungle"}
POSITION = {f"POSITION_{i}": i for i in range(1, 6)}
AWARD = {"MVP": "MVP", "TOP_CORE": "Melhor core", "TOP_SUPPORT": "Melhor suporte"}
OUTCOME = {"STOMPED": "atropelo", "COMEBACK": "virada", "CLOSE_GAME": "jogo apertado"}


class ApiError(Exception):
    pass


def account_id(steamid):
    """steamid64 (ou já account id de 32 bits) -> account id do Dota; None se não der."""
    try:
        n = int(steamid)
    except (TypeError, ValueError):
        return None
    return n - STEAM64_BASE if n > STEAM64_BASE else n or None


def physical_lane(is_radiant, lane):
    """safe/off dependem do lado: a safe do Radiant é a de baixo, a do Dire é a de cima."""
    if lane == "mid":
        return "mid"
    if lane == "safe":
        return "bottom" if is_radiant else "top"
    if lane == "off":
        return "top" if is_radiant else "bottom"
    return None


def lane_result(outcome, is_radiant):
    """Resultado da lane do ponto de vista do jogador: stomp_win, win, tie, loss, stomp_loss (ou None)."""
    if not outcome:
        return None
    if outcome == "TIE":
        return "tie"
    side, kind = outcome.split("_", 1)   # RADIANT_VICTORY, DIRE_STOMP...
    mine = (side == "RADIANT") == bool(is_radiant)
    return ("stomp_" if kind == "STOMP" else "") + ("win" if mine else "loss")


def _http(url, data=None, headers=None, timeout=20):
    req = urllib.request.Request(url, data=data, headers={"User-Agent": "CompanionPC", **(headers or {})})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return None
        raise ApiError(f"HTTP {e.code}") from e
    except (urllib.error.URLError, TimeoutError, ValueError) as e:
        raise ApiError(str(getattr(e, "reason", e))) from e


# --------------------------------------------------------------------------
# STRATZ
# --------------------------------------------------------------------------
class Stratz:
    def __init__(self, token, cache_dir):
        self.token = (token or "").strip()
        self.items_path = Path(cache_dir) / "dota-items.json"
        self._items = None

    def gql(self, query, variables=None):
        if not self.token:
            raise ApiError("sem chave do STRATZ")
        body = json.dumps({"query": query, "variables": variables or {}}).encode()
        # o STRATZ recusa requisições sem este User-Agent
        try:
            d = _http(STRATZ_URL, body, {"Content-Type": "application/json", "User-Agent": "STRATZ_API",
                                         "Authorization": f"Bearer {self.token}"})
        except ApiError as e:
            if "403" in str(e) or "401" in str(e):
                raise ApiError("chave do STRATZ recusada (confira em stratz.com/api)") from e
            raise
        if d is None:
            raise ApiError("STRATZ não respondeu")
        if d.get("errors") and not d.get("data"):
            raise ApiError(str(d["errors"][0].get("message", "erro"))[:160])
        return d.get("data") or {}

    def items(self):
        """id -> nome do item (lista do STRATZ, guardada em disco por 7 dias)."""
        if self._items is None:
            self._items = _cached(self.items_path, lambda: {
                i["id"]: i.get("displayName") or "" for i in (self.gql(ITEMS_QUERY).get("constants") or {}).get("items") or []
                if i.get("id")})
        return self._items

    def match(self, match_id):
        return self.gql(MATCH_QUERY, {"id": int(match_id)}).get("match")

    def request_download(self, match_id):
        return bool(self.gql("mutation($id: Long!) { retryMatchDownload(matchId: $id) }", {"id": int(match_id)})
                    .get("retryMatchDownload"))


def from_stratz(m, me_account=None, me_hero=None, items=None):
    items = items or {}
    lanes = {"bottom": m.get("bottomLaneOutcome"), "mid": m.get("midLaneOutcome"), "top": m.get("topLaneOutcome")}
    players = []
    for p in m.get("players") or []:
        rad, lane = bool(p.get("isRadiant")), LANE.get(p.get("lane"))
        phys = physical_lane(rad, lane)
        players.append({
            "r": rad, "hero_id": p.get("heroId"), "hero": (p.get("hero") or {}).get("displayName") or f"herói {p.get('heroId')}",
            "name": (p.get("steamAccount") or {}).get("name"), "acc": p.get("steamAccountId"),
            "k": p.get("kills"), "d": p.get("deaths"), "a": p.get("assists"), "lh": p.get("numLastHits"), "dn": p.get("numDenies"),
            "gpm": p.get("goldPerMinute"), "xpm": p.get("experiencePerMinute"), "nw": p.get("networth"), "lvl": p.get("level"),
            "hd": p.get("heroDamage"), "td": p.get("towerDamage"), "hh": p.get("heroHealing"),
            "items": [items.get(p.get(f"item{i}Id"), "") for i in range(6) if p.get(f"item{i}Id")],
            "neutral": items.get(p.get("neutral0Id"), "") if p.get("neutral0Id") else "",
            "pos": POSITION.get(p.get("position")), "lane": lane,
            "lane_res": lane_result(lanes.get(phys), rad) if phys else None,
            "imp": p.get("imp"), "award": AWARD.get(p.get("award")),
        })
    return _finish({"match_id": m.get("id"), "src": "stratz", "dur": m.get("durationSeconds"),
                    "radiant_win": m.get("didRadiantWin"), "outcome": OUTCOME.get(m.get("analysisOutcome")),
                    "nw_leads": m.get("radiantNetworthLeads") or [], "players": players}, me_account, me_hero)


# --------------------------------------------------------------------------
# OpenDota (reserva, sem chave)
# --------------------------------------------------------------------------
def _cached(path, build):
    """Lista de nomes (id -> nome) guardada em disco por 7 dias."""
    try:
        if time.time() - path.stat().st_mtime < 7 * 86400:
            return {int(k): v for k, v in json.loads(path.read_text(encoding="utf-8")).items()}
    except (OSError, ValueError):
        pass
    got = build()
    try:
        path.write_text(json.dumps(got, ensure_ascii=False), encoding="utf-8")
    except OSError:
        pass
    return got


class OpenDota:
    def __init__(self, cache_dir):
        self.cache_dir = Path(cache_dir)
        self._heroes = self._items = None

    def heroes(self):
        if self._heroes is None:
            self._heroes = _cached(self.cache_dir / "dota-heroes.json", lambda: {
                int(k): v.get("localized_name", "") for k, v in (_http(f"{OPENDOTA}/constants/heroes") or {}).items()})
        return self._heroes

    def items(self):
        """id -> nome; a mesma numeração do jogo (vale também para os ids do STRATZ)."""
        if self._items is None:
            def build():
                ids = _http(f"{OPENDOTA}/constants/item_ids") or {}
                info = _http(f"{OPENDOTA}/constants/items") or {}
                return {int(i): (info.get(key) or {}).get("dname") or key.replace("_", " ") for i, key in ids.items()}
            self._items = _cached(self.cache_dir / "dota-items-od.json", build)
        return self._items

    def match(self, match_id):
        m = _http(f"{OPENDOTA}/matches/{int(match_id)}")
        return m if m and m.get("players") else None

    def request_parse(self, match_id):
        try:
            _http(f"{OPENDOTA}/request/{int(match_id)}", data=b"")
            return True
        except ApiError:
            return False


def from_opendota(m, me_account=None, me_hero=None, items=None, heroes=None):
    items, heroes = items or {}, heroes or {}
    players = []
    for p in m.get("players") or []:
        hid = p.get("hero_id")
        players.append({
            "r": bool(p.get("isRadiant")), "hero_id": hid, "hero": heroes.get(hid) or f"herói {hid}",
            "name": p.get("personaname"), "acc": p.get("account_id"),
            "k": p.get("kills"), "d": p.get("deaths"), "a": p.get("assists"), "lh": p.get("last_hits"), "dn": p.get("denies"),
            "gpm": p.get("gold_per_min"), "xpm": p.get("xp_per_min"), "nw": p.get("net_worth"), "lvl": p.get("level"),
            "hd": p.get("hero_damage"), "td": p.get("tower_damage"), "hh": p.get("hero_healing"),
            "items": [items.get(p.get(f"item_{i}"), "") for i in range(6) if p.get(f"item_{i}")],
            "neutral": items.get(p.get("item_neutral"), "") if p.get("item_neutral") else "",
            "pos": None, "lane": OD_LANE_ROLE.get(p.get("lane_role")), "lane_res": None, "imp": None, "award": None,
        })
    return _finish({"match_id": m.get("match_id"), "src": "opendota", "dur": m.get("duration"),
                    "radiant_win": m.get("radiant_win"), "outcome": None,
                    "nw_leads": m.get("radiant_gold_adv") or [], "players": players}, me_account, me_hero)


def _finish(rep, me_account, me_hero):
    """Marca você (pela conta; sem conta pública, pelo herói) e diz se o relatório já está completo."""
    me = next((i for i, p in enumerate(rep["players"]) if me_account and p.get("acc") == me_account), None)
    if me is None and me_hero is not None:
        me = next((i for i, p in enumerate(rep["players"]) if p.get("hero_id") == me_hero), None)
    rep["me"] = me
    for i, p in enumerate(rep["players"]):
        p["me"] = i == me
        p.pop("acc", None)   # não precisa ir para o celular
    mine = rep["players"][me] if me is not None else {}
    rep["win"] = None if me is None or rep["radiant_win"] is None else mine["r"] == rep["radiant_win"]
    # STRATZ: completo quando a análise saiu (IMP); OpenDota: o que tem é o que vem
    rep["complete"] = rep["src"] == "opendota" or any(p.get("imp") is not None for p in rep["players"])
    rep["t"] = time.time()
    return rep


def fetch(match_id, token, cache_dir, me_account=None, me_hero=None, state=None):
    """Uma tentativa. state (dict) guarda entre tentativas o que já foi pedido. Devolve (relatório ou None, erro)."""
    state = state if state is not None else {}
    err = None
    if token:
        sz = Stratz(token, cache_dir)
        try:
            m = sz.match(match_id)
            if m and m.get("players"):
                return from_stratz(m, me_account, me_hero, sz.items()), None
            if not state.get("stratz_requested"):
                state["stratz_requested"] = sz.request_download(match_id) or True
        except ApiError as e:
            err = f"STRATZ: {e}"
    # sem chave, ou o STRATZ ainda não tem: OpenDota
    od = OpenDota(cache_dir)
    try:
        m = od.match(match_id)
        if m:
            rep = from_opendota(m, me_account, me_hero, od.items(), od.heroes())
            if token:
                rep["complete"] = False   # com chave, continua esperando o STRATZ (nota e lanes)
            return rep, err
        if not state.get("od_requested"):
            state["od_requested"] = od.request_parse(match_id)
    except ApiError as e:
        err = (err + "; " if err else "") + f"OpenDota: {e}"
    return None, err


# espera antes de cada tentativa (s): no STRATZ a partida aparece minutos depois do fim e a nota sai
# com a análise (~10-15 min em ranqueada; em lobbies de torneio pode passar de 1 h)
DELAYS = [60, 120, 180, 300, 300, 600, 600, 900, 1200, 1200, 1200]


async def report_job(match_id, token_fn, cache_dir, me_account, me_hero, push, delays=None, sleep=asyncio.sleep):
    """Tenta até o relatório ficar completo. push(relatório) a cada versão melhor (parcial -> completo,
    OpenDota -> STRATZ). Devolve o último relatório (ou None)."""
    state, last = {}, None
    for wait in DELAYS if delays is None else delays:
        await sleep(wait)
        rep, err = await asyncio.to_thread(fetch, match_id, token_fn(), cache_dir, me_account, me_hero, state)
        if err:
            log.info("Dota %s: %s", match_id, err)
        if rep and (last is None or (rep["src"], rep["complete"]) != (last["src"], last["complete"])):
            last = rep
            log.info("Dota %s: relatório %s (%s)", match_id, rep["src"], "completo" if rep["complete"] else "parcial")
            await push(rep, err)
        if last and last["complete"]:
            return last
    log.info("Dota %s: desisti de esperar o relatório completo", match_id)
    return last
