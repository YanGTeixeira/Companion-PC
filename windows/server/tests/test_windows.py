"""Chamadas reais do Windows (só leem estado, não mexem em nada). Fora do Windows são puladas."""
import ctypes
import sys
import unittest


@unittest.skipUnless(sys.platform == "win32", "só no Windows")
class TelaCheiaTest(unittest.TestCase):
    def test_tela_cheia_depois_do_extras_declarar_getmonitorinfo(self):
        # o extras.py declara GetMonitorInfoW com a estrutura dele na user32 compartilhada;
        # antes o screentime quebrava com ArgumentError em todo tick com o PC ocioso
        import importlib
        importlib.import_module("extras")
        import screentime
        hwnd = ctypes.windll.user32.GetForegroundWindow() or ctypes.windll.user32.GetDesktopWindow()
        self.assertIn(screentime.is_fullscreen(hwnd), (True, False))
        self.assertFalse(screentime.is_fullscreen(0))
