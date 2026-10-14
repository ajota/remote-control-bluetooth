import unittest

import tests  # noqa: F401
from bordebt.comun.disposicion import construir_vecinos, normalizar_lado, normalizar_mac
from bordebt.caracteristicas.calibracion import medidas
from bordebt.caracteristicas.hid_bluetooth import protocolo

DEVS = [{"name": "tablet", "mac": "AA:AA:AA:AA:AA:01", "side": "right", "of": "laptop"},
        {"name": "cel", "mac": "AA:AA:AA:AA:AA:02", "side": "left", "of": "laptop"},
        {"name": "cel2", "mac": "AA:AA:AA:AA:AA:03", "side": "right", "of": "tablet"}]


class Disposicion(unittest.TestCase):
    def test_vecinos_y_cadena(self):
        vec = construir_vecinos(DEVS)
        self.assertEqual(vec["laptop"], {"right": "tablet", "left": "cel"})
        self.assertEqual(vec["tablet"], {"left": "laptop", "right": "cel2"})

    def test_conflicto_en_un_borde(self):
        with self.assertRaises(ValueError):
            construir_vecinos(DEVS + [{"name": "x", "mac": "", "side": "right", "of": "laptop"}])

    def test_normalizar(self):
        self.assertEqual(normalizar_lado("Derecha"), "right")
        self.assertEqual(normalizar_mac("aa:bb:cc:dd:ee:ff"), "AA:BB:CC:DD:EE:FF")
        with self.assertRaises(ValueError):
            normalizar_lado("encima")


class Protocolo(unittest.TestCase):
    def test_respuestas_de_control(self):
        casos = [(b"\x70", False, b"\x00", True), (b"\x60", True, b"\xa0\x00", True),
                 (b"\x71", True, b"\x00", False), (b"\x41\x02", False, b"\xa1\x02" + bytes(7), False),
                 (b"\x41\x09", False, b"\x02", False), (b"\x90", False, b"\x00", False),
                 (b"\x30", False, b"\x03", False)]
        for peticion, boot, respuesta, boot_nuevo in casos:
            r, b, seguir = protocolo.responder_control(peticion, boot)
            self.assertEqual((r, b, seguir), (respuesta, boot_nuevo, True), peticion)
        self.assertFalse(protocolo.responder_control(b"\x15", False)[2])   # desconexión virtual

    def test_reportes_grandes_se_parten(self):
        rs = list(protocolo.reportes_raton(0, 40000, 0))
        self.assertEqual(len(rs), 2)
        self.assertEqual(len(protocolo.DESCRIPTOR), 171)


class Calibracion(unittest.TestCase):
    def test_desempate_descarta_la_ronda_mala(self):
        w, h, acel, lento, acuerdo = medidas.combinar([(4500, 2812, 2.5, 1.0), (5610, 3506, 3.1, 1.0),
                                                       (4500, 2812, 2.5, 1.0)])
        self.assertEqual((w, h, acuerdo), (4500, 2812, True))

    def test_sin_acuerdo_usa_mediana(self):
        *_, acuerdo = medidas.combinar([(1000, 600, 2, 1), (2000, 900, 2, 1), (3000, 1200, 2, 1)])
        self.assertFalse(acuerdo)

    def test_proporcion(self):
        self.assertAlmostEqual(medidas.proporcion("2560x1600"), 0.625)
        self.assertAlmostEqual(medidas.proporcion("16:10"), 0.625)
        with self.assertRaises(ValueError):
            medidas.proporcion("ancho")


if __name__ == "__main__":
    unittest.main()
