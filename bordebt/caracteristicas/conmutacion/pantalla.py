"""Modelo de una pantalla: posición del puntero, recorte en bordes y 'empuje' para saltar."""
import time

from bordebt.comun.disposicion import LADOS


class Pantalla:
    PAUSA_EMPUJE = 0.15   # s sin empujar que reinician el empuje (debe ser continuo)

    def __init__(self, w, h):
        self.w, self.h = float(w), float(h)
        self.x, self.y = self.w / 2, self.h / 2
        self.empuje = dict.fromkeys(LADOS, 0.0)
        self.t_ini = dict.fromkeys(LADOS, 0.0)
        self.t_empuje = 0.0

    def mover(self, dx, dy, lados, margen, espera=0.0):
        """Mueve recortando en los bordes. Devuelve el lado (de `lados`) contra el que se empujó más
        allá de `margen` de forma continua durante al menos `espera` segundos."""
        nx, ny = self.x + dx, self.y + dy
        exceso = {"left": -nx, "right": nx - self.w, "top": -ny, "bottom": ny - self.h}
        alejando = {"left": dx > 0, "right": dx < 0, "top": dy > 0, "bottom": dy < 0}
        self.x, self.y = min(max(nx, 0.0), self.w), min(max(ny, 0.0), self.h)
        ahora = time.monotonic()
        if ahora - self.t_empuje > self.PAUSA_EMPUJE:
            self.empuje = dict.fromkeys(LADOS, 0.0)
        salida = None
        for lado in LADOS:
            if exceso[lado] > 0 and lado in lados:
                if not self.empuje[lado]:
                    self.t_ini[lado] = ahora
                self.empuje[lado] += exceso[lado]
                self.t_empuje = ahora
                if self.empuje[lado] >= margen and ahora - self.t_ini[lado] >= espera:
                    salida = lado
            elif alejando[lado]:
                self.empuje[lado] = 0.0
        if salida:
            self.empuje = dict.fromkeys(LADOS, 0.0)
        return salida

    def fraccion(self, lado):
        return self.y / self.h if lado in ("left", "right") else self.x / self.w

    def entrar(self, lado, f):
        f = min(max(f, 0.0), 1.0)
        if lado in ("left", "right"):
            self.x, self.y = (0.0 if lado == "left" else self.w), f * self.h
        else:
            self.x, self.y = f * self.w, (0.0 if lado == "top" else self.h)
        self.empuje = dict.fromkeys(LADOS, 0.0)
