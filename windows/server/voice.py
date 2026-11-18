"""Comandos de voz: "PC, próxima música", "PC, abre o Spotify"...

Tudo roda no PC, offline:
  microfone -> detector de fala (energia) -> faster-whisper (texto) ->
  começa com "PC"? -> interpretador (parse) -> ação do servidor.

Só frases que começam com "PC" viram comando; o resto é descartado sem ir para
o log. Dizer só "PC" e parar abre uma janela de alguns segundos para o comando.
"""
import asyncio
import difflib
import logging
import os
import queue
import re
import tempfile
import threading
import time
import unicodedata
import wave
from pathlib import Path

log = logging.getLogger("companion")
for _n in ("faster_whisper", "httpx", "huggingface_hub"):
    logging.getLogger(_n).setLevel(logging.WARNING)

os.environ.setdefault("HF_HUB_DISABLE_PROGRESS_BARS", "1")  # pythonw não tem stderr
os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")
os.environ.setdefault("HF_HUB_DISABLE_TELEMETRY", "1")

DEFAULTS = {
    "enabled": True,
    "device": "",            # parte do nome do microfone; "" = o microfone padrão do Windows
    "speak": False,          # responder falando (voz do Windows)
    "beep": True,
    "model": "base",         # rápido (~0,5 s); "small" é mais preciso e ~3x mais lento
    "fallback_model": "small",  # usado de novo quando o rápido não entende o comando
    "follow_s": 6,           # depois de "PC" sozinho, quanto tempo espera o comando
}

# ==========================================================================
# Texto: normalização, números e o interpretador de comandos
# ==========================================================================
def norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", s.lower())
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = re.sub(r"(\d+)\s*h\s*(\d+)", r"\1 hora \2", s)       # 1h30
    s = re.sub(r"(\d+)\s*h\b", r"\1 hora", s)
    s = re.sub(r"(\d+)\s*%", r"\1 por cento", s)
    s = re.sub(r"[^a-z0-9+ ]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()


WAKE = {"pc", "pece", "pce", "pcs", "pecê", "pesse", "pesce", "pice", "pici", "pisi", "peace", "pecé", "bc", "tc"}
WAKE_PAIRS = {("p", "c"), ("pe", "ce"), ("pe", "se"), ("pi", "ci"), ("pi", "si"), ("pe", "c")}
LEAD = {"ei", "ok", "oi", "hey", "o", "e", "a", "ai", "eh"}


def split_wake(text: str):
    """(tem_wake, resto normalizado). O "PC" precisa vir no começo da frase."""
    t = norm(text).split()
    i = 0
    if t and t[0] in LEAD and len(t) > 1:
        i = 1
    if i < len(t) and t[i] in WAKE:
        return True, " ".join(t[i + 1:])
    if i + 1 < len(t) and (t[i], t[i + 1]) in WAKE_PAIRS:
        return True, " ".join(t[i + 2:])
    return False, ""


UNITS = {"zero": 0, "um": 1, "uma": 1, "dois": 2, "duas": 2, "tres": 3, "quatro": 4, "cinco": 5, "seis": 6,
         "sete": 7, "oito": 8, "nove": 9, "dez": 10, "onze": 11, "doze": 12, "treze": 13, "catorze": 14,
         "quatorze": 14, "quinze": 15, "dezesseis": 16, "dezessete": 17, "dezoito": 18, "dezenove": 19}
TENS = {"vinte": 20, "trinta": 30, "quarenta": 40, "cinquenta": 50, "sessenta": 60, "setenta": 70,
        "oitenta": 80, "noventa": 90, "cem": 100, "cento": 100}


def words_to_digits(s: str) -> str:
    """'vinte e cinco minutos' -> '25 minutos'."""
    out, cur, pend_e = [], None, False
    for w in s.split():
        v = UNITS.get(w, TENS.get(w))
        if w.isdigit():
            v = int(w)
        if v is not None:
            if cur is not None and pend_e and cur % 10 == 0 and (v < 10 or (cur == 100 and v < 100)):
                cur += v
            else:
                if cur is not None:
                    out.append(str(cur))
                cur = v
            pend_e = False
        elif w == "e" and cur is not None:
            pend_e = True
        else:
            if cur is not None:
                out.append(str(cur))
                if pend_e:
                    out.append("e")
                cur, pend_e = None, False
            out.append(w)
    if cur is not None:
        out.append(str(cur))
    return " ".join(out)


def parse_minutes(s: str):
    """'1 hora e 30', 'meia hora', 'uma hora e meia', '90 minutos', '10' -> minutos."""
    s = words_to_digits(s)
    if re.search(r"\bmeia hora\b", s) and not re.search(r"\d+ horas?", s):
        return 30
    total, found = 0.0, False
    m = re.search(r"(\d+) horas?(?: e)?(?: (\d+|meia))?(?! minutos?\b(?! e))", s)
    if m:
        total += int(m.group(1)) * 60
        if m.group(2):
            total += 30 if m.group(2) == "meia" else int(m.group(2))
        found = True
        s = s[:m.start()] + s[m.end():]
    m = re.search(r"(\d+) (?:minutos?|min)\b", s)
    if m:
        total += int(m.group(1))
        found = True
    elif not found:
        m = re.search(r"\b(\d+)\b", s)
        if m:
            total, found = int(m.group(1)), True
    return total if found and total > 0 else None


APP_ALIASES = {  # id do atalho -> outros jeitos de falar
    "opera": ["navegador", "browser", "opera", "opera gx", "internet"],
    "whatsapp": ["zap", "whats", "zapzap", "whatsapp"],
    "vscode": ["vs code", "visual studio code", "code", "editor"],
    "terminal": ["terminal", "prompt", "console"],
    "explorer": ["explorador", "arquivos", "explorer", "meu computador"],
    "obs": ["obs", "o b s"],
    "notepadpp": ["notepad", "notepad mais mais", "bloco de notas"],
    "calc": ["calculadora"],
    "taskmgr": ["gerenciador de tarefas", "gerenciador"],
    "settings": ["configuracoes", "configuracao", "ajustes"],
    "downloads": ["downloads", "pasta de downloads"],
    "epic": ["epic", "epic games"],
}

OPEN_RE = re.compile(r"^(?:(?:vamos|vou|quero|bora) )?(abre|abra|abrir|inicia|iniciar|executa|executar|roda|rodar|"
                     r"liga|ligar|joga|jogar|bota|botar|coloca|entra|entrar|carrega|starta|start|open|play)\b(.*)")
FILLER = re.compile(r"\b(o|a|os|as|um|uma|no|na|nos|nas|em|de|do|da|pra|para|por favor|ai|ae|pfv|agora|ali|jogo|app|programa|aplicativo)\b")


def _sim(a: str, b: str) -> float:
    if not a or not b:
        return 0.0
    if a == b:
        return 1.0
    r = difflib.SequenceMatcher(None, a, b).ratio()
    if len(a) >= 3 and (re.search(rf"\b{re.escape(a)}\b", b) or re.search(rf"\b{re.escape(b)}\b", a)):
        r = max(r, 0.86)
    ac, bc = a.replace(" ", ""), b.replace(" ", "")  # "counter strike" ~ "counterstrike"
    return max(r, difflib.SequenceMatcher(None, ac, bc).ratio())


class Catalog:
    """O que dá para abrir/apertar por voz. Preenchido pelo servidor."""

    def __init__(self, apps=(), games=(), deck=()):
        self.apps = list(apps)    # [(id, nome)]
        self.games = list(games)  # [(gid, nome)]
        self.deck = list(deck)    # [(page, index, rótulo)]

    def names(self):
        return [n for _i, n in self.apps] + [n for _i, n in self.games]

    def best_target(self, target: str, prefer_games=False):
        t = FILLER.sub(" ", target)
        t = re.sub(r"\s+", " ", t).strip()
        if not t:
            return None
        best = None
        for sid, name in self.apps:
            cands = [norm(name), sid] + APP_ALIASES.get(sid, [])
            sc = max(_sim(t, c) for c in cands) - (0.04 if prefer_games else 0)
            if not best or sc > best[0]:
                best = (sc, "app", sid, name)
        for gid, name in self.games:
            n = norm(name)
            words = [w for w in n.split() if w not in ("of", "the", "de", "do", "da")]
            initials = "".join(w[0] for w in words if not w.isdigit())
            sc = max(_sim(t, n), _sim(t, re.sub(r"\b\d+\b|\bgo\b", "", n).strip()),
                     1.0 if len(initials) >= 2 and t.replace(" ", "") in (initials, initials[:-1]) else 0)
            if prefer_games:
                sc += 0.04
            if not best or sc > best[0]:
                best = (sc, "game", gid, name)
        return best

    def best_deck(self, text: str):
        best = None
        for page, idx, label in self.deck:
            sc = _sim(text, norm(label))
            if not best or sc > best[0]:
                best = (sc, page, idx, label)
        return best


POWER_WORDS = [("monitor_off", r"(desliga|apaga|desligar|apagar) (a )?(tela|monitor)"),
               ("lock", r"(bloqueia|bloquear|trava|travar)"),
               ("sleep", r"(suspende|suspender|hiberna|hibernar|dorme|dormir|modo de suspensao)"),
               ("shutdown", r"(desliga|desligar|desligue)")]
POWER_LABEL = {"monitor_off": "Desligar monitor", "lock": "Bloquear", "sleep": "Suspender", "shutdown": "Desligar"}


def parse_command(cmd: str, cat: Catalog):
    """Texto já sem o "PC" -> {"action", "p", "say", "conf"} ou None (não entendi)."""
    c = words_to_digits(re.sub(r"\b(por favor|pfv|ai|ae)$", "", cmd).strip())
    if not c:
        return None
    has = lambda pat: re.search(rf"\b(?:{pat})\b", c)  # noqa: E731

    # --- timer / energia
    if has("cancela|cancelar|cancele|cancel") and has("timer|temporizador|desligamento|desligar|contagem|tudo"):
        return {"action": "timer.cancel", "p": {}, "say": "Timer cancelado", "conf": 1}
    for act, pat in POWER_WORDS:
        if re.search(rf"^(?:o pc |pc )?{pat}\b", c) or (act != "shutdown" and has(pat)):
            mins = parse_minutes(c) if has(r"em|daqui|depois|dentro|\d+") else None
            if mins:
                return {"action": "timer.start", "p": {"action": act, "minutes": mins},
                        "say": f"{POWER_LABEL[act]} em {_fmt_min(mins)}", "conf": 1}
            if act in ("lock", "monitor_off"):
                return {"action": "power", "p": {"action": act}, "say": POWER_LABEL[act], "conf": 1}
            if act == "shutdown" and has("som|musica|microfone|mic|discord|voz|tela|monitor"):
                break  # "desliga o som" etc. vão para as regras abaixo
            return {"error": f"Diga em quanto tempo: PC, {POWER_LABEL[act].lower()} em 10 minutos"}

    # --- microfone do PC / Discord / mudo
    if has("microfone|mic|mike"):
        if has("desmuta|desmutar|desmute|liga|ligar|ativa|ativar|abre|abrir|volta|tira do mudo"):
            return {"action": "mic.set", "p": {"muted": False}, "say": "Microfone ligado", "conf": 1}
        if has("muta|mutar|mute|desliga|desligar|silencia|mudo|corta|fecha|desativa"):
            return {"action": "mic.set", "p": {"muted": True}, "say": "Microfone no mudo", "conf": 1}
        return {"action": "mic.set", "p": {"muted": "toggle"}, "say": "Microfone alternado", "conf": 0.9}
    if has("discord|disco") and has("muta|mutar|mute|desmuta|desmutar|mudo"):
        return {"action": "discord.mute", "p": {}, "say": "Discord: mudo alternado", "conf": 1}
    if has("ensurdece|ensurdecer|surdo|deafen"):
        return {"action": "discord.deafen", "p": {}, "say": "Discord: ensurdecer alternado", "conf": 1}

    # --- volume
    up = has("aumenta|aumentar|aumente|sobe|subir|mais alto|aumenta o som")
    down = has("abaixa|abaixar|abaixe|diminui|diminuir|diminua|baixa|mais baixo|desce")
    m = None if up or down else re.search(r"\bvolume\b(?: (?:no|em|pra|para|a|o))?(?: (?:no|em|pra|para))? (\d+)\b", c) or \
        re.search(r"\b(?:poe|coloca|bota|deixa)\b.*\bvolume\b.*?\b(\d+)\b", c)
    if m:
        lvl = max(0, min(100, int(m.group(1))))
        return {"action": "volume.set", "p": {"level": lvl}, "say": f"Volume {lvl}", "conf": 1}
    if has("volume") and has("maximo|max|tudo"):
        return {"action": "volume.set", "p": {"level": 100}, "say": "Volume 100", "conf": 1}
    if has("volume") and has("metade"):
        return {"action": "volume.set", "p": {"level": 50}, "say": "Volume 50", "conf": 1}
    step = re.search(r"\b(\d+)\b", c)
    step = int(step.group(1)) if step else 10
    if up:
        return {"action": "volume.change", "p": {"delta": step}, "say": f"Volume +{step}", "conf": 1}
    if down:
        return {"action": "volume.change", "p": {"delta": -step}, "say": f"Volume -{step}", "conf": 1}
    if has("muta|mutar|mute|desmuta|desmutar|silencio|silencia|tira o som|volta o som|mudo|desliga o som|liga o som"):
        return {"action": "media.mute", "p": {}, "say": "Som do PC: mudo alternado", "conf": 1}

    # --- saída de áudio, print
    if has("troca|trocar|muda|mudar|alterna|alternar|passa") and has("saida|audio|som|fone|fones|caixa|caixas|headset|alto falante"):
        return {"action": "audio.cycle", "p": {}, "say": "Saída de áudio trocada", "conf": 1}
    if has("print|printa|captura|screenshot|foto da tela"):
        return {"action": "key.press", "p": {"keys": "win+printscreen"}, "say": "Print salvo em Imagens", "conf": 1}

    # --- mídia
    if has("que musica|qual musica|o que ta tocando|o que esta tocando|que som e esse|tocando agora"):
        return {"action": "media.what", "p": {}, "say": "", "conf": 1}
    if has("proxima|proximo|pula|pular|pule|avanca|avancar|next|skip") or c in ("passa", "passa a musica"):
        return {"action": "media.next", "p": {}, "say": "Próxima", "conf": 1}
    if has("anterior|volta a musica|voltar a musica|musica de antes|previous|volta uma") or c in ("volta",):
        return {"action": "media.prev", "p": {}, "say": "Anterior", "conf": 1}
    if has("pausa|pausar|pause|pausa a musica|para a musica|parar a musica|stop") or c in ("para", "parar"):
        return {"action": "media.pause", "p": {}, "say": "Pausado", "conf": 1}
    if has("toca|tocar|play|continua|continuar|despausa|despausar|solta o som|solta a musica|volta a tocar"):
        return {"action": "media.play", "p": {}, "say": "Tocando", "conf": 1}

    # --- abrir app / jogo
    m = OPEN_RE.match(c)
    if m:
        verb, target = m.group(1), m.group(2).strip()
        best = cat.best_target(target, prefer_games=verb in ("joga", "jogar", "play"))
        if best and best[0] >= 0.62:
            sc, kind, ident, name = best
            sc = min(1.0, sc)
            if kind == "app":
                return {"action": "app.launch", "p": {"id": ident}, "say": f"Abrindo {name}", "conf": sc}
            return {"action": "games.launch", "p": {"id": ident}, "say": f"Abrindo {name}", "conf": sc}
        if target:
            shown = re.sub(r"\s+", " ", FILLER.sub(" ", target)).strip() or target
            return {"error": f"Não achei \"{shown}\" nos atalhos nem nos jogos", "conf": best[0] if best else 0}

    # --- botões do deck (macros etc.): "PC, ausente", "PC, aperta modo stream"
    explicit = re.match(r"^(?:aperta|apertar|aperte|botao|clica|clicar|ativa|ativar|executa|roda|modo)\b(.*)", c)
    target = FILLER.sub(" ", explicit.group(1) if explicit else c).strip()
    best = cat.best_deck(re.sub(r"\s+", " ", target))
    if best and best[0] >= (0.6 if explicit else 0.8):
        sc, page, idx, label = best
        return {"action": "deck.press", "p": {"page": page, "index": idx}, "say": label, "conf": sc}
    return None


def _fmt_min(m):
    m = int(round(m))
    if m < 60:
        return f"{m} min"
    h, r = divmod(m, 60)
    return f"{h} h" + (f" {r:02d}" if r else "")


def interpret(text: str, cat: Catalog, following=False):
    """-> (wake?, comando, intent|None). following = já ouviu "PC" e espera o comando."""
    wake, rest = split_wake(text)
    if not wake:
        if not following:
            return False, "", None
        rest = norm(text)
    if not rest:
        return True, "", None
    return True, rest, parse_command(rest, cat)


# ==========================================================================
# Áudio: microfone, detector de fala, Whisper, bipes e voz
# ==========================================================================
SR = 16000
FRAME = 480  # 30 ms


def _tone_wav(path, notes, vol=0.25):
    import numpy as np
    parts = []
    for freq, ms in notes:
        n = int(SR * ms / 1000)
        t = np.arange(n) / SR
        env = np.minimum(1, np.minimum(t, t[::-1]) / 0.008)  # sem estalo
        parts.append(np.sin(2 * np.pi * freq * t) * env * vol if freq else np.zeros(n))
    data = (np.concatenate(parts) * 32767).astype("<i2")
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(data.tobytes())


class Voice:
    def __init__(self, cfg: dict, base: Path, save_cfg, catalog_fn, run_fn, event_fn, mic_fn=None):
        self.cfg = {**DEFAULTS, **(cfg or {})}
        self.base = base
        self._save_cfg = save_cfg      # (dict) -> None, grava no config.json
        self._catalog = catalog_fn     # () -> Catalog
        self._run = run_fn             # async (intent) -> mensagem
        self._event = event_fn         # async (dict) -> None, avisa o celular
        self._mic = mic_fn             # async () -> {"muted", "name"} do microfone padrão
        self.fallback = False          # ouvindo por outro microfone porque o principal está mudo
        self.loop = None
        self.status, self.error, self.device_name = "off", "", ""
        self.last = None
        self.models = {}
        self._thread, self._stop = None, threading.Event()
        self._mute_until = 0.0
        self._follow_until = 0.0
        self._tts_q = None
        try:
            import faster_whisper  # noqa: F401
            import numpy  # noqa: F401
            import sounddevice  # noqa: F401
            self.available = True
        except Exception as e:  # noqa: BLE001
            self.available, self.error = False, f"faltam pacotes: {e}"
        self._sounds = {}

    # ---------------------------------------------------------------- controle
    def state(self):
        return {"available": self.available, "on": bool(self.cfg["enabled"]), "status": self.status,
                "error": self.error, "device": self.device_name, "pick": self.cfg["device"], "fallback": self.fallback,
                "speak": bool(self.cfg["speak"]), "last": self.last}

    def start(self, loop):
        self.loop = loop
        if self.available and self.cfg["enabled"]:
            self._spawn()

    def _spawn(self):
        self._stop.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(3)
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._worker, args=(self._stop,), daemon=True, name="voz")
        self._thread.start()

    def set(self, p):
        restart = False
        if "on" in p:
            self.cfg["enabled"] = (not self.cfg["enabled"]) if p["on"] == "toggle" else bool(p["on"])
            restart = True
        if "device" in p:
            self.cfg["device"] = str(p["device"] or "")[:80]
            restart = True
        if "speak" in p:
            self.cfg["speak"] = bool(p["speak"])
        self._save_cfg(dict(self.cfg))
        if restart and self.available:
            if self.cfg["enabled"]:
                self._spawn()
            else:
                self._stop.set()
                self.status = "off"
        log.info("voz: %s", {k: self.cfg[k] for k in ("enabled", "device", "speak")})
        return self.state()

    @staticmethod
    def devices():
        import sounddevice as sd
        mme = next((i for i, h in enumerate(sd.query_hostapis()) if h["name"] == "MME"), None)
        out = []
        for d in sd.query_devices():
            if d["max_input_channels"] > 0 and d["hostapi"] == mme and "mapeador" not in d["name"].lower() \
                    and "mapper" not in d["name"].lower():
                out.append(d["name"])
        return out

    def _pick_device(self, default=None, avoid=None):
        """Microfone escolhido no app ou, no automático, o padrão do Windows (default).
        avoid = nome do microfone mudo: escolhe outro físico (ex.: o da webcam)."""
        import sounddevice as sd
        names = self.devices()
        want = self.cfg["device"].lower()
        pick = next((n for n in names if want and want in n.lower()), None)
        if not pick and default:  # o MME corta o nome em 31 letras
            pick = next((n for n in names if n == default or default.startswith(n)), None)
        if avoid:
            key = re.sub(r"^.*\(|\).*$", "", avoid).lower().strip()[:20] or avoid.lower()
            others = [n for n in names if key[:20] not in n.lower()
                      and not any(v in n.lower() for v in ("rtx voice", "broadcast", "steam", "virtual", "cable"))]
            if not others:
                return None, None
            pick = next((n for n in others if "webcam" in n.lower() or "cam" in n.lower()), others[0])
        mme = next((i for i, h in enumerate(sd.query_hostapis()) if h["name"] == "MME"), None)
        for i, d in enumerate(sd.query_devices()):
            if d["name"] == pick and d["hostapi"] == mme:
                return i, pick
        return None, "padrão do Windows"

    # ---------------------------------------------------------------- modelo
    def _model(self, name):
        if name not in self.models:
            from faster_whisper import WhisperModel
            t = time.time()
            kw = dict(device="cpu", compute_type="int8", cpu_threads=4, download_root=str(self.base / "models"))
            try:
                self.models[name] = WhisperModel(name, local_files_only=True, **kw)
            except Exception:  # noqa: BLE001  (primeira vez: baixa ~75 MB base / ~250 MB small)
                log.info("voz: baixando o modelo %s...", name)
                self.models[name] = WhisperModel(name, **kw)
            log.info("voz: modelo %s carregado em %.1fs", name, time.time() - t)
        return self.models[name]

    def _prompt(self, cat):
        names = ", ".join(cat.names()[:40])
        return f"PC, próxima música. PC, volume 30. PC, abre o Spotify. PC, desliga em 1 hora. {names}."

    def _transcribe(self, model, audio, prompt):
        segs, _ = self._model(model).transcribe(audio, language="pt", beam_size=1, initial_prompt=prompt,
                                                condition_on_previous_text=False, without_timestamps=True,
                                                vad_filter=False, temperature=0)
        return "".join(s.text for s in segs).strip()

    # ---------------------------------------------------------------- loop de áudio
    def _worker(self, stop):
        import numpy as np
        import sounddevice as sd
        self.error = ""
        try:
            self.status = "loading"
            self._prepare_sounds()
            self._model(self.cfg["model"])
            idx, self.device_name = self._pick_device()
        except Exception as e:  # noqa: BLE001
            log.exception("voz: falha ao iniciar")
            self.status, self.error = "error", str(e)[:200]
            return
        frames = queue.Queue()

        def cb(indata, _n, _t, _s):
            frames.put(indata[:, 0].copy())

        while not stop.is_set():
            info = self._mic_info()
            muted = info["name"] if info.get("muted") else None
            self.fallback = False
            try:
                idx, self.device_name = self._pick_device(default=info.get("name"))
            except Exception:  # noqa: BLE001
                pass
            if muted:
                alt = self._pick_device(avoid=muted)
                if alt[0] is not None:
                    (idx, self.device_name), self.fallback = alt, True
            try:
                with sd.InputStream(device=idx, channels=1, samplerate=SR, blocksize=FRAME, dtype="float32", callback=cb):
                    self.status, self.error = "listening", ""
                    log.info("voz: ouvindo (%s)%s", self.device_name, " - o principal está no mudo" if self.fallback else "")
                    self._listen(stop, frames, np, (bool(muted), info.get("name")))
                    while not frames.empty():
                        frames.get_nowait()
            except Exception as e:  # noqa: BLE001  (microfone desconectado etc.)
                if stop.is_set():
                    break
                log.warning("voz: microfone: %s", e)
                self.status, self.error = "error", f"microfone: {str(e)[:150]}"
                stop.wait(5)
        if self.status != "error":
            self.status = "off"

    def _mic_info(self):
        """Microfone padrão do Windows: {"name", "muted"} (vazio se não der para saber)."""
        if not self._mic or not self.loop:
            return {}
        try:
            return asyncio.run_coroutine_threadsafe(self._mic(), self.loop).result(timeout=5) or {}
        except Exception:  # noqa: BLE001
            return {}

    def _listen(self, stop, frames, np, sig):
        """Ouve até parar, ou até o microfone padrão do Windows mudar ou ir para o mudo (aí reabre)."""
        floor, pre, buf = 0.003, [], None
        hits, silence, too_long = [], 0, False
        next_check = time.monotonic() + 2
        while not stop.is_set():
            if buf is None and time.monotonic() > next_check:
                next_check = time.monotonic() + 2
                info = self._mic_info()
                if info and (bool(info.get("muted")), info.get("name")) != sig:
                    return
            try:
                f = frames.get(timeout=0.5)
            except queue.Empty:
                continue
            rms = float(np.sqrt(np.mean(f * f)))
            thr = max(floor * 3.0, 0.006)
            loud = rms > thr
            if buf is None:
                if not loud:
                    floor = floor * 0.97 + rms * 0.03
                pre.append(f)
                pre = pre[-10:]
                hits = (hits + [loud])[-6:]
                if sum(hits) >= 4:
                    buf, silence, too_long = list(pre), 0, False
                    hits = []
                continue
            buf.append(f)
            silence = 0 if rms > thr * 0.7 else silence + 1
            if len(buf) * FRAME > SR * 8:
                too_long, buf = True, buf[-30:]  # fala longa: não é comando, só espera acabar
            if silence >= 27:  # ~0,8 s de silêncio
                audio, buf, pre = np.concatenate(buf), None, []
                if not too_long and len(audio) > SR * 0.35 and time.monotonic() > self._mute_until:
                    try:
                        self._handle(audio, np)
                    except Exception:  # noqa: BLE001
                        log.exception("voz")
                    while frames.qsize() > 60:  # se ficou muito atrasado, descarta
                        frames.get_nowait()

    def _handle(self, audio, np):
        cat = self._catalog()
        prompt = self._prompt(cat)
        audio = audio / max(0.05, float(np.abs(audio).max())) * 0.9  # normaliza o volume
        audio = np.concatenate([np.zeros(SR // 5, "float32"), audio.astype("float32")])
        following = time.monotonic() < self._follow_until
        t = time.time()
        text = self._transcribe(self.cfg["model"], audio, prompt)
        wake, cmd, intent = interpret(text, cat, following)
        if not wake:
            return  # conversa normal: nem vai para o log
        fb = self.cfg.get("fallback_model")
        if cmd and (not intent or intent.get("conf", 1) < 0.8) and fb and fb != self.cfg["model"]:
            text2 = self._transcribe(fb, audio, prompt)
            w2, cmd2, it2 = interpret(text2, cat, following)
            if w2 and it2 and not it2.get("error") and (not intent or it2.get("conf", 1) >= intent.get("conf", 0)):
                text, cmd, intent = text2, cmd2, it2
        log.info("voz: \"%s\" (%.1fs) -> %s", text, time.time() - t, (intent or {}).get("action") or (intent or {}).get("error"))
        if not cmd:  # só "PC": espera o comando
            self._follow_until = time.monotonic() + self.cfg["follow_s"]
            self._beep("wake")
            self._post({"t": "event", "kind": "voice", "phase": "wake"})
            return
        self._follow_until = 0
        if not intent:
            self._finish(text, False, "Não entendi")
            return
        if intent.get("error"):
            self._finish(text, False, intent["error"])
            return
        try:
            fut = asyncio.run_coroutine_threadsafe(self._run(intent), self.loop)
            msg = fut.result(timeout=20)
            self._finish(text, True, msg or intent.get("say") or "Feito")
        except Exception as e:  # noqa: BLE001
            self._finish(text, False, str(e)[:120] or "falhou")

    def _finish(self, text, ok, msg):
        self.last = {"text": text, "ok": ok, "msg": msg, "at": int(time.time())}
        self._beep("ok" if ok else "err")
        if self.cfg["speak"] and msg:
            self._say(msg)
        self._post({"t": "event", "kind": "voice", "phase": "done", **self.last})

    def _post(self, ev):
        if self.loop:
            asyncio.run_coroutine_threadsafe(self._event(ev), self.loop)

    # ---------------------------------------------------------------- bipes e voz
    def _prepare_sounds(self):
        d = Path(tempfile.gettempdir()) / "companion-pc-sons"
        d.mkdir(exist_ok=True)
        spec = {"wake": [(660, 70), (0, 25), (990, 90)], "ok": [(880, 60), (0, 20), (1320, 70)],
                "err": [(330, 120), (0, 40), (260, 160)]}
        for k, notes in spec.items():
            p = d / f"{k}.wav"
            if not p.exists():
                _tone_wav(p, notes)
            self._sounds[k] = str(p)

    def _beep(self, kind):
        if not self.cfg["beep"] or kind not in self._sounds:
            return
        try:
            import winsound
            winsound.PlaySound(self._sounds[kind], winsound.SND_FILENAME | winsound.SND_ASYNC | winsound.SND_NODEFAULT)
        except Exception:  # noqa: BLE001
            pass

    def _say(self, text):
        if self._tts_q is None:
            self._tts_q = queue.Queue()
            threading.Thread(target=self._tts_worker, daemon=True, name="voz-tts").start()
        self._tts_q.put(text)

    def _tts_worker(self):
        try:
            import comtypes.client
            comtypes.CoInitialize()
            sp = comtypes.client.CreateObject("SAPI.SpVoice")
            for v in sp.GetVoices():
                if "pt-br" in v.GetDescription().lower() or "maria" in v.GetDescription().lower():
                    sp.Voice = v
                    break
        except Exception:  # noqa: BLE001
            log.exception("voz: sem síntese de fala")
            return
        while True:
            text = self._tts_q.get()
            self._mute_until = time.monotonic() + 30  # não escuta a própria voz
            try:
                time.sleep(0.25)  # deixa o bipe tocar antes
                sp.Speak(text, 0)
            except Exception:  # noqa: BLE001
                log.exception("voz: falar")
            self._mute_until = time.monotonic() + 0.4
