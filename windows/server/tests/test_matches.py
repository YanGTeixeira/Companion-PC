"""Histórico de partidas (matches.py): médias, sequência, relatório e o acompanhamento pelo GSI."""
import itertools
import unittest
from unittest import mock

import matches


class FakeClock:
    """time.time() que sempre anda: no Windows duas chamadas seguidas podem dar o mesmo valor."""
    def __init__(self, start=1_700_000_000.0):
        self.c = itertools.count()
        self.start = start

    def __call__(self):
        return self.start + next(self.c)


class StoreTest(unittest.TestCase):
    def setUp(self):
        p = mock.patch.object(matches.time, "time", FakeClock())
        p.start()
        self.addCleanup(p.stop)
        self.store = matches.Store(":memory:")

    def test_post_match_compara_com_media_do_mapa_e_geral(self):
        self.store.add("cs2", "a", "de_dust2", True, {"k": 20, "d": 10, "adr": 90})
        self.store.add("cs2", "b", "de_dust2", False, {"k": 10, "d": 20, "adr": 70})
        self.store.add("cs2", "c", "de_mirage", True, {"k": 30, "d": 5, "adr": 120})
        pm = self.store.post_match("cs2", "d", "de_dust2", True, {"k": 25})
        self.assertEqual(pm["n_same"], 2)
        self.assertEqual(pm["avg_same"], {"k": 15.0, "d": 15.0, "adr": 80.0})
        self.assertEqual(pm["n_all"], 3)
        self.assertEqual(pm["avg_all"]["k"], 20.0)
        self.assertEqual(pm["winrate_same"], 50)

    def test_post_match_ignora_a_propria_partida(self):
        self.store.add("cs2", "x", "de_dust2", True, {"k": 99})
        pm = self.store.post_match("cs2", "x", "de_dust2", True, {"k": 99})
        self.assertEqual(pm["n_all"], 0)
        self.assertEqual(pm["avg_all"], {})
        self.assertIsNone(pm["winrate_same"])

    def test_sequencia_de_vitorias(self):
        for key, win in [("1", False), ("2", True), ("3", True)]:
            self.store.add("dota2", key, "Pudge", win, {})
        self.assertEqual(self.store.post_match("dota2", "4", "Pudge", True, {})["streak"], 3)  # 3 + as 2 de antes
        self.assertEqual(self.store.post_match("dota2", "4", "Pudge", False, {})["streak"], 1)
        self.assertEqual(self.store.post_match("dota2", "4", "Pudge", None, {})["streak"], 0)

    def test_empate_interrompe_a_sequencia(self):
        self.store.add("cs2", "1", "de_nuke", True, {})
        self.store.add("cs2", "2", "de_nuke", None, {})
        self.assertEqual(self.store.post_match("cs2", "3", "de_nuke", True, {})["streak"], 1)

    def test_add_chama_on_saved_com_o_resumo(self):
        got = []
        self.store.on_saved = got.append
        self.store.add("cs2", "k1", "de_inferno", True, {"k": 1})
        self.assertEqual(len(got), 1)
        self.assertEqual(got[0]["title"], "de_inferno")

    def test_on_saved_com_erro_nao_derruba_o_salvamento(self):
        self.store.on_saved = mock.Mock(side_effect=RuntimeError("x"))
        with self.assertLogs("companion", "ERROR"):
            self.store.add("cs2", "k1", "de_inferno", True, {})
        self.assertEqual(self.store.report("cs2")["total"], 1)

    def test_mesma_chave_substitui(self):
        self.store.add("cs2", "k", "de_dust2", False, {})
        self.store.add("cs2", "k", "de_dust2", True, {})
        r = self.store.report("cs2")
        self.assertEqual(r["total"], 1)
        self.assertEqual(r["winrate"], 100)

    def test_report_agrupa_por_mapa(self):
        self.store.add("cs2", "1", "de_dust2", True, {"k": 10, "d": 5, "a": 2, "hs_pct": 40, "adr": 80})
        self.store.add("cs2", "2", "de_dust2", False, {"k": 20, "d": 15, "a": 4, "hs_pct": 60, "adr": None})
        self.store.add("cs2", "3", "de_mirage", True, {"k": 5})
        r = self.store.report("cs2")
        self.assertEqual(r["total"], 3)
        self.assertEqual(r["winrate"], 67)
        dust = r["groups"][0]
        self.assertEqual((dust["name"], dust["n"], dust["winrate"]), ("de_dust2", 2, 50))
        self.assertEqual((dust["k"], dust["d"], dust["a"]), (15.0, 10.0, 3.0))
        self.assertEqual((dust["x"], dust["y"]), (50, 80))   # ADR ausente não entra na média
        self.assertEqual(r["recent"][0]["title"], "de_mirage")  # mais recente primeiro
        self.assertIsNone(r["groups"][1]["x"])

    def test_report_vazio(self):
        r = self.store.report("dota2")
        self.assertEqual((r["total"], r["winrate"], r["groups"]), (0, None, []))


def cs_payload(rnd, phase="live", wins=None, kills=0, hs=0, dmg=0, ct=0, t=0, me=True):
    return {
        "provider": {"steamid": "ME"},
        "map": {"name": "de_dust2", "mode": "competitive", "round": rnd, "phase": phase,
                "round_wins": wins or {}, "team_ct": {"score": ct}, "team_t": {"score": t}},
        "player": {"steamid": "ME" if me else "OUTRO", "team": "CT",
                   "state": {"round_kills": kills, "round_killhs": hs, "round_totaldmg": dmg, "money": 800},
                   "match_stats": {"kills": 7, "deaths": 3, "assists": 1, "mvps": 2, "score": 20}},
    }


class CsTrackerTest(unittest.TestCase):
    def setUp(self):
        self.store = mock.Mock()
        self.tr = matches.CsTracker(self.store)

    def test_rounds_com_os_seus_numeros_e_estatisticas(self):
        self.tr.feed(cs_payload(0), {})
        self.tr.feed(cs_payload(1, wins={"1": "ct_win_elimination"}, kills=2, hs=1, dmg=150), {})
        s = self.tr.feed(cs_payload(2, wins={"1": "ct_win_elimination", "2": "t_win_bomb"}, kills=0, hs=0, dmg=50), {})
        self.assertEqual([(r["n"], r["side"], r["r"], r["win"]) for r in s["rounds"]],
                         [(1, "CT", "E", True), (2, "T", "B", False)])
        self.assertEqual(s["hs_pct"], 50)
        self.assertEqual(s["adr"], 100)

    def test_rounds_de_antes_de_abrir_ficam_sem_numeros(self):
        s = self.tr.feed(cs_payload(3, wins={"1": "ct_win_time", "2": "ct_win_defuse"}), {})
        self.assertTrue(all(r["dmg"] is None and r["win"] is None for r in s["rounds"]))
        self.assertIsNone(s["hs_pct"])

    def test_morto_mostra_os_seus_numeros(self):
        self.tr.feed(cs_payload(1), {})
        s = self.tr.feed(cs_payload(1, me=False), {"spectating": True})
        self.assertEqual((s["k"], s["d"], s["team"]), (7, 3, "CT"))

    def test_fim_de_jogo_salva_uma_vez(self):
        self.tr.feed(cs_payload(1), {})
        end = cs_payload(25, "gameover", wins={"1": "ct_win_elimination"}, ct=13, t=11)
        self.tr.feed(end, {"map": "Dust II"})
        self.tr.feed(end, {"map": "Dust II"})
        self.store.add.assert_called_once()
        game, key, title, win, data = self.store.add.call_args.args
        self.assertEqual((game, title, win, data["mine"], data["theirs"], data["k"]), ("cs2", "Dust II", True, 13, 11, 7))

    def test_placar_empatado_e_empate(self):
        self.tr.feed(cs_payload(1), {})
        self.tr.feed(cs_payload(30, "gameover", wins={"1": "t_win_elimination"}, ct=15, t=15), {})
        self.assertIsNone(self.store.add.call_args.args[3])

    def test_mapa_novo_zera(self):
        self.tr.feed(cs_payload(2, wins={"1": "ct_win_time"}), {})
        other = cs_payload(1)
        other["map"]["name"] = "de_inferno"
        self.assertEqual(self.tr.feed(other, {})["rounds"], [])

    def test_sem_mapa_nao_quebra(self):
        self.assertEqual(self.tr.feed({}, {})["rounds"], [])


def dota_payload(clock, matchid="42", events=None, win_team=None, state="DOTA_GAMERULES_STATE_GAME_IN_PROGRESS"):
    return ({"map": {"matchid": matchid, "clock_time": clock, "game_time": clock + 90, "win_team": win_team},
             "player": {"gold": 600, "gpm": 450, "xpm": 500, "last_hits": 30, "denies": 4, "team_name": "radiant",
                        "kills": 5, "deaths": 2, "assists": 9},
             "hero": {"level": 12}, "events": events or []},
            {"raw_state": state, "hero": "Pudge", "items": [{"name": "item_blink", "slot": "slot0"},
                                                             {"name": "item_tango", "slot": "stash0"}]})


class DotaTrackerTest(unittest.TestCase):
    def setUp(self):
        self.store = mock.Mock()
        self.tr = matches.DotaTracker(self.store)

    def test_uma_amostra_por_minuto(self):
        for c in (60, 65, 130):
            s = self.tr.feed(*dota_payload(c))
        self.assertEqual([x["m"] for x in s["series"]], [1, 2])

    def test_roshan_pelo_evento_usa_o_relogio_da_partida(self):
        d, s = dota_payload(600, events=[{"event_type": "roshan_killed", "game_time": 640}])
        with self.assertLogs("companion", "INFO"):
            s = self.tr.feed(d, s)
        self.assertEqual(s["marks"], {"rosh": 550, "aegis": 550})   # 640 - (690 - 600)

    def test_marcacao_manual(self):
        self.tr.feed(*dota_payload(300))
        self.tr.mark("rosh")
        self.assertEqual(self.tr.marks, {"rosh": 300, "aegis": 300})
        self.tr.mark("aegis", clear=True)
        self.assertEqual(self.tr.marks, {"rosh": 300})
        with self.assertRaises(ValueError):
            self.tr.mark("torre")

    def test_fim_salva_com_vitoria_e_itens(self):
        self.tr.feed(*dota_payload(1800, win_team="radiant"))
        self.tr.feed(*dota_payload(1801, win_team="radiant"))
        self.store.add.assert_called_once()
        game, key, title, win, data = self.store.add.call_args.args
        self.assertEqual((game, key, title, win), ("dota2", "dota2:42", "Pudge", True))
        self.assertEqual(data["items"], ["item_blink"])

    def test_partida_nova_zera(self):
        self.tr.feed(*dota_payload(120))
        s = self.tr.feed(*dota_payload(60, matchid="43"))
        self.assertEqual([x["m"] for x in s["series"]], [1])

    def test_sem_partida_nao_faz_nada(self):
        s = self.tr.feed(*dota_payload(100, matchid="0"))
        self.assertEqual(s["series"], [])
