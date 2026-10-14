"""Dobles de prueba de los puertos: permiten probar el núcleo sin hardware ni sistema operativo."""
import struct
import time

from bordebt.caracteristicas.hid_bluetooth.enlace import Enlace

CFG = None


def cfg():
    from bordebt.comun.config import DEFAULTS
    import copy
    return copy.deepcopy(DEFAULTS)


class EnlaceFalso(Enlace):
    """Enlace que guarda los reportes en vez de enviarlos."""

    def __init__(self, mac="AA:AA:AA:AA:AA:01", conectado=True):
        super().__init__(mac)
        self.on = conectado
        self.enviados = []

    @property
    def conectado(self):
        return self.on

    def _transmitir(self, datos):
        self.enviados.append(datos[1:])     # sin la cabecera HIDP 0xA1
        return True

    def ratones(self):
        return [struct.unpack("<BBhhbb", r) for r in self.enviados if r[0] == 2]

    def teclados(self):
        return [r for r in self.enviados if r[0] == 1]

    def consumos(self):
        return [struct.unpack("<BH", r)[1] for r in self.enviados if r[0] == 3]


class PunteroFalso:
    def __init__(self):
        self.pos = None
        self.escondido = False
        self.botones, self.scrolls = [], []
        self.despertares = 0

    def mover_a(self, fx, fy):
        self.pos, self.escondido = (fx, fy), False

    def esconder(self):
        self.escondido = True

    def despertar(self):
        self.despertares += 1

    def boton(self, b, valor):
        self.botones.append((b, valor))

    def scroll(self, v, h):
        self.scrolls.append((v, h))

    def cerrar(self):
        pass


class TecladoFalso:
    def __init__(self):
        self.reenviadas, self.presionadas, self.gestos = [], [], []
        self.soltado = 0

    def reenviar(self, ev):
        self.reenviadas.append((ev.uso, ev.valor))

    def soltar_todo(self):
        self.soltado += 1

    def presionar(self, uso, valor):
        self.presionadas.append((uso, valor))

    def gesto(self, direccion):
        self.gestos.append(direccion)


class ConexionesFalsas:
    def __init__(self):
        self.pedidas = []
        self.pausas = self.reanudaciones = 0

    def reconectar(self, mac, forzar=False):
        self.pedidas.append(mac)

    def pausar(self):
        self.pausas += 1

    def reanudar(self):
        self.reanudaciones += 1


class RadioFalsa:
    def __init__(self):
        self.activos = []

    def aplicar(self, mac):
        self.activos.append(mac)


class AccionesFalsas:
    """Registra lo que pide el intérprete de gestos."""
    ultimo_tecleo = 0.0

    def __init__(self):
        self.mov = [0.0, 0.0]
        self.eventos = []

    def px_por_mm(self, v):
        return 10.0

    def movimiento(self, dx, dy):
        self.mov[0] += dx
        self.mov[1] += dy

    def scroll(self, v, h):
        self.eventos.append(("scroll", v, h))

    def boton(self, b, v):
        self.eventos.append((b, v))

    def clic(self, b):
        self.eventos.append(("clic", b))

    def pellizco(self, n):
        self.eventos.append(("zoom", n))

    def pellizco_fin(self):
        self.eventos.append(("zoom_fin",))

    def gesto(self, d):
        self.eventos.append(("gesto", d))


def esperar(segundos, tick=None):
    fin = time.monotonic() + segundos
    while time.monotonic() < fin:
        if tick:
            tick(time.monotonic())
        time.sleep(0.005)
