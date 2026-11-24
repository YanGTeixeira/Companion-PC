"""Relatório do Dota (dota_stats.py) com respostas reais guardadas (partida pública de torneio 9103988169).

Nada aqui acessa a rede: STRATZ e OpenDota são substituídos por dublês.
"""
import asyncio
import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import dota_stats as ds

FIX = Path(__file__).resolve().parent / "fixtures"
SZ = json.loads((FIX / "stratz-match.json").read_text(encoding="utf-8"))
OD = json.loads((FIX / "opendota-match.json").read_text(encoding="utf-8"))
ITEMS = {1: "Blink Dagger", 116: "Black King Bar", 168: "Desolator"}
SAND_KING = 16   # herói do 4º jogador do Radiant (mid) nessa partida


def player(rep, hero):
    return next(p for p in rep["players"] if p["hero"] == hero)


class BasicoTest(unittest.TestCase):
    def test_conta(self):
        self.assertEqual(ds.account_id("76561198000000001"), 39734273)
        self.assertEqual(ds.account_id(39734273), 39734273)
        self.assertIsNone(ds.account_id(None))
        self.assertIsNone(ds.account_id("abc"))
        self.assertIsNone(ds.account_id(0))

    def test_lane_fisica_depende_do_lado(self):
        self.assertEqual(ds.physical_lane(True, "safe"), "bottom")
        self.assertEqual(ds.physical_lane(False, "safe"), "top")
        self.assertEqual(ds.physical_lane(True, "off"), "top")
        self.assertEqual(ds.physical_lane(False, "off"), "bottom")
        self.assertEqual(ds.physical_lane(False, "mid"), "mid")
        self.assertIsNone(ds.physical_lane(True, "jungle"))

    def test_resultado_da_lane_do_ponto_de_vista_do_jogador(self):
        self.assertEqual(ds.lane_result("RADIANT_STOMP", True), "stomp_win")
        self.assertEqual(ds.lane_result("RADIANT_STOMP", False), "stomp_loss")
        self.assertEqual(ds.lane_result("DIRE_VICTORY", False), "win")
        self.assertEqual(ds.lane_result("DIRE_VICTORY", True), "loss")
        self.assertEqual(ds.lane_result("TIE", True), "tie")
        self.assertIsNone(ds.lane_result(None, True))


class StratzTest(unittest.TestCase):
    def test_placar_lanes_e_voce_pela_conta(self):
        acc = SZ["players"][3]["steamAccountId"]
        r = ds.from_stratz(SZ, me_account=acc, items=ITEMS)
        self.assertEqual((r["src"], r["dur"], r["radiant_win"], len(r["players"])), ("stratz", 2474, False, 10))
        me = r["players"][r["me"]]
        self.assertEqual((me["hero"], me["pos"], me["lane"], me["lane_res"], me["me"]), ("Sand King", 2, "mid", "tie", True))
        self.assertFalse(r["win"])
        # lane de baixo foi atropelo do Radiant: safe do Radiant ganhou, off do Dire perdeu
        self.assertEqual(player(r, "Chaos Knight")["lane_res"], "stomp_win")
        self.assertEqual(player(r, "Underlord")["lane_res"], "stomp_loss")
        self.assertEqual(player(r, "Brewmaster")["items"][0], "Blink Dagger")
        self.assertNotIn("acc", me)   # o id das contas não vai para o celular
        self.assertEqual(len(r["nw_leads"]), 43)

    def test_sem_nota_ainda_e_parcial(self):
        self.assertFalse(ds.from_stratz(SZ)["complete"])

    def test_com_nota_e_completo(self):
        m = copy.deepcopy(SZ)
        for i, p in enumerate(m["players"]):
            p["imp"], p["award"] = i - 4, "MVP" if i == 5 else "NONE"
        m["analysisOutcome"] = "COMEBACK"
        r = ds.from_stratz(m, me_hero=SAND_KING)
        self.assertTrue(r["complete"])
        self.assertEqual(r["players"][r["me"]]["imp"], -1)
        self.assertEqual(player(r, "Kez")["award"], "MVP")
        self.assertIsNone(player(r, "Brewmaster")["award"])
        self.assertEqual(r["outcome"], "virada")

    def test_sem_conta_acha_pelo_heroi(self):
        r = ds.from_stratz(SZ, me_account=123, me_hero=SAND_KING)
        self.assertEqual(r["players"][r["me"]]["hero"], "Sand King")

    def test_sem_conta_nem_heroi(self):
        r = ds.from_stratz(SZ)
        self.assertIsNone(r["me"])
        self.assertIsNone(r["win"])


class OpenDotaTest(unittest.TestCase):
    def test_placar_sem_nota_nem_lanes(self):
        r = ds.from_opendota(OD, me_hero=SAND_KING, items=ITEMS, heroes={SAND_KING: "Sand King"})
        me = r["players"][r["me"]]
        self.assertEqual((r["src"], r["complete"], me["hero"], me["lane"], me["lane_res"], me["imp"]),
                         ("opendota", True, "Sand King", "mid", None, None))
        self.assertEqual(r["players"][0]["hero"][:5], "herói")   # sem nome conhecido: não quebra


class FetchTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        for name in ("match", "request_download", "items"):
            p = mock.patch.object(ds.Stratz, name)
            setattr(self, "sz_" + name, p.start())
            self.addCleanup(p.stop)
        for name in ("match", "request_parse", "items", "heroes"):
            p = mock.patch.object(ds.OpenDota, name)
            setattr(self, "od_" + name, p.start())
            self.addCleanup(p.stop)
        self.sz_items.return_value = self.od_items.return_value = ITEMS
        self.od_heroes.return_value = {}

    def fetch(self, token="tok", state=None):
        return ds.fetch(9103988169, token, self.tmp.name, me_hero=SAND_KING, state=state)

    def test_stratz_tem_a_partida(self):
        self.sz_match.return_value = SZ
        r, err = self.fetch()
        self.assertEqual((r["src"], err), ("stratz", None))
        self.od_match.assert_not_called()

    def test_stratz_ainda_nao_tem_pede_download_uma_vez_e_usa_opendota_como_parcial(self):
        self.sz_match.return_value = None
        self.od_match.return_value = OD
        state = {}
        r, _ = self.fetch(state=state)
        self.assertEqual((r["src"], r["complete"]), ("opendota", False))   # com chave, ainda espera o STRATZ
        self.fetch(state=state)
        self.sz_request_download.assert_called_once()

    def test_sem_chave_usa_opendota_e_pede_parse_uma_vez(self):
        self.od_match.return_value = None
        state = {}
        self.assertEqual(self.fetch("", state), (None, None))
        self.fetch("", state)
        self.od_request_parse.assert_called_once()
        self.sz_match.assert_not_called()
        self.od_match.return_value = OD
        r, _ = self.fetch("", state)
        self.assertTrue(r["complete"])   # sem chave, o OpenDota é o que vem

    def test_chave_recusada_cai_no_opendota_com_o_erro(self):
        self.sz_match.side_effect = ds.ApiError("chave do STRATZ recusada")
        self.od_match.return_value = OD
        r, err = self.fetch()
        self.assertEqual(r["src"], "opendota")
        self.assertIn("recusada", err)

    def test_os_dois_fora_do_ar(self):
        self.sz_match.side_effect = ds.ApiError("timeout")
        self.od_match.side_effect = ds.ApiError("HTTP 502")
        r, err = self.fetch()
        self.assertIsNone(r)
        self.assertIn("STRATZ", err)
        self.assertIn("OpenDota", err)


class JobTest(unittest.TestCase):
    """A espera entre tentativas: manda só versões melhores e para quando o relatório fica completo."""

    def run_job(self, results, delays=(1, 1, 1, 1, 1)):
        pushed, waits = [], []
        seq = iter(results)

        async def push(rep, err):
            pushed.append((rep["src"], rep["complete"]))

        async def sleep(s):
            waits.append(s)
        with mock.patch.object(ds, "fetch", side_effect=lambda *a, **k: next(seq)), self.assertLogs("companion", "INFO"):
            last = asyncio.run(ds.report_job(1, lambda: "tok", "/tmp", None, SAND_KING, push, list(delays), sleep))
        return pushed, waits, last

    def rep(self, src, complete):
        return {"src": src, "complete": complete}

    def test_parcial_depois_completo(self):
        pushed, waits, last = self.run_job([(None, "ainda não"), (self.rep("opendota", False), None),
                                            (self.rep("opendota", False), None), (self.rep("stratz", True), None)])
        self.assertEqual(pushed, [("opendota", False), ("stratz", True)])   # a repetida não é reenviada
        self.assertEqual(len(waits), 4)   # parou ao completar
        self.assertTrue(last["complete"])

    def test_desiste_depois_das_tentativas(self):
        pushed, waits, last = self.run_job([(None, "x")] * 3, delays=(5, 6, 7))
        self.assertEqual((pushed, waits, last), ([], [5, 6, 7], None))

    def test_intervalos_padrao_cobrem_duas_horas(self):
        self.assertGreaterEqual(sum(ds.DELAYS), 100 * 60)
        self.assertLessEqual(ds.DELAYS[0], 60)
