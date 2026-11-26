"""Conquistas, metas do dia, XP e nível."""
import sys
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import conquistas as cq  # noqa: E402

H, M = 3600, 60


def facts(scr=4 * H, foc=0, cats=None, hrs=None, talk=None, m=None):
    return {"scr": scr, "cats": cats or {"Trabalho": scr}, "hrs": hrs or [0] * 24, "foc": foc, "talk": talk or {}, "m": m or []}


def match(g="dota2", w=1, k=5, d=2, a=5, **kw):
    return {"g": g, "w": w, "k": k, "d": d, "a": a, "t": kw.pop("t", 0), **kw}


class FakeDays:
    """facts_fn de mentira: um dicionário dia -> facts (dia sem dado = PC desligado)."""

    def __init__(self, days):
        self.days = days
        self.calls = []

    def __call__(self, day):
        self.calls.append(day)
        return self.days.get(day, facts(scr=0, cats={}))


def d(n, ref="2026-11-26"):
    return (date.fromisoformat(ref) - timedelta(days=n)).isoformat()


class NivelTest(unittest.TestCase):
    def test_faixas(self):
        self.assertEqual(cq.level_of(0), (1, 0, 100))
        self.assertEqual(cq.level_of(99), (1, 0, 100))
        self.assertEqual(cq.level_of(100), (2, 100, 300))
        self.assertEqual(cq.level_of(4500)[0], 10)


class MetasTest(unittest.TestCase):
    def test_sorteio_fixo_por_dia_e_foco_sempre(self):
        base = cq.baseline([facts(scr=6 * H, foc=60, cats={"Social": H, "Trabalho": 3 * H, "Jogos": 2 * H}, m=[match()])] * 5)
        a, b = cq.pick_metas("2026-11-26", base), cq.pick_metas("2026-11-26", base)
        self.assertEqual([m[0] for m in a], [m[0] for m in b])
        self.assertEqual(a[0][0], "foco")
        self.assertEqual(len(a), 3)
        self.assertEqual(len({m[0] for m in a}), 3)

    def test_sem_historico_so_foco_de_25(self):
        base = cq.baseline([])
        metas = cq.eval_metas("2026-11-26", facts(foc=30), base, False)
        self.assertEqual([(m["id"], m["target"], m["status"]) for m in metas], [("foco", 25, "done")])

    def test_alvo_acompanha_a_media(self):
        base = cq.baseline([facts(foc=100)] * 3)
        self.assertEqual(cq.eval_metas("x", facts(), base, False)[0]["target"], 120)
        base = cq.baseline([facts(foc=500)])
        self.assertEqual(cq.eval_metas("x", facts(), base, False)[0]["target"], 180)   # teto

    def test_meta_de_maximo_so_fecha_no_fim_do_dia(self):
        base = cq.baseline([facts(scr=6 * H)] * 3)
        tela = next(m for m in cq.METAS if m[0] == "tela")
        f = facts(scr=3 * H)
        target = tela[5](base)
        self.assertEqual(target, 5 * H + 30 * M)   # 90% de 6 h, arredondado a 15 min
        orig = cq.pick_metas
        cq.pick_metas = lambda day, base: [tela]
        try:
            self.assertEqual(cq.eval_metas("x", f, base, False)[0]["status"], "ok")
            self.assertEqual(cq.eval_metas("x", f, base, True)[0]["status"], "done")
            self.assertEqual(cq.eval_metas("x", facts(scr=6 * H), base, False)[0]["status"], "failed")
            self.assertEqual(cq.eval_metas("x", facts(scr=10 * M), base, True)[0]["status"], "skip")  # PC quase desligado
        finally:
            cq.pick_metas = orig

    def test_xp_do_dia(self):
        metas = [{"status": "done"}] * 3
        f = facts(foc=200, m=[match(w=1), match(w=0)])
        self.assertEqual(cq.day_xp(f, metas), 300 + 20 + 20 + 150 + 50)
        self.assertEqual(cq.day_xp(facts(), [{"status": "open"}]), 0)


class AgregadoTest(unittest.TestCase):
    def test_sequencias_e_partidas(self):
        done = [{"status": "done"}] * 3
        none = [{"status": "open"}]
        ms = [match(w=1, t=1), match(w=1, t=2, d=0), match(w=0, t=3), match(w=1, t=4),
              match(g="cs2", w=1, t=5, k=20, d=1, a=0, hs=65, mvp=6),
              match(g="dota2", w=1, t=6, lh=400, dur=40 * M)]
        days = [("a", facts(foc=30, m=ms[:3]), done), ("b", facts(), done), ("c", facts(), none),
                ("d", facts(foc=200, hrs=[0, 0, 0, 1000, 0, 0, 0] + [0] * 17, m=ms[3:], talk={"meet": 3700}), done)]
        a = cq.aggregate(days)
        self.assertEqual((a["best_streak"], a["perfect"], a["metas"]), (2, 3, 9))
        self.assertEqual((a["wins"], a["win_streak"], a["deathless"]), (5, 3, 1))
        self.assertEqual((a["focus_total"], a["focus_day"]), (230, 200))
        self.assertEqual((a["owl"], a["early"]), (1, 0))
        self.assertEqual((a["kda"], a["hs"], a["mvp"], a["lh_min"]), (20, 65, 6, 10))
        self.assertGreater(a["talk_day"], 60)

    def test_detox_nao_conta_primeiro_dia_nem_hoje(self):
        short = facts(scr=H)
        self.assertEqual(cq.aggregate([("a", short, [])])["detox"], 0)                     # 1º dia: pela metade
        self.assertEqual(cq.aggregate([("a", facts(), []), ("b", short, [])], "b")["detox"], 0)   # hoje não acabou
        self.assertEqual(cq.aggregate([("a", facts(), []), ("b", short, [])], "c")["detox"], 1)

    def test_sequencia_atual_nao_quebra_hoje(self):
        done, none = [{"status": "done"}] * 2, []
        days = [(d(3), {}, none), (d(2), {}, done), (d(1), {}, done), (d(0), {}, none)]
        self.assertEqual(cq.current_streak(days, d(0)), 2)
        days[-1] = (d(0), {}, done)
        self.assertEqual(cq.current_streak(days, d(0)), 3)
        self.assertEqual(cq.current_streak(days[:2], d(0)), 0)   # ontem não cumpriu: zerou


class ConquistasTest(unittest.TestCase):
    def setUp(self):
        self.path = Path(tempfile.mkdtemp()) / "conquistas.db"

    def test_primeira_vez_e_silenciosa_depois_avisa(self):
        days = FakeDays({d(2): facts(foc=30), d(1): facts(foc=40)})
        c = cq.Conquistas(self.path, days, lambda: d(2))
        st, ev = c.refresh(d(0))
        self.assertEqual(ev, [])                                   # histórico: sem enxurrada de avisos
        unlocked = {x["id"] for x in st["conq"] if x["day"]}
        self.assertIn("foco1", unlocked)
        self.assertIn("meta1", unlocked)
        self.assertGreater(st["xp"], 0)
        # hoje: vence sem morrer e faz o foco da meta
        days.days[d(0)] = facts(foc=60, m=[match(w=1, d=0)])
        st2, ev = c.refresh(d(0))
        kinds = {(e["kind"], e.get("id")) for e in ev}
        self.assertIn(("conq", "imortal"), kinds)
        self.assertIn(("conq", "vit1"), kinds)
        self.assertIn(("meta", "foco"), kinds)
        self.assertGreater(st2["xp"], st["xp"])
        self.assertEqual(c.summary()["level"], st2["level"])
        # de novo, sem mudança: nada a avisar
        self.assertEqual(c.refresh(d(0))[1], [])

    def test_dias_passados_ficam_fixos(self):
        days = FakeDays({d(1): facts(foc=30)})
        c = cq.Conquistas(self.path, days, lambda: d(1))
        c.refresh(d(0))
        days.calls.clear()
        days.days[d(1)] = facts(foc=999)            # o focus.json mudou/perdeu dias: o resumo guardado vale
        st, _ = c.refresh(d(0))
        self.assertEqual(days.calls, [d(0)])         # só hoje é refeito
        self.assertEqual(next(x for x in st["conq"] if x["id"] == "foco3h")["day"], None)
        # outro processo (servidor reiniciado) lê o mesmo banco
        c2 = cq.Conquistas(self.path, days, lambda: d(1))
        self.assertEqual(c2.refresh(d(0))[0]["xp"], st["xp"])

    def test_build_facts(self):
        rep = {"total": 7200, "cats": [{"cat": "Jogos", "secs": 3600}], "hours": [1] * 24}
        f = cq.build_facts(rep, 25, {"meet": 61.4}, [(100.0, "cs2", 1, {"k": 3, "d": 1, "a": 2, "hs_pct": 50, "mvp": 1})])
        self.assertEqual(f["scr"], 7200)
        self.assertEqual(f["cats"], {"Jogos": 3600})
        self.assertEqual(f["talk"], {"meet": 61})
        self.assertEqual(f["m"][0]["hs"], 50)
        self.assertEqual(f["m"][0]["w"], 1)


if __name__ == "__main__":
    unittest.main()
