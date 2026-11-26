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
        self.assertTrue(st["nr"])                       # supressão de ruído ligada por padrão
        self.assertFalse(self.b.set({"nr": False})["nr"])
        self.assertFalse(self.saved[-1]["nr"])

    def test_supressao_sem_rnnoise_deixa_passar(self):
        old, sb._RNN = sb._RNN, False
        try:
            d = sb.Denoiser()
            a = np.linspace(-1, 1, 480, dtype=np.float32)
            self.assertIs(d(a), a)
            d.close()
        finally:
            sb._RNN = old

    @unittest.skipUnless(sb._rnnoise_lib(), "precisa do pyrnnoise")
    def test_supressao_tira_ruido_e_junta_blocos_quebrados(self):
        rng = np.random.default_rng(1)
        noise = (rng.standard_normal(48000) * 0.05).astype(np.float32)
        d = sb.Denoiser()
        out = np.concatenate([d(noise[i:i + 300]) for i in range(0, len(noise), 300)])
        d.close()
        self.assertEqual(len(out), len(noise) // 480 * 480)   # blocos de 300 viram quadros de 480
        self.assertLess(d.prob, sb.VAD_PROB)                   # ruído não é voz
        tail = out[len(out) // 2:]                              # depois de o modelo se ajustar
        self.assertLess(np.sqrt(np.mean(tail ** 2)), 0.05 / 4)

    def test_limpeza_apaga_so_os_sem_botao_e_antigos(self):
        keep, old, new = self.add()["id"], self.add()["id"], self.add()["id"]
        d = Path(self.tmp) / "sons"
        past = time.time() - 7200
        for sid in (keep, old):
            os.utime(d / f"{sid}.wav", (past, past))
        self.b.cleanup({keep})
        self.assertEqual(sorted(f.stem for f in d.glob("*.wav")), sorted([keep, new]))


@unittest.skipIf(np is None, "precisa de numpy")
class VozTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.b, self.saved = board(self.tmp)
        self.b._spawn = lambda: None
        self.b.mic_name = "Microfone (fifine)"

    def tone(self, amp, n=480, f=220):
        return (np.sin(2 * np.pi * f * np.arange(n) / sb.SR) * amp).astype(np.float32)

    def test_fala_pelo_rnnoise_e_pelo_nivel(self):
        self.b._vad(self.tone(0.3), 0.2)               # alto, mas o RNNoise diz que não é voz
        self.assertFalse(self.b.talking)
        self.b._vad(self.tone(0.001), 0.95)            # é voz, mas baixinho (TV no fundo)
        self.assertFalse(self.b.talking)
        self.b._vad(self.tone(0.3), 0.95)
        self.assertTrue(self.b.talking)
        self.assertAlmostEqual(self.b.talk_secs, 0.01)
        self.b._talk_t -= sb.TALK_HOLD + 0.01          # passou o tempo de "segurar"
        self.assertFalse(self.b.talking)
        self.b._vad(self.tone(0.3), None)              # sem RNNoise: só o nível
        self.assertTrue(self.b.talking)
        self.b.mic_name = ""                           # sem microfone na mesa: nunca "falando"
        self.assertFalse(self.b.talking)

    def test_mudo_e_efeito_nao_ficam_salvos(self):
        st = self.b.set({"muted": "toggle", "fx": "robo"})
        self.assertEqual((st["muted"], st["fx"]), (True, "robo"))
        self.assertNotIn("muted", self.saved[-1])
        self.assertNotIn("fx", self.saved[-1])
        self.assertEqual(self.b.set({"fx": "robo", "toggle": True})["fx"], "")   # botão do deck: de novo desliga
        self.assertEqual(self.b.set({"fx": "eco", "toggle": True})["fx"], "eco")
        self.assertFalse(self.b.set({"muted": "toggle"})["muted"])
        with self.assertRaises(ValueError):
            self.b.set({"fx": "../x"})

    def test_efeitos_mantem_tamanho_e_nao_explodem(self):
        x = self.tone(0.5, 48000)
        for kind in list(sb.FX) + [""]:
            fx = sb.VoiceFx()
            out = np.concatenate([fx(x[i:i + 480], kind) for i in range(0, len(x), 480)])
            self.assertEqual(out.shape, x.shape, kind)
            self.assertTrue(np.isfinite(out).all(), kind)
            self.assertLess(np.abs(out).max(), 1.6, kind)
            self.assertGreater(np.abs(out[24000:]).max(), 0.1, kind)   # a voz continua lá

    def test_troca_de_tom_muda_a_frequencia(self):
        x = self.tone(0.5, 48000, f=300)
        for kind, r in sb.VoiceFx.PITCH.items():
            fx = sb.VoiceFx()
            out = np.concatenate([fx(x[i:i + 480], kind) for i in range(0, len(x), 480)])[8000:]
            spec = np.abs(np.fft.rfft(out * np.hanning(len(out))))
            peak = np.argmax(spec) * sb.SR / len(out)
            self.assertAlmostEqual(peak / 300, r, delta=0.06, msg=kind)

    def test_eco_repete_depois_de_250ms(self):
        fx = sb.VoiceFx()
        x = np.zeros(48000, dtype=np.float32)
        x[:480] = 0.5
        out = np.concatenate([fx(x[i:i + 480], "eco") for i in range(0, len(x), 480)])
        d = sb.VoiceFx.ECHO
        self.assertAlmostEqual(float(out[d + 10]), 0.5 * sb.VoiceFx.ECHO_FB, places=4)
        self.assertAlmostEqual(float(out[2 * d + 10]), 0.5 * sb.VoiceFx.ECHO_FB ** 2, places=4)
        self.assertEqual(float(out[d - 100]), 0.0)


class TalkWatchTest(unittest.TestCase):
    def test_avisa_so_com_fala_continua_no_mudo(self):
        w = sb.TalkWatch()
        total, t = 0.0, 0.0
        self.assertIsNone(w.step(t, total, "meet", "meet"))   # primeira leitura: só referência
        for _ in range(2):                                    # 1 s falando sem mudo: nada
            t += 0.5; total += 0.5
            self.assertIsNone(w.step(t, total, "meet", ""))
        t += 0.5; total += 0.5                                # 0,5 s no mudo, ainda não
        self.assertIsNone(w.step(t, total, "meet", "meet"))
        t += 10                                               # pausa longa: zera
        self.assertIsNone(w.step(t, total, "meet", "meet"))
        t += 0.5; total += 0.5
        self.assertIsNone(w.step(t, total, "meet", "meet"))
        got = []
        for _ in range(3):
            t += 0.5; total += 0.5
            got.append(w.step(t, total, "meet", "meet"))
        self.assertIn("meet", got)
        for _ in range(6):                                    # já avisou: espera o intervalo
            t += 0.5; total += 0.5
            self.assertIsNone(w.step(t, total, "meet", "mesa"))
        t += sb.TalkWatch.COOLDOWN_S                          # passou o intervalo: avisa de novo
        got = []
        for _ in range(3):
            t += 0.5; total += 0.5
            got.append(w.step(t, total, "game", "mesa"))
        self.assertIn("mesa", got)
        self.assertEqual(w.take(t, force=True), {"meet": 6.5, "game": 1.5})

    def test_junta_por_contexto_e_grava_no_db(self):
        w = sb.TalkWatch(now=0)
        w.step(0, 0.0, "other", "")
        w.step(1, 2.0, "meet", "")
        w.step(2, 3.0, "game", "")
        w.step(3, 3.5, "meet", "")
        self.assertIsNone(w.take(5))                          # antes de FLUSH_S
        got = w.take(sb.TalkWatch.FLUSH_S)
        self.assertEqual(got, {"meet": 2.5, "game": 1.0})
        self.assertIsNone(w.take(100, force=True))
        log = sb.TalkLog(Path(tempfile.mkdtemp()) / "voz.db")
        log.add("2026-11-26", got)
        log.add("2026-11-26", {"meet": 1.5})
        self.assertEqual(log.day("2026-11-26"), {"meet": 4.0, "game": 1.0})
        self.assertEqual(log.day("2026-11-25"), {})


class Dispositivos(unittest.TestCase):
    def test_cabo_e_microfone_virtual(self):
        self.assertTrue(sb.Board._is_cable("CABLE Input (VB-Audio Virtual Cable)"))
        self.assertFalse(sb.Board._is_cable("Fones de ouvido (Fuxi-H5B)"))
        self.assertTrue(sb.Board._virtual_in("CABLE Output (VB-Audio Virtual Cable)"))
        self.assertTrue(sb.Board._virtual_in("Microfone (Steam Streaming Microphone)"))
        self.assertFalse(sb.Board._virtual_in("Microfone (NVIDIA RTX Voice)"))
        self.assertFalse(sb.Board._virtual_in("Microfone (2- fifine Microphone)"))
        self.assertTrue(sb.Board._is_cable("CABLE In 16ch (VB-Audio Virtual Cable)"))

    def test_fone_e_o_padrao_atual_do_windows(self):
        """O padrão do PortAudio é o da hora em que ele iniciou (ex.: antes do fone Bluetooth conectar)."""
        devs = [{"name": "CABLE Input (VB-Audio Virtual Cable)", "hostapi": 0, "max_input_channels": 0, "max_output_channels": 2},
                {"name": "Fones de ouvido (Fuxi-H5B)", "hostapi": 0, "max_input_channels": 0, "max_output_channels": 2},
                {"name": "Microfone (2- fifine Microphone)", "hostapi": 0, "max_input_channels": 2, "max_output_channels": 0}]

        class FakeSd:
            query_hostapis = staticmethod(lambda i=None: [{"name": "Windows WASAPI"}] if i is None else
                                          {"default_output_device": 0, "default_input_device": 2})
            query_devices = staticmethod(lambda i=None: devs if i is None else devs[i])

        with tempfile.TemporaryDirectory() as tmp:
            b = board(tmp)[0]
            cable, mic, mon = b._devices(FakeSd, "Fones de ouvido (Fuxi-H5B)")
            self.assertEqual((cable[0], mic[0], mon[0]), (0, 2, 1))
            self.assertIsNone(b._devices(FakeSd, "CABLE Input (VB-Audio Virtual Cable)")[2])  # cabo não é fone
            self.assertIsNone(b._devices(FakeSd, "")[2])                                       # sem saída nenhuma
            self.assertIsNone(b._devices(FakeSd, None)[2])  # sem pycaw: usa o do PortAudio (aqui, o cabo)


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
