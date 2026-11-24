"""Draft e build do Dota (dota_draft.py) com dados pequenos inventados. Nada aqui acessa a rede."""
import json
import os
import tempfile
import time
import unittest
from unittest import mock

import dota_draft as dd
import dota_stats
import gsi

AM, PA, LION, CM, SK, RIKI = 1, 44, 26, 5, 16, 32
HEROES = {AM: {"n": "Anti-Mage"}, PA: {"n": "Phantom Assassin"}, LION: {"n": "Lion"}, CM: {"n": "Crystal Maiden"},
          SK: {"n": "Sand King"}, RIKI: {"n": "Riki"}}


class BasicoTest(unittest.TestCase):
    def test_faixa_pelo_rank(self):
        self.assertEqual(dd.bracket_of(11), "HERALD_GUARDIAN")
        self.assertEqual(dd.bracket_of(45), "CRUSADER_ARCHON")
        self.assertEqual(dd.bracket_of(54), "LEGEND_ANCIENT")
        self.assertEqual(dd.bracket_of(80), "DIVINE_IMMORTAL")
        self.assertIsNone(dd.bracket_of(None))
        self.assertIsNone(dd.bracket_of(0))

    def test_rank_pelas_partidas(self):
        self.assertEqual(dd.median_rank([14, 23, 0, 22, None, 22, 32]), 22)
        self.assertIsNone(dd.median_rank([0, None]))

    def test_valida_o_que_vem_do_celular(self):
        self.assertEqual(dd.check_pos("3"), 3)
        for bad in (0, 6, "x", None):
            with self.assertRaises(ValueError):
                dd.check_pos(bad)
        self.assertEqual(dd.check_heroes([1, "44", 1], 5), [1, 44])
        for bad in (["abc"], [-1], [1, 2, 3, 4, 5, 6], ["1) { x }"]):
            with self.assertRaises(ValueError):
                dd.check_heroes(bad, 5)


class SuggestTest(unittest.TestCase):
    # mid: SK e Riki jogam bastante; PA quase nunca (fica fora)
    POS = {2: {SK: [1000, 540], RIKI: [800, 470], PA: [5, 3], AM: [300, 150]}}
    # do ponto de vista do inimigo: AM perde muito para Riki (vantagem -6), ganha um pouco de SK
    MU = {AM: {"vs": {RIKI: [-6.0, 0.40, 900], SK: [1.5, 0.52, 700]}, "with": {}},
          LION: {"vs": {RIKI: [2.0, 0.55, 600], SK: [-1.0, 0.48, 20]}, "with": {}},   # SK x Lion: poucas partidas
          CM: {"vs": {}, "with": {SK: [3.0, 0.56, 400], RIKI: [-1.0, 0.49, 400]}}}

    def run_(self, enemies, allies=(), mine=None, prefer=()):
        return dd.suggest(2, list(enemies), list(allies), self.POS, self.MU, HEROES, mine, prefer)

    def test_sem_inimigos_e_o_meta(self):
        r = self.run_([])
        self.assertEqual([x["n"] for x in r], ["Riki", "Sand King", "Anti-Mage"])   # 58,75% > 54% > 50%
        self.assertNotIn(PA, [x["id"] for x in r])   # 0,2% das partidas do mid

    def test_counter_sobe_e_inimigo_sai_da_lista(self):
        r = self.run_([AM, LION])
        self.assertEqual(r[0]["n"], "Riki")
        riki = r[0]
        self.assertEqual(riki["vs"], [[AM, 6.0, 60.0], [LION, -2.0, 45.0]])
        self.assertEqual(riki["adv"], 4.0)
        self.assertNotIn(AM, [x["id"] for x in r])
        sk = next(x for x in r if x["id"] == SK)
        self.assertEqual(sk["vs"][1], [LION, 0, None])   # 20 partidas: não conta

    def test_aliado_soma_metade_da_sinergia(self):
        sk = next(x for x in self.run_([], [CM]) if x["id"] == SK)
        self.assertEqual((sk["with"], sk["adv"]), ([[CM, 3.0]], 1.5))

    def test_meus_herois(self):
        r = self.run_([], mine={SK: [20, 13]})
        self.assertEqual(next(x for x in r if x["id"] == SK)["mine"], [20, 65])
        self.assertIsNone(r[0]["mine"])

    def test_preferido_entra_mesmo_raro_e_vem_marcado(self):
        r = self.run_([], prefer=[PA])
        pa = next(x for x in r if x["id"] == PA)
        self.assertTrue(pa["fav"])
        self.assertFalse(next(x for x in r if x["id"] == SK)["fav"])

    def test_bans_sao_os_counters_dos_preferidos(self):
        pos = {"1": {AM: [500, 250], PA: [400, 200]}, "2": {SK: [300, 150], RIKI: [10, 5]}, "3": {LION: [300, 150]}}
        # Riki aparece em 10 de 151 partidas (6,6%); com min_pick 10% ele sai
        mu = {AM: {"vs": {SK: [-4.0, .45, 300], LION: [-1.0, .49, 300], RIKI: [-9.0, .4, 300], PA: [2.0, .52, 300]}},
              PA: {"vs": {SK: [-2.0, .48, 300], LION: [1.0, .51, 300], RIKI: [-1, .5, 10]}}}
        b = dd.ban_suggestions([AM, PA], pos, mu, HEROES, min_pick=0.1)
        self.assertEqual([(x["n"], x["score"]) for x in b], [("Sand King", 6.0), ("Lion", 1.0)])
        self.assertEqual(b[0]["vs"], [[AM, -4.0], [PA, -2.0]])
        self.assertEqual(b[0]["pick"], 199)   # 1510 heróis = 151 partidas; SK em 300 (dados inventados, só confere a conta)
        self.assertEqual([x["n"] for x in dd.ban_suggestions([AM, PA], pos, mu, HEROES, min_pick=0.05)][0], "Riki")

    def test_posicoes_do_heroi(self):
        pos = {"1": {PA: [90, 50]}, "2": {PA: [10, 5]}, "3": {}}
        self.assertEqual(dd.hero_positions(pos, PA), {1: 0.9, 2: 0.1, 3: 0.0})
        self.assertEqual(dd.hero_positions(pos, AM), {})


ITEMS = {29: {"n": "Boots of Speed", "c": 500}, 63: {"n": "Power Treads", "c": 1400}, 44: {"n": "Tango", "c": 90},
         16: {"n": "Iron Branch", "c": 50}, 12: {"n": "Ring of Protection", "c": 175}, 36: {"n": "Magic Wand", "c": 450},
         145: {"n": "Battle Fury", "c": 4100}, 116: {"n": "Black King Bar", "c": 4050}, 112: {"n": "Abyssal Blade", "c": 6250}}
RAW = {
    "start": [{"itemId": 44, "instance": 0, "wasGiven": False, "matchCount": 1000, "winsAverage": .5},
              {"itemId": 16, "instance": 0, "wasGiven": False, "matchCount": 950, "winsAverage": .5},
              {"itemId": 16, "instance": 1, "wasGiven": False, "matchCount": 900, "winsAverage": .5},
              {"itemId": 16, "instance": 2, "wasGiven": False, "matchCount": 800, "winsAverage": .5},
              {"itemId": 16, "instance": 3, "wasGiven": False, "matchCount": 100, "winsAverage": .5},   # 4º galho: raro
              {"itemId": 12, "instance": 0, "wasGiven": False, "matchCount": 120, "winsAverage": .5},  # 12%: fica fora
              {"itemId": 36, "instance": 0, "wasGiven": True, "matchCount": 999, "winsAverage": .5}],  # dado por aliado
    "boots": [{"itemId": 63, "timeAverage": 540, "matchCount": 900, "winAverage": .55},
              {"itemId": 29, "timeAverage": 300, "matchCount": 100, "winAverage": .5}],
    "full": [{"itemId": 36, "time": 3, "matchCount": 500, "winsAverage": .5},
             {"itemId": 145, "time": 14, "matchCount": 400, "winsAverage": .5},
             {"itemId": 145, "time": 16, "matchCount": 400, "winsAverage": .6},
             {"itemId": 116, "time": 25, "matchCount": 700, "winsAverage": .6},
             {"itemId": 112, "time": 38, "matchCount": 80, "winsAverage": .8},
             {"itemId": 29, "time": 4, "matchCount": 999, "winsAverage": .5}],   # botas não entram nos itens
    "abilities": [{"abilityId": 10, "name": "Dagger", "ult": False}, {"abilityId": 11, "name": "Strike", "ult": False},
                  {"abilityId": 12, "name": "Coup", "ult": True},
                  {"abilityId": 13, "name": "Inata", "ult": False}],
    "maxlvl": [{"abilityId": 10, "level": 7, "matchCount": 900}, {"abilityId": 10, "level": 9, "matchCount": 50},
               {"abilityId": 11, "level": 12, "matchCount": 800}, {"abilityId": 12, "level": 18, "matchCount": 700},
               {"abilityId": 99, "level": 1, "matchCount": 999},   # habilidade que não é do herói
               {"abilityId": 13, "level": 1, "matchCount": 999}],  # inata de um nível só
    "talents": [{"slot": 0, "abilityId": 100, "name": "+10 Dano"}, {"slot": 1, "abilityId": 101, "name": "+5 Armadura"},
                {"slot": 2, "abilityId": 102, "name": "+20% Crítico"}, {"slot": 3, "abilityId": 103, "name": "+300 Vida"}],
    "talent": [{"abilityId": 100, "matchCount": 300, "winsAverage": .5}, {"abilityId": 101, "matchCount": 700, "winsAverage": .55},
               {"abilityId": 102, "matchCount": 500, "winsAverage": .6}],
}


class BuildTest(unittest.TestCase):
    def setUp(self):
        self.b = dd.make_build(RAW, ITEMS, total=800)

    def test_itens_iniciais(self):
        self.assertEqual([(x["name"], x["q"], x["pct"], x["c"]) for x in self.b["start"]], [("Tango", 1, 100, 90), ("Iron Branch", 3, 95, 50)])

    def test_botas(self):
        self.assertEqual([(x["name"], x["min"], x["pct"]) for x in self.b["boots"]], [("Power Treads", 9, 90), ("Boots of Speed", 5, 10)])

    def test_itens_na_ordem_do_minuto(self):
        # denominador: soma das botas (1000), maior que as 800 partidas
        self.assertEqual([(x["name"], x["min"], x["pct"]) for x in self.b["core"]], [("Battle Fury", 15, 80), ("Black King Bar", 25, 70)])
        self.assertEqual(self.b["core"][0]["wr"], 55)
        self.assertEqual([x["name"] for x in self.b["early"]], ["Magic Wand"])
        self.assertEqual([x["name"] for x in self.b["situ"]], ["Abyssal Blade"])

    def test_skills_e_talentos(self):
        self.assertEqual([(s["name"], s["max"]) for s in self.b["skills"]], [("Dagger", 7), ("Strike", 12), ("Coup", 18)])
        self.assertEqual(self.b["talents"][0], {"lvl": 10, "name": "+5 Armadura", "id": 101, "pct": 70, "wr": 55, "alt": "+10 Dano", "alt_id": 100})
        self.assertEqual(self.b["talents"][1]["pct"], 100)   # o outro lado nunca escolhido
        self.assertEqual(len(self.b["talents"]), 2)          # sem dados para 20 e 25

    def test_vazio_nao_quebra(self):
        b = dd.make_build({}, {}, 0)
        self.assertEqual((b["start"], b["core"], b["skills"], b["talents"]), ([], [], [], []))


class DraftCacheTest(unittest.TestCase):
    """Draft com o STRATZ trocado por um dublê: cache em disco, cache vencido quando cai, faixa automática."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.d = dd.Draft(lambda: "tok", self.tmp.name)
        self.calls = []
        p = mock.patch.object(dota_stats.Stratz, "gql", autospec=True, side_effect=self.gql)
        p.start()
        self.addCleanup(p.stop)
        self.down = False
        self.medal = 72

    def gql(self, _self, query, variables=None):
        self.calls.append(query)
        if self.down:
            raise dota_stats.ApiError("timeout")
        if "heroes {" in query:
            return {"constants": {"heroes": [{"id": h, "displayName": v["n"], "shortName": ""} for h, v in HEROES.items()]}}
        if "seasonRank" in query:
            return {"player": {"steamAccount": {"seasonRank": self.medal}, "heroesPerformance": [{"heroId": SK, "matchCount": 10, "winCount": 6}],
                               "matches": [{"rank": 22}, {"rank": 0}, {"rank": 14}]}}
        if "groupByPosition" in query:
            assert variables["b"] == ["DIVINE_IMMORTAL"]
            return {"heroStats": {"stats": [{"heroId": SK, "position": "POSITION_2", "matchCount": 100, "winCount": 55},
                                            {"heroId": RIKI, "position": "POSITION_2", "matchCount": 100, "winCount": 52}]}}
        if "winWeek" in query:
            assert variables["b"] == ["DIVINE", "IMMORTAL"]
            return {"heroStats": {"p2": [{"heroId": SK, "matchCount": 100, "winCount": 70}, {"heroId": RIKI, "matchCount": 100, "winCount": 45}]}}
        if "heroVsHeroMatchup" in query:
            assert f"h{AM}:" in query
            return {"heroStats": {f"h{AM}": {"advantage": [{"heroId": AM, "vs": [{"heroId2": RIKI, "synergy": -5, "winsAverage": .4, "matchCount": 500}], "with": []}]}}}
        raise AssertionError(query)

    def test_draft_completo_e_cache(self):
        r = self.d.draft(2, [AM], [], "auto", 123)
        self.assertEqual((r["bracket"], r["auto"], r["list"][0]["n"], r["list"][0]["vs"]), ("DIVINE_IMMORTAL", "medal", "Riki", [[AM, 5.0, 60.0]]))
        self.assertEqual(next(x for x in r["list"] if x["id"] == SK)["mine"], [10, 60])
        n = len(self.calls)
        self.d.mem.clear()   # servidor reiniciado: vem do disco
        self.d.draft(2, [AM], [], "auto", 123)
        self.assertEqual(len(self.calls), n)

    def test_draft_turbo_usa_o_meta_do_turbo(self):
        r = self.d.draft(2, [AM], [], "DIVINE_IMMORTAL", None, turbo=True)
        self.assertTrue(r["turbo"])
        self.assertEqual([x["n"] for x in r["list"]], ["Sand King", "Riki"])   # no Turbo, SK 70% passa o Riki
        self.assertEqual(next(x for x in r["list"] if x["id"] == RIKI)["vs"], [[AM, 5.0, 60.0]])   # counters normais

    def test_sem_posicao_so_bans(self):
        r = self.d.draft(None, [], [], "DIVINE_IMMORTAL", None, prefer=[AM])
        self.assertEqual((r["pos"], r["list"], r["prefer"]), (None, [], [AM]))
        self.assertEqual(r["bans"][0]["n"], "Riki")   # AM perde 5 para Riki

    def test_stratz_fora_usa_cache_vencido(self):
        self.d.hero_list()
        for f in os.listdir(os.path.join(self.tmp.name, "dota-cache")):
            p = os.path.join(self.tmp.name, "dota-cache", f)
            os.utime(p, (time.time() - 30 * 86400,) * 2)
        self.d.mem.clear()
        self.down = True
        with self.assertLogs("companion", "WARNING"):
            self.assertEqual(len(self.d.hero_list()), len(HEROES))

    def test_sem_cache_e_fora_do_ar_avisa(self):
        self.down = True
        with self.assertRaises(dota_stats.ApiError):
            self.d.hero_list()

    def test_sem_medalha_usa_as_partidas(self):
        self.medal = None
        self.assertEqual(self.d.bracket("auto", 123), ("HERALD_GUARDIAN", "matches"))

    def test_sem_conta_usa_a_faixa_do_meio(self):
        self.assertEqual(self.d.bracket("auto", None), ("LEGEND_ANCIENT", False))
        self.assertEqual(self.d.bracket("HERALD_GUARDIAN", None), ("HERALD_GUARDIAN", False))
        self.assertEqual(self.d.bracket("'); drop", None), ("LEGEND_ANCIENT", False))

    def test_cache_grava_json_valido(self):
        self.d.hero_list()
        with open(os.path.join(self.tmp.name, "dota-cache", "heroes.json"), encoding="utf-8") as f:
            data = json.load(f)
        self.assertEqual(data[str(AM)]["n"], "Anti-Mage")


class TurboTest(unittest.TestCase):
    def test_minutos_do_turbo(self):
        b = dd.turbo_times({"boots": [{"min": 9}], "core": [{"min": 15}, {"min": 1}], "early": [], "start": [{"q": 1}]})
        self.assertEqual((b["boots"][0]["min"], b["core"][0]["min"], b["core"][1]["min"]), (5, 8, 1))
        self.assertEqual(b["start"], [{"q": 1}])   # iniciais não têm minuto

    def test_faixas_do_winweek_cobrem_todas(self):
        self.assertEqual(set(dd.BRACKET_RANKS), set(dd.BRACKETS))


class PortuguesTest(unittest.TestCase):
    def test_talento_com_numeros_do_ingles(self):
        self.assertEqual(dd.talent_pt("+{s:bonus_duration}s de duração para Ataque Fantasma", "+0.8s Phantom Strike Duration"),
                         "+0,8s de duração para Ataque Fantasma")
        self.assertEqual(dd.talent_pt("Golpe triplo para Adaga Sufocante", "Triple Strike Stifling Dagger"), "Golpe triplo para Adaga Sufocante")
        # números não batem: fica o inglês (melhor que um texto com buraco)
        self.assertEqual(dd.talent_pt("+{s:a}/{s:b} de algo", "+10 Damage"), "+10 Damage")
        self.assertEqual(dd.talent_pt(None, "+10 Damage"), "+10 Damage")

    def test_build_em_portugues(self):
        b = dd.make_build(RAW, {**ITEMS, 145: {"n": "Battle Fury", "c": 4100, "k": "item_bfury"}}, total=800)
        dd.localize(b, {"items": {145: "Fúria de Batalha", "63": "Coturnos do Poder"}, "abil": {10: "Adaga", 100: "+{s:x} de Dano", 101: "+{s:x} de Armadura"}})
        self.assertEqual(b["core"][0]["name"], "Fúria de Batalha")
        self.assertEqual(b["core"][0]["k"], "item_bfury")   # nome interno continua (para cruzar com o GSI)
        self.assertEqual(b["boots"][0]["name"], "Coturnos do Poder")
        self.assertEqual(b["skills"][0]["name"], "Adaga")
        self.assertEqual((b["talents"][0]["name"], b["talents"][0]["alt"]), ("+5 de Armadura", "+10 de Dano"))
        self.assertEqual(b["skills"][1]["name"], "Strike")   # sem tradução: fica como veio

    def test_sem_lista_da_valve_fica_em_ingles(self):
        b = dd.localize(dd.make_build(RAW, ITEMS, 800), {})
        self.assertEqual(b["core"][0]["name"], "Battle Fury")


class PlanTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = os.path.join(self.tmp.name, "dota-plan.json")

    def test_grava_le_e_zera(self):
        p = dd.Plan(self.path)
        self.assertEqual((p.state()["pos"], p.state()["heroes"]), (None, []))
        p.set({"pos": 2})
        p.set({"heroes": [SK, "32"]})
        q = dd.Plan(self.path)   # servidor reiniciado
        self.assertEqual((q.state()["pos"], q.state()["heroes"]), (2, [SK, RIKI]))
        q.reset()
        self.assertEqual((dd.Plan(self.path).state()["pos"], dd.Plan(self.path).state()["heroes"]), (None, []))

    def test_turbo_nao_zera(self):
        p = dd.Plan(self.path)
        p.set({"turbo": True, "pos": 1})
        self.assertEqual((p.reset()["turbo"], dd.Plan(self.path).state()["turbo"]), (True, True))
        self.assertFalse(p.set({"turbo": "sim"})["turbo"])   # só true liga

    def test_tirar_a_posicao_e_validar(self):
        p = dd.Plan(self.path)
        p.set({"pos": 3})
        self.assertIsNone(p.set({"pos": None})["pos"])
        for bad in ({"pos": 9}, {"heroes": list(range(1, 8))}, {"heroes": ["x"]}):
            with self.assertRaises(ValueError):
                p.set(bad)
        self.assertEqual(p.state()["heroes"], [])   # nada mudou com os pedidos inválidos

    def test_arquivo_estragado_comeca_vazio(self):
        with open(self.path, "w", encoding="utf-8") as f:
            f.write('{"pos": 99, "heroes": "abc"')
        self.assertEqual(dd.Plan(self.path).state()["pos"], None)


class GsiHeroIdTest(unittest.TestCase):
    def test_inventario_completo_habilidades_e_talentos(self):
        s = gsi.summarize_dota({"map": {"game_state": "DOTA_GAMERULES_STATE_GAME_IN_PROGRESS"},
                                "hero": {"id": 44, "name": "npc_dota_hero_phantom_assassin", "talent_1": True, "talent_4": False},
                                "items": {"slot0": {"name": "item_bfury"}, "slot1": {"name": "empty"}, "slot6": {"name": "item_magic_wand"},
                                          "stash0": {"name": "item_ogre_axe"}, "neutral0": {"name": "empty"}},
                                "abilities": {"ability0": {"name": "phantom_assassin_stifling_dagger", "level": 2}}})
        self.assertEqual(s["inv"], ["item_bfury", "item_magic_wand", "item_ogre_axe"])
        self.assertEqual([i["k"] for i in s["items"]], ["item_bfury"])   # na tela: só os 6 slots + neutro
        self.assertEqual(s["abilities"][0]["k"], "phantom_assassin_stifling_dagger")
        self.assertEqual(s["tal"], [True] + [False] * 7)

    def test_id_do_heroi_vai_para_o_celular(self):
        s = gsi.summarize_dota({"map": {"game_state": "DOTA_GAMERULES_STATE_STRATEGY_TIME"},
                                "hero": {"id": 44, "name": "npc_dota_hero_phantom_assassin"}})
        self.assertEqual((s["hero_id"], s["hero"]), (44, "Phantom Assassin"))
        self.assertIsNone(gsi.summarize_dota({"map": {}, "hero": {"id": 0}})["hero_id"])


if __name__ == "__main__":
    unittest.main()
