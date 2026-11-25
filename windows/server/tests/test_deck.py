"""Deck: salvar não pode travar por macro antiga que cita programa fora do config.json."""
import json
import tempfile
import unittest
from pathlib import Path

import extras


def ok_combo(_):
    return True


class DeckMacroTest(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.deck = extras.Deck(Path(self.dir.name))

    def tearDown(self):
        self.dir.cleanup()

    def test_deck_padrao_salva_sem_os_programas(self):
        d = self.deck.get()
        d["pages"].append({"name": "Sons", "buttons": []})
        saved = self.deck.save(d, ok_combo, shortcuts={})
        self.assertEqual(saved["pages"][-1]["name"], "Sons")

    def test_macro_nova_confere_programa(self):
        d = self.deck.get()
        d["pages"].append({"name": "X", "buttons": [{"label": "m", "type": "macro", "value": "abrir naoexiste"}]})
        with self.assertRaisesRegex(ValueError, "naoexiste"):
            self.deck.save(d, ok_combo, shortcuts={})

    def test_macro_ja_salva_continua_salvando(self):
        self.deck.path.write_text(json.dumps({"pages": [
            {"name": "X", "buttons": [{"label": "m", "type": "macro", "value": "abrir sumiu"}]}]}), encoding="utf-8")
        d = self.deck.get()
        d["pages"][0]["name"] = "Y"
        self.assertEqual(self.deck.save(d, ok_combo, shortcuts={})["pages"][0]["name"], "Y")

    def test_rodar_ainda_avisa(self):
        with self.assertRaisesRegex(ValueError, "config.json"):
            extras.parse_macro("abrir vscode", ok_combo, {})


if __name__ == "__main__":
    unittest.main()
