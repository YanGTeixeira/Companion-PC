"""Tempo de tela por aplicativo (como no celular).

A cada poucos segundos soma o tempo do programa em foco. Não conta quando o PC está
bloqueado ou parado (sem mouse/teclado há IDLE_S), a não ser que algo esteja passando
na tela: jogo, tela cheia ou mídia tocando. Os totais ficam em screentime.db (SQLite),
por dia e por hora.
"""
import ctypes
import logging
import os
import sqlite3
import threading
import time
from ctypes import wintypes
from datetime import date, datetime, timedelta

import psutil

log = logging.getLogger("companion")
user32 = ctypes.windll.user32
IDLE_S = 120
MAX_STEP = 10  # um passo maior que isso (PC suspenso, laço travado) não conta

CATS = ["Trabalho", "Jogos", "Social", "Navegação", "Entretenimento", "Criação", "Sistema", "Outros"]
DEFAULT_CATS = {
    "Navegação": ["opera.exe", "msedge.exe", "chrome.exe", "firefox.exe", "brave.exe", "vivaldi.exe"],
    "Social": ["discord.exe", "whatsapp.exe", "whatsapp.root.exe", "telegram.exe", "slack.exe", "teams.exe", "ms-teams.exe", "zoom.exe"],
    "Trabalho": ["code.exe", "windowsterminal.exe", "wt.exe", "powershell.exe", "pwsh.exe", "cmd.exe", "insomnia.exe",
                 "mongodbcompass.exe", "notepad++.exe", "obsidian.exe", "devenv.exe", "idea64.exe", "pycharm64.exe",
                 "postman.exe", "winword.exe", "excel.exe", "powerpnt.exe", "outlook.exe", "notion.exe"],
    "Entretenimento": ["spotify.exe", "vlc.exe", "mpc-hc64.exe", "netflix.exe", "primevideo.exe"],
    "Criação": ["obs64.exe", "photoshop.exe", "blender.exe", "figma.exe", "davinci resolve.exe", "resolve.exe", "audacity.exe"],
    "Sistema": ["explorer.exe", "taskmgr.exe", "systemsettings.exe", "steam.exe", "epicgameslauncher.exe", "steamwebhelper.exe"],
}
SKIP = {"", "lockapp.exe", "logonui.exe", "searchhost.exe", "searchapp.exe", "shellexperiencehost.exe",
        "startmenuexperiencehost.exe", "pythonw.exe", "screenclippinghost.exe"}
NICE = {"opera.exe": "Opera GX", "code.exe": "VS Code", "windowsterminal.exe": "Terminal", "msedge.exe": "Edge",
        "explorer.exe": "Explorador de Arquivos", "whatsapp.root.exe": "WhatsApp", "whatsapp.exe": "WhatsApp"}


class _LASTINPUT(ctypes.Structure):
    _fields_ = [("cbSize", wintypes.UINT), ("dwTime", wintypes.DWORD)]


def idle_seconds():
    li = _LASTINPUT(ctypes.sizeof(_LASTINPUT))
    if not user32.GetLastInputInfo(ctypes.byref(li)):
        return 0
    return ((ctypes.windll.kernel32.GetTickCount() - li.dwTime) & 0xFFFFFFFF) / 1000


class _MI(ctypes.Structure):   # MONITORINFO
    _fields_ = [("cbSize", wintypes.DWORD), ("rcMonitor", wintypes.RECT), ("rcWork", wintypes.RECT), ("dwFlags", wintypes.DWORD)]


# ctypes.windll.user32 é um objeto só para o processo todo: o extras.py declara GetMonitorInfoW com a
# estrutura dele, e aí a nossa era recusada (ArgumentError). Uma instância própria não divide declarações.
_user32_own = ctypes.WinDLL("user32")
_user32_own.GetMonitorInfoW.argtypes = [wintypes.HMONITOR, ctypes.POINTER(_MI)]
_user32_own.GetMonitorInfoW.restype = wintypes.BOOL
_user32_own.MonitorFromWindow.argtypes = [wintypes.HWND, wintypes.DWORD]
_user32_own.MonitorFromWindow.restype = wintypes.HMONITOR   # ponteiro: sem isso volta cortado em int


def is_fullscreen(hwnd):
    r = wintypes.RECT()
    if not hwnd or not user32.GetWindowRect(hwnd, ctypes.byref(r)):
        return False
    mon = _user32_own.MonitorFromWindow(hwnd, 2)   # MONITOR_DEFAULTTONEAREST
    mi = _MI(ctypes.sizeof(_MI))
    if not _user32_own.GetMonitorInfoW(mon, ctypes.byref(mi)):
        return False
    m = mi.rcMonitor
    return r.left <= m.left and r.top <= m.top and r.right >= m.right and r.bottom >= m.bottom


_ENUM = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)


def _pid(hwnd):
    pid = wintypes.DWORD()
    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    return pid.value


def foreground():
    """(hwnd, pid) do programa em foco. Apps da loja (WhatsApp, Spotify...) ficam dentro do
    ApplicationFrameHost: aí procura a janela filha de outro processo."""
    hwnd = user32.GetForegroundWindow()
    pid = _pid(hwnd)
    try:
        name = psutil.Process(pid).name().lower()
    except psutil.Error:
        return hwnd, pid
    if name == "applicationframehost.exe":
        found = []

        def cb(h, _):
            p = _pid(h)
            if p != pid:
                found.append(p)
                return False
            return True
        user32.EnumChildWindows(hwnd, _ENUM(cb), 0)
        if found:
            pid = found[0]
    return hwnd, pid


def file_description(path):
    """Nome amigável do exe (FileDescription da versão), ou None."""
    try:
        ver = ctypes.windll.version
        size = ver.GetFileVersionInfoSizeW(path, None)
        if not size:
            return None
        buf = ctypes.create_string_buffer(size)
        if not ver.GetFileVersionInfoW(path, 0, size, buf):
            return None
        ptr, ln = ctypes.c_void_p(), wintypes.UINT()
        if not ver.VerQueryValueW(buf, r"\VarFileInfo\Translation", ctypes.byref(ptr), ctypes.byref(ln)) or not ln.value:
            return None
        lang, cp = ctypes.cast(ptr, ctypes.POINTER(ctypes.c_uint16 * 2)).contents
        for key in (f"\\StringFileInfo\\{lang:04x}{cp:04x}\\FileDescription", "\\StringFileInfo\\040904b0\\FileDescription"):
            if ver.VerQueryValueW(buf, key, ctypes.byref(ptr), ctypes.byref(ln)) and ln.value > 1:
                s = ctypes.wstring_at(ptr, ln.value - 1).strip()
                if s:
                    return s
    except Exception:  # noqa: BLE001
        pass
    return None


class ScreenTime:
    def __init__(self, base, cfg, match_game=None, media_playing=None):
        """cfg: dict do config.json["screentime"] (é alterado e salvo por save_cfg)."""
        self.path = os.path.join(base, "screentime.db")
        self.cfg = cfg
        self.match_game = match_game or (lambda exe: None)
        self.media_playing = media_playing or (lambda: False)
        self.lock = threading.Lock()
        self.pending: dict = {}   # (dia, hora, app) -> segundos ainda não gravados
        self.names: dict = {}     # app -> nome amigável
        self.last = time.monotonic()
        self.last_flush = self.last
        self.current = None       # app em foco contando agora
        self.pid_cache: dict = {}  # pid -> (app, nome, é_jogo)
        db = self._db()
        db.executescript("""
            CREATE TABLE IF NOT EXISTS usage (day TEXT, hour INT, app TEXT, secs REAL, PRIMARY KEY (day, hour, app));
            CREATE TABLE IF NOT EXISTS apps (app TEXT PRIMARY KEY, name TEXT, game INT DEFAULT 0);
        """)
        self.names = {a: (n, bool(g)) for a, n, g in db.execute("SELECT app, name, game FROM apps")}
        db.close()

    def _db(self):
        return sqlite3.connect(self.path, timeout=5)

    # ------------------------------------------------------------ coleta
    def _identify(self, pid):
        hit = self.pid_cache.get(pid)
        if hit:
            return hit
        try:
            p = psutil.Process(pid)
            exe_name, exe = p.name().lower(), p.exe()
        except (psutil.Error, OSError):
            return None
        game = None
        try:
            game = self.match_game(exe)
        except Exception:  # noqa: BLE001
            pass
        if game:
            app, name = "game:" + game["name"], game["name"]
        else:
            app = exe_name
            name = NICE.get(exe_name) or file_description(exe) or exe_name.removesuffix(".exe")
        if len(self.pid_cache) > 300:
            self.pid_cache.clear()
        hit = self.pid_cache[pid] = (app, name, bool(game))
        return hit

    def tick(self):
        """Chamado a cada ~2 s numa thread."""
        now = time.monotonic()
        step, self.last = now - self.last, now
        if step > MAX_STEP or step <= 0:
            return
        hwnd, pid = foreground()
        ident = self._identify(pid) if pid else None
        if not ident or ident[0] in SKIP:
            self.current = None
            return
        app, name, game = ident
        if idle_seconds() > IDLE_S and not (game or is_fullscreen(hwnd) or self.media_playing()):
            self.current = None
            return
        self.current = app
        dt = datetime.now()
        key = (dt.strftime("%Y-%m-%d"), dt.hour, app)
        with self.lock:
            self.pending[key] = self.pending.get(key, 0) + step
            if self.names.get(app) != (name, game):
                self.names[app] = (name, game)
                self._dirty_names = True
        if now - self.last_flush > 60:
            self.flush()

    def flush(self):
        with self.lock:
            pend, self.pending = self.pending, {}
            names = dict(self.names) if getattr(self, "_dirty_names", False) else None
            self._dirty_names = False
        self.last_flush = time.monotonic()
        if not pend and not names:
            return
        try:
            db = self._db()
            with db:
                db.executemany("INSERT INTO usage VALUES (?,?,?,?) ON CONFLICT(day,hour,app) DO UPDATE SET secs = secs + excluded.secs",
                               [(d, h, a, s) for (d, h, a), s in pend.items()])
                if names:
                    db.executemany("INSERT OR REPLACE INTO apps VALUES (?,?,?)", [(a, n, int(g)) for a, (n, g) in names.items()])
            db.close()
        except sqlite3.Error:
            log.exception("tempo de tela: gravar")
            with self.lock:  # devolve para tentar de novo
                for k, v in pend.items():
                    self.pending[k] = self.pending.get(k, 0) + v

    # ------------------------------------------------------------ categorias
    def default_category(self, app):
        if app.startswith("game:") or self.names.get(app, ("", False))[1]:
            return "Jogos"
        for cat, exes in DEFAULT_CATS.items():
            if app in exes:
                return cat
        return "Outros"

    def category(self, app):
        return (self.cfg.get("categories") or {}).get(app) or self.default_category(app)

    def set_category(self, app, cat):
        """Muda a categoria de um app; voltar para a padrão apaga a escolha."""
        if cat not in CATS:
            raise ValueError("categoria inválida")
        cats = self.cfg.setdefault("categories", {})
        if cat == self.default_category(app):
            cats.pop(app, None)
        else:
            cats[app] = cat
        return cat

    # ------------------------------------------------------------ consulta
    def report(self, rng="day", day=None, end=None):
        """rng: day | week | month | range (de day até end). day: 'AAAA-MM-DD' (padrão hoje). Inclui o que ainda não foi gravado."""
        ref = date.fromisoformat(day) if day else date.today()
        if rng == "week":
            start = ref - timedelta(days=ref.weekday())
            end = start + timedelta(days=6)
        elif rng == "month":
            start = ref.replace(day=1)
            end = (start + timedelta(days=32)).replace(day=1) - timedelta(days=1)
        elif rng == "range":
            start, end = ref, date.fromisoformat(end)
        else:
            start = end = ref
        a, b = start.isoformat(), end.isoformat()
        db = self._db()
        rows = db.execute("SELECT day, hour, app, secs FROM usage WHERE day BETWEEN ? AND ?", (a, b)).fetchall()
        db.close()
        with self.lock:
            rows += [(d, h, ap, s) for (d, h, ap), s in self.pending.items() if a <= d <= b]
            names = dict(self.names)
        apps, hours, days, cats = {}, [0.0] * 24, {}, {}
        for d, h, ap, s in rows:
            apps[ap] = apps.get(ap, 0) + s
            days[d] = days.get(d, 0) + s
            if rng == "day":
                hours[h] += s
        app_list = []
        for ap, s in sorted(apps.items(), key=lambda x: -x[1]):
            c = self.category(ap)
            cats[c] = cats.get(c, 0) + s
            app_list.append({"app": ap, "name": names.get(ap, (ap, False))[0], "cat": c, "secs": round(s)})
        n_days = (end - start).days + 1
        out = {"range": rng, "start": a, "end": b, "total": round(sum(apps.values())), "apps": app_list[:60],
               "cats": [{"cat": c, "secs": round(s)} for c, s in sorted(cats.items(), key=lambda x: -x[1])],
               "current": self.current, "cat_list": CATS}
        if rng == "day":
            out["hours"] = [round(x) for x in hours]
            # média dos 7 dias anteriores, para comparar
            out["prev_avg"] = self._avg(ref - timedelta(days=7), ref - timedelta(days=1))
        else:
            out["days"] = [{"day": (start + timedelta(days=i)).isoformat(), "secs": round(days.get((start + timedelta(days=i)).isoformat(), 0))}
                           for i in range(n_days)]
            past = [x["secs"] for x in out["days"] if x["day"] <= date.today().isoformat()]
            out["avg"] = round(sum(past) / len(past)) if past else 0
        return out

    def _avg(self, a, b):
        db = self._db()
        r = db.execute("SELECT SUM(secs), COUNT(DISTINCT day) FROM usage WHERE day BETWEEN ? AND ?", (a.isoformat(), b.isoformat())).fetchone()
        db.close()
        return round((r[0] or 0) / r[1]) if r and r[1] else 0

    def app_report(self, app, days=7):
        """Últimos dias de um app (para o detalhe)."""
        start = date.today() - timedelta(days=days - 1)
        db = self._db()
        rows = db.execute("SELECT day, SUM(secs) FROM usage WHERE app = ? AND day >= ? GROUP BY day", (app, start.isoformat())).fetchall()
        db.close()
        per = dict(rows)
        with self.lock:
            for (d, _h, ap), s in self.pending.items():
                if ap == app:
                    per[d] = per.get(d, 0) + s
        return {"app": app, "name": self.names.get(app, (app, False))[0], "cat": self.category(app),
                "days": [{"day": (start + timedelta(days=i)).isoformat(), "secs": round(per.get((start + timedelta(days=i)).isoformat(), 0))}
                         for i in range(days)]}
