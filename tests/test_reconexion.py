"""Reconexión: espera creciente y pausa para no ocupar la radio buscando dispositivos ausentes."""
import unittest

import tests  # noqa: F401
from bordebt.caracteristicas.hid_bluetooth.reconexion import Reintentos

MAC = "AA:BB:CC:DD:EE:FF"


class PoliticaReintentos(unittest.TestCase):
    def test_espera_crece_hasta_el_maximo(self):
        r = Reintentos(base=20, maximo=300, intentos=0)
        esperas = []
        for _ in range(7):
            esperas.append(r.espera(MAC))
            r.fallo(MAC)
        self.assertEqual(esperas, [20, 20, 40, 80, 160, 300, 300])

    def test_respeta_la_espera(self):
        r = Reintentos(base=20)
        self.assertTrue(r.toca(MAC, 0.0))         # primer intento: inmediato
        r.intento(MAC, 0.0)
        r.fallo(MAC)
        self.assertFalse(r.toca(MAC, 19.0))
        self.assertTrue(r.toca(MAC, 20.0))
        r.intento(MAC, 20.0)
        r.fallo(MAC)
        self.assertFalse(r.toca(MAC, 59.0))       # ahora espera 40 s
        self.assertTrue(r.toca(MAC, 60.0))

    def test_se_pausa_tras_varios_fallos_y_vuelve_con_exito(self):
        r = Reintentos(base=20, intentos=3)
        for _ in range(3):
            r.fallo(MAC)
        self.assertTrue(r.en_pausa(MAC))
        self.assertFalse(r.toca(MAC, 1e6))
        r.exito(MAC)
        self.assertFalse(r.en_pausa(MAC))
        self.assertTrue(r.toca(MAC, 1e6))

    def test_cero_intentos_nunca_pausa(self):
        r = Reintentos(base=20, maximo=300, intentos=0)
        for _ in range(100):
            r.fallo(MAC)
        self.assertFalse(r.en_pausa(MAC))
        self.assertEqual(r.espera(MAC), 300)


try:
    from bordebt.caracteristicas.hid_bluetooth.linux import l2cap
except (ImportError, SystemExit, AttributeError):
    l2cap = None


@unittest.skipIf(l2cap is None, "sin soporte de sockets Bluetooth")
class GestorConReintentos(unittest.TestCase):
    """GestorBT sin sockets reales: el hilo de conexión se reemplaza por un fallo inmediato."""

    def setUp(self):
        self.reloj = [1000.0]
        self._monotonic = l2cap.time.monotonic
        l2cap.time.monotonic = lambda: self.reloj[0]
        g = l2cap.GestorBT.__new__(l2cap.GestorBT)
        g.enlaces = {MAC: l2cap.EnlaceL2CAP(MAC)}
        g.seguro, g.desconocido, g.al_cambiar = True, None, None
        g.reintentos = Reintentos(20, 300, 3)
        g.en_curso, g.pausado = set(), False
        self.intentos = []

        def falla(mac):
            self.intentos.append(self.reloj[0])
            g.en_curso.discard(mac)
            g.reintentos.fallo(mac)
        l2cap.threading.Thread = lambda target, args, daemon: type("H", (), {"start": lambda s: falla(*args)})()
        self.g = g

    def tearDown(self):
        l2cap.time.monotonic = self._monotonic
        import threading
        l2cap.threading.Thread = threading.Thread

    def avanzar_minutos(self, minutos):
        self.avanzar_segundos(minutos * 60)

    def avanzar_segundos(self, segundos):
        for _ in range(int(segundos)):
            self.reloj[0] += 1
            self.g.tick(self.reloj[0])

    def test_tras_pausarse_no_busca_en_segundo_plano(self):
        self.avanzar_minutos(60)
        self.assertEqual(len(self.intentos), 3)   # 0 s, +20 s, +40 s y luego en pausa

    def test_empujar_hacia_el_dispositivo_reintenta_aunque_este_en_pausa(self):
        self.avanzar_minutos(10)
        self.g.reconectar(MAC, forzar=True)
        self.assertEqual(len(self.intentos), 4)

    def test_perder_una_conexion_reanuda_la_busqueda(self):
        self.avanzar_minutos(10)
        self.g._cerrado(self.g.enlaces[MAC])
        self.avanzar_segundos(10)
        self.assertEqual(len(self.intentos), 4)   # intento inmediato con la espera base

    def test_en_pausa_no_busca_y_al_reanudar_conecta_ya(self):
        self.avanzar_minutos(10)                  # ya en pausa por fallos
        self.g.pausar()
        self.g.reconectar(MAC, forzar=True)       # pausado por reposo: ni forzando
        self.assertEqual(len(self.intentos), 3)
        self.g.reanudar()
        self.assertEqual(len(self.intentos), 4)
        self.avanzar_segundos(25)
        self.assertEqual(len(self.intentos), 5)   # con la espera base de nuevo


if __name__ == "__main__":
    unittest.main()
