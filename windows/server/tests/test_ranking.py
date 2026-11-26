"""Ranking público: cliente do PC (o servidor tem os próprios testes em cloud/ranking)."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import ranking as rk  # noqa: E402


class Fake(rk.Ranking):
    """Ranking com um servidor de mentira: replies[(método, rota)] = dict ou RankError."""

    def __init__(self, cfg=None, url="https://r.example"):
        self.saved = []
        super().__init__(cfg if cfg is not None else {}, self.saved.append, url)
        self.calls, self.replies = [], {}

    def _req(self, method, path, body=None, auth=False, timeout=10):
        if not self.configured:
            raise rk.RankError("o ranking ainda não foi publicado")
        if auth and not self.joined:
            raise rk.RankError("você não está no ranking")
        self.calls.append((method, path.split("?")[0], body))
        r = self.replies.get((method, path.split("?")[0]), {})
        if isinstance(r, Exception):
            raise r
        return dict(r)


SUM = {"xp": 900, "week_xp": 300, "streak": 1, "best_streak": 2, "unlocked": 3, "week": "2026-W48", "level": 4}


class RankingTest(unittest.TestCase):
    def test_sem_servidor_publicado(self):
        r = Fake()
        r.url = ""
        self.assertFalse(r.state()["available"])
        with self.assertRaises(rk.RankError):
            r.join("Yan")
        self.assertFalse(r.submit(SUM, force=True))

    def test_entrar_guarda_a_chave(self):
        r = Fake()
        r.replies[("POST", "/v1/register")] = {"id": "abc123456", "key": "k" * 43, "nick": "Yan"}
        st = r.join("Yan")
        self.assertEqual((st["joined"], st["nick"]), (True, "Yan"))
        self.assertEqual(r.saved[-1]["key"], "k" * 43)

    def test_envio_so_o_resumo_e_nao_repete(self):
        r = Fake({"id": "abc123456", "key": "k" * 43})
        self.assertTrue(r.submit(SUM, force=True))
        sent = r.calls[-1][2]
        self.assertEqual(set(sent), {"xp", "week_xp", "streak", "best_streak", "unlocked", "week", "title", "frame", "show", "profile"})   # nada além disso
        self.assertEqual(sent["profile"], {})   # o perfil (1.19) só leva ids de itens e a frase; sem resumo, vazio
        r2 = Fake({"id": "abc123456", "key": "k" * 43})
        pf = {"bg": "b_lava", "avatar": "av_robo", "effect": "e_fogo", "accent": "a_holo", "bio": "oi", "lay": ["bio"]}
        r2.submit({**SUM, "profile": pf}, force=True)
        self.assertEqual(r2.calls[-1][2]["profile"], pf)
        self.assertFalse(r.submit(SUM))                 # igual e cedo: não envia
        self.assertFalse(r.submit({**SUM, "xp": 950}))  # diferente, mas antes de 15 min
        r.last_submit -= rk.SUBMIT_EVERY_S + 1
        self.assertTrue(r.submit({**SUM, "xp": 950}))

    def test_erros_do_envio(self):
        r = Fake({"id": "abc123456", "key": "k" * 43})
        r.replies[("POST", "/v1/submit")] = rk.RankError("cedo demais", 429)
        self.assertFalse(r.submit(SUM, force=True))
        self.assertEqual(r.error, "")                   # 429 não é erro para mostrar
        r.replies[("POST", "/v1/submit")] = rk.RankError("XP não pode diminuir", 422)
        self.assertFalse(r.submit(SUM, force=True))
        self.assertIn("diminuir", r.error)
        r.replies[("POST", "/v1/submit")] = rk.RankError("chave inválida", 401)
        self.assertFalse(r.submit(SUM, force=True))
        self.assertIn("entre de novo", r.error)

    def test_sair_apaga_e_esquece(self):
        r = Fake({"id": "abc123456", "key": "k" * 43, "nick": "Yan"})
        r.replies[("DELETE", "/v1/me")] = rk.RankError("sem conexão", 0)
        with self.assertRaises(rk.RankError):          # servidor fora: não esquece a chave (tenta de novo depois)
            r.leave()
        self.assertTrue(r.joined)
        r.replies[("DELETE", "/v1/me")] = rk.RankError("chave inválida", 401)   # já não existe lá: pode esquecer
        self.assertFalse(r.leave()["joined"])
        self.assertNotIn("key", r.saved[-1])

    def test_ranking_com_a_minha_posicao_e_cache(self):
        r = Fake({"id": "abc123456", "key": "k" * 43, "nick": "Yan"})
        r.replies[("GET", "/v1/board")] = {"kind": "week", "rows": [{"rank": 1, "nick": "Yan", "value": 300}]}
        r.replies[("GET", "/v1/me")] = {"ranks": {"week": 1}}
        b = r.board("week")
        self.assertEqual((b["me"]["ranks"]["week"], b["you"]), (1, "Yan"))
        n = len(r.calls)
        r.board("week")
        self.assertEqual(len(r.calls), n)               # cache de 60 s
        with self.assertRaises(rk.RankError):
            r.board("../x")


    def test_amigos_duelos_e_cache(self):
        r = Fake({"id": "abc123456", "key": "k" * 43, "nick": "Yan"})
        r.replies[("GET", "/v1/duels")] = {"rows": [{"id": 3, "res": "won"}, {"id": 4, "res": "lost"}, {"id": 5, "res": None}]}
        self.assertEqual(rk.Ranking.duels_won(r.duels()), [3])
        n = len(r.calls)
        r.duels()
        self.assertEqual(len(r.calls), n)               # cache
        r.duel_answer("3", True)
        self.assertEqual(r.calls[-1], ("POST", "/v1/duels/answer", {"id": 3, "accept": True}))
        r.friend_del("João Silva")
        self.assertEqual(r.calls[-1][:2], ("DELETE", "/v1/friends"))
        with self.assertRaises(rk.RankError):
            Fake().league()                              # sem conta


if __name__ == "__main__":
    unittest.main()
