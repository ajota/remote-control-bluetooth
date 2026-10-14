import time
import unittest

import tests  # noqa: F401
from tests.dobles import AccionesFalsas, cfg, esperar
from bordebt.caracteristicas.entrada.eventos import CuadroTactil
from bordebt.caracteristicas.gestos.interprete import InterpreteTactil

ANCHO, ALTO = 100.0, 62.0


def cuadro(dedos, x=None, y=None, puntos=(), presion=False, suelta=False):
    return CuadroTactil(time.monotonic(), dedos, x, y, ANCHO, ALTO, list(puntos), presion, suelta)


class Toques(unittest.TestCase):
    def setUp(self):
        self.a = AccionesFalsas()
        self.it = InterpreteTactil(self.a, cfg())

    def tocar(self, dedos):
        self.it.cuadro(cuadro(dedos, 50, 30))
        time.sleep(0.05)
        self.it.cuadro(cuadro(0))

    def test_toque_es_clic_izquierdo(self):
        self.tocar(1)
        self.assertEqual(self.a.eventos, [])                  # espera por si es arrastre
        esperar(0.3, self.it.tick)
        self.assertEqual(self.a.eventos, [("clic", "L")])

    def test_dos_dedos_clic_derecho(self):
        self.tocar(2)
        self.assertEqual(self.a.eventos, [("clic", "R")])

    def test_toque_toque_mantener_arrastra(self):
        self.tocar(1)
        time.sleep(0.05)
        self.it.cuadro(cuadro(1, 50, 30))
        for i in range(10):
            time.sleep(0.008)
            self.it.cuadro(cuadro(1, 50 + i, 30))
        self.it.cuadro(cuadro(0))
        self.assertEqual(self.a.eventos[0], ("L", 1))
        self.assertEqual(self.a.eventos[-1], ("L", 0))
        self.assertGreater(self.a.mov[0], 0)

    def test_esquina_inferior_derecha_es_clic_derecho(self):
        self.it.cuadro(cuadro(1, 90, 60))
        self.it.cuadro(cuadro(1, 90, 60, presion=True))
        self.it.cuadro(cuadro(1, 90, 60, suelta=True))
        self.it.cuadro(cuadro(0))
        esperar(0.3, self.it.tick)
        self.assertEqual(self.a.eventos, [("R", 1), ("R", 0)])   # y sin clic extra por el toque


class DosYTresDedos(unittest.TestCase):
    def setUp(self):
        self.a = AccionesFalsas()
        self.it = InterpreteTactil(self.a, cfg())

    def test_pellizco_con_un_dedo_quieto(self):
        for i in range(25):
            self.it.cuadro(cuadro(2, 40, 30, [(40, 30), (50 + i * 0.6, 30)]))
            time.sleep(0.008)
        self.it.cuadro(cuadro(0))
        zoom = sum(e[1] for e in self.a.eventos if e[0] == "zoom")
        self.assertGreater(zoom, 0)
        self.assertIn(("zoom_fin",), self.a.eventos)

    def test_scroll_natural(self):
        for i in range(25):
            self.it.cuadro(cuadro(2, 40, 20 + i, [(40, 20 + i), (50, 20 + i)]))
            time.sleep(0.008)
        v = sum(e[1] for e in self.a.eventos if e[0] == "scroll")
        self.assertGreater(v, 0)                              # dedos hacia abajo = rueda hacia arriba

    def test_tres_dedos(self):
        for i in range(20):
            self.it.cuadro(cuadro(3, 50, 50 - i))
            time.sleep(0.008)
        self.assertEqual([e for e in self.a.eventos if e[0] == "gesto"], [("gesto", "arriba")])


if __name__ == "__main__":
    unittest.main()
