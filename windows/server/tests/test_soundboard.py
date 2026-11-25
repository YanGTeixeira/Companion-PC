"""Mesa de som: conversão dos WAV, tocar/parar, mistura com o microfone e botões "Tocar som" do deck."""
import base64
import io
import os
import sys
import tempfile
import time
import unittest
import wave
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

try:
    import numpy as np
except ImportError:  # pragma: no cover
    np = None

import soundboard as sb


def make_wav(secs=0.5, rate=48000, ch=1, width=2, amp=0.5):
    n = int(secs * rate)
    t = np.arange(n) / rate
    a = (np.sin(2 * np.pi * 440 * t) * amp * 32767).astype("<i2")
    if ch == 2:
        a = np.repeat(a, 2)
    bio = io.BytesIO()
    with wave.open(bio, "wb") as w:
        w.setnchannels(ch)
        w.setsampwidth(width)
        w.setframerate(rate)
        w.writeframes(a.tobytes() if width == 2 else (a // 256).astype("i1").tobytes())
    return bio.getvalue()


def board(tmp, **cfg):
    saved = []
    b = sb.Board(Path(tmp), cfg, saved.append, None)
    b.status = "on"
    b._out_c = b._out_m = True
    return b, saved


@unittest.skipIf(np is None, "precisa de numpy")
class WavTest(unittest.TestCase):
    def test_mono_48k(self):
        a = sb.wav_to_array(make_wav(0.5))
        self.assertEqual(a.dtype, np.float32)
        self.assertEqual(len(a), 24000)
        self.assertAlmostEqual(float(np.abs(a).max()), 0.5, places=2)

    def test_estereo_e_outra_taxa_viram_mono_48k(self):
        a = sb.wav_to_array(make_wav(1.0, rate=44100, ch=2))
        self.assertEqual(len(a), 48000)
        self.assertAlmostEqual(float(np.abs(a).max()), 0.5, places=2)

    def test_recusa_8_bits_e_longo_demais(self):
        with self.assertRaises(ValueError):
            sb.wav_to_array(make_wav(0.2, width=1))
        with self.assertRaises(ValueError):
            sb.wav_to_array(make_wav(sb.MAX_SECS + 2, rate=8000))
        with self.assertRaises(Exception):
            sb.wav_to_array(b"nao e wav")


@unittest.skipIf(np is None, "precisa de numpy")
class BoardTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.b, self.saved = board(self.tmp)

    def add(self, secs=0.1):
        return self.b.add(base64.b64encode(make_wav(secs)).decode())

    def test_add_grava_e_info(self):
        r = self.add(0.5)
        self.assertRegex(r["id"], sb.SOUND_ID)
        self.assertTrue((Path(self.tmp) / "sons" / f"{r['id']}.wav").exists())
        self.b._cache.clear()
        self.assertEqual(self.b.info(r["id"])["dur"], 0.5)

    def test_raw_devolve_o_wav_guardado(self):
        r = self.add(0.2)
        raw = base64.b64decode(self.b.raw(r["id"])["data"])
        self.assertEqual(len(sb.wav_to_array(raw)), 9600)
        with self.assertRaises(ValueError):
            self.b.raw("../deck")

    def test_add_recusa_vazio_e_lixo(self):
        with self.assertRaises(ValueError):
            self.add(0.01)
        with self.assertRaises(Exception):
            self.b.add("@@@")

    def test_id_invalido_nao_vira_caminho(self):
        for bad in ("../config", "abc", "0123456789ab/../x"):
            with self.assertRaises(ValueError):
                self.b.play(bad)

    def test_tocar_de_novo_para(self):
        sid = self.add()["id"]
        self.assertTrue(self.b.play(sid))
        self.assertEqual(self.b.state()["playing"], [sid])
        self.assertFalse(self.b.play(sid))
        self.assertEqual(self.b.state()["playing"], [])

    def test_um_por_vez(self):
        a, c = self.add()["id"], self.add()["id"]
        self.b.cfg["overlap"] = False
        self.b.play(a)
        self.b.play(c)
        self.assertEqual(self.b.state()["playing"], [c])

    def test_sem_saida_nao_toca(self):
        sid = self.add()["id"]
        self.b.status, self.b.error = "error", "sem fone"
        with self.assertRaisesRegex(ValueError, "sem fone"):
            self.b.play(sid)

    def test_mistura_cada_saida_ate_o_fim(self):
        sid = self.add(0.1)["id"]      # 4800 amostras
        self.b.cfg["vol"] = 100
        self.b.play(sid, vol=50)
        total_c = sum(float(np.abs(self.b._mix(np, 480, "c")).sum()) for _ in range(10))
        self.assertGreater(total_c, 0)
        self.assertEqual(self.b.state()["playing"], [sid])      # o fone ainda não tocou
        out = self.b._mix(np, 480, "m")
        self.assertAlmostEqual(float(np.abs(out).max()), 0.25, places=2)   # 0,5 x volume 50%
        for _ in range(9):
            self.b._mix(np, 480, "m")
        self.assertEqual(self.b.state()["playing"], [])
        self.assertFalse(self.b._mix(np, 480, "c").any())

    def test_som_preso_expira(self):
        sid = self.add(0.1)["id"]
        self.b.play(sid)
        self.b._voices[0]["t"] = time.monotonic() - 10
        self.b._expire()
        self.assertEqual(self.b.state()["playing"], [])

    def test_microfone_com_atraso_limitado(self):
        for _ in range(20):          # chega bem mais microfone do que sai: guarda só os últimos 60 ms
            with self.b._lock:
                self.b._mic.append(np.ones(480, dtype=np.float32))
                self.b._mic_n += 480
                while self.b._mic_n > sb.MIC_MAX and self.b._mic:
                    self.b._mic_n -= len(self.b._mic.popleft())
        self.assertLessEqual(self.b._mic_n, sb.MIC_MAX)
        out = self.b._pull_mic(np, 700)
        self.assertTrue((out == 1).all())
        self.assertEqual(self.b._mic_n, sb.MIC_MAX - 700)

    def test_microfone_ainda_enchendo_da_silencio(self):
        with self.b._lock:
            self.b._mic.append(np.ones(100, dtype=np.float32))
            self.b._mic_n = 100
        self.assertFalse(self.b._pull_mic(np, 480).any())
        self.assertEqual(self.b._mic_n, 100)

    def test_ajustes_limitados_e_salvos(self):
        self.b._spawn = lambda: None
        st = self.b.set({"vol": 500, "mic_vol": -3, "overlap": False, "mic": "fifine"})
        self.assertEqual((st["vol"], st["mic_vol"], st["overlap"], st["pick"]), (100, 0, False, "fifine"))
        self.assertEqual(self.saved[-1]["vol"], 100)

    def test_limpeza_apaga_so_os_sem_botao_e_antigos(self):
        keep, old, new = self.add()["id"], self.add()["id"], self.add()["id"]
        d = Path(self.tmp) / "sons"
        past = time.time() - 7200
        for sid in (keep, old):
            os.utime(d / f"{sid}.wav", (past, past))
        self.b.cleanup({keep})
        self.assertEqual(sorted(f.stem for f in d.glob("*.wav")), sorted([keep, new]))


class Dispositivos(unittest.TestCase):
    def test_cabo_e_microfone_virtual(self):
        self.assertTrue(sb.Board._is_cable("CABLE Input (VB-Audio Virtual Cable)"))
        self.assertFalse(sb.Board._is_cable("Fones de ouvido (Fuxi-H5B)"))
        self.assertTrue(sb.Board._virtual_in("CABLE Output (VB-Audio Virtual Cable)"))
        self.assertTrue(sb.Board._virtual_in("Microfone (Steam Streaming Microphone)"))
        self.assertFalse(sb.Board._virtual_in("Microfone (NVIDIA RTX Voice)"))
        self.assertFalse(sb.Board._virtual_in("Microfone (2- fifine Microphone)"))


class DeckSomTest(unittest.TestCase):
    def setUp(self):
        import extras
        self.extras = extras
        self.deck = extras.Deck(Path(tempfile.mkdtemp()))

    def save(self, b):
        return self.deck.save({"pages": [{"name": "Sons", "buttons": [b]}]}, lambda v: None)["pages"][0]["buttons"][0]

    def test_botao_de_som(self):
        b = self.save({"label": "Risada", "type": "sound", "value": "0123456789ab", "vol": 350})
        self.assertEqual(b, {"label": "Risada", "type": "sound", "value": "0123456789ab", "vol": 200})
        self.assertEqual(self.save({"label": "x", "type": "sound", "value": "0123456789ab", "vol": "?"})["vol"], 100)

    def test_som_sem_audio_ou_com_caminho(self):
        for v in ("", "../../x.wav", "0123456789AB"):
            with self.assertRaises(ValueError):
                self.save({"label": "x", "type": "sound", "value": v})

    def test_outros_botoes_nao_ganham_volume(self):
        self.assertNotIn("vol", self.save({"label": "x", "type": "text", "value": "oi", "vol": 50}))


if __name__ == "__main__":
    unittest.main()
