"""HTTPS para o app: certificado do Tailscale (ou um par cert/key qualquer, ex.: mkcert).

Com HTTPS o navegador trata o app como "seguro" também fora do cabo: instala como app (inclusive
no iPhone), notificações, tela ligada sem truque, "Compartilhar com" e o service worker.

Tailscale: no painel (login.tailscale.com > DNS) ative MagicDNS e HTTPS Certificates. O endereço
fica https://<pc>.<tailnet>.ts.net:<porta> e funciona em casa e fora, em qualquer aparelho com o
Tailscale ligado na mesma conta. O certificado vale 90 dias; o servidor pede de novo todo dia
(o tailscale só renova quando está perto de vencer).
"""
import json
import logging
import os
import shutil
import ssl
import subprocess
import time
from pathlib import Path

log = logging.getLogger("companion")

NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)
TS_CANDIDATES = [r"%ProgramFiles%\Tailscale\tailscale.exe", r"%ProgramFiles(x86)%\Tailscale\tailscale.exe"]
DEFAULT = {"enabled": True, "port": 8771, "cert_file": "", "key_file": ""}
RENEW_S = 24 * 3600


def find_tailscale():
    for c in ["tailscale"] + [os.path.expandvars(p) for p in TS_CANDIDATES]:
        found = shutil.which(c) or (c if os.path.isfile(c) else None)
        if found:
            return found
    return None


def dns_name(status):
    """Nome MagicDNS deste PC a partir de `tailscale status --json` (None se desligado ou sem MagicDNS)."""
    if not isinstance(status, dict) or status.get("BackendState") != "Running":
        return None
    name = str((status.get("Self") or {}).get("DNSName") or "").rstrip(".").lower()
    return name if name.endswith(".ts.net") else None


def explain(stderr):
    """Mensagem de erro do `tailscale cert` em português, com o que fazer."""
    s = (stderr or "").lower()
    if "not enabled" in s or "does not support" in s or "https" in s and "enable" in s:
        return "HTTPS desativado no Tailscale: no painel (DNS) ative MagicDNS e HTTPS Certificates"
    if "access denied" in s or "permission" in s:
        return "o Tailscale recusou (permissão): rode o servidor com o mesmo usuário logado no Tailscale"
    return (stderr or "falhou").strip().splitlines()[-1][:200]


class Https:
    def __init__(self, base, cfg):
        self.cfg = {**DEFAULT, **(cfg or {})}
        self.dir = Path(base) / "certs"
        self.ctx = None
        self.host = None          # nome que vai no link (o do certificado)
        self.mode = "off"         # off | tailscale | manual
        self.error = ""
        self.renewed = 0.0

    @property
    def port(self):
        return int(self.cfg["port"])

    @property
    def enabled(self):
        return bool(self.cfg.get("enabled"))

    def state(self):
        return {"on": self.ctx is not None, "mode": self.mode, "host": self.host, "port": self.port,
                "error": self.error, "url": self.url()}

    def url(self):
        return f"https://{self.host}:{self.port}/" if self.ctx and self.host else None

    def _run(self, exe, *args, timeout=60):
        return subprocess.run([exe, *args], capture_output=True, text=True, timeout=timeout, creationflags=NO_WINDOW)

    def obtain(self):
        """Arruma o par cert/key. Devolve (cert, key, host) ou None (e deixa o motivo em self.error)."""
        cert, key = self.cfg.get("cert_file"), self.cfg.get("key_file")
        if cert and key:
            cert, key = os.path.expandvars(cert), os.path.expandvars(key)
            if not (os.path.isfile(cert) and os.path.isfile(key)):
                self.error = "cert_file/key_file do config.json não existem"
                return None
            self.mode = "manual"
            return cert, key, self.cfg.get("host") or None
        exe = find_tailscale()
        if not exe:
            self.error = "Tailscale não instalado (ou configure cert_file/key_file)"
            return None
        try:
            st = json.loads(self._run(exe, "status", "--json", timeout=15).stdout or "{}")
        except (OSError, ValueError, subprocess.TimeoutExpired) as e:
            self.error = f"não consegui ler o estado do Tailscale: {e}"
            return None
        host = dns_name(st)
        if not host:
            self.error = "Tailscale desligado ou sem MagicDNS"
            return None
        self.dir.mkdir(exist_ok=True)
        cert, key = self.dir / f"{host}.crt", self.dir / f"{host}.key"
        try:
            r = self._run(exe, "cert", "--cert-file", str(cert), "--key-file", str(key), host)
        except (OSError, subprocess.TimeoutExpired) as e:
            self.error = f"tailscale cert: {e}"
            return None
        if r.returncode != 0 or not cert.is_file():
            self.error = explain(r.stderr or r.stdout)
            return None
        self.mode = "tailscale"
        return str(cert), str(key), host

    def refresh(self):
        """Pede/renova o certificado e (re)carrega no contexto TLS. True se há HTTPS utilizável."""
        got = self.obtain()
        self.renewed = time.time()
        if not got:
            log.warning("HTTPS indisponível: %s", self.error)
            return self.ctx is not None   # certificado anterior continua valendo até vencer
        cert, key, host = got
        try:
            ctx = self.ctx or ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
            ctx.minimum_version = ssl.TLSVersion.TLSv1_2
            ctx.load_cert_chain(cert, key)   # no contexto já em uso: vale para as próximas conexões
        except (OSError, ssl.SSLError) as e:
            self.error = f"certificado inválido: {e}"
            log.warning("HTTPS: %s", self.error)
            return self.ctx is not None
        self.ctx, self.host, self.error = ctx, host, ""
        log.info("HTTPS pronto (%s): %s", self.mode, self.url() or f"porta {self.port}")
        return True

    def due(self):
        return time.time() - self.renewed > RENEW_S
