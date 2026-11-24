"""Leitura de dados de fora: VDF da Steam, estado de download, agenda iCal, GSI e teclas permitidas."""
import datetime as dt
import unittest
from unittest import mock

import daily
import games
import gsi
import steam
import win_input


class VdfTest(unittest.TestCase):
    def test_aninhado_e_barras(self):
        d = games.parse_vdf('"AppState" { "appid" "570" "name" "Dota 2" "UserConfig" { "path" "C:\\\\Games" } }')
        self.assertEqual(d["AppState"]["appid"], "570")
        self.assertEqual(d["AppState"]["UserConfig"]["path"], "C:\\Games")

    def test_ci_sem_diferenciar_maiusculas(self):
        d = {"AppState": {"BytesToDownload": "10"}}
        self.assertEqual(games._ci(d, "appstate", "bytestodownload"), "10")
        self.assertIsNone(games._ci(d, "appstate", "nada"))
        self.assertIsNone(games._ci(d, "appstate", "bytestodownload", "mais"))

    def test_chave_quebrada_nao_explode(self):
        self.assertIsInstance(games.parse_vdf('"a" { "b" "c" } } }'), dict)


class SteamStateTest(unittest.TestCase):
    def test_estados(self):
        self.assertEqual(steam._state(steam.F_DOWNLOADING), "baixando")
        self.assertEqual(steam._state(steam.F_DOWNLOADING | steam.F_PAUSED), "pausado")
        self.assertEqual(steam._state(steam.F_UPDATE_REQUIRED), "na fila")
        self.assertEqual(steam._state(steam.F_STAGING), "instalando")
        self.assertIsNone(steam._state(steam.F_INSTALLED))


class P:
    """Propriedade do icalendar (só .dt importa aqui)."""
    def __init__(self, v):
        self.dt = v


class AgendaTest(unittest.TestCase):
    def test_link_do_meet(self):
        e = daily._event({"SUMMARY": "Daily", "DTSTART": P(dt.datetime(2026, 11, 24, 9, 30)),
                          "DTEND": P(dt.datetime(2026, 11, 24, 9, 45)),
                          "DESCRIPTION": "Entrar: https://meet.google.com/abc-defg-hij ok"})
        self.assertEqual(e["link"], "https://meet.google.com/abc-defg-hij")
        self.assertEqual((e["start"], e["end"], e["all_day"], e["where"]), ("2026-11-24T09:30", "2026-11-24T09:45", False, ""))

    def test_sem_fim_dura_uma_hora_e_mostra_local(self):
        e = daily._event({"SUMMARY": " Dentista ", "DTSTART": P(dt.datetime(2026, 11, 24, 14, 0)), "LOCATION": "Rua A, 10"})
        self.assertEqual((e["title"], e["end"], e["link"], e["where"]), ("Dentista", "2026-11-24T15:00", None, "Rua A, 10"))

    def test_dia_inteiro(self):
        e = daily._event({"SUMMARY": "Feriado", "DTSTART": P(dt.date(2026, 11, 20))})
        self.assertEqual((e["all_day"], e["start"], e["end"]), (True, "2026-11-20T00:00", "2026-11-21T00:00"))

    def test_agenda_so_livre_ocupado(self):
        self.assertEqual(daily._event({"SUMMARY": "Busy", "DTSTART": P(dt.datetime(2026, 1, 1, 8))})["title"], "Ocupado")
        self.assertEqual(daily._event({"DTSTART": P(dt.datetime(2026, 1, 1, 8))})["title"], "(sem título)")

    def test_link_tem_que_ser_https(self):
        with self.assertRaises(ValueError):
            daily.calendar("http://exemplo.com/basic.ics")


class GsiTest(unittest.TestCase):
    def test_token_errado_ou_jogo_desconhecido_e_ignorado(self):
        got = []
        g = gsi.GSI(0, "segredo", lambda game, s: got.append(game))
        g._ingest({"auth": {"token": "outro"}, "provider": {"appid": 730}})
        g._ingest({"provider": {"appid": 730}})
        g._ingest({"auth": {"token": "segredo"}, "provider": {"appid": 440}})
        self.assertEqual(got, [])
        self.assertIsNone(g.current())

    def test_tracker_com_erro_nao_derruba_o_resumo(self):
        got = []
        tr = mock.Mock()
        tr.feed.side_effect = RuntimeError("bug")
        g = gsi.GSI(0, "t", lambda game, s: got.append(game), trackers={"cs2": tr})
        with self.assertLogs("companion", "ERROR"):
            g._ingest({"auth": {"token": "t"}, "provider": {"appid": 730}, "map": {"name": "de_dust2"}})
        self.assertEqual(got, ["cs2"])
        self.assertIsNotNone(g.current("cs2"))


class TeclasTest(unittest.TestCase):
    def test_combinacoes_validas(self):
        self.assertEqual(win_input.valid_combo("Ctrl + Shift + M"), ["ctrl", "shift", "m"])
        self.assertEqual(win_input.valid_combo("win+alt+g"), ["win", "alt", "g"])
        self.assertEqual(win_input.valid_combo("f12"), ["f12"])

    def test_fora_da_lista(self):
        for combo in ["", "+", "ctrl+ç", "f13", "ctrl+alt+del ete", "rm -rf"]:
            with self.assertRaises(ValueError, msg=combo):
                win_input.valid_combo(combo)
