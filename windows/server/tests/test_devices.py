"""Bateria dos periféricos: BLE, Windows.Gaming.Input e a junção com o resto (sem hardware)."""
import sys
import types
import unittest

import devices as dv


class BleTest(unittest.TestCase):
    def test_endereco_do_id(self):
        self.assertEqual(dv.ble_parse_id(r"BTHLE\DEV_d1c1b2a3f4e5\7&2B0C3E4&0&D1C1B2A3F4E5"), "D1C1B2A3F4E5")
        self.assertIsNone(dv.ble_parse_id(r"BTHLE\{0000180f-0000-1000-8000-00805f9b34fb}_Dev_VID&02046d"))
        self.assertIsNone(dv.ble_parse_id(r"BTHENUM\DEV_3CF775BF8850\9&23005B20&0&BLUETOOTHDEVICE_3CF775BF8850"))
        self.assertIsNone(dv.ble_parse_id(r"BTHLE\DEV_XYZ"))

    def test_tipo_pelo_nome(self):
        self.assertEqual(dv._name_kind("MX Master 3S"), "mouse")
        self.assertEqual(dv._name_kind("Keychron K2"), "other")
        self.assertEqual(dv._name_kind("Logi POP Keys"), "keyboard")
        self.assertEqual(dv._name_kind("Galaxy Buds2"), "headset")
        self.assertEqual(dv._name_kind("Xbox Wireless Controller"), "gamepad")

    def test_classico_e_ble_juntos_sem_repetir(self):
        classic = [("3CF775BF8850", "Fuxi-H5B", True, "headset"), ("AAAAAAAAAAAA", "Celular", False, "phone")]
        ble = [("D1C1B2A3F4E5", "MX Master 3S", True, "mouse"), ("3CF775BF8850", "Fuxi-H5B LE", True, "headset"),
               ("BBBBBBBBBBBB", "Teclado BLE", False, "keyboard"), ("CCCCCCCCCCCC", "Mouse desligado", False, "mouse")]
        out = dv.bt_list(classic, ble, {"3CF775BF8850": 80, "D1C1B2A3F4E5": 55, "CCCCCCCCCCCC": 20})
        got = {d["id"]: (d["name"], d["pct"], d["status"]) for d in out}
        self.assertEqual(got, {"bt-3CF775BF8850": ("Fuxi-H5B", 80, "ok"), "bt-D1C1B2A3F4E5": ("MX Master 3S", 55, "ok"),
                               "bt-CCCCCCCCCCCC": ("Mouse desligado", 20, "off")})


def ctrl(name="Xbox Wireless Controller", wireless=True):
    return types.SimpleNamespace(display_name=name, hardware_vendor_id=0x045E, hardware_product_id=0x0B13,
                                 non_roamable_id="{abc}-12345678", is_wireless=wireless)


def report(status, left, full):
    return types.SimpleNamespace(status=status, remaining_capacity_in_milliwatt_hours=left,
                                 full_charge_capacity_in_milliwatt_hours=full)


class ControleTest(unittest.TestCase):
    def test_porcentagem_e_estado(self):
        d = dv.wgi_entry(ctrl(), report(1, 1500, 2000))
        self.assertEqual((d["pct"], d["charging"], d["full"], d["wired"], d["kind"]), (75, False, False, False, "gamepad"))
        self.assertTrue(dv.wgi_entry(ctrl(), report(3, 500, 2000))["charging"])
        self.assertTrue(dv.wgi_entry(ctrl(), report(2, 2000, 2000))["full"])
        self.assertEqual(dv.wgi_entry(ctrl(""), report(1, 3000, 2000))["name"], "Controle")
        self.assertEqual(dv.wgi_entry(ctrl(), report(1, 3000, 2000))["pct"], 100)

    def test_sem_bateria_fica_de_fora(self):
        self.assertIsNone(dv.wgi_entry(ctrl(), report(0, None, None)))
        self.assertIsNone(dv.wgi_entry(ctrl(), report(1, None, 2000)))
        self.assertIsNone(dv.wgi_entry(ctrl(), report(1, 100, 0)))

    def test_lista_do_windows(self):
        cs = [(ctrl(), report(1, 1000, 2000)), (ctrl("Sem bateria"), None), (ctrl("Com fio"), report(0, None, None))]
        objs = []
        for c, r in cs:
            c.try_get_battery_report = (lambda r=r: r)
            objs.append(c)
        old = dv._wgi
        dv._wgi = types.SimpleNamespace(raw_game_controllers=objs)
        try:
            self.assertEqual([d["pct"] for d in dv.wgi_pads()], [50])
        finally:
            dv._wgi = old

    def test_xinput_cede_o_lugar(self):
        wg = [{"id": "wgi-1", "pct": 50}]
        xi = [{"id": "pad0", "pct": 70}, {"id": "pad1", "pct": 35}]
        self.assertEqual([d["id"] for d in dv.merge_pads(wg, xi)], ["wgi-1", "pad1"])
        self.assertEqual([d["id"] for d in dv.merge_pads([], xi)], ["pad0", "pad1"])


@unittest.skipUnless(sys.platform == "win32", "só no Windows")
class WindowsDeVerdadeTest(unittest.TestCase):
    def test_listas_nao_quebram(self):
        for addr, name, conn, kind in dv.ble_devices():
            self.assertEqual(len(addr), 12)
            self.assertIsInstance(conn, bool)
        self.assertIsInstance(dv.wgi_pads(), list)
        b = dv.Batteries()
        b.poll()
        self.assertIsInstance(b.state(), list)


if __name__ == "__main__":
    unittest.main()
