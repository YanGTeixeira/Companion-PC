"""Retrospectiva do mês."""
import sys
import tempfile
import time
import unittest
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import conquistas as cq  # noqa: E402
import retro  # noqa: E402

H, M = 3600, 60


def facts(scr=4 * H, foc=0, cats=None, hrs=None, talk=None, m=None):
    hrs = hrs or [0] * 9 + [scr // 8] * 8 + [0] * 7
    return {"scr": scr, "cats": cats or {"Trabalho": scr}, "hrs": hrs, "foc": foc, "talk": talk or {}, "m": m or []}


def ts(day, h=20):
    return time.mktime(date.fromisoformat(day).timetuple()) + h * H


class LimitesTest(unittest.TestCase):
    def test_meses(self):
        self.assertEqual(retro.month_bounds("2026-02"), (date(2026, 2, 1), date(2026, 2, 28)))
        self.assertEqual(retro.month_bounds("2026-12")[1], date(2026, 12, 31))
        self.assertEqual(retro.prev_month("2026-01"), "2025-12")


class PersonaTest(unittest.TestCase):
    def test_regras(self):
        h = [0] * 24
        self.assertEqual(retro.persona(h, {}, 0, 0, 0)["name"], "Fantasma")
        night = [100] * 5 + [0] * 17 + [100] * 2
        self.assertEqual(retro.persona(night, {"Trabalho": 700}, 700, 0, 0)["name"], "Coruja")
        day = [0] * 9 + [100] * 10 + [0] * 5
        self.assertEqual(retro.persona(day, {"Jogos": 600, "Trabalho": 400}, 1000, 0, 0)["name"], "Gamer de carteirinha")
        self.assertEqual(retro.persona(day, {"Trabalho": 400, "Outros": 600}, 1000, 0, 0)["name"], "Equilibrado")
        p = retro.persona(day, {"Social": 500, "Outros": 500}, 1000, 0, 0)
        self.assertEqual((p["name"], p["why"]), ("Rolador de feed", "50% foi rede social e vídeo"))


class BuildTest(unittest.TestCase):
    def test_mes_completo(self):
        done = [{"status": "done"}] * 3
        days = [("2026-11-02", facts(scr=6 * H, foc=90, cats={"Trabalho": 4 * H, "Jogos": 2 * H}, talk={"meet": 600}), done, 300),
                ("2026-11-03", facts(scr=2 * H, foc=30), done, 200),
                ("2026-11-04", facts(scr=0, cats={}), [], 0)]
        matches = [(ts("2026-11-02"), "dota2", "Lina", 1, {"k": 10, "d": 1, "a": 10}),
                   (ts("2026-11-02", 21), "dota2", "Lina", 0, {"k": 2, "d": 8, "a": 3}),
                   (ts("2026-11-03"), "dota2", "Axe", 1, {"k": 5, "d": 5, "a": 5}),
                   (ts("2026-11-03", 21), "cs2", "de_mirage", None, {"k": 20, "d": 15, "a": 2})]
        apps = {"apps": [{"name": "VS Code", "secs": 5 * H, "cat": "Trabalho"}, {"name": "Dota 2", "secs": 2 * H, "cat": "Jogos"}]}
        conq = [{"id": "vit1", "name": "Primeira vitória", "tier": "bronze", "xp": 50, "day": "2026-11-02"}]
        r = retro.build("2026-11", days, 50, conq, apps, matches, prev_days=[("2026-10-02", facts(scr=4 * H), [], 0)],
                        today="2026-12-01")
        self.assertEqual(r["label"], "novembro de 2026")
        self.assertFalse(r["partial"])
        self.assertEqual((r["days_used"], r["screen"]["total"], r["screen"]["avg"]), (2, 8 * H, 4 * H))
        self.assertEqual(r["screen"]["best_day"], {"day": "2026-11-02", "secs": 6 * H})
        self.assertEqual(r["screen"]["prev_total"], 4 * H)
        self.assertEqual(r["screen"]["weekday"], "segunda")         # 02/11/2026 é segunda
        self.assertEqual(r["cats"][0], {"cat": "Trabalho", "secs": 6 * H, "pct": 75})
        self.assertEqual(r["focus"]["min"], 120)
        self.assertEqual((r["focus"]["metas_done"], r["focus"]["best_streak"], r["focus"]["perfect"]), (6, 2, 2))
        g = r["games"]
        self.assertEqual((g["matches"], g["wins"], g["losses"], g["winrate"]), (4, 2, 1, 67))
        self.assertEqual(g["fav"]["dota2"], {"title": "Lina", "n": 2, "w": 1})
        self.assertEqual(g["fav"]["cs2"]["title"], "de_mirage")
        self.assertEqual((g["best"]["title"], g["best"]["kda"]), ("Lina", 20.0))
        self.assertEqual(g["top"], [{"name": "Dota 2", "secs": 2 * H}])
        self.assertEqual(r["talk"], {"total": 600, "meet": 600, "game": 0})
        self.assertEqual(r["xp"], {"month": 550, "level_start": 2, "level_end": 6})   # 1.21: 17·N·(N−1)
        self.assertEqual(r["persona"]["name"], "Workaholic")

    def test_mes_vazio(self):
        r = retro.build("2026-10", [], 0, [], {}, [], today="2026-10-05")
        self.assertTrue(r["partial"])
        self.assertEqual((r["screen"]["total"], r["screen"]["best_day"], r["games"]["winrate"]), (0, None, None))
        self.assertEqual(r["persona"]["name"], "Fantasma")


class MonthDataTest(unittest.TestCase):
    def test_xp_antes_e_conquistas_do_mes(self):
        days = {"2026-10-30": facts(foc=60), "2026-11-01": facts(foc=60)}
        c = cq.Conquistas(Path(tempfile.mkdtemp()) / "c.db", lambda d: days.get(d, facts(scr=0, cats={})), lambda: "2026-10-30")
        c.refresh("2026-11-02")
        inside, before, got, all_days = c.month_data("2026-11")
        self.assertEqual([x[0] for x in inside], ["2026-11-01", "2026-11-02"])
        self.assertEqual(before, sum(x[3] for x in c._calc["days"] if x[0] < "2026-11-01"))
        self.assertTrue(all(g["day"][:7] == "2026-11" for g in got))
        self.assertEqual(all_days[0], "2026-10-30")
        self.assertIsNone(c.flag("retro_seen"))
        c.flag("retro_seen", "2026-10")
        self.assertEqual(c.flag("retro_seen"), "2026-10")


if __name__ == "__main__":
    unittest.main()


class AnoTest(unittest.TestCase):
    """1.20: retrospectiva do ano ("Sua jornada")."""

    def test_anos_abertos(self):
        days = ["2025-12-30", "2026-03-01", "2026-11-26"]
        self.assertEqual(retro.years_open(days, "2026-11-26"), [2025])
        self.assertEqual(retro.years_open(days, "2026-12-15"), [2026, 2025])
        self.assertEqual(retro.years_open(days, "2027-01-01"), [2026, 2025])
        self.assertEqual(retro.years_open(["2027-01-02"], "2027-01-02"), [])

    def test_ano(self):
        done = [{"status": "done"}] * 2
        days = [("2026-10-10", facts(scr=5 * H, foc=60), done, 400), ("2026-11-02", facts(scr=3 * H, foc=600), done, 900),
                ("2026-11-03", facts(scr=2 * H, foc=30), [], 100)]
        conq = [{"id": "vit1", "name": "Primeira vitória", "tier": "bronze", "xp": 50, "day": "2026-10-10"}]
        col = {"credits": 99, "sets": [], "events": [], "items": 10, "items_total": 161}
        r = retro.build_year(2026, date(2026, 10, 10), date(2026, 12, 31), days, 0, conq, {"apps": []}, [], col, today="2026-12-20")
        self.assertEqual((r["kind"], r["month"], r["since"], r["partial"]), ("year", "2026", "2026-10-10", True))
        self.assertEqual([m["month"] for m in r["months_sum"]], ["2026-10", "2026-11"])
        self.assertEqual(r["months_sum"][0]["xp"], 450)                 # dia + conquista do mês
        self.assertEqual(r["best_month"]["month"], "2026-11")
        self.assertEqual(r["collection"]["credits"], 99)
        self.assertEqual(r["xp"]["month"], 1450)
        self.assertEqual(r["days_in_month"], 83)
        # 11 h de foco num período de quase 3 meses: não é "Monge do foco" (20 h por mês)
        self.assertNotEqual(r["persona"]["name"], "Monge do foco")
        self.assertFalse(retro.build_year(2026, date(2026, 10, 10), date(2026, 12, 31), days, 0, conq, {"apps": []}, [], col,
                                          today="2027-01-01")["partial"])
