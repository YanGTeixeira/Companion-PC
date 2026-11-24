"""HTTPS (https_cert.py): nome do Tailscale, erros, certificado manual e o app servido com TLS de verdade.

tests/fixtures/localhost.{crt,key}: certificado autoassinado só para estes testes (CN=localhost).
"""
import asyncio
import json
import os
import ssl
import subprocess
import tempfile
import threading
import unittest
import urllib.request
from pathlib import Path
from unittest import mock

import https_cert
import web_static

FIX = Path(__file__).resolve().parent / "fixtures"
CERT, KEY = str(FIX / "localhost.crt"), str(FIX / "localhost.key")


def done(stdout="", stderr="", code=0):
    return subprocess.CompletedProcess([], code, stdout, stderr)


class NomeTest(unittest.TestCase):
    def test_nome_magicdns(self):
        st = {"BackendState": "Running", "Self": {"DNSName": "Meu-PC.tail1234.ts.net."}}
        self.assertEqual(https_cert.dns_name(st), "meu-pc.tail1234.ts.net")

    def test_desligado_ou_sem_magicdns(self):
        self.assertIsNone(https_cert.dns_name({"BackendState": "Stopped", "Self": {"DNSName": "pc.x.ts.net."}}))
        self.assertIsNone(https_cert.dns_name({"BackendState": "Running", "Self": {"DNSName": ""}}))
        self.assertIsNone(https_cert.dns_name({"BackendState": "Running", "Self": {"DNSName": "pc.example.com."}}))
        self.assertIsNone(https_cert.dns_name(None))

    def test_explica_erros(self):
        self.assertIn("HTTPS Certificates", https_cert.explain("500 Internal: your Tailscale account does not support getting TLS certs"))
        self.assertIn("HTTPS Certificates", https_cert.explain("HTTPS cert support is not enabled/configured for your tailnet"))
        self.assertIn("permissão", https_cert.explain("Access denied: cert access denied"))
        self.assertEqual(https_cert.explain("linha 1\nalgo estranho"), "algo estranho")


class ObterTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)

    def test_desligado_no_config(self):
        self.assertFalse(https_cert.Https(self.tmp.name, {"enabled": False}).enabled)

    def test_sem_tailscale(self):
        h = https_cert.Https(self.tmp.name, {})
        with mock.patch.object(https_cert, "find_tailscale", return_value=None), self.assertLogs("companion", "WARNING"):
            self.assertFalse(h.refresh())
        self.assertIn("não instalado", h.error)
        self.assertEqual(h.state()["on"], False)

    def test_tailscale_pede_o_certificado_com_o_nome_certo(self):
        h = https_cert.Https(self.tmp.name, {})
        status = json.dumps({"BackendState": "Running", "Self": {"DNSName": "pc.tail1.ts.net."}})
        calls = []

        def run(exe, *args, timeout=60):
            calls.append(args)
            if args[0] == "status":
                return done(status)
            # o tailscale de verdade grava os arquivos: aqui copia os de teste
            cert, key = args[args.index("--cert-file") + 1], args[args.index("--key-file") + 1]
            Path(cert).write_bytes(Path(CERT).read_bytes())
            Path(key).write_bytes(Path(KEY).read_bytes())
            return done()
        with mock.patch.object(https_cert, "find_tailscale", return_value="tailscale"), \
             mock.patch.object(h, "_run", side_effect=run), self.assertLogs("companion", "INFO"):
            self.assertTrue(h.refresh())
        self.assertEqual(calls[1][0], "cert")
        self.assertEqual(calls[1][-1], "pc.tail1.ts.net")
        self.assertTrue(str(Path(calls[1][2]).parent).endswith("certs"))
        self.assertEqual(h.url(), "https://pc.tail1.ts.net:8771/")
        self.assertEqual((h.mode, h.error), ("tailscale", ""))
        self.assertFalse(h.due())

    def test_https_desativado_na_tailnet(self):
        h = https_cert.Https(self.tmp.name, {})
        st = done(json.dumps({"BackendState": "Running", "Self": {"DNSName": "pc.tail1.ts.net."}}))
        with mock.patch.object(https_cert, "find_tailscale", return_value="tailscale"), \
             mock.patch.object(h, "_run", side_effect=[st, done(stderr="HTTPS cert support is not enabled", code=1)]), \
             self.assertLogs("companion", "WARNING"):
            self.assertFalse(h.refresh())
        self.assertIn("MagicDNS", h.error)

    def test_falha_na_renovacao_mantem_o_certificado_anterior(self):
        h = https_cert.Https(self.tmp.name, {"cert_file": CERT, "key_file": KEY, "host": "pc.local"})
        with self.assertLogs("companion", "INFO"):
            self.assertTrue(h.refresh())
        ctx = h.ctx
        h.cfg["cert_file"] = os.path.join(self.tmp.name, "sumiu.crt")
        with self.assertLogs("companion", "WARNING"):
            self.assertTrue(h.refresh())
        self.assertIs(h.ctx, ctx)
        self.assertIn("não existem", h.error)

    def test_par_invalido(self):
        bad = Path(self.tmp.name) / "x.crt"
        bad.write_text("não é certificado")
        h = https_cert.Https(self.tmp.name, {"cert_file": str(bad), "key_file": KEY})
        with self.assertLogs("companion", "WARNING"):
            self.assertFalse(h.refresh())
        self.assertIn("inválido", h.error)


class ServidorTlsTest(unittest.TestCase):
    """Sobe o app numa porta TLS com o mesmo serve_static do servidor e conecta como o celular conectaria."""

    @classmethod
    def setUpClass(cls):
        from websockets.asyncio.server import serve
        h = https_cert.Https(tempfile.gettempdir(), {"cert_file": CERT, "key_file": KEY, "host": "localhost", "port": 0})
        with mock.patch.object(https_cert.log, "info"):
            assert h.refresh()
        cls.loop = asyncio.new_event_loop()
        ready = threading.Event()

        async def handler(ws):
            msg = json.loads(await ws.recv())
            await ws.send(json.dumps({"t": "welcome", "eco": msg.get("token")}))

        async def main():
            cls.server = await serve(handler, "127.0.0.1", 0, ssl=h.ctx, process_request=web_static.serve_static)
            cls.port = cls.server.sockets[0].getsockname()[1]
            ready.set()
            try:
                await cls.server.serve_forever()
            except asyncio.CancelledError:
                pass   # tearDownClass fechou
        cls.thread = threading.Thread(target=lambda: cls.loop.run_until_complete(main()), daemon=True)
        cls.thread.start()
        ready.wait(5)
        cls.client_ctx = ssl.create_default_context(cafile=CERT)

    @classmethod
    def tearDownClass(cls):
        cls.loop.call_soon_threadsafe(cls.server.close)

    def test_pagina_e_service_worker_por_https(self):
        for path, needle in [("/", b"Companion PC"), ("/sw.js", b"APP_CACHE")]:
            with urllib.request.urlopen(f"https://localhost:{self.port}{path}", context=self.client_ctx, timeout=5) as r:
                self.assertEqual(r.status, 200)
                self.assertIn(needle, r.read())

    def test_websocket_seguro(self):
        from websockets.sync.client import connect
        with connect(f"wss://localhost:{self.port}/ws", ssl=self.client_ctx, open_timeout=5) as ws:
            ws.send(json.dumps({"t": "hello", "token": "abc"}))
            self.assertEqual(json.loads(ws.recv(timeout=5)), {"t": "welcome", "eco": "abc"})

    def test_cliente_sem_confiar_no_certificado_e_recusado(self):
        with self.assertRaises(Exception):
            urllib.request.urlopen(f"https://localhost:{self.port}/", context=ssl.create_default_context(), timeout=5)
