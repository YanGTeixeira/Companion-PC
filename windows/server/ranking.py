"""Ranking público (opcional): envia o resumo das conquistas para o servidor do ranking e busca as posições.

O servidor é um Cloudflare Worker (pasta cloud/ranking). Só sai do PC: apelido, XP total e da semana, sequência
e quantos troféus (Conquistas.summary). Nada de tempo de tela, apps ou horários. Sem e-mail nem senha: no
cadastro o servidor devolve um id e uma chave secreta, que ficam no config.json ("ranking").
"""
import json
import logging
import threading
import time
import urllib.error
import urllib.request

log = logging.getLogger("companion")

URL = "https://companion-ranking.yancubot.workers.dev"   # Worker de cloud/ranking
UA = {"User-Agent": "CompanionPC", "Content-Type": "application/json"}
SUBMIT_EVERY_S = 15 * 60
BOARD_CACHE_S = 60
KINDS = ("week", "level", "streak")


class RankError(Exception):
    def __init__(self, msg, status=0):
        super().__init__(msg)
        self.status = status


class Ranking:
    def __init__(self, cfg, save_cfg, url=None):
        """cfg: dict do config.json["ranking"] ({id, key, nick}); save_cfg(cfg) grava."""
        self.cfg = cfg if cfg is not None else {}
        self._save = save_cfg
        self.url = (url or self.cfg.get("url") or URL).rstrip("/")
        self.lock = threading.Lock()
        self._boards = {}             # kind -> (quando, dados)
        self.last_submit = 0.0
        self.last_sent = None         # último resumo aceito (não reenvia igual)
        self.error = ""

    @property
    def joined(self):
        return bool(self.cfg.get("id") and self.cfg.get("key"))

    @property
    def configured(self):
        return bool(self.url)

    def state(self):
        return {"available": self.configured, "joined": self.joined, "nick": self.cfg.get("nick", ""), "error": self.error}

    # ------------------------------------------------------------ http
    def _req(self, method, path, body=None, auth=False, timeout=10):
        if not self.configured:
            raise RankError("o ranking ainda não foi publicado")
        headers = dict(UA)
        if auth:
            if not self.joined:
                raise RankError("você não está no ranking")
            headers["Authorization"] = f"Bearer {self.cfg['id']}.{self.cfg['key']}"
        data = json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request(self.url + path, data=data, headers=headers, method=method)
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return json.loads(r.read() or b"{}")
        except urllib.error.HTTPError as e:
            try:
                msg = json.loads(e.read() or b"{}").get("error") or e.reason
            except ValueError:
                msg = e.reason
            raise RankError(str(msg), e.code) from None
        except (urllib.error.URLError, OSError, ValueError) as e:
            raise RankError(f"sem conexão com o ranking ({getattr(e, 'reason', e)})") from None

    # ------------------------------------------------------------ conta
    def join(self, nick):
        r = self._req("POST", "/v1/register", {"nick": str(nick or "")[:40]})
        with self.lock:
            self.cfg.update(id=r["id"], key=r["key"], nick=r["nick"])
            self._save(dict(self.cfg))
        self.last_sent = None
        log.info("ranking: entrou como %s", r["nick"])
        return self.state()

    def set_nick(self, nick):
        r = self._req("POST", "/v1/nick", {"nick": str(nick or "")[:40]}, auth=True)
        with self.lock:
            self.cfg["nick"] = r["nick"]
            self._save(dict(self.cfg))
        self._boards.clear()
        return self.state()

    def leave(self):
        """Apaga a conta no servidor e esquece a chave. Se o servidor não responder, não esquece (dá para tentar de novo)."""
        if self.joined:
            try:
                self._req("DELETE", "/v1/me", auth=True)
            except RankError as e:
                if e.status != 401:     # 401: a conta já não existe lá
                    raise
        with self.lock:
            for k in ("id", "key", "nick"):
                self.cfg.pop(k, None)
            self._save(dict(self.cfg))
        self._boards.clear()
        log.info("ranking: saiu e apagou a conta")
        return self.state()

    # ------------------------------------------------------------ envio e leitura
    def submit(self, summary, force=False):
        """Envia o resumo (a cada SUBMIT_EVERY_S, ou já se force). Devolve True se enviou."""
        if not (self.configured and self.joined and summary and summary.get("xp") is not None):
            return False
        body = {k: summary.get(k) or 0 for k in ("xp", "week_xp", "streak", "best_streak", "unlocked")}
        body["week"] = summary.get("week")
        now = time.monotonic()
        if not force and (body == self.last_sent or now - self.last_submit < SUBMIT_EVERY_S):
            return False
        self.last_submit = now
        try:
            self._req("POST", "/v1/submit", body, auth=True)
        except RankError as e:
            if e.status == 429:        # cedo demais: tenta na próxima
                return False
            if e.status == 401:        # a conta sumiu do servidor
                self.error = "a sua conta não existe mais no ranking; entre de novo"
            else:
                self.error = str(e)
            log.warning("ranking: envio recusado: %s", e)
            return False
        self.error = ""
        self.last_sent = body
        self._boards.clear()
        return True

    def board(self, kind="week"):
        if kind not in KINDS:
            raise RankError("ranking inválido")
        hit = self._boards.get(kind)
        if hit and time.monotonic() - hit[0] < BOARD_CACHE_S:
            return hit[1]
        data = self._req("GET", f"/v1/board?kind={kind}")
        if self.joined:
            try:
                data["me"] = self._req("GET", "/v1/me", auth=True)
            except RankError as e:
                data["me"] = None
                if e.status == 401:
                    self.error = "a sua conta não existe mais no ranking; entre de novo"
        data["you"] = self.cfg.get("nick", "")
        self._boards[kind] = (time.monotonic(), data)
        return data
