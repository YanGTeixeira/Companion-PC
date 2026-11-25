"""Atualização automática pelo GitHub.

Quem publica roda tools/release.sh: ele grava release.json na raiz do repositório (versão + novidades),
cria a tag v<versão> e manda tudo para o GitHub. Aqui o servidor lê esse release.json de tempos em tempos
(raw.githubusercontent, sem limite de API) e, se a versão for maior que a instalada, oferece atualizar.
Atualizar = baixar o zip da tag, extrair numa pasta temporária e rodar o install-server.ps1 de lá
(copia os arquivos, instala dependências novas e reinicia o servidor). config.json, deck.json etc. ficam.
"""
import json
import logging
import re
import shutil
import subprocess
import tempfile
import threading
import time
import urllib.request
import zipfile
from pathlib import Path

log = logging.getLogger("companion")

DEFAULT = {"repo": "YanGTeixeira/Companion-PC", "branch": "main", "check": True}
CHECK_EVERY_S = 6 * 3600
UA = {"User-Agent": "CompanionPC-updater"}


def vtuple(v):
    """'v1.10' -> (1, 10). Partes não numéricas viram 0."""
    return tuple(int(x) if x.isdigit() else 0 for x in re.split(r"[.\-]", str(v).strip().lstrip("vV")) if x)


class Updater:
    def __init__(self, version: str, cfg: dict, base: Path):
        self.version = version
        self.cfg = {**DEFAULT, **(cfg or {})}
        self.base = base
        self.latest = None      # {"version", "notes"} quando há versão nova
        self.checked = 0.0
        self.err = None
        self.busy = None        # texto do que está fazendo ("Baixando…") ou None
        self._lock = threading.Lock()
        self.on_change = None   # callback(state) — o servidor avisa os aparelhos

    def state(self):
        return {"current": self.version, "latest": (self.latest or {}).get("version"),
                "notes": (self.latest or {}).get("notes", ""), "busy": self.busy, "err": self.err,
                "checked": int(self.checked)}

    @property
    def available(self):
        return bool(self.latest)

    def _get(self, url, timeout=20):
        with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=timeout) as r:
            return r.read()

    def check(self):
        """Lê o release.json publicado. Devolve state()."""
        repo, branch = self.cfg["repo"], self.cfg["branch"]
        try:
            # o parâmetro muda a URL a cada vez: a CDN do GitHub segura cópia por ~5 min
            raw = self._get(f"https://raw.githubusercontent.com/{repo}/{branch}/release.json?t={int(time.time())}")
            info = json.loads(raw)
            v = str(info["version"])
            if not re.fullmatch(r"\d+(\.\d+){0,3}", v):
                raise ValueError(f"versão inválida no release.json: {v}")
            self.latest = {"version": v, "notes": str(info.get("notes", ""))[:2000]} \
                if vtuple(v) > vtuple(self.version) else None
            self.err = None
            if self.latest:
                log.info("atualização disponível: %s -> %s", self.version, v)
        except Exception as e:  # noqa: BLE001
            self.err = f"não deu para ver se há atualização: {e}"
            log.warning(self.err)
        self.checked = time.time()
        self._changed()
        return self.state()

    def _changed(self):
        if self.on_change:
            try:
                self.on_change(self.state())
            except Exception:  # noqa: BLE001
                log.exception("updater: avisar")

    def install(self):
        """Baixa a versão nova e roda o instalador dela (que reinicia o servidor). Bloqueia até disparar."""
        if not self._lock.acquire(blocking=False):
            raise RuntimeError("a atualização já está em andamento")
        try:
            if not self.latest:
                self.check()
            if not self.latest:
                raise RuntimeError(self.err or "já está na versão mais nova")
            v = self.latest["version"]
            self.busy = f"Baixando a versão {v}…"
            self._changed()
            work = Path(tempfile.gettempdir()) / "companion-pc-update"
            shutil.rmtree(work, ignore_errors=True)
            work.mkdir(parents=True)
            zpath = work / f"v{v}.zip"
            zpath.write_bytes(self._get(f"https://github.com/{self.cfg['repo']}/archive/refs/tags/v{v}.zip", 120))
            with zipfile.ZipFile(zpath) as z:
                z.extractall(work / "src")   # extractall já recusa caminhos com ".." ou absolutos
            found = list((work / "src").glob("*/windows/install-server.ps1"))
            if not found:
                raise RuntimeError("o pacote baixado não tem windows/install-server.ps1")
            src = found[0].parent
            logf = self.base / "update.log"
            self.busy = f"Instalando a versão {v}… o servidor reinicia sozinho"
            self._changed()
            log.info("atualizando para %s a partir de %s", v, src)
            # grupo próprio: sobrevive quando o instalador encerra este servidor
            # (DETACHED_PROCESS não serve: o PowerShell sem console nem chega a rodar)
            q = lambda x: "'" + str(x).replace("'", "''") + "'"  # aspas do PowerShell
            cmd = f"& {q(src / 'install-server.ps1')} -Source {q(src)} *> {q(logf)}"
            subprocess.Popen(
                ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", cmd],
                cwd=str(src),
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0) | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0),
                close_fds=True,
            )
            return {"ok": True, "version": v}
        except Exception as e:
            self.busy = None
            self.err = f"a atualização falhou: {e}"
            log.exception("atualização")
            self._changed()
            raise RuntimeError(self.err) from None
        finally:
            self._lock.release()

    def loop_forever(self, stop=lambda: False):
        """Thread: confere ao iniciar (depois de 1 min) e a cada 6 h."""
        if not self.cfg.get("check", True):
            return
        time.sleep(60)
        while not stop():
            self.check()
            time.sleep(CHECK_EVERY_S)


def run_detached_check(upd: Updater):
    threading.Thread(target=upd.loop_forever, daemon=True, name="updater").start()

