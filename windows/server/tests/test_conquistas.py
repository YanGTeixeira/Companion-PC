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
        self.assertEqual(cq.level_of(0), (1, 0, 34))                # 1.21: 17·N·(N−1)
        self.assertEqual(cq.level_of(33), (1, 0, 34))
        self.assertEqual(cq.level_of(34), (2, 34, 102))
        self.assertEqual(cq.level_of(1530)[0], 10)
        self.assertEqual(cq.level_of(14789)[0], 29)
        self.assertEqual(cq.level_of(14790), (30, 14790, 14790))    # o máximo: a faixa fecha
        self.assertEqual(cq.level_of(10 ** 7)[0], 30)


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


class Regras118Test(unittest.TestCase):
    """Congelamento, multiplicador, dia em dobro, desafios, chefão, recompensas e secretas."""

    def setUp(self):
        self.path = Path(tempfile.mkdtemp()) / "conquistas.db"

    def test_congelamento_salva_um_dia(self):
        ok, no = [{"status": "done"}] * 2, []
        days = [(d(i), {}, ok) for i in range(20, 6, -1)]            # 14 dias seguidos: 2 congelamentos
        days += [(d(6), {}, no), (d(5), {}, ok), (d(4), {}, no), (d(3), {}, no), (d(2), {}, ok)]
        sim = cq.streak_sim(days, d(0), since=d(30))
        self.assertTrue(sim["per"][d(6)][1])                       # dia perdido salvo
        self.assertEqual(sim["used"], 2)
        self.assertEqual(sim["streak"], 1)                         # 3º dia perdido: sem congelamento, zerou
        self.assertEqual(sim["best"], 15)                          # o dia congelado não soma
        # antes da 1.18 não havia congelamento
        self.assertEqual(cq.streak_sim(days, d(0), since=d(0))["used"], 0)

    def test_fenix(self):
        ok, no = [{"status": "done"}] * 2, []
        days = [(f"2026-01-{i:02d}", {}, ok) for i in range(1, 8)] + [("2026-01-08", {}, no)]
        days += [(f"2026-01-{i:02d}", {}, ok) for i in range(9, 16)]
        self.assertEqual(cq.streak_sim(days, "2026-02-01", since="2027-01-01")["phoenix"], 1)

    def test_multiplicador_e_dobro(self):
        self.assertEqual([cq.streak_mult(n) for n in (0, 3, 7, 14, 30)], [1.0, 1.1, 1.2, 1.35, 1.5])
        n = sum(cq.is_x2(f"2026-{m:02d}-{x:02d}") for m in range(1, 13) for x in range(1, 29))
        self.assertTrue(20 < n < 80, n)                              # ~1 em 7
        self.assertEqual(cq.is_x2("2026-11-26"), cq.is_x2("2026-11-26"))

    def test_semana_desafios_e_chefao(self):
        mon = "2026-11-23"
        prev = [(d(i, mon), facts(foc=60), [{"status": "done"}] * 2) for i in range(1, 15)]
        wd = [((date.fromisoformat(mon) + timedelta(days=i)).isoformat(), facts(foc=200), [{"status": "done"}] * 3)
              for i in range(4)]
        w = cq.eval_week(mon, wd, prev, "2026-11-26")
        self.assertEqual(w["id"], "2026-W48")
        self.assertEqual(w["quests"][0]["id"], "foco")
        self.assertEqual(len(w["quests"]), 3)
        foco = w["quests"][0]
        self.assertEqual(foco["target"], 480)                      # 60 min/dia x 7 x 1,15, arredondado
        self.assertEqual((foco["status"], foco["day"]), ("done", "2026-11-25"))
        self.assertTrue(w["boss"]["dead"])
        self.assertIn(w["boss"]["dead"], w["xp"])
        # semana que já acabou sem cumprir: falhou e o chefão fugiu
        w2 = cq.eval_week("2026-11-09", [], prev, "2026-11-26")
        self.assertEqual({q["status"] for q in w2["quests"]}, {"failed"})
        self.assertTrue(w2["boss"]["escaped"])
        # sorteio fixo por semana
        self.assertEqual([q["id"] for q in cq.eval_week(mon, wd, prev, "2026-11-26")["quests"]], [q["id"] for q in w["quests"]])

    def test_regras_novas_nao_mudam_o_passado(self):
        hist = {d(i): facts(foc=60) for i in range(1, 40)}
        old = cq.Conquistas(self.path, FakeDays(hist), lambda: d(39))
        with old._db() as db:                                      # banco de antes da 1.18 (sem "rules2")
            pass
        st, _ = old.refresh(d(0))
        self.assertEqual(st["since"], d(0))
        past = sum(x[3] for x in old._calc["days"] if x[0] < d(0))
        self.assertEqual(past, sum(cq.day_xp(f, m) for _k, f, m, _x in old._calc["days"] if _k < d(0)))

    def test_recompensas_e_equipar(self):
        hist = {d(i): facts(foc=60, hrs=[0, 0, 0, 1000] + [0] * 20) for i in range(1, 30)}
        c = cq.Conquistas(self.path, FakeDays(hist), lambda: d(29))
        st, _ = c.refresh(d(0))
        got = {r["id"] for r in st["rewards"] if r["got"]}
        self.assertIn("novato", got)
        self.assertIn("coruja", got)                                # título da conquista Coruja
        self.assertNotIn("mito", got)
        self.assertEqual(st["equip"]["title"], "novato")
        c.equip("title", "coruja")
        with self.assertRaises(ValueError):
            c.equip("title", "mito")
        with self.assertRaises(ValueError):
            c.equip("frame", "coruja")                              # tipo errado
        c.equip("show", ["coruja", "foco1"])
        with self.assertRaises(ValueError):
            c.equip("show", ["imortal"])
        st, _ = c.refresh(d(0))
        self.assertEqual((st["equip"]["title"], st["equip"]["show"]), ("coruja", ["coruja", "foco1"]))
        s = c.summary()
        self.assertEqual((s["title"], s["frame"], s["show"]), ("coruja", "f_simples", ["coruja", "foco1"]))

    def test_secreta_fica_escondida(self):
        c = cq.Conquistas(self.path, FakeDays({d(1): facts(foc=30)}), lambda: d(1))
        st, _ = c.refresh(d(0))
        g = next(x for x in st["conq"] if x["id"] == "gelo")
        self.assertEqual((g["name"], g["secret"], g["day"]), ("???", True, None))
        self.assertNotIn("congelamento", g["desc"])

    def test_conquistas_novas_entram_sem_aviso(self):
        days = FakeDays({d(i): facts(foc=30, m=[match(w=1, t=1) for _ in range(60)][:2]) for i in range(1, 40)})
        c = cq.Conquistas(self.path, days, lambda: d(39))
        with c._db() as db:                                        # simula um banco da 1.17
            db.execute("INSERT INTO kv VALUES ('init', ?)", (d(39),))
            db.execute("INSERT INTO kv VALUES ('conq_ver', '1')")
        st, ev = c.refresh(d(0))
        self.assertIn("part50", {x["id"] for x in st["conq"] if x["day"]})   # 78 partidas no histórico
        self.assertEqual([e for e in ev if e["kind"] == "conq"], [])

    def test_duelos_vencidos(self):
        c = cq.Conquistas(self.path, FakeDays({d(1): facts()}), lambda: d(1))
        c.refresh(d(0))
        self.assertTrue(c.set_duels_won([5, 7]))
        self.assertFalse(c.set_duels_won([5]))
        st, ev = c.refresh(d(0))
        self.assertIn(("conq", "duelo1"), {(e["kind"], e.get("id")) for e in ev})

    def test_eventos_de_desafio_e_chefao(self):
        days = FakeDays({d(i): facts(foc=10) for i in range(1, 20)})
        c = cq.Conquistas(self.path, days, lambda: d(19))
        c.refresh(d(0))
        days.days[d(0)] = facts(foc=2000)
        _st, ev = c.refresh(d(0))
        kinds = {e["kind"] for e in ev}
        self.assertIn("boss", kinds)
        self.assertIn("quest", kinds)


if __name__ == "__main__":
    unittest.main()
