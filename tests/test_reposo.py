"""Reposo: pausar con la pantalla apagada o en suspensión y mantener despierta la laptop en uso remoto."""
import io
import time
import unittest
from contextlib import redirect_stdout

import tests  # noqa: F401
from tests.dobles import ConexionesFalsas, EnlaceFalso, PunteroFalso, RadioFalsa, TecladoFalso, cfg
from bordebt.comun.disposicion import construir_vecinos
from bordebt.caracteristicas.conmutacion.destinos import DestinoLocal, DestinoRemoto
from bordebt.caracteristicas.conmutacion.motor import Motor
from bordebt.caracteristicas.conmutacion.reposo import Reposo

DEVS = [{"name": "tablet", "mac": "AA:AA:AA:AA:AA:01", "side": "right", "of": "laptop", "width": 1000, "height": 600}]


class CapturaFalsa:
    def __init__(self):
        self.pausada = False
        self.teclas_presionadas = 0      # intentos de retomar que fallarán por teclas presionadas

    def pausar(self):
        self.pausada = True

    def retomar(self):
        if self.teclas_presionadas:
            self.teclas_presionadas -= 1
            return False
        self.pausada = False
        return True


def armar(**opciones):
    c = cfg()
    puntero = PunteroFalso()
    local = DestinoLocal(puntero, 1000, 500, 25)
    remotos = {d["name"]: DestinoRemoto(d, EnlaceFalso(d["mac"]), c) for d in DEVS}
    conexiones, captura = ConexionesFalsas(), CapturaFalsa()
    m = Motor(construir_vecinos(DEVS), local, remotos, conexiones, TecladoFalso(), RadioFalsa())
    return Reposo(m, conexiones, captura, puntero, **opciones), m, conexiones, captura, puntero


class Pausa(unittest.TestCase):
    def setUp(self):
        self.salida = redirect_stdout(io.StringIO())
        self.salida.__enter__()
        self.t = time.monotonic()

    def tearDown(self):
        self.salida.__exit__(None, None, None)

    def test_pantalla_apagada_en_la_laptop_pausa_y_al_encender_reanuda(self):
        r, m, con, cap, _ = armar()
        r.tick(self.t, pantalla=False, durmiendo=False)
        self.assertTrue(r.pausado)
        self.assertEqual(con.pausas, 1)
        self.assertTrue(cap.pausada)
        r.tick(self.t + 1, pantalla=False, durmiendo=False)
        self.assertEqual(con.pausas, 1)               # una sola vez
        r.tick(self.t + 2, pantalla=True, durmiendo=False)
        self.assertFalse(r.pausado)
        self.assertFalse(cap.pausada)
        self.assertEqual(con.reanudaciones, 1)

    def test_no_pausa_si_estas_usando_un_dispositivo(self):
        r, m, con, _, _ = armar()
        m.cambiar("tablet", "left", 0.5)
        m.ultima_actividad = self.t
        r.tick(self.t + 10, pantalla=False, durmiendo=False)
        self.assertFalse(r.pausado)
        self.assertEqual(m.activo, "tablet")

    def test_dispositivo_abandonado_con_la_pantalla_apagada_pausa_sin_encenderla(self):
        r, m, con, _, puntero = armar()
        m.cambiar("tablet", "left", 0.5)
        pos = puntero.pos
        m.ultima_actividad = self.t
        r.tick(self.t + Reposo.INACTIVO + 1, pantalla=False, durmiendo=False)
        self.assertTrue(r.pausado)
        self.assertEqual(m.activo, "laptop")
        self.assertEqual(puntero.pos, pos)            # mover el puntero encendería la pantalla
        self.assertTrue(puntero.escondido)

    def test_reanudar_espera_a_que_se_suelten_las_teclas(self):
        r, m, con, cap, _ = armar()
        r.tick(self.t, pantalla=False, durmiendo=False)
        cap.teclas_presionadas = 2
        r.tick(self.t + 1, pantalla=True, durmiendo=False)
        self.assertTrue(r.pausado)
        self.assertEqual(r.espera(), Reposo.REINTENTO)
        r.tick(self.t + 1.2, pantalla=True, durmiendo=False)
        r.tick(self.t + 1.4, pantalla=True, durmiendo=False)
        self.assertFalse(r.pausado)
        self.assertEqual(con.reanudaciones, 1)
        self.assertEqual(r.espera(), 1.0)

    def test_suspension_pausa_aunque_la_pantalla_siga_encendida(self):
        r, m, con, _, _ = armar()
        m.cambiar("tablet", "left", 0.5)
        m.ultima_actividad = self.t
        r.tick(self.t, pantalla=True, durmiendo=True)
        self.assertTrue(r.pausado)
        self.assertEqual(m.activo, "laptop")
        r.tick(self.t + 5, pantalla=True, durmiendo=False, despertares=1)
        self.assertFalse(r.pausado)
        self.assertEqual(con.reanudaciones, 1)

    def test_vuelta_de_suspension_no_vista_reconecta(self):
        r, m, con, _, _ = armar()
        r.tick(self.t, pantalla=True, durmiendo=False, despertares=1)   # se durmió y despertó entre vueltas
        self.assertFalse(r.pausado)
        self.assertEqual(con.reanudaciones, 1)

    def test_sin_pausar_con_pantalla_apagada_si_se_desactiva(self):
        r, m, con, _, _ = armar(pausar_pantalla=False)
        r.tick(self.t, pantalla=False, durmiendo=False)
        self.assertFalse(r.pausado)


class MantenerDespierta(unittest.TestCase):
    def test_toca_el_puntero_mientras_usas_un_dispositivo(self):
        r, m, _, _, puntero = armar()
        t = time.monotonic()
        with redirect_stdout(io.StringIO()):
            m.cambiar("tablet", "left", 0.5)
        for s in range(0, 61, 5):                     # un minuto de uso continuo
            m.ultima_actividad = t + s
            r.tick(t + s, pantalla=True, durmiendo=False)
        self.assertEqual(puntero.despertares, 3)      # a los 0, 30 y 60 s

    def test_no_toca_en_la_laptop_ni_sin_uso(self):
        r, m, _, _, puntero = armar()
        t = time.monotonic()
        r.tick(t, pantalla=True, durmiendo=False)     # en la laptop: el escritorio ya ve la actividad
        with redirect_stdout(io.StringIO()):
            m.cambiar("tablet", "left", 0.5)
        m.ultima_actividad = t - Reposo.INACTIVO - 1  # tablet abandonada
        r.tick(t, pantalla=True, durmiendo=False)
        self.assertEqual(puntero.despertares, 0)

    def test_desactivado(self):
        r, m, _, _, puntero = armar(mantener_despierta=False)
        t = time.monotonic()
        with redirect_stdout(io.StringIO()):
            m.cambiar("tablet", "left", 0.5)
        m.ultima_actividad = t
        r.tick(t, pantalla=True, durmiendo=False)
        self.assertEqual(puntero.despertares, 0)


if __name__ == "__main__":
    unittest.main()
