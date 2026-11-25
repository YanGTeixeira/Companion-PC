"""Apps do Menu Iniciar (Get-StartApps): programas comuns e da Microsoft Store (Spotify, WhatsApp...).

Usado pela voz ("PC, abre o Spotify") quando o app não está nos atalhos do config.json.
Abre por shell:AppsFolder\\<AppID>, o mesmo que clicar no Menu Iniciar; só IDs que estão na lista abrem.
"""
import json
import logging
import re
import subprocess
import threading
import time

log = logging.getLogger("companion")

REFRESH_S = 600
# atalhos do Menu Iniciar que ninguém quer abrir por voz
SKIP = re.compile(r"uninstall|desinstal|unins\d|readme|leia-me|release notes|\bhelp\b|\bajuda\b|manual|"
                  r"licen[cs]|website|support|documenta", re.I)
PS = ("[Console]::OutputEncoding=[Text.Encoding]::UTF8; "
      "Get-StartApps | Select-Object Name, AppID | ConvertTo-Json -Compress")


def clean(items):
    """[{Name, AppID}] -> [(AppID, nome)] sem desinstaladores, links e repetidos."""
    out, seen = [], set()
    for it in items or []:
        name, appid = str(it.get("Name") or "").strip(), str(it.get("AppID") or "").strip()
        if not name or not appid or SKIP.search(name) or re.match(r"^[a-z]+://", appid, re.I):
            continue
        if name.lower() in seen:
            continue
        seen.add(name.lower())
        out.append((appid, name))
    return out


class StartApps:
    def __init__(self):
        self.apps: list = []
        self.t = 0.0
        self._lock = threading.Lock()

    def _load(self):
        r = subprocess.run(["powershell", "-NoProfile", "-Command", PS], capture_output=True, timeout=30,
                           creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        data = json.loads(r.stdout.decode("utf-8-sig") or "[]")
        return clean(data if isinstance(data, list) else [data])

    def get(self):
        """Lista em cache (recarrega a cada 10 min). Nunca levanta erro."""
        with self._lock:
            if time.monotonic() - self.t > REFRESH_S or not self.t:
                try:
                    self.apps = self._load()
                except Exception as e:  # noqa: BLE001
                    log.warning("apps do Menu Iniciar: %s", e)
                self.t = time.monotonic()
            return self.apps

    def name_of(self, appid):
        return next((n for a, n in self.get() if a == appid), None)
