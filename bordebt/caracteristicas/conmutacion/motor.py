"""Motor: enruta teclado y puntero al destino activo y decide los saltos entre pantallas."""
import time

from bordebt.comun.diagnostico import STATS
from bordebt.comun.disposicion import OPUESTO
from bordebt.comun.config import DEFAULTS
from bordebt.caracteristicas.entrada.eventos import (EventoTecla, MOD_ALT, MOD_CTRL, USO_CTRL_IZQ, USO_ESC,
                                                     USO_F12, bit_modificador, es_modificador)
from bordebt.caracteristicas.gestos.interprete import px_por_mm
from bordebt.caracteristicas.hid_bluetooth.protocolo import ATRAS, INICIO


class Motor:
    """Implementa las 'acciones' que pide el intérprete de gestos y recibe las teclas capturadas."""

    GESTOS_REMOTOS = {"arriba": INICIO, "izquierda": ATRAS, "derecha": ATRAS}

    def __init__(self, vecinos, local, remotos, conexiones, teclado_local=None, radio=None):
        self.vec, self.conexiones = vecinos, conexiones
        self.teclado_local, self.radio = teclado_local, radio
        self.pant = dict(remotos, laptop=local)
        self.orden = ["laptop"] + list(remotos)
        self.activo = "laptop"
        self.ultimo_tecleo = 0.0
        self.ultima_actividad = 0.0     # último uso del teclado/trackpad/mouse (para el reposo)
        self.mods = 0
        self.tragadas = set()
        self.salir = False
        self.entradas = []      # intérpretes del trackpad (para tick y esperas)
        self.avisado = {}
        self.speed, self.remote_speed, self.remote_accel = 1.0, DEFAULTS["remote_speed"], DEFAULTS["remote_accel"]
        self.zoom = False

    @property
    def t(self):
        return self.pant[self.activo]

    # ---- ganancia del trackpad
    def px_por_mm(self, v):
        """Con curva de aceleración en la laptop; hacia un dispositivo, la respuesta objetivo (igual en
        todos): 1:1 hasta 500 unidades/s y hasta `remote_accel` veces en movimientos rápidos. Lo que el
        dispositivo no haga (según su calibración) se completa aquí; nunca se frena."""
        if self.activo == "laptop":
            return px_por_mm(v) * self.speed
        r = self.t
        v_env = v * self.remote_speed * r.gain        # unidades/s que enviaríamos sin compensar
        lo, hi = r.acc_lo, r.acc_hi
        objetivo = 1.0 if v_env <= lo else 1.0 + min(1.0, (v_env - lo) / (hi - lo)) * (self.remote_accel - 1.0)
        extra = 1.0
        for _ in range(3):   # al compensar cambia la velocidad que ve el dispositivo: se itera
            extra = min(4.0, max(1.0, objetivo / max(r.curva_host(v_env * extra), 0.1)))
        return self.remote_speed * extra

    # ---- acciones del intérprete de gestos
    def _disponible(self, nombre):
        if nombre == "laptop" or self.pant[nombre].enlace.conectado:
            return True
        self.conexiones.reconectar(self.pant[nombre].enlace.mac, forzar=True)
        ahora = time.monotonic()
        if ahora - self.avisado.get(nombre, -1e9) > 5:
            self.avisado[nombre] = ahora
            print("'%s' no está conectado; intentando reconectar..." % nombre)
        return False

    def movimiento(self, dx, dy):
        self.ultima_actividad = time.monotonic()
        STATS["mx"] += dx
        STATS["my"] += dy
        vec = self.vec[self.activo]
        salida = self.t.mover(dx, dy, vec.keys())
        if salida and self._disponible(vec[salida]):
            self.cambiar(vec[salida], OPUESTO[salida], self.t.p.fraccion(salida))

    def scroll(self, v, h):
        self.ultima_actividad = time.monotonic()
        self.t.scroll(v, h)

    def boton(self, b, valor):
        self.ultima_actividad = time.monotonic()
        self.t.boton(b, valor)

    def clic(self, b):
        self.t.boton(b, 1)
        self.t.boton(b, 0)

    def _ctrl(self, valor):
        if self.activo != "laptop":
            self.t.tecla(EventoTecla(USO_CTRL_IZQ, valor))
        elif self.teclado_local:
            self.teclado_local.presionar(USO_CTRL_IZQ, valor)

    def pellizco(self, pasos):
        """Zoom: Ctrl + rueda (pasos > 0 = acercar). Ctrl queda presionado hasta pellizco_fin()."""
        if not self.zoom:
            self.zoom = True
            self._ctrl(1)
        self.t.scroll(pasos, 0)

    def pellizco_fin(self):
        if self.zoom:
            self.zoom = False
            self._ctrl(0)

    def gesto(self, direccion):
        """Deslizar con tres dedos: Inicio/Atrás en los dispositivos; atajo del escritorio en la laptop."""
        if self.activo != "laptop":
            uso = self.GESTOS_REMOTOS.get(direccion)
            if uso:
                self.t.enlace.consumo(uso)
                self.t.enlace.consumo(0)
        elif self.teclado_local:
            self.teclado_local.gesto(direccion)

    # ---- teclas
    def tecla(self, ev):
        self.ultima_actividad = time.monotonic()
        u, v = ev.uso, ev.valor
        if es_modificador(u):
            b = bit_modificador(u)
            self.mods = (self.mods | b) if v else (self.mods & ~b)
        elif v == 1:
            self.ultimo_tecleo = time.monotonic()
        clave = ev.nativo if ev.nativo is not None else u
        if clave in self.tragadas:
            if v == 0:
                self.tragadas.discard(clave)
            return
        if v == 1 and not ev.consumo and self.mods & MOD_CTRL and self.mods & MOD_ALT and u in (USO_F12, USO_ESC):
            self.tragadas.add(clave)
            if u == USO_F12:
                self.ciclar()
            else:
                self.salir = True
            return
        if self.activo == "laptop":
            if self.teclado_local:
                self.teclado_local.reenviar(ev)
        elif v in (0, 1):
            self.t.tecla(ev)

    def soltar_teclas_locales(self):
        if self.teclado_local:
            self.teclado_local.soltar_todo()

    # ---- cambios de pantalla
    def cambiar(self, destino, lado_entrada, f, mostrar=True):
        """Pasa el control a `destino`. Con `mostrar=False` (al pausar) el puntero de la laptop no se mueve."""
        self.pellizco_fin()
        if self.activo != "laptop" and not self.t.botones:
            self.t.ocultar_puntero()        # lo más visible primero: esconder el puntero al instante
            self.t.soltar()
        else:
            self.t.soltar()                 # con un botón presionado, soltarlo antes de mover (no arrastrar)
            if self.activo != "laptop":
                self.t.ocultar_puntero()
        if self.activo == "laptop":
            self.soltar_teclas_locales()
            self.t.ocultar()
        self.activo = destino
        if destino != "laptop":
            self.t.aparcar_en = []          # ya lo usamos: cancelar el escondido pendiente tras conectar
        if self.radio:
            self.radio.aplicar(None if destino == "laptop" else self.t.enlace.mac)
        if lado_entrada:
            self.t.entrar(lado_entrada, f)
        elif destino == "laptop" and mostrar:
            self.t.mostrar()            # vuelve donde estaba (atajo o desconexión)
        print(("<<< Control en la LAPTOP" if destino == "laptop" else ">>> Control en '%s'" % destino))

    def ciclar(self):
        i = self.orden.index(self.activo)
        for n in self.orden[i + 1:] + self.orden[:i]:
            if n == "laptop" or self.pant[n].enlace.conectado:
                lado = None if n == "laptop" else OPUESTO[self.pant[n].lado]
                return self.cambiar(n, lado, 0.5)

    def enlace_cambio(self, enlace, conectado):
        nombre = next((n for n in self.orden[1:] if self.pant[n].enlace is enlace), enlace.mac)
        print("%s '%s'" % ("Conectado:" if conectado else "Desconectado:", nombre))
        if nombre in self.pant:
            r = self.pant[nombre]
            r.aparcado = False                    # tras (re)conectar no sabemos dónde quedó su puntero...
            # ...así que lo escondemos, pero no al instante: recién conectado, el dispositivo aún está creando
            # su mouse e ignoraría el movimiento, dejando el puntero visible en el centro. Se hace a los 0.5 s
            # y se repite cada 0.5 s hasta los 2 s (se cancela si antes entramos a ese dispositivo).
            ahora = time.monotonic()
            r.aparcar_en = [ahora + 0.5 * i for i in range(1, 5)] if conectado else []
        if conectado and self.radio:              # una conexión nueva hereda la política por defecto
            self.radio.aplicar(None if self.activo == "laptop" else self.t.enlace.mac)
        if not conectado and self.activo == nombre:
            self.cambiar("laptop", None, 0)

    # ---- bucle
    def tick(self, ahora):
        for x in self.entradas:
            x.tick(ahora)
        self.t.tick(ahora)
        for nombre, r in self.pant.items():      # esconder punteros de dispositivos recién conectados
            if nombre != "laptop" and r.aparcar_en and ahora >= r.aparcar_en[0]:
                r.aparcar_en.pop(0)
                if nombre != self.activo and r.enlace.conectado:
                    r.ocultar_puntero()
        if self.activo != "laptop":
            self.t.enlace.vaciar()

    def espera(self, ahora):
        """Cuánto puede dormir el bucle antes de la próxima tarea."""
        t = 1.0
        if self.activo != "laptop" and self.t.enlace.pendiente:
            t = 0.004
        for x in self.entradas:
            if x.tap_hasta:
                t = min(t, max(0.0, x.tap_hasta - ahora))
        for nombre, r in self.pant.items():
            if nombre != "laptop" and r.aparcar_en:
                t = min(t, max(0.0, r.aparcar_en[0] - ahora))
        return t
