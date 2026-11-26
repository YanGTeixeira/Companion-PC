"""Coleção da 1.19: créditos, loja da semana, eventos, vitrine que cresce e o catálogo igual no Python, no app e no ranking."""
import json
import re
import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(HERE))

import colecao as co  # noqa: E402
import conquistas as cq  # noqa: E402
from test_conquistas import FakeDays, d, facts, match  # noqa: E402

WEB = HERE.parent / "web"
ROOT = HERE.parent.parent.parent


def history(n=60):
    return FakeDays({d(k): facts(foc=90, m=[match(), match(w=0)]) for k in range(n)})


class ShopTest(unittest.TestCase):
    def test_sorteio_fixo_e_com_raro(self):
        for wk in ("2026-W48", "2026-W49", "2027-W01", "2027-W30"):
            a = co.shop_pick(wk, set())
            self.assertEqual(a, co.shop_pick(wk, set()))
            self.assertEqual(len(a), co.SHOP_N)
            self.assertTrue(all(co.BY_ID[i][4] == co.SHOP for i in a))
            self.assertTrue(any(co.BY_ID[i][3] != "comum" for i in a))

    def test_nao_vende_o_que_ja_e_seu(self):
        a = co.shop_pick("2026-W48", set())
        b = co.shop_pick("2026-W48", set(a))
        self.assertFalse(set(a) & set(b))
        every = {i[0] for i in co.ITEMS if i[4] == co.SHOP}
        self.assertEqual(co.shop_pick("2026-W48", every), [])

    def test_pascoa(self):
        self.assertEqual(co.easter(2026), date(2026, 4, 5))
        self.assertEqual(co.easter(2027), date(2027, 3, 28))


class ColecaoTest(unittest.TestCase):
    def setUp(self):
        self.path = Path(tempfile.mkdtemp()) / "conquistas.db"

    def mk(self, days=None, first=59):
        return cq.Conquistas(self.path, days or history(), lambda: d(first))

    def test_creditos_retroativos_e_fixos(self):
        c = self.mk()
        st, _ = c.refresh(d(0))
        cr = st["credits"]
        self.assertGreater(cr["earned"], 0)
        self.assertEqual(cr["bal"], cr["earned"] - cr["spent"])
        self.assertGreaterEqual(cr["earned"], (st["level"] - 1) * co.CR_LEVEL)
        again = cq.Conquistas(self.path, history(), lambda: d(59)).refresh(d(0))[0]["credits"]
        self.assertEqual(again["earned"], cr["earned"])          # recalculado do histórico: dá o mesmo

    def test_comprar(self):
        c = self.mk()
        st, _ = c.refresh(d(0))
        shop = st["shop"]["items"]
        rw = {r["id"]: r for r in st["rewards"]}
        with self.assertRaisesRegex(ValueError, "não é da loja"):
            c.buy("explorador", d(0))
        out = next(i for i in rw if rw[i]["shop"] and i not in shop and not rw[i]["got"])
        with self.assertRaisesRegex(ValueError, "não está na loja"):
            c.buy(out, d(0))
        cheap = min(shop, key=lambda i: rw[i]["price"])
        bal = st["credits"]["bal"]
        if bal < rw[cheap]["price"]:
            with self.assertRaisesRegex(ValueError, "faltam"):
                c.buy(cheap, d(0))
            return
        st2, ev = c.buy(cheap, d(0))
        got = {r["id"]: r for r in st2["rewards"]}[cheap]
        self.assertTrue(got["got"])
        self.assertEqual(st2["credits"]["bal"], bal - rw[cheap]["price"])
        self.assertEqual(st2["credits"]["spent"], rw[cheap]["price"])
        self.assertIn(cheap, st2["shop"]["items"])               # a loja da semana não muda depois da compra
        self.assertFalse(any(e.get("kind") == "reward" and e.get("id") == cheap for e in ev))
        with self.assertRaisesRegex(ValueError, "já é seu"):
            c.buy(cheap, d(0))
        c.equip(got["kind"], cheap) if got["kind"] in co.EQUIP_KINDS else None

    def test_sem_creditos(self):
        c = self.mk(FakeDays({d(0): facts()}), first=0)
        st, _ = c.refresh(d(0))
        it = st["shop"]["items"][0]
        with self.assertRaisesRegex(ValueError, "faltam"):
            c.buy(it, d(0))

    def test_vitrine_cresce_com_o_nivel(self):
        self.assertEqual([co.show_max(n) for n in (1, 9, 10, 19, 20, 29, 30)], [3, 3, 4, 4, 5, 5, 6])
        self.assertEqual(co.show_max(1, prestige=1), 6)              # prestigiar mantém os 6 lugares
        c = self.mk()
        st, _ = c.refresh(d(0))
        got = [x["id"] for x in st["conq"] if x["day"]]
        n = st["show_max"]
        self.assertEqual(n, co.show_max(st["level"]))
        c.equip("show", got[:n])
        with self.assertRaisesRegex(ValueError, "lugares"):
            c.equip("show", got[:n + 1])

    def test_equipar_novos_tipos_e_bloqueados(self):
        c = self.mk()
        st, _ = c.refresh(d(0))
        for r in st["rewards"]:
            if r["kind"] in ("avatar", "bg", "effect", "accent") and r["got"]:
                self.assertEqual(c.equip(r["kind"], r["id"])["equip"][r["kind"]], r["id"])
        locked = next(r for r in st["rewards"] if r["kind"] == "avatar" and not r["got"])
        with self.assertRaisesRegex(ValueError, "bloqueada"):
            c.equip("avatar", locked["id"])
        with self.assertRaises(ValueError):
            c.equip("theme", "fallout:green")                    # tema fica no layout, não no equip

    def test_perfil_frase_blocos_cor(self):
        c = self.mk(FakeDays({d(0): facts()}), first=0)
        c.refresh(d(0))
        st = c.set_profile({"bio": "  oi\n" + "x" * 100, "lay": ["show", "bio", "nada", "show"]})
        self.assertEqual(len(st["equip"]["bio"]), co.BIO_MAX)
        self.assertNotIn("\n", st["equip"]["bio"])
        self.assertEqual(st["equip"]["lay"], ["show", "bio"])
        with self.assertRaisesRegex(ValueError, "bloqueada"):    # nível baixo: sem cor livre
            c.set_profile({"color": "#ff0000"})
        with self.assertRaisesRegex(ValueError, "inválida"):
            c.set_profile({"color": "vermelho"})
        sm = c.summary()["profile"]
        self.assertEqual(set(sm), {"bg", "avatar", "effect", "accent", "bio", "lay"})
        self.assertEqual(sm["lay"], ["show", "bio"])


class EventosTest(unittest.TestCase):
    def test_natal(self):
        days = [(f"2026-12-{k:02d}", facts(), [{"status": "done"}] * 2) for k in range(1, 15)]
        done, cur = co.events_eval(days, [], "2026-12-14", "2026-11-26")
        self.assertEqual(done.get("natal"), "2026-12-10")        # 2 metas por dia: a 20ª no dia 10
        self.assertEqual((cur["id"], cur["live"], cur["done"]), ("natal", True, True))

    def test_so_conta_depois_da_119(self):
        days = [(f"2026-12-{k:02d}", facts(), [{"status": "done"}] * 3) for k in range(1, 15)]
        done, _ = co.events_eval(days, [], "2026-12-14", "2026-12-12")
        self.assertNotIn("natal", done)                          # 3 dias x 3 metas = 9 < 20

    def test_proximo_evento(self):
        _done, cur = co.events_eval([], [], "2026-11-26", "2026-11-26")
        self.assertEqual((cur["id"], cur["live"], cur["start"]), ("natal", False, "2026-12-01"))
        _done, cur = co.events_eval([], [], "2027-01-20", "2026-11-26")
        self.assertEqual(cur["id"], "carnaval")                  # Páscoa 2027: 28/03 -> carnaval a partir de 29/01

    def test_carnaval_foco(self):
        start, end = co.EVENTS[2][3](2027)
        self.assertEqual((start, end), (date(2027, 1, 29), date(2027, 2, 10)))
        days = [(f"2027-02-{k:02d}", facts(foc=100), []) for k in range(1, 4)]
        done, _ = co.events_eval(days, [], "2027-02-05", "2026-11-26")
        self.assertEqual(done.get("carnaval"), "2027-02-03")


def _js_list(src, start, end):
    i = src.index(start)
    return src[i:src.index(end, i)]


class CatalogoTest(unittest.TestCase):
    """Os ids da coleção têm que existir em todo lugar que desenha ou valida."""

    @classmethod
    def setUpClass(cls):
        cls.js = (WEB / "js" / "catalogo.js").read_text(encoding="utf-8")
        cls.css = (WEB / "css" / "colecao.css").read_text(encoding="utf-8") + (WEB / "css" / "temas.css").read_text(encoding="utf-8")
        cls.ids = {k: {i[0] for i in co.ITEMS if i[1] == k} for k in co.KINDS}

    def test_temas(self):
        block = _js_list(self.js, "const THEMES = [", "const VAR_NAME")
        have = set()
        for part in block.split('{ id: "')[1:]:
            skin = part.split('"')[0]
            have |= {f"{skin}:{v}" for v in re.findall(r'\["([a-z0-9]+)", "', part)}
        self.assertTrue(self.ids["theme"] <= have, self.ids["theme"] - have)
        src = (HERE.parent / "companion_server.py").read_text(encoding="utf-8")   # importar abre os bancos de verdade
        skins = set(re.findall(r'"([a-z]+)"', _js_list(src, "SKINS = {", "}")))
        self.assertEqual({t.split(":")[0] for t in have}, skins)

    def test_fundos_avatares_cores_efeitos(self):
        bgs = set(re.findall(r"^\s+(b_[a-z]+):", _js_list(self.js, "const BGS = {", "function bgSvg"), re.M))
        self.assertEqual(bgs, self.ids["bg"])
        avs = set(re.findall(r"^\s+(av_[a-z]+):", _js_list(self.js, "const AVATARS = {", "function avatarSvg"), re.M))
        self.assertEqual(avs | {"av_nivel"}, self.ids["avatar"])
        acc = set(re.findall(r"(a_[a-z]+):", _js_list(self.js, "const ACC_SWATCH", "function themeVariant")))
        self.assertEqual(acc, self.ids["accent"])
        fx = set(re.findall(r"\.fx\.(e_[a-z]+)", self.css))
        self.assertEqual(fx | {"e_nenhum"}, self.ids["effect"])
        frames = set(re.findall(r"\.badge\.(f_[a-z0-9]+)", self.css))
        self.assertTrue(self.ids["frame"] - {"f_simples"} <= frames, self.ids["frame"] - frames)

    def test_sons(self):
        for src in ((WEB / "js" / "jogador.js").read_text(encoding="utf-8"), (WEB / "js" / "pcjogador.js").read_text(encoding="utf-8")):
            have = set(re.findall(r"\b(s_[a-z]+): \[", src)) | set(re.findall(r"SOUNDS\.(s_[a-z]+) =", src))
            self.assertEqual(have, self.ids["sound"])

    def test_ranking_aceita_os_mesmos_ids(self):
        src = (ROOT / "cloud" / "ranking" / "src" / "logic.js").read_text(encoding="utf-8")
        block = _js_list(src, "export const PROFILE_IDS", "};")
        for kind in ("bg", "avatar", "effect", "accent"):
            m = re.search(kind + r": \[(.*?)\]", block, re.S)
            self.assertEqual(set(re.findall(r'"([a-z_]+)"', m.group(1))), self.ids[kind], kind)
            self.assertEqual(json.loads("[" + m.group(1).replace("\n", "") + "]")[0], co.EQUIP_DEFAULT[kind])

    def test_itens_validos(self):
        self.assertEqual(len(co.BY_ID), len(co.ITEMS))           # sem id repetido
        for i in co.ITEMS:
            self.assertIn(i[1], co.KINDS)
            self.assertIn(i[3], co.RARITY)
            req = i[4]
            if isinstance(req, int):
                self.assertLessEqual(req, co.LEVEL_MAX, i)
            ok = isinstance(req, int) or req == co.SHOP or req in {c[0] for c in cq.CONQ} or \
                (isinstance(req, str) and req.startswith(("p:", "shop:")) and 1 <= int(req.split(":")[1]) <= co.PRESTIGE_MAX) or \
                (isinstance(req, str) and req.startswith("ev:") and req[3:] in {e[0] for e in co.EVENTS}) or \
                (isinstance(req, str) and req.startswith("set:") and req[4:] in {x[0] for x in co.SETS})
            self.assertTrue(ok, i)
        for k, v in co.EQUIP_DEFAULT.items():
            if k in co.EQUIP_KINDS:
                self.assertEqual(co.BY_ID[v][4], 1, k)            # o padrão é de todo mundo


if __name__ == "__main__":
    unittest.main()


class ConjuntosTest(unittest.TestCase):
    """1.20: conjuntos da coleção."""

    def setUp(self):
        self.path = Path(tempfile.mkdtemp()) / "conquistas.db"
        self.orig = co.SETS

    def tearDown(self):
        co.SETS = self.orig

    def test_catalogo(self):
        for sid, _n, _i, items in co.SETS:
            self.assertIn(sid, co.SET_REWARD)
            self.assertTrue(all(i in co.BY_ID for i in items), sid)
            self.assertNotIn(co.SET_REWARD[sid], items)             # o prêmio não faz parte do conjunto
            self.assertFalse(any(str(co.BY_ID[i][4]).startswith("set:") for i in items))
        self.assertEqual(set(co.SET_REWARD), {s[0] for s in co.SETS})
        self.assertEqual(co.sets_complete({"b_lava", "e_fogo", "f_chamas", "a_brasa"}), ["fogo"])

    def test_completar_libera_premio_e_creditos(self):
        co.SETS = [("retro", "Fliperama", "🕹️", ["b_grade", "f_pixel"])]   # um item de nível 2 e um da loja
        c = cq.Conquistas(self.path, history(20), lambda: d(19))
        st, _ = c.refresh(d(0))
        s = st["sets"][0]
        self.assertEqual((s["have"], s["done"]), (1, None))
        self.assertFalse(next(r for r in st["rewards"] if r["id"] == "oldschool")["got"])
        before = st["credits"]["earned"]
        with c._db() as db:                                          # como se tivesse comprado a moldura na loja
            db.execute("INSERT OR REPLACE INTO kv VALUES ('bought', ?)", (json.dumps([{"id": "f_pixel", "price": 150, "day": d(0)}]),))
        st, ev = c.refresh(d(0))
        s = st["sets"][0]
        self.assertEqual((s["have"], s["done"], s["reward"], s["credits"]), (2, d(0), "oldschool", 60))
        rw = next(r for r in st["rewards"] if r["id"] == "oldschool")
        self.assertTrue(rw["got"])
        self.assertEqual(rw["set"], "retro")
        self.assertTrue(any(e["kind"] == "set" and e["id"] == "retro" and e["credits"] == 60 for e in ev))
        self.assertFalse(any(e["kind"] == "reward" and e["id"] == "oldschool" for e in ev))   # um aviso só
        self.assertEqual(st["credits"]["earned"] - before, 60)
        self.assertEqual(st["credits"]["today"] - 60 >= 0, True)
        self.assertEqual(c.refresh(d(0))[1], [])                     # não avisa de novo
        self.assertEqual(c.equip("title", "oldschool")["equip"]["title"], "oldschool")
        col = c.collection_data(d(0), d(0))
        self.assertEqual([x["name"] for x in col["sets"]], ["Fliperama"])
        self.assertEqual(col["bought"], 1)
        self.assertEqual(c.collection_data(d(30), d(1))["sets"], [])


class PrestigioTest(unittest.TestCase):
    """1.21: nível máximo 30 e prestígio estilo COD."""

    def setUp(self):
        self.path = Path(tempfile.mkdtemp()) / "conquistas.db"

    def test_prestigiar(self):
        c = cq.Conquistas(self.path, history(60), lambda: d(59))
        st, _ = c.refresh(d(0))
        self.assertEqual((st["level"], st["prestige"], st["can_prestige"]), (30, 0, True))
        self.assertEqual(st["lvl_lo"], st["lvl_hi"])                 # no máximo a faixa fecha
        self.assertIsNotNone(st["extra"])
        self.assertIn("insignia:naval", st["prestige_next"])
        cr = st["credits"]["earned"]
        rw = lambda st, i: next(r for r in st["rewards"] if r["id"] == i)  # noqa: E731
        self.assertFalse(rw(st, "f_p1")["got"])
        self.assertEqual(rw(st, "f_p1")["prestige"], 1)
        st, ev = c.prestige(d(0))
        self.assertEqual((st["prestige"], st["prestige_label"]), (1, "★1"))
        self.assertLess(st["level"], 30)                             # recomeçou
        self.assertTrue(rw(st, "imperador")["got"])                  # o que o nível 30 deu continua
        self.assertTrue(rw(st, "f_p1")["got"] and rw(st, "insignia:naval")["got"])
        self.assertFalse(rw(st, "av_dragao")["got"])                 # é do prestígio 2
        self.assertEqual(st["show_max"], 6)
        self.assertGreaterEqual(st["credits"]["earned"], cr)         # os créditos dos níveis não se perdem
        self.assertTrue(any(e["kind"] == "prestige" and e["n"] == 1 for e in ev))
        self.assertFalse(any(e["kind"] == "reward" and e["id"] == "f_p1" for e in ev))
        self.assertIn("prest1", {x["id"] for x in st["conq"] if x["day"]})
        self.assertFalse(st["can_prestige"])
        with self.assertRaisesRegex(ValueError, "nível 30"):
            c.prestige(d(0))
        sm = c.summary()
        self.assertEqual((sm["prestige"], sm["pxp"]), (1, c._calc["pxp"]))
        self.assertGreater(sm["pxp"], 0)
        # outro processo lê o mesmo banco: continua no prestígio 1
        self.assertEqual(cq.Conquistas(self.path, history(60), lambda: d(59)).refresh(d(0))[0]["prestige"], 1)

    def test_loja_de_prestigio(self):
        pre = {i[0] for i in co.ITEMS if co.shop_req(i)}
        self.assertEqual(pre, {"av_fenix", "b_vortice", "e_prisma"})
        for wk in ("2026-W50", "2027-W02", "2027-W20"):
            self.assertFalse(set(co.shop_pick(wk, set(), 0)) & pre)
        self.assertTrue(any(set(co.shop_pick(f"2027-W{w:02d}", set(), 9)) & pre for w in range(1, 30)))

    def test_mestre_e_o_ultimo(self):
        self.assertEqual(co.prestige_label(11), "Mestre")
        self.assertEqual({i[0] for i in co.ITEMS if i[4] == "p:11"}, {"mestre_p", "f_mestre", "e_mestre"})
