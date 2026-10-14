import collections
import time
import unittest

import tests  # noqa: F401
from tests.dobles import EnlaceFalso


class Radio:
    """Entrega como mucho `tasa` reportes/s; el resto espera en cola (enlace saturado)."""

    def __init__(self, tasa):
        self.tasa, self.cola, self.t, self.entregados = tasa, collections.deque(), time.monotonic(), []

    def avanzar(self):
        ahora = time.monotonic()
        n = int((ahora - self.t) * self.tasa)
        if n:
            self.t += n / self.tasa
        for _ in range(min(n, len(self.cola))):
            self.cola.popleft()
            self.entregados.append(ahora)


class EnlaceSaturado(EnlaceFalso):
    def __init__(self, radio, cola_rota=False):
        super().__init__()
        self.r, self.rota = radio, cola_rota

    def _transmitir(self, datos):
        self.r.avanzar()
        self.r.cola.append(1)
        return super()._transmitir(datos)

    def cola(self):
        self.r.avanzar()
        return 212992 if self.rota else len(self.r.cola) * 800


def mover_y_parar(en, radio, segundos=1.0):
    fin = time.monotonic() + segundos
    while time.monotonic() < fin:
        en.raton(0, 5, 0)
        en.vaciar()
        time.sleep(0.01)
    parada = time.monotonic()
    while en.pendiente or radio.cola:
        en.vaciar()
        radio.avanzar()
        time.sleep(0.004)
    return radio.entregados[-1] - parada


class Agrupacion(unittest.TestCase):
    def test_enlace_saturado_no_acumula_retraso(self):
        radio = Radio(40)
        retraso = mover_y_parar(EnlaceSaturado(radio), radio)
        self.assertLess(retraso, 0.15)

    def test_sin_agrupar_si_acumula(self):
        radio = Radio(40)
        en = EnlaceSaturado(radio)
        en.agrupar = False
        self.assertGreater(mover_y_parar(en, radio), 0.5)

    def test_medicion_rota_no_congela(self):
        en = EnlaceSaturado(Radio(1000), cola_rota=True)
        fin = time.monotonic() + 0.5
        while time.monotonic() < fin:
            en.raton(0, 5, 0)
            en.vaciar()
            time.sleep(0.01)
        self.assertGreater(sum(r[2] for r in en.ratones()), 150)

    def test_clic_sale_inmediato(self):
        en = EnlaceSaturado(Radio(10))
        en.raton(0, 5, 0)
        en.raton(1)
        self.assertEqual(en.ratones()[-1][1], 1)


if __name__ == "__main__":
    unittest.main()
