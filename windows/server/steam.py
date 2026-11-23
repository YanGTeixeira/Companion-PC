"""Steam: downloads/atualizações (dos arquivos appmanifest no PC, sem chave) e amigos (Web API, com a chave do usuário).

A Steam regrava o appmanifest de tempos em tempos durante o download, então o progresso anda em passos.
Amigos: GetFriendList + GetPlayerSummaries com a chave de steamcommunity.com/dev/apikey; a lista de amigos
precisa estar visível (público ou só amigos) no perfil.
"""
import glob
import json
import logging
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from games import _ci, parse_vdf

log = logging.getLogger("companion")

# EAppState
F_UPDATE_REQUIRED, F_INSTALLED, F_RUNNING, F_PAUSED, F_STARTED = 2, 4, 256, 512, 1024
F_VALIDATING, F_ALLOCATING, F_DOWNLOADING, F_STAGING, F_COMMITTING = 131072, 524288, 1048576, 2097152, 4194304
PERSONA = {0: "offline", 1: "online", 2: "ocupado", 3: "ausente", 4: "ausente", 5: "online", 6: "online"}
KEY_RE = re.compile(r"[0-9A-Fa-f]{32}")


def _state(flags):
    if flags & F_PAUSED:
        return "pausado"
    if flags & F_VALIDATING:
        return "verificando"
    if flags & (F_STAGING | F_COMMITTING):
        return "instalando"
    if flags & F_ALLOCATING:
        return "reservando espaço"
    if flags & (F_DOWNLOADING | F_RUNNING | F_STARTED):
        return "baixando"
    if flags & F_UPDATE_REQUIRED:
        return "na fila"
    return None


class Steam:
    def __init__(self, catalog, cfg):
        self.catalog, self.cfg = catalog, cfg
        self.prev = {}          # appid -> (bytes, time) para a velocidade
        self.active = {}        # appid -> nome (para avisar quando terminar)
        self.friend_ids, self.friend_ids_t = [], 0.0
        self.err = None

    # ---------------------------------------------------------------- downloads
    def _libs(self):
        sp = getattr(self.catalog, "steam_path", None)
        if not sp or not os.path.isdir(sp):
            return []
        libs = {os.path.normcase(sp)}
        try:
            lf = parse_vdf(Path(sp, "steamapps", "libraryfolders.vdf").read_text(encoding="utf-8", errors="ignore"))
            for v in (_ci(lf, "libraryfolders") or {}).values():
                if isinstance(v, dict) and v.get("path"):
                    libs.add(os.path.normcase(v["path"]))
        except OSError:
            pass
        return sorted(libs)

    def downloads(self):
        """(lista de downloads ativos, nomes dos que terminaram desde a última chamada)."""
        out, now, seen = [], time.time(), set()
        for lib in self._libs():
            for acf in glob.glob(os.path.join(lib, "steamapps", "appmanifest_*.acf")):
                try:
                    st = _ci(parse_vdf(Path(acf).read_text(encoding="utf-8", errors="ignore")), "AppState") or {}
                    flags = int(st.get("StateFlags") or 0)
                except (OSError, ValueError):
                    continue
                state = _state(flags)
                appid = str(st.get("appid") or "")
                if not state or not appid:
                    continue
                seen.add(appid)
                dl, tdl = int(st.get("BytesDownloaded") or 0), int(st.get("BytesToDownload") or 0)
                sg, tsg = int(st.get("BytesStaged") or 0), int(st.get("BytesToStage") or 0)
                if state == "instalando" and tsg:
                    done, total = sg, tsg
                else:
                    done, total = dl, tdl
                # velocidade: só muda quando a Steam regrava o arquivo; sem mudança por 90 s = parado
                p = self.prev.get(appid)
                if not p or done != p[0]:
                    speed = (done - p[0]) / (now - p[1]) if p and done > p[0] and now > p[1] else None
                    self.prev[appid] = (done, now, speed)
                else:
                    speed = p[2] if now - p[1] < 90 else 0
                if state != "baixando":
                    speed = None
                self.active[appid] = st.get("name") or appid
                out.append({"appid": appid, "name": st.get("name") or appid, "state": state, "done": done, "total": total,
                            "pct": round(100 * done / total, 1) if total else None, "speed": round(speed) if speed else None})
        finished = [self.active.pop(a) for a in list(self.active) if a not in seen]
        for a in list(self.prev):
            if a not in seen:
                self.prev.pop(a)
        out.sort(key=lambda d: (d["state"] != "baixando", d["name"].lower()))
        return out, finished

    # ---------------------------------------------------------------- amigos
    def steamid(self):
        sp = getattr(self.catalog, "steam_path", None)
        if self.cfg.get("steamid"):
            return str(self.cfg["steamid"])
        try:
            users = _ci(parse_vdf(Path(sp, "config", "loginusers.vdf").read_text(encoding="utf-8", errors="ignore")), "users") or {}
        except (OSError, TypeError):
            return None
        best = None
        for sid, u in users.items():
            if isinstance(u, dict) and (best is None or str(_ci(u, "MostRecent") or "0") == "1"):
                best = sid
        return best

    def _api(self, path, **q):
        q["key"] = self.cfg["key"]
        url = f"https://api.steampowered.com/{path}/?" + urllib.parse.urlencode(q)
        with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "CompanionPC"}), timeout=15) as r:
            return json.loads(r.read())

    def friends(self):
        if not self.cfg.get("key"):
            return None
        sid = self.steamid()
        if not sid:
            raise RuntimeError("não achei a sua conta da Steam neste PC")
        try:
            if time.time() - self.friend_ids_t > 600 or not self.friend_ids:
                fl = self._api("ISteamUser/GetFriendList/v1", steamid=sid, relationship="friend")
                self.friend_ids = [f["steamid"] for f in (fl.get("friendslist") or {}).get("friends", [])]
                self.friend_ids_t = time.time()
            out = []
            for i in range(0, len(self.friend_ids), 100):
                ps = self._api("ISteamUser/GetPlayerSummaries/v2", steamids=",".join(self.friend_ids[i:i + 100]))
                for p in (ps.get("response") or {}).get("players", []):
                    st = int(p.get("personastate") or 0)
                    out.append({"id": p["steamid"], "name": p.get("personaname") or "?", "state": PERSONA.get(st, "online"),
                                "on": st != 0, "game": p.get("gameextrainfo"), "gameid": p.get("gameid"),
                                "avatar": p.get("avatar"), "seen": p.get("lastlogoff")})
        except urllib.error.HTTPError as e:
            if e.code in (401, 403):
                raise RuntimeError("a Steam recusou: confira a chave e se a lista de amigos está visível no perfil") from e
            raise
        out.sort(key=lambda f: (not f["game"], not f["on"], f["name"].lower()))
        return out
