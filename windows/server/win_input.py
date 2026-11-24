"""Win32: teclado e mouse virtuais e a janela em foco (user32).

Teclas e combinações só da lista VK; textos viram eventos Unicode (SendInput).
"""
import ctypes
import time
from ctypes import wintypes

import psutil

user32 = ctypes.windll.user32
user32.keybd_event.argtypes = [wintypes.BYTE, wintypes.BYTE, wintypes.DWORD, ctypes.c_size_t]
user32.mouse_event.argtypes = [wintypes.DWORD, wintypes.DWORD, wintypes.DWORD, wintypes.DWORD, ctypes.c_size_t]
user32.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
user32.PostMessageW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
user32.MapVirtualKeyW.argtypes = [wintypes.UINT, wintypes.UINT]
user32.MapVirtualKeyW.restype = wintypes.UINT

KEYEVENTF_EXTENDEDKEY, KEYEVENTF_KEYUP = 0x1, 0x2
VK = {
    "enter": 0x0D, "esc": 0x1B, "tab": 0x09, "space": 0x20, "backspace": 0x08,
    "delete": 0x2E, "home": 0x24, "end": 0x23, "pageup": 0x21, "pagedown": 0x22,
    "up": 0x26, "down": 0x28, "left": 0x25, "right": 0x27,
    "win": 0x5B, "alt": 0x12, "ctrl": 0x11, "shift": 0x10,
    **{f"f{i}": 0x6F + i for i in range(1, 13)},
    **{chr(c): c - 32 for c in range(ord("a"), ord("z") + 1)},  # VK das letras = ASCII maiúsculo
    **{str(d): 0x30 + d for d in range(10)},
    "insert": 0x2D, "printscreen": 0x2C, "menu": 0x5D, "plus": 0xBB, "minus": 0xBD,
    "comma": 0xBC, "period": 0xBE,
    "play_pause": 0xB3, "next": 0xB0, "prev": 0xB1, "stop": 0xB2,
    "vol_mute": 0xAD, "vol_down": 0xAE, "vol_up": 0xAF,
}
EXTENDED = {"delete", "home", "end", "pageup", "pagedown", "up", "down", "left", "right", "win",
            "insert", "printscreen", "menu",
            "play_pause", "next", "prev", "stop", "vol_mute", "vol_down", "vol_up"}
MODIFIERS = {"alt", "ctrl", "shift", "win"}
held_modifiers: set[str] = set()


def _key(name, up=False):
    flags = (KEYEVENTF_EXTENDEDKEY if name in EXTENDED else 0) | (KEYEVENTF_KEYUP if up else 0)
    # Scan code junto com o VK: apps que leem o teclado em baixo nível (atalhos
    # globais do Discord) ignoram eventos com scan code 0.
    scan = user32.MapVirtualKeyW(VK[name], 0) & 0xFF  # MAPVK_VK_TO_VSC
    user32.keybd_event(VK[name], scan, flags, 0)


def valid_combo(combo: str):
    keys = [k.strip().lower() for k in str(combo).split("+") if k.strip()]
    if not keys or any(k not in VK for k in keys):
        raise ValueError(f"tecla não permitida: {combo}")
    return keys


def press_combo(combo: str):
    keys = valid_combo(combo)
    # Pequenas pausas: o Discord não reconhece um atalho pressionado e solto
    # no mesmo instante.
    for k in keys:
        _key(k)
        time.sleep(0.02)
    time.sleep(0.05)
    for k in reversed(keys):
        _key(k, up=True)
        time.sleep(0.01)


class _KEYBDINPUT(ctypes.Structure):
    _fields_ = [("wVk", wintypes.WORD), ("wScan", wintypes.WORD), ("dwFlags", wintypes.DWORD),
                ("time", wintypes.DWORD), ("dwExtraInfo", ctypes.c_size_t)]


class _INPUT(ctypes.Structure):
    class _U(ctypes.Union):
        # MOUSEINPUT é o maior membro da união: reserva o tamanho certo
        _fields_ = [("ki", _KEYBDINPUT), ("_pad", ctypes.c_byte * 32)]
    _anonymous_ = ("u",)
    _fields_ = [("type", wintypes.DWORD), ("u", _U)]


user32.SendInput.argtypes = [wintypes.UINT, ctypes.POINTER(_INPUT), ctypes.c_int]
KEYEVENTF_UNICODE = 0x4


def type_text(text: str):
    """Digita texto qualquer (acentos, emoji) como eventos Unicode.
    "\\n" vira Enter e "\\b" vira Backspace."""
    inputs = []

    def flush():
        if inputs:
            _send(inputs)
            inputs.clear()

    for ch in str(text)[:1000].replace("\r\n", "\n"):
        if ch in "\n\b":
            flush()
            press_combo("enter" if ch == "\n" else "backspace")
            continue
        data = ch.encode("utf-16-le")
        for i in range(0, len(data), 2):  # emoji = par substituto (2 unidades)
            unit = int.from_bytes(data[i:i + 2], "little")
            for flags in (KEYEVENTF_UNICODE, KEYEVENTF_UNICODE | KEYEVENTF_KEYUP):
                inp = _INPUT(type=1)  # INPUT_KEYBOARD
                inp.ki = _KEYBDINPUT(0, unit, flags, 0, 0)
                inputs.append(inp)
    flush()


def _send(inputs):
    arr = (_INPUT * len(inputs))(*inputs)
    user32.SendInput(len(inputs), arr, ctypes.sizeof(_INPUT))


def modifier(name, down):
    """Segura/solta Alt, Ctrl, Shift ou Win (ex.: Alt segurado para Alt+Tab)."""
    if name not in MODIFIERS:
        raise ValueError("só modificadores podem ser segurados")
    _key(name, up=not down)
    (held_modifiers.add if down else held_modifiers.discard)(name)


def release_modifiers():
    for k in list(held_modifiers):
        _key(k, up=True)
    held_modifiers.clear()


MOUSE = {"left": (0x2, 0x4), "right": (0x8, 0x10), "middle": (0x20, 0x40)}


def _u32(v):
    return int(v) & 0xFFFFFFFF


def mouse_move(dx, dy):
    dx, dy = max(-400, min(400, int(dx))), max(-400, min(400, int(dy)))
    user32.mouse_event(0x1, _u32(dx), _u32(dy), 0, 0)


def mouse_button(button="left", state="click"):
    down, up = MOUSE[button]
    if state in ("click", "down"):
        user32.mouse_event(down, 0, 0, 0, 0)
    if state in ("click", "up"):
        user32.mouse_event(up, 0, 0, 0, 0)


def mouse_scroll(dy=0, dx=0):
    if dy:
        user32.mouse_event(0x800, 0, 0, _u32(max(-1200, min(1200, int(dy)))), 0)
    if dx:
        user32.mouse_event(0x1000, 0, 0, _u32(max(-1200, min(1200, int(dx)))), 0)


def foreground_title():
    hwnd = user32.GetForegroundWindow()
    buf = ctypes.create_unicode_buffer(256)
    user32.GetWindowTextW(hwnd, buf, 256)
    return buf.value


_WNDENUM = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)


def focus_window_titled(part, exe=None):
    """Traz para a frente a primeira janela visível cujo título contém `part`.
    O Windows só deixa trocar o foco depois de uma tecla: um Alt solto antes destrava."""
    found = []

    def cb(h, _):
        if user32.IsWindowVisible(h):
            buf = ctypes.create_unicode_buffer(256)
            user32.GetWindowTextW(h, buf, 256)
            if part.lower() in buf.value.lower():
                pid = ctypes.c_ulong()
                user32.GetWindowThreadProcessId(h, ctypes.byref(pid))
                try:
                    ok = not exe or psutil.Process(pid.value).name().lower() == exe
                except psutil.Error:
                    ok = False
                if ok:
                    found.append(h)
                    return False
        return True
    user32.EnumWindows(_WNDENUM(cb), 0)
    if not found:
        return False
    h = found[0]
    if user32.IsIconic(h):
        user32.ShowWindow(h, 9)  # SW_RESTORE
    user32.keybd_event(0x12, 0, 0, 0)
    user32.keybd_event(0x12, 0, 2, 0)
    user32.SetForegroundWindow(h)
    return True


def foreground_app():
    """(nome do exe em minúsculas, caminho, pid) do programa em foco."""
    pid = ctypes.c_ulong()
    user32.GetWindowThreadProcessId(user32.GetForegroundWindow(), ctypes.byref(pid))
    try:
        p = psutil.Process(pid.value)
        return p.name().lower(), p.exe(), pid.value
    except (psutil.Error, OSError):
        return "", None, 0
