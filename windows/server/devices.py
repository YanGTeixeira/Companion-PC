"""Bateria dos aparelhos sem fio ligados ao PC.

- Mouse Attack Shark X11 (receptor 1d57:fa60): o mouse manda sozinho, a cada ~2 s
  enquanto está acordado, o relatório 03 55 40 <estado> <%>.
- Teclado AULA F75 (receptor Compx 3554:fa09): pergunta 13 4A 00.. <soma> na coleção
  FF02 e a resposta traz o % no byte 5 e o estado no byte 6 (01 bateria, 10 no cabo).
- Fone/aparelhos Bluetooth (clássico e BLE): propriedade DEVPKEY_Bluetooth_Battery do Windows.
- Controles: Windows.Gaming.Input (% de verdade: Xbox e outros que informam) e, para o resto,
  XInputGetBatteryInformation (8BitDo no modo X etc.; só 4 níveis).
"""
import ctypes
import logging
import threading
import time
from ctypes import wintypes

log = logging.getLogger("companion")

try:
    import hid
except Exception:  # noqa: BLE001
    hid = None

MOUSE_IDS = (0x1D57, 0xFA60)
KEYB_IDS = (0x3554, 0xFA09)
KEYB_EVERY = 300   # s: cada pergunta acorda o rádio do teclado, então sem exagero
MOUSE_SLEEP = 600  # s sem relatório = mouse dormindo/desligado (mostra o último valor)


def _now():
    return time.time()


# --------------------------------------------------------------------------
# Mouse Attack Shark X11: só escuta
# --------------------------------------------------------------------------
class SharkMouse:
    name, kind = "Mouse", "mouse"

    def __init__(self):
        self.pct = self.charging = self.full = None
        self.seen = 0.0
        self.present = False
        threading.Thread(target=self._run, daemon=True, name="bat-mouse").start()

    def _open(self):
        hs = []
        for d in hid.enumerate(*MOUSE_IDS):
            if d["interface_number"] != 2:
                continue
            try:
                h = hid.device()
                h.open_path(d["path"])
                hs.append(h)
            except OSError:
                pass  # coleções de teclado/mouse do Windows não abrem: tudo bem
        return hs

    def _run(self):
        while True:
            hs = self._open() if hid else []
            self.present = bool(hs)
            if not hs:
                time.sleep(30)
                continue
            try:
                for h in hs:
                    h.set_nonblocking(1)
                while hs:
                    got = False
                    for h in list(hs):
                        try:
                            r = h.read(64)
                        except (OSError, ValueError):
                            # coleção sem relatórios de entrada (só feature) dá "read error": descarta
                            hs.remove(h)
                            h.close()
                            continue
                        if r:
                            got = True
                            self._parse(r)
                    if not got:
                        time.sleep(0.25)
            except (OSError, ValueError):
                pass  # receptor desconectado: tenta abrir de novo
            finally:
                for h in hs:
                    try:
                        h.close()
                    except Exception:  # noqa: BLE001
                        pass
            time.sleep(5)

    def _parse(self, r):
        if len(r) >= 5 and r[0] == 0x03 and r[1] == 0x55 and r[2] in (0x40, 0x41) and 0 <= r[4] <= 100:
            self.pct, self.seen = r[4], _now()
            self.charging = r[3] == 0x03
            self.full = r[3] == 0x02

    def state(self):
        if not self.present and not self.seen:
            return None
        asleep = not self.seen or _now() - self.seen > MOUSE_SLEEP
        return {"id": "mouse", "name": self.name, "kind": self.kind, "pct": self.pct,
                "charging": bool(self.charging), "full": bool(self.full),
                "status": "off" if not self.present else ("sleep" if asleep else "ok"), "seen": int(self.seen)}


# --------------------------------------------------------------------------
# Teclado AULA F75: pergunta e espera a resposta
# --------------------------------------------------------------------------
class AulaKeyboard:
    name, kind = "Teclado", "keyboard"

    def __init__(self):
        self.pct = None
        self.charging = False
        self.seen = 0.0
        self.present = False
        self.misses = 0
        self.next = 0.0
        self.lock = threading.Lock()

    def _query(self):
        dev = next((d for d in hid.enumerate(*KEYB_IDS) if d["usage_page"] == 0xFF02), None)
        self.present = dev is not None
        if not dev:
            return None
        req = [0x13, 0x4A] + [0] * 17
        req.append(sum(req) & 0xFF)
        h = hid.device()
        h.open_path(dev["path"])
        try:
            h.set_nonblocking(1)
            for _ in range(5):  # teclado parado ignora a 1ª pergunta (ela acorda o rádio)
                h.write(req)
                t = time.monotonic()
                while time.monotonic() - t < 0.6:
                    r = h.read(64)
                    if r and len(r) >= 7 and r[0] == 0x13 and (r[1] & 0x7F) == 0x4A:
                        return r
                    if not r:
                        time.sleep(0.02)
            return None
        finally:
            h.close()

    def poll(self, force=False):
        if not hid or (not force and _now() < self.next) or not self.lock.acquire(blocking=False):
            return
        try:
            r = self._query()
            if r and 1 <= r[5] <= 100:
                self.pct, self.charging, self.seen, self.misses = r[5], r[6] == 0x10, _now(), 0
            elif self.present:
                self.misses += 1
        except OSError as e:
            log.debug("teclado: %s", e)
        finally:
            self.lock.release()
        # sem resposta: tenta de novo antes (o teclado pode só ter acordado agora)
        self.next = _now() + (KEYB_EVERY if self.misses == 0 else 60)

    def state(self):
        if not self.present and not self.seen:
            return None
        st = "off" if not self.present else ("sleep" if self.misses >= 2 or not self.seen else "ok")
        return {"id": "keyboard", "name": self.name, "kind": self.kind, "pct": self.pct,
                "charging": self.charging, "full": False, "status": st, "seen": int(self.seen)}


# --------------------------------------------------------------------------
# Bluetooth: lista dos pareados (conectado ou não) + bateria que o Windows informa
# --------------------------------------------------------------------------
class _GUID(ctypes.Structure):
    _fields_ = [("Data1", wintypes.DWORD), ("Data2", wintypes.WORD), ("Data3", wintypes.WORD),
                ("Data4", ctypes.c_ubyte * 8)]


class _DEVPROPKEY(ctypes.Structure):
    _fields_ = [("fmtid", _GUID), ("pid", wintypes.ULONG)]


class _SP_DEVINFO_DATA(ctypes.Structure):
    _fields_ = [("cbSize", wintypes.DWORD), ("ClassGuid", _GUID), ("DevInst", wintypes.DWORD),
                ("Reserved", ctypes.c_void_p)]


class _SYSTEMTIME(ctypes.Structure):
    _fields_ = [(n, wintypes.WORD) for n in ("y", "mo", "dow", "d", "h", "mi", "s", "ms")]


class _BT_DEVICE_INFO(ctypes.Structure):
    _fields_ = [("dwSize", wintypes.DWORD), ("Address", ctypes.c_ulonglong), ("ulClassofDevice", wintypes.ULONG),
                ("fConnected", wintypes.BOOL), ("fRemembered", wintypes.BOOL), ("fAuthenticated", wintypes.BOOL),
                ("stLastSeen", _SYSTEMTIME), ("stLastUsed", _SYSTEMTIME), ("szName", ctypes.c_wchar * 248)]


class _BT_SEARCH(ctypes.Structure):
    _fields_ = [("dwSize", wintypes.DWORD), ("fReturnAuthenticated", wintypes.BOOL),
                ("fReturnRemembered", wintypes.BOOL), ("fReturnUnknown", wintypes.BOOL),
                ("fReturnConnected", wintypes.BOOL), ("fIssueInquiry", wintypes.BOOL),
                ("cTimeoutMultiplier", ctypes.c_ubyte), ("hRadio", wintypes.HANDLE)]


def _guid(s):
    import uuid
    u = uuid.UUID(s)
    g = _GUID(u.time_low, u.time_mid, u.time_hi_version)
    g.Data4[:] = list(u.bytes[8:])
    return g


BT_BATTERY = _DEVPROPKEY(_guid("104EA319-6EE2-4701-BD47-8DDBF425BBE5"), 2)
FRIENDLY_NAME = _DEVPROPKEY(_guid("A45C254E-DF1C-4EFD-8020-67D146A850E0"), 14)
IS_CONNECTED = _DEVPROPKEY(_guid("83DA6326-97A6-4088-9453-A1923F573B29"), 15)   # aparelho BLE ligado agora


def _bt_kind(cod):
    major, minor = (cod >> 8) & 0x1F, (cod >> 2) & 0x3F
    if major == 4:
        return "headset"
    if major == 5:
        return {1: "keyboard", 2: "mouse"}.get((minor >> 4) & 3) or ("gamepad" if minor & 0xF in (1, 2) else "other")
    if major == 2:
        return "phone"
    return "other"


def bt_devices():
    """[(endereço hex, nome, conectado, tipo)] dos aparelhos Bluetooth clássicos pareados."""
    try:
        bt = ctypes.WinDLL("bthprops.cpl")
    except OSError:
        return []
    sp = _BT_SEARCH(ctypes.sizeof(_BT_SEARCH), 1, 1, 0, 1, 0, 0, None)
    info = _BT_DEVICE_INFO()
    info.dwSize = ctypes.sizeof(info)
    bt.BluetoothFindFirstDevice.restype = wintypes.HANDLE
    h = bt.BluetoothFindFirstDevice(ctypes.byref(sp), ctypes.byref(info))
    out = []
    if not h:
        return out
    try:
        while True:
            out.append((f"{info.Address:012X}", info.szName, bool(info.fConnected), _bt_kind(info.ulClassofDevice)))
            if not bt.BluetoothFindNextDevice(wintypes.HANDLE(h), ctypes.byref(info)):
                break
    finally:
        bt.BluetoothFindDeviceClose(wintypes.HANDLE(h))
    return out


def _name_kind(name):
    """Tipo de um aparelho BLE pelo nome (o BLE não tem a "classe" do Bluetooth clássico)."""
    n = name.lower()
    for kind, words in (("mouse", ("mouse", "mx ", "mx-", "trackball")), ("keyboard", ("keyboard", "teclado", "keys")),
                        ("headset", ("headset", "headphone", "fone", "buds", "earbuds", "airpods", "wh-", "wf-")),
                        ("gamepad", ("controller", "gamepad", "controle", "joy-con", "8bitdo"))):
        if any(w in n for w in words):
            return kind
    return "other"


def ble_parse_id(iid):
    """Endereço (12 hex) de um id BTHLE\\DEV_<endereço>\\..., ou None."""
    iid = iid.upper()
    if not iid.startswith("BTHLE\\DEV_"):
        return None
    addr = iid[10:22]
    return addr if len(addr) == 12 and all(c in "0123456789ABCDEF" for c in addr) else None


def ble_devices():
    """[(endereço hex, nome, conectado, tipo)] dos aparelhos Bluetooth LE pareados (mouse, teclado, fone BLE...).
    O BluetoothFindFirstDevice só enxerga o Bluetooth clássico; o BLE fica nos nós BTHLE\\DEV_ do Windows."""
    sa = ctypes.WinDLL("setupapi")
    sa.SetupDiGetClassDevsW.restype = wintypes.HANDLE
    hdev = sa.SetupDiGetClassDevsW(None, "BTHLE", None, 0x2 | 0x4)  # PRESENT | ALLCLASSES
    out = []
    if not hdev or hdev == wintypes.HANDLE(-1).value:
        return out
    try:
        i = 0
        dd = _SP_DEVINFO_DATA()
        dd.cbSize = ctypes.sizeof(dd)
        buf = ctypes.create_unicode_buffer(512)
        while sa.SetupDiEnumDeviceInfo(wintypes.HANDLE(hdev), i, ctypes.byref(dd)):
            i += 1
            if not sa.SetupDiGetDeviceInstanceIdW(wintypes.HANDLE(hdev), ctypes.byref(dd), buf, 512, None):
                continue
            addr = ble_parse_id(buf.value)
            if not addr:
                continue
            ptype = wintypes.ULONG()
            if not sa.SetupDiGetDevicePropertyW(wintypes.HANDLE(hdev), ctypes.byref(dd), ctypes.byref(FRIENDLY_NAME),
                                                ctypes.byref(ptype), buf, 1024, None, 0):
                continue
            name = buf.value or addr
            conn = ctypes.c_ubyte()
            if sa.SetupDiGetDevicePropertyW(wintypes.HANDLE(hdev), ctypes.byref(dd), ctypes.byref(IS_CONNECTED),
                                            ctypes.byref(ptype), ctypes.byref(conn), 1, None, 0):
                connected = conn.value != 0
            else:  # sem a propriedade: presente = conectado
                connected = True
            out.append((addr, name, connected, _name_kind(name)))
    finally:
        sa.SetupDiDestroyDeviceInfoList(wintypes.HANDLE(hdev))
    return out


def bt_batteries():
    """{endereço hex: %} de todo nó de dispositivo com a propriedade de bateria Bluetooth."""
    sa = ctypes.WinDLL("setupapi")
    sa.SetupDiGetClassDevsW.restype = wintypes.HANDLE
    hdev = sa.SetupDiGetClassDevsW(None, None, None, 0x2 | 0x4)  # PRESENT | ALLCLASSES
    out = {}
    if not hdev or hdev == wintypes.HANDLE(-1).value:
        return out
    try:
        i = 0
        dd = _SP_DEVINFO_DATA()
        dd.cbSize = ctypes.sizeof(dd)
        buf = ctypes.create_unicode_buffer(512)
        while sa.SetupDiEnumDeviceInfo(wintypes.HANDLE(hdev), i, ctypes.byref(dd)):
            i += 1
            ptype, val = wintypes.ULONG(), ctypes.c_ubyte()
            if not sa.SetupDiGetDevicePropertyW(wintypes.HANDLE(hdev), ctypes.byref(dd), ctypes.byref(BT_BATTERY),
                                                ctypes.byref(ptype), ctypes.byref(val), 1, None, 0):
                continue
            if sa.SetupDiGetDeviceInstanceIdW(wintypes.HANDLE(hdev), ctypes.byref(dd), buf, 512, None):
                iid = buf.value.upper()
                # o endereço Bluetooth (12 hex) aparece no id da instância: ..._3CF775BF8850_C0000...
                for part in iid.replace("&", "_").replace("\\", "_").split("_"):
                    if len(part) == 12 and all(c in "0123456789ABCDEF" for c in part):
                        out[part] = val.value
    finally:
        sa.SetupDiDestroyDeviceInfoList(wintypes.HANDLE(hdev))
    return out


# --------------------------------------------------------------------------
# Controles XInput (8BitDo no modo X, Xbox...)
# --------------------------------------------------------------------------
class _XBAT(ctypes.Structure):
    _fields_ = [("type", ctypes.c_ubyte), ("level", ctypes.c_ubyte)]


class _XSTATE(ctypes.Structure):
    _fields_ = [("packet", wintypes.DWORD), ("pad", ctypes.c_ubyte * 12)]


def xinput_pads():
    try:
        xi = ctypes.WinDLL("xinput1_4")
    except OSError:
        return []
    out = []
    for i in range(4):
        st = _XSTATE()
        if xi.XInputGetState(i, ctypes.byref(st)) != 0:
            continue
        b = _XBAT()
        if xi.XInputGetBatteryInformation(i, 0, ctypes.byref(b)) != 0 or b.type == 0:
            continue
        wired = b.type == 1
        pct = None if wired or b.type == 0xFF else (5, 35, 70, 100)[min(b.level, 3)]
        out.append({"id": f"pad{i}", "name": "Controle" if i == 0 else f"Controle {i + 1}", "kind": "gamepad",
                    "pct": pct, "approx": True, "charging": False, "full": False, "wired": wired,
                    "status": "ok", "seen": int(_now())})
    return out


# --------------------------------------------------------------------------
# Controles pelo Windows.Gaming.Input: % de verdade, para quem informa (Xbox sem fio e afins)
# --------------------------------------------------------------------------
_wgi = None   # a classe RawGameController (a lista enche sozinha alguns instantes depois do 1º acesso)


def wgi_pads():
    global _wgi
    if _wgi is None:
        try:
            from winrt.windows.gaming.input import RawGameController
            _wgi = RawGameController
        except Exception as e:  # noqa: BLE001
            log.info("bateria dos controles pelo Windows.Gaming.Input indisponível: %s", e)
            _wgi = False
    if not _wgi:
        return []
    out = []
    for c in list(_wgi.raw_game_controllers):
        r = c.try_get_battery_report()
        if r is None:
            continue
        out.append(wgi_entry(c, r))
    return [d for d in out if d]


def wgi_entry(c, r):
    """Um controle + seu BatteryReport -> item da lista (None se não tem bateria)."""
    status = int(r.status)                     # 0 sem bateria, 1 descarregando, 2 parado (cheio no cabo), 3 carregando
    full, left = r.full_charge_capacity_in_milliwatt_hours, r.remaining_capacity_in_milliwatt_hours
    if status == 0 or not full or left is None:
        return None
    pct = max(0, min(100, round(left * 100 / full)))
    name = (c.display_name or "").strip() or "Controle"
    return {"id": f"wgi-{c.hardware_vendor_id:04x}{c.hardware_product_id:04x}-{c.non_roamable_id[-8:] if c.non_roamable_id else ''}",
            "name": name, "kind": "gamepad", "pct": pct, "charging": status == 3, "full": status == 2 and pct >= 99,
            "wired": not c.is_wireless, "status": "ok", "seen": int(_now())}


def merge_pads(wgi, xinput):
    """O mesmo controle Xbox aparece nos dois: cada um com % do Windows.Gaming.Input tira um do XInput
    (que só tem 4 níveis). Não dá para casar um com o outro com certeza, então tira na ordem."""
    return wgi + xinput[len(wgi):]


def bt_list(classic, ble, bats):
    """Clássicos + BLE (sem repetir quem é os dois), só os conectados ou que têm bateria conhecida."""
    seen, out = set(), []
    for addr, name, conn, kind in [*classic, *ble]:
        if addr in seen or not (conn or addr in bats):
            continue
        seen.add(addr)
        out.append({"id": "bt-" + addr, "name": name, "kind": kind, "pct": bats.get(addr),
                    "charging": False, "full": False, "status": "ok" if conn else "off", "seen": int(_now())})
    return out


# --------------------------------------------------------------------------
class Batteries:
    def __init__(self, cfg=None):
        self.cfg = cfg or {}
        self.mouse = SharkMouse() if hid else None
        self.keyb = AulaKeyboard() if hid else None
        self.bt: list = []
        self.pads: list = []
        self.bt_next = 0.0
        if not hid:
            log.info("bateria do mouse/teclado indisponível: instale o pacote hidapi")

    def poll(self):
        """Roda numa thread; chamado a cada poucos segundos."""
        if self.keyb:
            self.keyb.poll()
        if _now() >= self.bt_next:
            self.bt_next = _now() + 30
            try:
                bats = bt_batteries()
                self.bt = bt_list(bt_devices(), ble_devices(), bats)
            except Exception:  # noqa: BLE001
                log.exception("bateria bluetooth")
        try:
            xi = xinput_pads()
        except Exception:  # noqa: BLE001
            xi = []
        try:
            wg = wgi_pads()
        except Exception:  # noqa: BLE001
            log.exception("bateria dos controles")
            wg = []
        self.pads = merge_pads(wg, xi)

    def refresh(self):
        if self.keyb:
            self.keyb.poll(force=True)
        self.bt_next = 0
        self.poll()
        return self.state()

    def state(self):
        names = self.cfg.get("names") or {}
        hidden = set(self.cfg.get("hide") or [])
        out = []
        for d in [self.mouse and self.mouse.state(), self.keyb and self.keyb.state(), *self.bt, *self.pads]:
            if d and d["id"] not in hidden:
                out.append({**d, "name": names.get(d["id"], d["name"])})
        order = {"ok": 0, "sleep": 1, "off": 2}
        out.sort(key=lambda d: order.get(d["status"], 3))
        return out


if __name__ == "__main__":
    b = Batteries()
    for _ in range(4):
        b.poll()
        time.sleep(1.5)
    import json
    print(json.dumps(b.state(), indent=1, ensure_ascii=False))
    print(bt_devices())
    print(ble_devices())
