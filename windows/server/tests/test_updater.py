"""Atualização: comparação de versões e leitura do release.json (sem rede)."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import updater


class UpdaterTest(unittest.TestCase):
    def mk(self, version="1.9"):
        self.dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)
        return updater.Updater(version, {}, Path(self.dir.name))

    def test_versao_por_numero(self):
        self.assertGreater(updater.vtuple("1.10"), updater.vtuple("1.9"))
        self.assertGreater(updater.vtuple("v2.0"), updater.vtuple("1.99"))
        self.assertEqual(updater.vtuple("1.9"), updater.vtuple("v1.9"))

    def check(self, upd, release):
        with mock.patch.object(upd, "_get", return_value=json.dumps(release).encode()):
            return upd.check()

    def test_tem_versao_nova(self):
        st = self.check(self.mk(), {"version": "1.10", "notes": "sons"})
        self.assertEqual((st["latest"], st["notes"]), ("1.10", "sons"))

    def test_mesma_ou_mais_velha(self):
        self.assertIsNone(self.check(self.mk(), {"version": "1.9"})["latest"])
        self.assertIsNone(self.check(self.mk(), {"version": "1.2"})["latest"])

    def test_versao_estranha_ou_sem_rede(self):
        upd = self.mk()
        self.assertIn("inválida", self.check(upd, {"version": "1.9; rm"})["err"])
        with mock.patch.object(upd, "_get", side_effect=OSError("offline")):
            st = upd.check()
        self.assertIsNone(st["latest"])
        self.assertIn("offline", st["err"])

    def test_instalar_sem_versao_nova(self):
        upd = self.mk()
        with mock.patch.object(upd, "_get", return_value=b'{"version": "1.9"}'):
            with self.assertRaisesRegex(RuntimeError, "mais nova"):
                upd.install()

    def test_instalar_baixa_e_roda_o_instalador(self):
        import io, zipfile
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as z:
            z.writestr("Companion-PC-1.10/windows/install-server.ps1", "# ok")
        upd = self.mk()
        upd.latest = {"version": "1.10", "notes": ""}
        with mock.patch.object(upd, "_get", return_value=buf.getvalue()) as get, \
                mock.patch.object(updater.tempfile, "gettempdir", return_value=self.dir.name), \
                mock.patch.object(updater.subprocess, "Popen") as popen:
            self.assertEqual(upd.install()["version"], "1.10")
        self.assertTrue(get.call_args[0][0].endswith("/archive/refs/tags/v1.10.zip"))
        cmd = popen.call_args[0][0][-1]
        self.assertIn("install-server.ps1", cmd)
        self.assertIn("-Source", cmd)
        self.assertIn("Instalando", upd.state()["busy"])


if __name__ == "__main__":
    unittest.main()
