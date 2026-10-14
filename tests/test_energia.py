"""Monitor de energía de Linux con un sysfs simulado (sin root ni hardware)."""
import os
import tempfile
import unittest

import tests  # noqa: F401
from bordebt.caracteristicas.energia.linux import MonitorEnergia


class Pantalla(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.m = MonitorEnergia()
        self.m.CONECTORES = os.path.join(self.dir.name, "card*-*")

    def tearDown(self):
        self.dir.cleanup()

    def conector(self, nombre, status, dpms):
        d = os.path.join(self.dir.name, nombre)
        os.makedirs(d, exist_ok=True)
        for archivo, valor in (("status", status), ("dpms", dpms)):
            with open(os.path.join(d, archivo), "w") as f:
                f.write(valor + "\n")

    def test_lee_el_dpms_de_las_pantallas_conectadas(self):
        self.conector("card1-eDP-1", "connected", "Off")
        self.conector("card1-HDMI-A-1", "disconnected", "On")     # desconectada: no cuenta
        self.assertFalse(self.m.pantalla_encendida(0.0))
        self.conector("card1-eDP-1", "connected", "On")
        self.assertFalse(self.m.pantalla_encendida(0.5))           # aún no toca leer de nuevo
        self.assertTrue(self.m.pantalla_encendida(1.0))

    def test_con_un_monitor_externo_encendido_no_esta_apagada(self):
        self.conector("card1-eDP-1", "connected", "Off")           # tapa cerrada
        self.conector("card1-HDMI-A-1", "connected", "On")
        self.assertTrue(self.m.pantalla_encendida(0.0))

    def test_si_no_se_puede_saber_se_asume_encendida(self):
        self.assertTrue(self.m.pantalla_encendida(0.0))


class Suspension(unittest.TestCase):
    def test_senal_de_logind(self):
        m = MonitorEnergia()
        m._al_dormir(True)
        self.assertTrue(m.durmiendo)
        m._al_dormir(False)
        self.assertFalse(m.durmiendo)
        self.assertEqual(m.despertares, 1)
        for h in m.fds().values():      # el aviso por la tubería se vacía sin bloquear
            h()
            h()


if __name__ == "__main__":
    unittest.main()
