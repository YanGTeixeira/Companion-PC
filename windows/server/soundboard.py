"""Mesa de som: botões do deck que tocam áudio "pelo microfone" (Discord, jogos...).

O Windows não deixa um programa falar dentro de um microfone. O jeito padrão é um cabo virtual
(VB-CABLE, grátis): o servidor toca no "CABLE Input" o seu microfone de verdade misturado com os
sons, e no Discord o dispositivo de entrada vira "CABLE Output". Os sons também tocam no seu fone
(dá para desligar). Sem cabo, os sons tocam só no PC.

Os áudios chegam do celular já convertidos (WAV 16 bits, mono, 48 kHz, normalizado) e ficam em
sons/<id>.wav. O deck guarda só o id e o volume do botão.
"""
import asyncio
import base64
import io
import logging
import re
import secrets
import threading
import time
import wave
from collections import deque
from pathlib import Path

log = logging.getLogger("companion")

SR = 48000
BLOCK = 480                  # 10 ms
MAX_SECS = 30
MIC_MAX = BLOCK * 6          # atraso máximo do microfone dentro do cabo (60 ms)
SOUND_ID = re.compile(r"^[0-9a-f]{12}$")
# saídas que são "cabo virtual" (o que tocar nelas vira microfone), em ordem de preferência
CABLES = ("cable input", "cable-a input", "cable-b input", "voicemeeter input", "voicemeeter aux input", "cable in 16ch")
# entradas que são a outra ponta de um cabo: nunca servem como "meu microfone" (daria eco infinito)
NOT_MIC = ("cable output", "cable-a output", "cable-b output", "voicemeeter out", "steam streaming", "mapeador", "mapper",
           "driver de captura", "primary sound")
DEFAULTS = {"mic": "", "monitor": True, "vol": 80, "mic_vol": 100, "overlap": True}
CHECK_S = 2                  # de quanto em quanto tempo olha se a saída padrão do Windows mudou
REFRESH_MIN_S = 20           # intervalo mínimo entre reinícios do PortAudio


def wav_to_array(raw: bytes):
    """WAV PCM 16 bits (mono ou estéreo, qualquer taxa) -> float32 mono a 48 kHz."""
    import numpy as np
    with wave.open(io.BytesIO(raw)) as w:
        ch, width, rate, n = w.getnchannels(), w.getsampwidth(), w.getframerate(), w.getnframes()
        if width != 2 or ch not in (1, 2) or not 8000 <= rate <= 96000:
            raise ValueError("áudio precisa ser WAV 16 bits mono ou estéreo")
        if n / rate > MAX_SECS + 0.5:
            raise ValueError(f"áudio longo demais (máximo {MAX_SECS} s)")
        a = np.frombuffer(w.readframes(n), dtype="<i2").astype(np.float32) / 32768.0
    if ch == 2:
        a = a.reshape(-1, 2).mean(axis=1)
    if rate != SR and len(a):
        m = int(round(len(a) * SR / rate))
        a = np.interp(np.linspace(0, len(a) - 1, m), np.arange(len(a)), a).astype(np.float32)
    return a


class Board:
    def __init__(self, base: Path, cfg, save_cfg, event_fn, refresh_fn=None):
        self.dir = base / "sons"
        self.cfg = {**DEFAULTS, **(cfg or {})}
        self._save_cfg = save_cfg
        self._event = event_fn          # async (dict) -> None, avisa os celulares
        # O PortAudio só enxerga os dispositivos que existiam quando ele iniciou (fone Bluetooth que conecta
        # depois do boot fica de fora). refresh_fn() reinicia o PortAudio com segurança (pausa a voz antes).
        self._refresh = refresh_fn
        self._refreshed = 0.0
        self.loop = None
        self._lock = threading.Lock()
        self._voices = []               # {"id", "a", "pos": {"c": i, "m": i}, "gain", "t"}
        self._cache = {}
        self._mic, self._mic_n = deque(), 0
        self._thread, self._stop = None, threading.Event()
        self.status, self.error = "off", ""
        self.cable = self.mic_name = self.mon_name = ""
        self._sent = None
        try:
            import numpy  # noqa: F401
            import sounddevice  # noqa: F401
            self.available = True
        except Exception as e:  # noqa: BLE001
            self.available, self.error = False, f"faltam pacotes: {e}"

    # ---------------------------------------------------------------- estado / ajustes
    def state(self):
        with self._lock:
            playing = sorted({v["id"] for v in self._voices})
        return {"available": self.available, "status": self.status, "error": self.error, "cable": self.cable,
                "mic": self.mic_name, "monitor_dev": self.mon_name, "pick": self.cfg["mic"],
                "monitor": bool(self.cfg["monitor"]), "vol": self.cfg["vol"], "mic_vol": self.cfg["mic_vol"],
                "overlap": bool(self.cfg["overlap"]), "playing": playing}

    def mics(self):
        """Microfones físicos (WASAPI) para escolher qual vai junto com os sons."""
        if not self.available:
            return []
        sd = self._sd()
        api = self._wasapi(sd)
        return [d["name"] for d in sd.query_devices()
                if d["hostapi"] == api and d["max_input_channels"] > 0 and not self._virtual_in(d["name"])]

    def set(self, p):
        restart = False
        if "mic" in p:
            self.cfg["mic"] = str(p["mic"] or "")[:80]
            restart = True
        if "monitor" in p:
            self.cfg["monitor"] = bool(p["monitor"])
            restart = True
        for k in ("vol", "mic_vol"):
            if k in p:
                self.cfg[k] = max(0, min(150 if k == "mic_vol" else 100, int(p[k])))
        if "overlap" in p:
            self.cfg["overlap"] = bool(p["overlap"])
        self._save_cfg(dict(self.cfg))
        if restart:
            self._spawn()
        return self.state()

    # ---------------------------------------------------------------- arquivos
    def add(self, data_b64: str):
        raw = base64.b64decode(data_b64, validate=True)
        if len(raw) > 6 * 2**20:
            raise ValueError("arquivo grande demais")
        a = wav_to_array(raw)
        if len(a) < SR // 20:
            raise ValueError("áudio vazio ou curto demais")
        self.dir.mkdir(parents=True, exist_ok=True)
        sid = secrets.token_hex(6)
        (self.dir / f"{sid}.wav").write_bytes(raw)
        self._cache[sid] = a
        log.info("som: novo %s (%.1f s)", sid, len(a) / SR)
        return {"id": sid, "dur": round(len(a) / SR, 2)}

    def raw(self, sid):
        """O WAV guardado (base64), para cortar de novo no app ou no editor."""
        self._clip(sid)
        return {"id": sid, "data": base64.b64encode((self.dir / f"{sid}.wav").read_bytes()).decode()}

    def info(self, sid):
        a = self._clip(sid)
        return {"id": sid, "dur": round(len(a) / SR, 2)}

    def cleanup(self, used, min_age=3600):
        """Apaga os sons que nenhum botão usa (os enviados há pouco ficam: o botão pode estar sendo criado)."""
        if not self.dir.exists():
            return
        now = time.time()
        for f in self.dir.glob("*.wav"):
            if f.stem not in used and now - f.stat().st_mtime > min_age:
                f.unlink(missing_ok=True)
                self._cache.pop(f.stem, None)
                log.info("som: apagado %s (sem botão)", f.stem)

    def _clip(self, sid):
        if not SOUND_ID.match(str(sid)):
            raise ValueError("som inválido")
        if sid not in self._cache:
            f = self.dir / f"{sid}.wav"
            if not f.exists():
                raise ValueError("esse som não está mais no PC; escolha o arquivo de novo")
            self._cache[sid] = wav_to_array(f.read_bytes())
        return self._cache[sid]

    # ---------------------------------------------------------------- tocar
    def play(self, sid, vol=100):
        """Toca o som; se ele já está tocando, para (como no Stream Deck). Devolve True se começou."""
        a = self._clip(sid)
        if self.status not in ("on", "nocable"):
            raise ValueError(self.error or "mesa de som desligada")
        with self._lock:
            if any(v["id"] == sid for v in self._voices):
                self._voices = [v for v in self._voices if v["id"] != sid]
                started = False
            else:
                if not self.cfg["overlap"]:
                    self._voices.clear()
                keys = {k for k, on in (("c", self._out_c), ("m", self._out_m)) if on}
                gain = max(0, min(200, int(vol))) / 100
                self._voices.append({"id": sid, "a": a, "pos": dict.fromkeys(keys, 0), "gain": gain, "t": time.monotonic()})
                started = True
        self._notify()
        return started

    def stop(self):
        with self._lock:
            self._voices.clear()
        self._notify()

    def _mix(self, np, frames, key):
        out = np.zeros(frames, dtype=np.float32)
        with self._lock:
            if not self._voices:
                return out
            master = self.cfg["vol"] / 100
            keep = []
            for v in self._voices:
                pos = v["pos"]
                if key in pos:
                    i = pos[key]
                    chunk = v["a"][i:i + frames]
                    out[:len(chunk)] += chunk * (v["gain"] * master)
                    pos[key] = i + frames
                    if pos[key] >= len(v["a"]):
                        del pos[key]
                if pos:
                    keep.append(v)
            self._voices = keep
        return out

    # ---------------------------------------------------------------- áudio (thread)
    @staticmethod
    def _sd():
        import sounddevice as sd
        return sd

    @staticmethod
    def _wasapi(sd):
        return next((i for i, h in enumerate(sd.query_hostapis()) if h["name"] == "Windows WASAPI"), None)

    @staticmethod
    def _virtual_in(name):
        n = name.lower()
        return any(x in n for x in NOT_MIC)

    @staticmethod
    def _is_cable(name):
        n = name.lower()
        return any(n.startswith(c) for c in CABLES)

    @staticmethod
    def _default_out():
        """Nome da saída padrão do Windows agora ("" se não há nenhuma; None se não dá para saber)."""
        try:
            from pycaw.pycaw import AudioUtilities
        except Exception:  # noqa: BLE001
            return None
        try:
            d = AudioUtilities.GetDeviceEnumerator().GetDefaultAudioEndpoint(0, 1)  # eRender, eMultimedia
            return AudioUtilities.CreateDevice(d).FriendlyName or ""
        except Exception:  # noqa: BLE001  (nenhuma saída ativa)
            return ""

    def _try_refresh(self, sd):
        """Reinicia o PortAudio para enxergar dispositivos novos (no máximo a cada REFRESH_MIN_S)."""
        if not self._refresh or time.monotonic() - self._refreshed < REFRESH_MIN_S:
            return False
        self._refreshed = time.monotonic()
        try:
            ok = self._refresh()
        except Exception as e:  # noqa: BLE001
            log.warning("sons: não deu para atualizar a lista de dispositivos: %s", e)
            return False
        if ok:
            log.info("sons: lista de dispositivos de áudio atualizada")
        return ok

    def _devices(self, sd, win_out=None):
        api = self._wasapi(sd)
        devs = [(i, d) for i, d in enumerate(sd.query_devices()) if d["hostapi"] == api]
        outs = [(i, d) for i, d in devs if d["max_output_channels"] > 0]
        cable = None
        for c in CABLES:
            cable = next(((i, d) for i, d in outs if d["name"].lower().startswith(c)), None)
            if cable:
                break
        h = sd.query_hostapis(api) if api is not None else {}
        mon = None
        if win_out is not None:   # o padrão de agora no Windows (o do PortAudio é o da hora em que ele iniciou)
            mon = next(((i, d) for i, d in outs if d["name"] == win_out), None)
        else:
            di = h.get("default_output_device", -1)
            if di is not None and di >= 0:
                mon = (di, sd.query_devices(di))
        if mon and self._is_cable(mon[1]["name"]):
            mon = None
        mic = None
        if cable and self.cfg["mic"] != "nenhum":
            ins = [(i, d) for i, d in devs if d["max_input_channels"] > 0 and not self._virtual_in(d["name"])]
            want = self.cfg["mic"].lower()
            mic = next(((i, d) for i, d in ins if want and want in d["name"].lower()), None)
            if not mic:
                di = h.get("default_input_device", -1)
                mic = next(((i, d) for i, d in ins if i == di), None) or (ins[0] if ins else None)
        return cable, mic, mon

    def start(self, loop):
        self.loop = loop
        if self.available:
            self._spawn()

    def _spawn(self):
        if not self.available:
            return
        self._stop.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(3)
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._worker, args=(self._stop,), daemon=True, name="sons")
        self._thread.start()

    _out_c = _out_m = False

    def _worker(self, stop):
        import numpy as np
        sd = self._sd()
        try:  # o WASAPI precisa de COM nesta thread, senão nenhum stream abre
            import ctypes
            ctypes.windll.ole32.CoInitializeEx(None, 0)
        except (AttributeError, OSError):
            pass
        extra = sd.WasapiSettings(auto_convert=True)
        failed = False
        while not stop.is_set():
            streams = []
            try:
                win_out = self._default_out()
                names = {d["name"] for d in sd.query_devices() if d["max_output_channels"] > 0}
                if failed or (self.cfg["monitor"] and win_out and win_out not in names):
                    if self._try_refresh(sd):   # dispositivo novo (fone que conectou depois) ou um que sumiu
                        extra = sd.WasapiSettings(auto_convert=True)
                failed = False
                cable, mic, mon = self._devices(sd, win_out)
                self.cable = cable[1]["name"] if cable else ""
                self.mic_name = mic[1]["name"] if mic else ""
                self.mon_name = mon[1]["name"] if mon and self.cfg["monitor"] else ""
                with self._lock:
                    self._mic.clear()
                    self._mic_n = 0
                if mic:
                    def cb_in(indata, frames, _t, _s):
                        a = indata[:, 0].copy()
                        with self._lock:
                            self._mic.append(a)
                            self._mic_n += len(a)
                            while self._mic_n > MIC_MAX and self._mic:
                                self._mic_n -= len(self._mic.popleft())
                    streams.append(sd.InputStream(device=mic[0], channels=min(2, mic[1]["max_input_channels"]),
                                                  samplerate=SR, blocksize=BLOCK, dtype="float32", latency="low",
                                                  extra_settings=extra, callback=cb_in))
                if cable:
                    ch = min(2, cable[1]["max_output_channels"])

                    def cb_cable(outdata, frames, _t, _s):
                        out = self._mix(np, frames, "c")
                        if mic:
                            out += self._pull_mic(np, frames) * (self.cfg["mic_vol"] / 100)
                        np.clip(out, -1, 1, out=out)
                        outdata[:] = out[:, None]
                    streams.append(sd.OutputStream(device=cable[0], channels=ch, samplerate=SR, blocksize=BLOCK,
                                                   dtype="float32", latency="low", extra_settings=extra, callback=cb_cable))
                for s in streams:
                    s.start()
                if mon and self.cfg["monitor"]:
                    ch = min(2, mon[1]["max_output_channels"])

                    def cb_mon(outdata, frames, _t, _s):
                        out = self._mix(np, frames, "m")
                        np.clip(out, -1, 1, out=out)
                        outdata[:] = out[:, None]
                    try:  # se o fone falhar, o cabo (microfone) segue funcionando
                        s = sd.OutputStream(device=mon[0], channels=ch, samplerate=SR, blocksize=BLOCK, dtype="float32",
                                            latency="low", extra_settings=extra, callback=cb_mon)
                        s.start()
                        streams.append(s)
                    except Exception as e:  # noqa: BLE001
                        log.warning("sons: fone %s: %s", mon[1]["name"], e)
                        mon, self.mon_name = None, ""
                self._out_c, self._out_m = bool(cable), bool(mon and self.cfg["monitor"])
                self.status = "on" if cable else "nocable" if self._out_m else "error"
                self.error = "" if cable or self._out_m else "sem cabo virtual e com \"eu também ouço\" desligado: os sons não tocam em lugar nenhum"
                log.info("sons: cabo=%s | microfone=%s | fone=%s", self.cable or "-", self.mic_name or "-", self.mon_name or "-")
                self._notify(force=True)
                next_check = time.monotonic() + CHECK_S
                changed = False
                while not stop.is_set() and all(s.active for s in streams):
                    stop.wait(0.1)
                    self._expire()
                    self._notify()
                    if time.monotonic() > next_check:   # trocou o fone/caixa padrão no Windows: reabre
                        next_check = time.monotonic() + CHECK_S
                        if self._default_out() != win_out:
                            log.info("sons: a saída padrão do Windows mudou")
                            changed = True
                            break
                if not stop.is_set() and not changed:
                    raise RuntimeError("o dispositivo de áudio parou (desconectado?)")
            except Exception as e:  # noqa: BLE001
                if stop.is_set():
                    break
                failed = True
                log.warning("sons: %s", e)
                self.status, self.error = "error", str(e)[:160]
                self._notify(force=True)
                stop.wait(5)
            finally:
                self._out_c = self._out_m = False
                for s in streams:
                    try:
                        s.close()
                    except Exception:  # noqa: BLE001
                        pass
        self.status = "off"

    def _pull_mic(self, np, frames):
        out = np.zeros(frames, dtype=np.float32)
        with self._lock:
            if self._mic_n < frames:     # ainda enchendo: silêncio (evita picotar)
                return out
            got = 0
            while got < frames and self._mic:
                c = self._mic[0]
                take = min(frames - got, len(c))
                out[got:got + take] = c[:take]
                got += take
                if take == len(c):
                    self._mic.popleft()
                else:
                    self._mic[0] = c[take:]
            self._mic_n -= got
        return out

    def _expire(self):
        """Segurança: se uma saída parou no meio, o som não fica "tocando" para sempre."""
        now = time.monotonic()
        with self._lock:
            self._voices = [v for v in self._voices if now - v["t"] < len(v["a"]) / SR + 2]

    def _notify(self, force=False):
        st = self.state()
        key = (st["status"], tuple(st["playing"]), st["cable"], st["mic"], st["error"])
        if not force and key == self._sent:
            return
        self._sent = key
        if self.loop and self._event:
            try:
                asyncio.run_coroutine_threadsafe(self._event(st), self.loop)
            except RuntimeError:
                pass
