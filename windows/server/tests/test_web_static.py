"""Arquivos do app (web_static.py): só serve o que está dentro de web/, com o tipo certo."""
import unittest

import extras
import web_static


class Req:
    def __init__(self, path, upgrade=""):
        self.path = path
        self.headers = {"Upgrade": upgrade} if upgrade else {}


class Conn:
    def respond(self, status, text):
        return ("erro", int(status), text)


def get(path):
    return web_static.serve_static(Conn(), Req(path))


class ServeStaticTest(unittest.TestCase):
    def test_raiz_e_editor(self):
        r = get("/")
        self.assertEqual(r.status_code, 200)
        self.assertIn(b"<title>Companion PC</title>", r.body)
        self.assertIn(b"Personalizar", get("/editor").body)
        self.assertIn(b"Personalizar", get("/editor/").body)

    def test_pagina_leva_a_versao_do_app(self):
        # sem isso, uma cópia velha guardada pelo service worker nunca percebia a atualização
        meta = f'<meta name="build" content="{web_static.web_build()}">'.encode()
        self.assertIn(meta, get("/").body)
        self.assertIn(meta, get("/editor").body)
        self.assertEqual(get("/").headers["Content-Length"], str(len(get("/").body)))

    def test_query_string_e_hash_ignorados(self):
        self.assertEqual(get("/?preview=1#t=abc").status_code, 200)

    def test_tipos(self):
        for path, ctype in [("/css/base.css", "text/css"), ("/js/core.js", "text/javascript"),
                            ("/fonts/vt323.woff2", "font/woff2"), ("/manifest.webmanifest", "application/manifest+json")]:
            r = get(path)
            self.assertEqual(r.status_code, 200, path)
            self.assertTrue(r.headers["Content-Type"].startswith(ctype), path)
            self.assertEqual(r.headers["X-Content-Type-Options"], "nosniff")

    def test_todo_arquivo_referenciado_existe(self):
        import re
        for page in ("/", "/editor"):
            refs = re.findall(r'(?:href|src)="([^"#:]+)"', get(page).body.decode())
            self.assertTrue(refs, page)
            for ref in refs:
                self.assertEqual(get(ref if ref.startswith("/") else "/" + ref).status_code, 200, (page, ref))
        # o editor também abre como /editor/: os caminhos dele têm que ser absolutos
        self.assertNotRegex(get("/editor").body.decode(), r'(?:href|src)="(?!/|https?:)')

    def test_nao_sai_da_pasta_web(self):
        for path in ["/../companion_server.py", "/..%2Fcompanion_server.py", "/../../README.md",
                     "/css/../../config.json", "//etc/passwd", "/fonts/../../web_static.py"]:
            r = get(path)
            self.assertIsInstance(r, tuple, path)
            self.assertEqual(r[1], 404, path)

    def test_nao_entrega_config_ao_lado_da_pasta_web(self):
        # o config.json (com o token) fica ao lado de web/ e tem extensão permitida
        import tempfile
        from pathlib import Path
        from unittest import mock
        with tempfile.TemporaryDirectory() as d:
            web = Path(d) / "web"
            (web / "css").mkdir(parents=True)
            (web / "index.html").write_text("ok")
            (Path(d) / "config.json").write_text('{"token": "x"}')
            (Path(d) / "web-x").mkdir()
            (Path(d) / "web-x" / "a.json").write_text("{}")
            with mock.patch.object(web_static, "WEB_DIR", web):
                self.assertEqual(get("/").status_code, 200)
                for path in ["/../config.json", "/css/../../config.json", "/%2E%2E/config.json", "/../web-x/a.json"]:
                    r = get(path)
                    self.assertIsInstance(r, tuple, path)
                    self.assertEqual(r[1], 404, path)

    def test_extensao_fora_da_lista(self):
        self.assertEqual(get("/fonts/LICENSE.txt").status_code, 200)
        self.assertEqual(get("/tests").__class__, tuple)

    def test_websocket_segue_normal(self):
        self.assertIsNone(web_static.serve_static(Conn(), Req("/", upgrade="websocket")))

    def test_link_de_download(self):
        url = extras.dl_register("nota.txt", data=b"oi", ctype="text/plain")
        r = get(url)
        self.assertEqual(r.body, b"oi")
        self.assertIn("nota.txt", r.headers["Content-Disposition"])
        self.assertEqual(r.headers["Cache-Control"], "no-store")
        self.assertEqual(get("/dl/naoexiste/x")[1], 404)

    def test_web_build_muda_com_arquivo(self):
        self.assertGreater(web_static.web_build(), 0)
