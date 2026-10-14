"""Destinos del teclado y el puntero: la laptop y cada dispositivo Bluetooth."""
import math
import time

from bordebt.caracteristicas.conmutacion.pantalla import Pantalla
from bordebt.caracteristicas.entrada.eventos import bit_modificador, es_modificador
from bordebt.caracteristicas.hid_bluetooth.protocolo import BOTONES


class DestinoLocal:
    """La laptop. Su puntero se controla en coordenadas absolutas (puerto PunteroLocal), así el modelo
    siempre coincide con la realidad y se sabe exactamente cuándo se toca un borde."""

    pendiente = False

    def __init__(self, puntero, w, h, margen):
        self.puntero, self.p, self.margen = puntero, Pantalla(w, h), margen
        self.botones = set()
        self._colocar()

    def _colocar(self):
        self.puntero.mover_a(self.p.x / self.p.w, self.p.y / self.p.h)

    def mover(self, dx, dy, lados):
        salida = self.p.mover(dx, dy, lados, self.margen)
        self._colocar()
        return salida

    def entrar(self, lado, f):
        self.p.entrar(lado, f)
        self._colocar()

    def ocultar(self):
        self.puntero.esconder()        # la posición se conserva en el modelo para restaurarla

    def mostrar(self):
        self._colocar()

    def scroll(self, v, h):
        self.puntero.scroll(v, h)

    def boton(self, b, valor):
        self.puntero.boton(b, valor)
        (self.botones.add if valor else self.botones.discard)(b)

    def soltar(self):
        for b in list(self.botones):
            self.boton(b, 0)

    def tick(self, ahora):
        pass  # la laptop no tiene tareas periódicas


class DestinoRemoto:
    """Tablet/celular por Bluetooth. Como un mouse es relativo y el dispositivo nunca dice dónde está su
    puntero, se lleva un modelo calibrado de su pantalla y de cómo responde a la velocidad."""

    V_MUY_LENTA, V_LENTA = 120.0, 300.0   # velocidades (unidades/s) de las pasadas de calibración
    TOPE_CAUTELA = 0.025                  # la prudencia nunca separa el modelo más que esto de la pantalla
    pendiente = False

    def __init__(self, d, enlace, cfg):
        self.nombre, self.lado, self.enlace = d["name"], d["side"], enlace
        self.p = Pantalla(d.get("width", 2000), d.get("height", 1200))
        self.nom = Pantalla(self.p.w, self.p.h)   # mismo cálculo sin prudencia (referencia)
        self.gain, self.k_scroll = d.get("gain", 1.0), d.get("scroll", 1.0)
        self.margen = cfg["remote_margin"]
        # Respuesta del dispositivo según la velocidad (medida al calibrar): `g_lento` a velocidad muy lenta,
        # 1 entre las pasadas lentas, e interpolación hasta `accel` entre `acc_lo` y `acc_hi` unidades/s.
        self.accel = d.get("accel", 3.0)
        self.acc_lo, self.acc_hi = d.get("accel_low", 500.0), d.get("accel_high", 3000.0)
        self.g_lento = d.get("slow_gain", 1.0)
        self.v_host, self.t_mov = 0.0, 0.0
        self.ocultar = cfg.get("hide_remote_pointer", True)
        self.aparcado = False   # puntero real en la esquina inferior derecha
        self.aparcar_en = []    # momentos en que hay que esconder el puntero (tras conectar)
        self.consumo_activo = False
        self.espera = cfg.get("remote_dwell", 0.05)    # empuje continuo exigido en el borde para saltar
        self.cautela = cfg.get("remote_caution", 0.15)  # subestimar avance hacia la salida (salto tardío)
        self.botones = self.mods = 0
        self.teclas = []
        self.ax = self.ay = self.av = self.ah = 0.0

    # ---- modelo de respuesta del dispositivo
    def curva_host(self, v):
        """Respuesta del dispositivo según la velocidad recibida, relativa a la pasada lenta (= 1)."""
        if v <= self.V_MUY_LENTA:
            return self.g_lento
        if v <= self.V_LENTA:
            return self.g_lento + (1.0 - self.g_lento) * (v - self.V_MUY_LENTA) / (self.V_LENTA - self.V_MUY_LENTA)
        if v <= self.acc_lo:
            return 1.0
        t = min(1.0, (v - self.acc_lo) / (self.acc_hi - self.acc_lo))
        return 1.0 + t * (self.accel - 1.0)

    def _factor_host(self, ux, uy):
        """Cuánto amplificará el dispositivo este movimiento según la velocidad a la que lo enviamos."""
        ahora = time.monotonic()
        dt = ahora - self.t_mov
        self.t_mov = ahora
        v = math.hypot(ux, uy) / max(dt, 0.005)
        self.v_host = v if dt > 0.1 else 0.6 * self.v_host + 0.4 * v
        return self.curva_host(self.v_host)

    def _cautela(self, d, menos, mas, lados):
        """Factor prudente por eje: <1 si el movimiento va hacia un borde de salida, >1 si se aleja."""
        hacia, desde = (mas, menos) if d > 0 else (menos, mas)
        if hacia in lados and desde not in lados:
            return 1.0 - self.cautela
        if desde in lados and hacia not in lados:
            return 1.0 + self.cautela
        return 1.0

    # ---- movimiento
    def _enviar_mov(self, dx, dy):
        self.ax += dx
        self.ay += dy
        ix, iy = int(self.ax), int(self.ay)
        self.ax -= ix
        self.ay -= iy
        if ix or iy:
            self.enlace.raton(self.botones, ix, iy)

    def mover(self, dx, dy, lados):
        ux, uy = dx * self.gain, dy * self.gain
        k = self._factor_host(ux, uy)
        mx = ux * k * self._cautela(ux, "left", "right", lados)
        my = uy * k * self._cautela(uy, "top", "bottom", lados)
        self.nom.mover(ux * k, uy * k, (), 0)
        salida = self.p.mover(mx, my, lados, self.margen, self.espera)
        # La prudencia se acumularía con cada movimiento (tras navegar un rato habría que empujar mucho para
        # volver): se limita a TOPE_CAUTELA de la pantalla respecto al cálculo sin prudencia.
        for eje, tam in (("x", self.p.w), ("y", self.p.h)):
            tope = self.TOPE_CAUTELA * tam
            ref = getattr(self.nom, eje)
            setattr(self.p, eje, min(max(getattr(self.p, eje), ref - tope), ref + tope))
        self._enviar_mov(ux, uy)   # sin recortar ni acelerar: eso lo hace el dispositivo
        return salida

    def _grande(self):
        return int(3 * max(self.p.w, self.p.h)) + 1000

    def entrar(self, lado, f):
        """Coloca el puntero real en UN solo reporte, sin recorrido visible: golpe contra el borde de entrada
        y, si sabemos dónde estaba (aparcado en la esquina inferior derecha), salto a la misma altura relativa
        por la que entramos. Un reporte aislado tras una pausa el dispositivo lo mueve sin aceleración, así
        que se divide por su respuesta a velocidad casi nula (calibrada)."""
        horizontal = lado in ("left", "right")
        g = self._grande()
        sx = {"left": -g, "right": g}.get(lado, 0)
        sy = {"top": -g, "bottom": g}.get(lado, 0)
        antes = self.p.y if horizontal else self.p.x
        self.p.entrar(lado, f)
        if self.aparcado:
            k = max(self.curva_host(0.0), 0.2)
            if horizontal:
                sy = round((self.p.y - self.p.h) / k)
            else:
                sx = round((self.p.x - self.p.w) / k)
        elif horizontal:      # no sabemos su altura: el puntero se queda donde está
            self.p.y = antes
        else:
            self.p.x = antes
        self.enlace.vaciar(forzar=True)
        self.enlace.raton_inmediato(self.botones, sx, sy)
        self.aparcado = False
        self.ax = self.ay = 0.0
        self.nom.x, self.nom.y = self.p.x, self.p.y

    def ocultar_puntero(self):
        """Al irnos, su puntero va a la esquina inferior derecha: la flecha se dibuja hacia abajo a la
        derecha de su punta, así que solo asoma la punta. Al volver sabemos dónde está."""
        if self.ocultar and self.enlace.conectado:
            g = self._grande()
            self.enlace.descartar_pendiente()        # el movimiento pendiente ya no importa: nos vamos
            self.enlace.raton_inmediato(self.botones, g, g)
            self.aparcado = True

    def tick(self, ahora):
        pass  # sin tareas periódicas: el movimiento pendiente lo envía el motor

    # ---- botones, scroll y teclas
    def scroll(self, v, h):
        self.av += v * self.k_scroll
        self.ah += h * self.k_scroll
        iv, ih = int(self.av), int(self.ah)
        self.av -= iv
        self.ah -= ih
        if iv or ih:
            self.enlace.raton(self.botones, 0, 0, iv, ih)

    def boton(self, b, valor):
        self.botones = (self.botones | BOTONES[b]) if valor else (self.botones & ~BOTONES[b])
        self.enlace.raton(self.botones)

    def tecla(self, ev):
        """Tecla capturada (EventoTecla con uso HID)."""
        if ev.valor not in (0, 1) or ev.uso is None:
            return
        if ev.consumo:
            self.enlace.consumo(ev.uso if ev.valor else 0)
            self.consumo_activo = bool(ev.valor)
            return
        if es_modificador(ev.uso):
            b = bit_modificador(ev.uso)
            self.mods = (self.mods | b) if ev.valor else (self.mods & ~b)
        elif ev.valor and ev.uso not in self.teclas:
            self.teclas.append(ev.uso)
        elif not ev.valor and ev.uso in self.teclas:
            self.teclas.remove(ev.uso)
        else:
            return
        self.enlace.teclado(self.mods, self.teclas)

    def soltar(self):
        """Suelta lo que esté presionado. Solo envía lo necesario: cada reporte de más retrasa los
        siguientes (por ejemplo, el que esconde el puntero al salir)."""
        if self.enlace.conectado:
            if self.mods or self.teclas:
                self.enlace.teclado(0, [])
            if self.botones:
                self.enlace.vaciar(forzar=True)
                self.enlace.raton(0)
            if self.consumo_activo:
                self.enlace.consumo(0)
        self.mods, self.teclas, self.botones, self.consumo_activo = 0, [], 0, False
