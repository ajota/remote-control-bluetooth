"""Intérprete del trackpad: convierte cuadros táctiles en movimiento, clics, arrastre, scroll y gestos."""
import math

from bordebt.comun.diagnostico import STATS


def px_por_mm(v):
    """Curva de aceleración del puntero de la laptop: ~3 px/mm lento, ~16 px/mm rápido (v en mm/s)."""
    t = min(max((v - 20.0) / 230.0, 0.0), 1.0)
    return 3.0 + 13.0 * t * t * (3 - 2 * t)


class InterpreteTactil:
    TAP_T, TAP_MM, ARRASTRE_T, TECLEO_T, PAUSA_T = 0.18, 2.0, 0.20, 0.4, 0.08
    ZOOM_MM, GESTO3_MM, DECIDIR_MM = 6.0, 15.0, 3.0
    ZONA_MM, ZONA_MAX = 10.0, 0.18   # franja inferior de botones (como Ubuntu): 10 mm, máx. 18% del alto

    def __init__(self, acciones, cfg):
        self.m, self.cfg = acciones, cfg
        self.lx = self.ly = None
        self.dedos = self.max_dedos = 0
        self.t0 = self.t_ant = self.vel = self.mov = 0.0
        self.hubo_clic = self.ignorar = self.arrastre = False
        self.tap_hasta = self.btn = None
        self._reiniciar_gestos()

    def _reiniciar_gestos(self):
        if getattr(self, "modo2", None) == "zoom":
            self.m.pellizco_fin()
        self.modo2 = None                  # con 2 dedos: None (aún sin decidir), "scroll" o "zoom"
        self.prev2 = None                  # (distancia, centro x, centro y) en mm del cuadro anterior
        self.acc_d = self.acc_c = self.acc_zoom = 0.0
        self.g3x = self.g3y = 0.0
        self.gesto3_hecho = False

    def _boton_fisico(self, c, dedos):
        """Qué botón es un clic físico: por zona (franja inferior: mitad derecha = derecho) o, fuera de
        la zona, por número de dedos (2 = derecho, 3 = medio)."""
        if c.y is not None and c.y >= c.alto - min(self.ZONA_MM, self.ZONA_MAX * c.alto):
            return "R" if c.x is not None and c.x > c.ancho / 2 else "L"
        return {2: "R", 3: "M"}.get(dedos, "L")

    def cuadro(self, c):
        ahora, dedos = c.t, c.dedos
        if c.resinc:
            self.lx = self.ly = None
            self.prev2 = None
        for b, v in c.botones:                # botones físicos dedicados
            self.hubo_clic = True
            self.m.boton(b, v)
        if c.presion:
            self.hubo_clic = True
            self.btn = self._boton_fisico(c, dedos)
            self.m.boton(self.btn, 1)
        if c.suelta and self.btn:
            self.m.boton(self.btn, 0)
            self.btn = None
        if dedos and self.dedos and ahora - self.t_ant > self.PAUSA_T:
            self.lx = self.ly = None     # pausa sin cuadros: no convertirla en un salto
        STATS["frames"] += 1
        STATS["dedos"] = dedos
        if dedos != self.dedos:
            self._reiniciar_gestos()
        if dedos and not self.dedos:                     # empieza un toque
            self.t0, self.mov, self.vel, self.max_dedos = ahora, 0.0, 0.0, dedos
            self.hubo_clic = self.btn is not None
            self.ignorar = ahora - self.m.ultimo_tecleo < self.TECLEO_T   # palma mientras escribes
            if self.tap_hasta and ahora < self.tap_hasta and not self.ignorar:
                self.tap_hasta, self.arrastre = None, True                # toque + toque = arrastrar
                self.m.boton("L", 1)
        if dedos != self.dedos:
            self.lx = self.ly = None
            self.max_dedos = max(self.max_dedos, dedos)
        if dedos and c.x is not None and c.y is not None:
            if self.lx is not None:
                mx, my = c.x - self.lx, c.y - self.ly
                d = math.hypot(mx, my)
                self.mov += d
                if not self.ignorar:
                    if dedos == 1 or self.btn or self.arrastre:
                        if d:
                            self.vel = 0.6 * self.vel + 0.4 * d / max(ahora - self.t_ant, 0.005)
                            f = self.m.px_por_mm(self.vel)
                            self.m.movimiento(mx * f, my * f)
                    elif dedos == 2:
                        self._dos_dedos(c.puntos, mx, my)   # aunque el primer dedo esté quieto (pellizco)
                    elif dedos == 3:
                        self._tres_dedos(mx, my)
            self.lx, self.ly, self.t_ant = c.x, c.y, ahora
        if not dedos and self.dedos:                     # termina el toque
            corto = ahora - self.t0 < self.TAP_T and self.mov < self.TAP_MM
            if self.arrastre:
                self.arrastre = False
                self.m.boton("L", 0)
                if corto:
                    self.m.clic("L")                     # fue doble toque = doble clic
            elif corto and self.cfg["tap"] and not self.hubo_clic and not self.ignorar:
                if self.max_dedos == 1:
                    self.tap_hasta = ahora + self.ARRASTRE_T
                elif self.max_dedos == 2:
                    self.m.clic("R")
                elif self.max_dedos == 3:
                    self.m.clic("M")
        self.dedos = dedos

    def tick(self, ahora):
        if self.tap_hasta and ahora >= self.tap_hasta:
            self.tap_hasta = None
            self.m.clic("L")

    def _dos_dedos(self, puntos, mx, my):
        """Dos dedos: scroll si se mueven juntos, zoom (pellizco) si se separan o se juntan."""
        dd = 0.0
        if len(puntos) >= 2:
            (x1, y1), (x2, y2) = puntos[:2]
            actual = (math.hypot(x1 - x2, y1 - y2), (x1 + x2) / 2, (y1 + y2) / 2)
            if self.prev2 is None:
                self.prev2 = actual
                return
            dd, mx, my = (actual[i] - self.prev2[i] for i in range(3))   # usar el centro de los dos dedos
            self.prev2 = actual
        if self.modo2 is None:            # decidir tras unos mm de movimiento
            self.acc_d += dd
            self.acc_c += math.hypot(mx, my)
            if abs(self.acc_d) + self.acc_c < self.DECIDIR_MM:
                return
            self.modo2 = "zoom" if abs(self.acc_d) > 1.5 * self.acc_c else "scroll"
        if self.modo2 == "zoom":
            self.acc_zoom += dd / self.ZOOM_MM       # separar = acercar (rueda arriba con Ctrl)
            n = int(self.acc_zoom)
            if n:
                self.acc_zoom -= n
                self.m.pellizco(n)
        else:
            s = (1 if self.cfg["natural_scroll"] else -1) / self.cfg["scroll_mm"]
            self.m.scroll(my * s, -mx * s)

    def _tres_dedos(self, mx, my):
        """Tres dedos: un deslizamiento por toque (arriba, abajo, izquierda o derecha)."""
        if self.gesto3_hecho:
            return
        self.g3x += mx
        self.g3y += my
        if max(abs(self.g3x), abs(self.g3y)) < self.GESTO3_MM:
            return
        self.gesto3_hecho = True
        if abs(self.g3y) > abs(self.g3x):
            self.m.gesto("arriba" if self.g3y < 0 else "abajo")
        else:
            self.m.gesto("izquierda" if self.g3x < 0 else "derecha")
