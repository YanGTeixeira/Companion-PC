"""Mesa de som: botões do deck que tocam áudio "pelo microfone" (Discord, jogos...).

O Windows não deixa um programa falar dentro de um microfone. O jeito padrão é um cabo virtual
(VB-CABLE, grátis): o servidor toca no "CABLE Input" o seu microfone de verdade misturado com os
sons, e no Discord o dispositivo de entrada vira "CABLE Output". Os sons também tocam no seu fone
(dá para desligar). Sem cabo, os sons tocam só no PC.

Supressão de ruído: a do Discord (Krisp) age em tudo o que chega pelo cabo e corta música e efeitos.
Por isso o servidor limpa só o microfone (RNNoise, pacote pyrnnoise) antes de misturar com os sons;
no Discord a supressão fica desligada.

O RNNoise também diz a chance de cada 10 ms ser voz: com isso o servidor sabe quando você está falando
(medidor no celular, aviso de "falando no mudo" e tempo de fala do dia, em voz.db). O "mudo" daqui corta só
o seu microfone no cabo (os sons continuam), e os efeitos de voz (robô, rádio...) também só mexem nele.

Os áudios chegam do celular já convertidos (WAV 16 bits, mono, 48 kHz, normalizado) e ficam em
sons/<id>.wav. O deck guarda só o id e o volume do botão.
"""
import asyncio
import base64
import ctypes
import importlib.util
import io
import logging
import os
import sys
import re
import secrets
import sqlite3
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
DEFAULTS = {"mic": "", "monitor": True, "vol": 80, "mic_vol": 100, "overlap": True, "nr": True}
FX = {"robo": "Robô", "radio": "Rádio", "grave": "Voz grossa", "agudo": "Voz fina", "eco": "Eco"}
VAD_PROB = 0.7               # chance de voz (RNNoise) para contar como fala
VAD_RMS = 0.004              # ... e nível mínimo (~ -48 dBFS), para a TV no fundo não contar
VAD_RMS_ONLY = 0.02          # sem RNNoise: só o nível (~ -34 dBFS)
TALK_HOLD = 0.4              # "falando" continua por esse tempo depois da última voz (sem piscar entre palavras)
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


_RNN = None


def _rnnoise_lib():
    """A DLL do RNNoise que vem no pacote pyrnnoise (None se não instalado). Não importa o pacote:
    o __init__ dele puxa audiolab/matplotlib, que não usamos (instalamos com --no-deps)."""
    global _RNN
    if _RNN is None:
        _RNN = False
        try:
            spec = importlib.util.find_spec("pyrnnoise")
            if spec and spec.submodule_search_locations:
                name = {"win32": "rnnoise.dll", "darwin": "librnnoise.dylib"}.get(sys.platform, "librnnoise.so")
                lib = ctypes.CDLL(os.path.join(list(spec.submodule_search_locations)[0], name))
                lib.rnnoise_create.argtypes = [ctypes.c_void_p]
                lib.rnnoise_create.restype = ctypes.c_void_p
                lib.rnnoise_destroy.argtypes = [ctypes.c_void_p]
                lib.rnnoise_process_frame.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_float),
                                                      ctypes.POINTER(ctypes.c_float)]
                lib.rnnoise_process_frame.restype = ctypes.c_float
                lib.rnnoise_get_frame_size.restype = ctypes.c_int
                if lib.rnnoise_get_frame_size() == BLOCK:
                    _RNN = lib
        except Exception as e:  # noqa: BLE001
            log.warning("sons: RNNoise indisponível: %s", e)
    return _RNN or None


class Denoiser:
    """Supressão de ruído do microfone (RNNoise, quadros de 10 ms a 48 kHz)."""

    def __init__(self):
        import numpy as np
        self.np = np
        self.lib = _rnnoise_lib()
        self.st = self.lib.rnnoise_create(None) if self.lib else None
        self.buf = np.zeros(0, dtype=np.float32)
        self.frame = np.zeros(BLOCK, dtype=np.float32)
        self.prob = None      # maior chance de voz dos quadros do último bloco (None sem RNNoise)

    def __call__(self, a):
        """float32 [-1, 1] -> o mesmo áudio limpo (pode atrasar até 10 ms se os blocos não forem de 480)."""
        np = self.np
        if not self.st:
            return a
        if not len(self.buf) and len(a) == BLOCK:
            todo = a
        else:
            todo = np.concatenate((self.buf, a))
        n = len(todo) // BLOCK * BLOCK
        self.buf = todo[n:].copy()
        out = np.empty(n, dtype=np.float32)
        ptr = self.frame.ctypes.data_as(ctypes.POINTER(ctypes.c_float))
        probs = []
        for i in range(0, n, BLOCK):
            self.frame[:] = todo[i:i + BLOCK] * 32768.0   # o RNNoise trabalha na escala de 16 bits
            probs.append(self.lib.rnnoise_process_frame(self.st, ptr, ptr))
            out[i:i + BLOCK] = self.frame / 32768.0
        if probs:
            self.prob = max(probs)
        return out

    def close(self):
        if self.st:
            self.lib.rnnoise_destroy(self.st)
            self.st = None


class VoiceFx:
    """Efeitos de voz ao vivo (só no microfone). Cada bloco sai com o mesmo tamanho com que entrou."""
    HIST = 16384                 # 340 ms de passado (o eco usa 250 ms; a troca de tom, 40 ms)
    PITCH = {"grave": 0.72, "agudo": 1.4}
    WIN = 1920                   # janela da troca de tom (40 ms)
    ECHO, ECHO_FB = 12000, 0.38  # eco: 250 ms, cada repetição a 38%

    def __init__(self):
        import numpy as np
        self.np = np
        self.n = 0                                   # amostras já processadas (relógio dos efeitos)
        self.x = np.zeros(self.HIST, dtype=np.float32)   # entrada passada
        self.y = np.zeros(self.HIST, dtype=np.float32)   # saída passada (eco)
        # rádio: passa-faixa 350-3200 Hz (FIR com janela de Hann)
        t = np.arange(129) - 64
        lp = lambda f: 2 * f / SR * np.sinc(2 * f / SR * t)  # noqa: E731
        self.bp = ((lp(3200) - lp(350)) * np.hanning(129)).astype(np.float32)

    def __call__(self, a, kind):
        np = self.np
        k = len(a)
        if not k:
            return a
        xh = np.concatenate((self.x, a))
        m = self.n + np.arange(k)
        if kind == "robo":        # modulação em anel: voz "metálica"
            out = a * np.sin(2 * np.pi * 55 * m / SR).astype(np.float32) * 1.6
        elif kind == "radio":     # faixa de telefone + saturação
            y = np.convolve(xh[-(k + len(self.bp) - 1):], self.bp, "valid")
            out = np.tanh(3 * y) / np.tanh(3) * 0.8
        elif kind in self.PITCH:  # dois leitores num atraso que varia (efeito Doppler), com crossfade
            r, w = self.PITCH[kind], self.WIN
            d1 = np.mod(m * (1 - r), w)
            d2 = np.mod(d1 + w / 2, w)
            idx = len(xh) - k + np.arange(k)

            def tap(d):
                pos = idx - d - 1
                i = np.floor(pos).astype(int)
                f = pos - i
                return xh[i] * (1 - f) + xh[i + 1] * f
            out = tap(d1) * np.sin(np.pi * d1 / w) ** 2 + tap(d2) * np.sin(np.pi * d2 / w) ** 2
        elif kind == "eco":
            out = a + self.ECHO_FB * self.y[-self.ECHO:-self.ECHO + k]
        else:
            out = a
        out = out.astype(np.float32)
        self.x = xh[-self.HIST:]
        self.y = np.concatenate((self.y, out))[-self.HIST:]
        self.n += k
        return out


class TalkLog:
    """Segundos falando por dia e contexto (reunião, jogo, outro), em voz.db."""

    def __init__(self, path):
        self.path = str(path)
        self.lock = threading.Lock()
        with self._db() as db:
            db.execute("CREATE TABLE IF NOT EXISTS talk (day TEXT, ctx TEXT, secs REAL, PRIMARY KEY (day, ctx))")

    def _db(self):
        return sqlite3.connect(self.path, timeout=5)

    def add(self, day, secs_by_ctx):
        with self.lock, self._db() as db:
            for ctx, secs in secs_by_ctx.items():
                db.execute("INSERT INTO talk VALUES (?, ?, ?) ON CONFLICT(day, ctx) DO UPDATE SET secs = secs + excluded.secs",
                           (day, ctx, secs))

    def day(self, day):
        with self.lock, self._db() as db:
            return dict(db.execute("SELECT ctx, secs FROM talk WHERE day = ?", (day,)).fetchall())


class TalkWatch:
    """Soma o tempo de fala por contexto e decide quando avisar "você está falando no mudo"."""
    WARN_S = 1.2       # segundos de voz no mudo...
    QUIET_S = 4        # ... sem pausa maior que isso (tosse e "hum" soltos não avisam)
    COOLDOWN_S = 25    # entre dois avisos
    FLUSH_S = 15       # de quanto em quanto tempo grava no voz.db

    def __init__(self, now=0.0):
        self.last = None
        self.pend = {}
        self.flushed = now
        self.muted_voice, self.muted_t, self.warned = 0.0, -1e9, -1e9

    def step(self, now, total, ctx, mute):
        """total: Board.talk_secs; ctx: "meet"/"game"/"other"; mute: onde está no mudo ("" se não está).
        Devolve o motivo do aviso (mute) quando é hora de avisar, senão None."""
        d = 0.0 if self.last is None else max(0.0, total - self.last)
        self.last = total
        if d:
            self.pend[ctx] = self.pend.get(ctx, 0.0) + d
        if not mute:
            self.muted_voice = 0.0
            return None
        if d:
            if now - self.muted_t > self.QUIET_S:
                self.muted_voice = 0.0
            self.muted_voice += d
            self.muted_t = now
            if self.muted_voice >= self.WARN_S and now - self.warned > self.COOLDOWN_S:
                self.warned, self.muted_voice = now, 0.0
                return mute
        return None

    def take(self, now, force=False):
        """O que juntou para gravar (a cada FLUSH_S, ou já se force)."""
        if self.pend and (force or now - self.flushed >= self.FLUSH_S):
            out, self.pend, self.flushed = self.pend, {}, now
            return out
        return None


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
        # não ficam salvos: ninguém quer abrir o PC amanhã com voz de robô ou mudo sem saber
        self.muted, self.fx = False, ""
        self._talk_t = -1e9             # última vez (monotonic) que ouviu voz
        self.talk_secs = 0.0            # total de segundos com voz desde que o servidor abriu
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
                "overlap": bool(self.cfg["overlap"]), "nr": bool(self.cfg["nr"]),
                "nr_ok": _rnnoise_lib() is not None, "muted": self.muted, "fx": self.fx, "fxs": FX,
                "talk": self.talking, "playing": playing}

    @property
    def talking(self):
        return bool(self.mic_name) and time.monotonic() - self._talk_t < TALK_HOLD

    def _vad(self, raw, prob):
        """Marca fala no bloco do microfone (antes de limpar). prob: chance do RNNoise, ou None sem ele."""
        rms = float((raw * raw).mean()) ** 0.5 if len(raw) else 0.0
        if (rms > VAD_RMS and prob > VAD_PROB) if prob is not None else rms > VAD_RMS_ONLY:
            self._talk_t = time.monotonic()
            self.talk_secs += len(raw) / SR

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
        for k in ("overlap", "nr"):
            if k in p:
                self.cfg[k] = bool(p[k])
        if "muted" in p:
            self.muted = not self.muted if p["muted"] == "toggle" else bool(p["muted"])
        if "fx" in p:
            fx = str(p["fx"] or "")
            if fx and fx not in FX:
                raise ValueError("efeito de voz inválido")
            self.fx = "" if p.get("toggle") and fx == self.fx else fx
        self._save_cfg(dict(self.cfg))
        self._notify()
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
            streams, nr = [], None
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
                    nr, fx = Denoiser(), VoiceFx()

                    def cb_in(indata, frames, _t, _s):
                        a = indata[:, 0].copy()
                        clean = nr(a)             # roda sempre: a chance de voz serve ao medidor
                        self._vad(a, nr.prob)
                        if self.cfg["nr"] and nr.st:
                            a = clean
                        if self.fx:
                            a = fx(a, self.fx)
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
                        if mic:   # sempre puxa (o atraso não cresce no mudo); no mudo, joga fora
                            m = self._pull_mic(np, frames)
                            if not self.muted:
                                out += m * (self.cfg["mic_vol"] / 100)
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
                if nr:
                    nr.close()
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
        key = (st["status"], tuple(st["playing"]), st["cable"], st["mic"], st["error"], st["talk"], st["muted"], st["fx"])
        if not force and key == self._sent:
            return
        self._sent = key
        if self.loop and self._event:
            try:
                asyncio.run_coroutine_threadsafe(self._event(st), self.loop)
            except RuntimeError:
                pass
