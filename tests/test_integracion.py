"""El comando `run` completo con adaptadores de plataforma simulados (sin root ni hardware)."""
import io
import types
import unittest
from contextlib import redirect_stdout

import tests  # noqa: F401
from tests.dobles import EnlaceFalso, PunteroFalso, TecladoFalso, cfg
from bordebt import plataforma
from bordebt.caracteristicas.conmutacion import comandos
from bordebt.caracteristicas.entrada.eventos import EventoTecla


class GestorFalso:
    def __init__(self, enlaces, seguro=True, reintento=20, desconocido=None, reintento_max=300, intentos=6):
        self.enlaces, self.al_cambiar, self.reconexiones, self.cerrado = enlaces, None, [], False

    def pausar(self):
        pass

    def reanudar(self):
        pass

    def fds(self):
        return {}

    def reconectar(self, mac, forzar=False):
        self.reconexiones.append(mac)

    def tick(self, ahora):
        pass

    def cerrar(self):
        self.cerrado = True


class MonitorFalso:
    durmiendo, despertares = False, 0

    def __init__(self, bus=None):
        pass

    def pantalla_encendida(self, ahora):
        return True

    def fds(self):
        return {}


class Plataforma:
    """Módulos de plataforma falsos para hid_bluetooth, entrada y conmutacion."""

    def __init__(self):
        self.capturas = []
        p = self

        class Captura:
            def __init__(self, acciones, al_teclear, c):
                self.al_teclear, self.vueltas, self.liberada = al_teclear, 0, False
                self.teclado_local, self.interpretes = TecladoFalso(), []
                p.capturas.append(self)

            def fuentes(self):
                self.vueltas += 1
                if self.vueltas == 3:      # Ctrl+Alt+Esc: salir
                    for uso in (0xE0, 0xE2, 0x29):
                        self.al_teclear(EventoTecla(uso, 1, nativo=uso))
                return {}

            def capturar(self):
                pass

            def liberar(self):
                self.liberada = True

            def pausar(self):
                pass

            def retomar(self):
                return True

        class Radio:
            def __init__(self, hci, macs):
                self.qos, self.restaurada = True, False

            def preparar(self):
                pass

            def aplicar(self, mac):
                pass

            def restaurar(self):
                self.restaurada = True

        bluez = types.SimpleNamespace(encender=lambda: None, registrar_perfil=lambda: None, id_adaptador="hci0")
        self.modulos = {
            "hid_bluetooth": types.SimpleNamespace(BlueZ=lambda: bluez, Enlace=EnlaceFalso, GestorBT=GestorFalso,
                                                   Radio=Radio),
            "entrada": types.SimpleNamespace(Captura=Captura),
            "energia": types.SimpleNamespace(MonitorEnergia=MonitorFalso),
            "conmutacion": types.SimpleNamespace(tamano_pantalla=lambda fija=None: (1000, 500),
                                                 PunteroUinput=PunteroFalso),
        }


class Run(unittest.TestCase):
    def test_run_arma_todo_y_sale_con_el_atajo(self):
        p = Plataforma()
        originales = plataforma.adaptador, plataforma.requiere_privilegios
        plataforma.adaptador = lambda nombre: p.modulos[nombre]
        plataforma.requiere_privilegios = lambda: None
        c = cfg()
        c["devices"] = [{"name": "tablet", "mac": "AA:AA:AA:AA:AA:01", "side": "left", "of": "laptop",
                         "width": 2500, "height": 1600}]
        salida = io.StringIO()
        try:
            with redirect_stdout(salida):
                comandos.cmd_run(types.SimpleNamespace(), c)
        finally:
            plataforma.adaptador, plataforma.requiere_privilegios = originales
        texto = salida.getvalue()
        self.assertIn("'tablet' a la izquierda de 'laptop'", texto)
        self.assertIn("Fin.", texto)
        self.assertTrue(p.capturas[0].liberada)


if __name__ == "__main__":
    unittest.main()
