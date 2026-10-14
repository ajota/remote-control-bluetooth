"""Comandos `calibrate` y `test`. La terminal (esperar el Enter) la pone el adaptador de la plataforma."""
import select
import sys
import time

from bordebt import plataforma
from bordebt.comun.config import COMANDO, guardar
from bordebt.comun.diagnostico import STATS
from bordebt.caracteristicas.calibracion import medidas as calc
from bordebt.caracteristicas.hid_bluetooth import servicio

REACCION = 0.25    # s típicos entre ver el borde y presionar Enter
# (unidades por reporte, reportes por ráfaga, pausa entre ráfagas). Lenta: 300 u/s en reportes espaciados
# que el Bluetooth no agrupa. Rápida: ráfagas cortas que el dispositivo ve como movimiento veloz. Muy lenta:
# 120 u/s en pasos pequeños, como un movimiento suave del dedo.
LENTA, RAPIDA, MUY_LENTA = (15, 1, 0.05), (20, 4, 0.15), (2, 1, 1 / 60.0)


def registrar(sub):
    s = sub.add_parser("calibrate", help="medir la pantalla de un dispositivo")
    s.add_argument("nombre")
    s.add_argument("--resolucion", "--resolution", dest="resolucion", metavar="ANCHOxALTO",
                   help="resolución o proporción de la pantalla en la orientación de uso (p.ej. 2000x1200 "
                        "o 16:10); evita la pasada vertical")
    s.set_defaults(func=cmd_calibrar)
    s = sub.add_parser("test", help="mover el puntero del dispositivo solo, para diagnosticar")
    s.add_argument("nombre")
    s.set_defaults(func=cmd_test)


class Sesion:
    """Mueve el puntero del dispositivo de forma controlada y atiende el Enter del usuario."""

    def __init__(self, enlace, gestor):
        self.en, self.gestor = enlace, gestor
        self.terminal = plataforma.adaptador("calibracion")

    def esperar(self, segundos, con_enter=True):
        """Atiende el Bluetooth durante `segundos`. True si se presionó Enter (cuando se escucha)."""
        fin_t = time.monotonic() + segundos
        while True:
            resto = fin_t - time.monotonic()
            mapa = self.gestor.fds()
            entrada = self.terminal.descriptor_entrada()
            fds = list(mapa) + ([entrada] if con_enter else [])
            listos, _, _ = select.select(fds, [], [], max(0.0, resto))
            if entrada in listos:
                if not sys.stdin.readline():
                    sys.exit("Entrada cerrada; repite la calibración.")
                return True
            for fd in listos:
                mapa[fd]()
            if not self.en.conectado:
                sys.exit("Se perdió la conexión.")
            if resto <= 0:
                return False

    def recorrer(self, dx, dy, perfil, total=None):
        """Avanza según `perfil` hasta `total` unidades o hasta que se presione Enter."""
        por_reporte, rafaga, pausa = perfil
        if total is None:
            self.terminal.descartar_entrada()
        enviado, t0 = 0, time.monotonic()
        while total is None or enviado < total:
            for _ in range(rafaga):
                self.en.raton(0, por_reporte * dx, por_reporte * dy)
                enviado += por_reporte
            if self.esperar(pausa, total is None):
                velocidad = enviado / max(time.monotonic() - t0, 0.01)
                return max(0, round(enviado - velocidad * REACCION))
            if enviado > 40000:
                sys.exit("No se presionó Enter; repite la calibración.")
        return enviado

    def a_la_esquina(self, separar_x, separar_y):
        for _ in range(3):
            self.en.raton(0, -32767, -32767)
        self.esperar(0.3, False)
        # separarse un poco del borde por el que no se mide (evita esquinas activas del sistema)
        self.recorrer(separar_x, separar_y, LENTA, 60)


def cmd_calibrar(a, cfg):
    """Mide la pantalla del dispositivo moviendo su puntero solo; tú solo presionas Enter cuando toca el
    borde. Pasadas: lenta (tamaño), muy lenta (si frena lo suave) y rápida (cuánto acelera)."""
    plataforma.requiere_privilegios()
    prop = None
    if a.resolucion:
        try:
            prop = calc.proporcion(a.resolucion)
        except ValueError as ex:
            sys.exit(str(ex))
    d, en, gestor = servicio.conectar_uno(cfg, a.nombre)
    en.agrupar = False     # aquí el ritmo exacto de los reportes es parte de la medición
    s = Sesion(en, gestor)

    print("\nEl puntero de '%s' se moverá SOLO. No toques el trackpad." % a.nombre)
    print("Presiona Enter en la terminal en el instante en que el puntero toque el borde indicado.")
    if prop:
        print("Proporción conocida (alto/ancho = %.3f): el alto se calcula, sin pasada vertical." % prop)
    print("Son %d pasadas por ronda y 2 rondas." % (3 if prop else 4))

    def ronda(n, total):
        s.a_la_esquina(0, 1)
        print("\nRonda %d/%d — 1) avanza LENTO hacia la DERECHA. Enter al tocar el borde derecho." % (n, total))
        w = s.recorrer(1, 0, LENTA)
        if prop:
            h = round(w * prop)
        else:
            s.a_la_esquina(1, 0)
            print("Ronda %d/%d — 2) avanza LENTO hacia ABAJO. Enter al tocar el borde inferior." % (n, total))
            h = s.recorrer(0, 1, LENTA)
        paso = 2 if prop else 3
        s.a_la_esquina(0, 1)
        print("Ronda %d/%d — %d) avanza MUY LENTO hacia la DERECHA. Enter al tocar el borde derecho."
              % (n, total, paso))
        wl = s.recorrer(1, 0, MUY_LENTA)
        s.a_la_esquina(0, 1)
        print("Ronda %d/%d — %d) avanza a SALTOS RÁPIDOS hacia la DERECHA. Enter al tocar el borde derecho."
              % (n, total, paso + 1))
        wr = s.recorrer(1, 0, RAPIDA)
        m = (w, h, w / max(wr, 1), w / max(wl, 1))
        print("  medido: %d x %d, aceleración %.2f, respuesta lenta %.2f" % m)
        return m

    rondas = []
    try:
        rondas += [ronda(1, 2), ronda(2, 2)]
        if not calc.parecidas(*rondas):
            print("\nLas dos rondas no coinciden; hago una tercera para desempatar.")
            rondas.append(ronda(3, 3))
    finally:
        gestor.cerrar()
    w, h, acel, g_lento, acuerdo = calc.combinar(rondas)
    if not acuerdo:
        print("\nAVISO: las rondas no coinciden bien; guardo la mediana. Si los saltos fallan, repite la calibración.")
    if w < calc.MINIMO or h < calc.MINIMO:
        sys.exit("Medida demasiado pequeña (%dx%d): parece que presionaste Enter antes de tiempo. Repite."
                 % (w, h))
    d["width"], d["height"], d["accel"], d["slow_gain"] = w, h, acel, g_lento
    print("Pantalla de '%s': %d x %d unidades, aceleración %.2f, respuesta lenta %.2f"
          % (a.nombre, w, h, acel, g_lento))
    if g_lento < 0.85:
        print("  '%s' frena los movimientos lentos (responde al %d%%); el script lo compensará."
              % (a.nombre, g_lento * 100))
    if acel < 1.3:
        print("  '%s' casi no acelera los movimientos rápidos; el script lo compensará." % a.nombre)
    guardar(a.config, cfg)


def cmd_test(a, cfg):
    """Mueve el puntero remoto solo, sin trackpad, para separar fallas de Bluetooth de fallas de entrada."""
    plataforma.requiere_privilegios()
    _, en, gestor = servicio.conectar_uno(cfg, a.nombre)
    en.agrupar = False
    servicio.atender(gestor, 1.0)
    print("Protocolo pedido por el host: %s" % ("boot" if en.boot else "report"))
    try:
        print("\n1) Movimiento grande: el puntero debe ir a la esquina superior izquierda y luego al centro.")
        en.raton(0, -32767, -32767)
        servicio.atender(gestor, 0.5)
        en.raton(0, 400, 300)
        servicio.atender(gestor, 2.0)
        print("2) Movimientos pequeños: el puntero debe dibujar un cuadrado lentamente (3 vueltas).")
        for _ in range(3):
            for dx, dy in ((4, 0), (0, 4), (-4, 0), (0, -4)):
                for _ in range(50):
                    en.raton(0, dx, dy)
                    servicio.atender(gestor, 0.01)
        print("\nEnviados %d reportes, %d con timeout." % (STATS["enviados"], STATS["timeouts"]))
        print("Si el puntero se movió en ambas pruebas, el Bluetooth funciona: el problema está en el trackpad")
        print("(prueba: %s --debug calibrate %s)." % (COMANDO, a.nombre))
        print("Si solo funcionó la prueba 1, o ninguna, cuéntame el modelo de la tablet y esta salida.")
    finally:
        gestor.cerrar()
