"""Testes do servidor (lógica pura: nada aqui aperta tecla, mexe no mouse ou abre rede).

Rodar, dentro de windows/server:   py -3 -m unittest -v
Fora do Windows (CI, WSL) as APIs do Windows viram dublês só para os módulos importarem.
"""
import ctypes
import sys
import unittest.mock
from pathlib import Path

SERVER = Path(__file__).resolve().parent.parent
if str(SERVER) not in sys.path:
    sys.path.insert(0, str(SERVER))

if not hasattr(ctypes, "windll"):
    ctypes.windll = unittest.mock.MagicMock()
    ctypes.WINFUNCTYPE = ctypes.CFUNCTYPE
    sys.modules.setdefault("winreg", unittest.mock.MagicMock())
