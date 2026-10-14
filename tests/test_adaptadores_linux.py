"""Adaptadores de Linux con dispositivos simulados (necesitan python3-evdev, no root ni hardware)."""
import sys
import time
import types
import unittest

import tests  # noqa: F401

try:
    from evdev import ecodes as e
    from bordebt.caracteristicas.entrada import linux as entrada
except (ImportError, SystemExit):
    e = None


class Ev:
    def __init__(self, t, c, v):
        self.type, self.code, self.value = t, c, v


class Absinfo:
    def __init__(self, value, maximo):
        self.value, self.min, self.max, self.resolution = value, 0, maximo, 32


class TouchpadSimulado:
    def __init__(self):
        self.keys = set()
        self.ax = self.ay = 0

    def absinfo(self, c):
        return Absinfo(self.ax if c == e.ABS_X else self.ay, 3200 if c == e.ABS_X else 2000)

    def active_keys(self):
        return list(self.keys)

    def capabilities(self):
        return {e.EV_KEY: [e.BTN_TOUCH, e.BTN_TOOL_FINGER, e.BTN_LEFT]}


@unittest.skipIf(e is None, "requiere python3-evdev")
class Touchpad(unittest.TestCase):
    def setUp(self):
        self.dev = TouchpadSimulado()
        self.cuadros = []
        self.tp = entrada.Touchpad(self.dev, self.cuadros.append)

    def cuadro(self, x, y, keys, evs=()):
        self.dev.keys = keys
        for ev in evs:
            self.tp.evento(Ev(*ev))
        self.tp.evento(Ev(e.EV_ABS, e.ABS_X, x))
        self.tp.evento(Ev(e.EV_ABS, e.ABS_Y, y))
        self.tp.evento(Ev(e.EV_SYN, e.SYN_REPORT, 0))

    def test_dedo_flotando_no_cuenta_como_contacto(self):
        self.cuadro(1600, 1000, {e.BTN_TOOL_FINGER, e.BTN_TOUCH}, [(e.EV_KEY, e.BTN_TOUCH, 1)])
        self.cuadro(1700, 1000, {e.BTN_TOOL_FINGER}, [(e.EV_KEY, e.BTN_TOUCH, 0)])   # hover
        self.assertEqual([c.dedos for c in self.cuadros], [1, 0])

    def test_milimetros(self):
        self.cuadro(1600, 1000, {e.BTN_TOUCH, e.BTN_TOOL_FINGER})
        c = self.cuadros[-1]
        self.assertAlmostEqual(c.x, 50.0)
        self.assertAlmostEqual(c.ancho, 100.0)

    def test_eventos_perdidos_resincronizan(self):
        self.cuadro(1000, 1000, {e.BTN_TOUCH, e.BTN_TOOL_FINGER})
        self.tp.evento(Ev(e.EV_SYN, 3, 0))                    # SYN_DROPPED
        self.tp.evento(Ev(e.EV_ABS, e.ABS_X, 3000))
        self.dev.ax = 3000
        self.tp.evento(Ev(e.EV_SYN, e.SYN_REPORT, 0))         # se descarta hasta aquí
        self.cuadro(3010, 1000, {e.BTN_TOUCH, e.BTN_TOOL_FINGER})
        self.assertTrue(self.cuadros[-1].resinc)


@unittest.skipIf(e is None, "requiere python3-evdev")
class Teclas(unittest.TestCase):
    def test_traduccion_a_hid(self):
        self.assertEqual(entrada.evento_tecla(e.KEY_A, 1).uso, 0x04)
        self.assertEqual(entrada.evento_tecla(e.KEY_LEFTCTRL, 1).uso, 0xE0)
        ev = entrada.evento_tecla(e.KEY_VOLUMEUP, 1)
        self.assertTrue(ev.consumo and ev.uso == 0xE9)
        self.assertIsNone(entrada.evento_tecla(e.KEY_PROG1, 1).uso)


class DispositivoSimulado:
    def __init__(self, nombre):
        self.name, self.keys, self.tomado, self.pendientes = nombre, set(), False, []

    def grab(self):
        self.tomado = True

    def ungrab(self):
        self.tomado = False

    def active_keys(self):
        return list(self.keys)

    def read(self):
        if not self.pendientes:
            raise BlockingIOError
        evs, self.pendientes = self.pendientes, []
        return iter(evs)


@unittest.skipIf(e is None, "requiere python3-evdev")
class CapturaEnReposo(unittest.TestCase):
    def setUp(self):
        self.teclado, self.dev_tp = DispositivoSimulado("teclado"), TouchpadSimulado()
        self.dev_tp.name = "touchpad"
        self.dev_tp.grab = self.dev_tp.ungrab = lambda: None
        self.dev_tp.read = lambda: iter(())
        c = entrada.Captura.__new__(entrada.Captura)
        c.devs, c.lectores = [self.teclado, self.dev_tp], []
        c.teclado_local = types.SimpleNamespace(fuentes=lambda: {1: None})
        self.tp = entrada.Touchpad(self.dev_tp, lambda cuadro: None)
        c.touchpads, c.pausada, c._t_retomar = [self.tp], False, None
        self.c = c

    def test_pausada_suelta_y_no_lee(self):
        self.teclado.tomado = True
        self.c.pausar()
        self.assertFalse(self.teclado.tomado)
        self.assertEqual(self.c.fuentes(), {})

    def test_retoma_solo_sin_teclas_presionadas_y_descarta_lo_de_la_pausa(self):
        self.c.pausar()
        self.teclado.pendientes = [Ev(e.EV_KEY, e.KEY_A, 1), Ev(e.EV_KEY, e.KEY_A, 0)]
        self.teclado.keys = {e.KEY_A}
        self.assertFalse(self.c.retomar())
        self.assertFalse(self.teclado.tomado)
        self.teclado.keys = set()
        self.dev_tp.keys = {e.BTN_TOOL_FINGER}           # dedo flotando: no impide retomar
        self.assertTrue(self.c.retomar())
        self.assertTrue(self.teclado.tomado)
        self.assertEqual(self.teclado.pendientes, [])    # lo de la pausa ya lo atendió el sistema
        self.assertTrue(self.tp.resinc)
        self.assertNotEqual(self.c.fuentes(), {})

    def test_una_tecla_trabada_no_impide_retomar_para_siempre(self):
        self.c.pausar()
        self.teclado.keys = {e.KEY_A}
        self.assertFalse(self.c.retomar())
        self.c._t_retomar -= entrada.Captura.ESPERA_TECLAS
        self.assertTrue(self.c.retomar())


class Radio(unittest.TestCase):
    def test_politica_por_dispositivo_y_qos(self):
        from bordebt.caracteristicas.hid_bluetooth.linux import radio
        cmds = []
        salida = ("hci0:\tType: Primary\n\tLink policy: RSWITCH HOLD SNIFF \n"
                  "\t< ACL AA:BB:CC:DD:EE:02 handle 256 state 1 lm PERIPHERAL AUTH ENCRYPT \n")
        original = radio.subprocess.run
        radio.subprocess.run = lambda c, **k: (cmds.append(" ".join(c)),
                                               types.SimpleNamespace(stdout=salida, returncode=0))[1]
        try:
            r = radio.Radio("hci0", ["AA:BB:CC:DD:EE:01", "AA:BB:CC:DD:EE:02"])
            r.preparar()
            cmds.clear()
            r.aplicar("AA:BB:CC:DD:EE:02")
            time.sleep(0.2)
        finally:
            radio.subprocess.run = original
        self.assertIn("hcitool -i hci0 lp AA:BB:CC:DD:EE:01 RSWITCH,HOLD,SNIFF", cmds)
        self.assertIn("hcitool -i hci0 lp AA:BB:CC:DD:EE:02 RSWITCH,HOLD", cmds)
        self.assertTrue(any(c.startswith("hcitool -i hci0 cmd 0x02 0x0007 00 01") for c in cmds))


if __name__ == "__main__":
    unittest.main()
