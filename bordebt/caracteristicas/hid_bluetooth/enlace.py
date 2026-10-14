"""Enlace HID con un anfitrión (tablet o celular): reportes y agrupación del movimiento.

La lógica es independiente del sistema operativo. Cada plataforma hereda de `Enlace` e implementa el
transporte: `conectado`, `_transmitir(bytes)` y, si puede medirla, `cola()`.
"""
import time

from bordebt.comun.diagnostico import STATS
from bordebt.caracteristicas.hid_bluetooth import protocolo


class Enlace:
    INTERVALO_MIN = 0.008    # como mucho ~125 reportes/s
    ESPERA_MAX = 0.02        # sin medición de cola: no retener el movimiento más que esto
    EN_CAMINO = 2            # reportes que pueden estar esperando a la radio sin agrupar
    RETENCION_MAX = 0.1      # tope absoluto de retención del movimiento

    def __init__(self, mac):
        self.mac = mac.upper()
        self.boot = False
        self.al_cerrar = None
        # Movimiento sin enviar: si el Bluetooth no da abasto, se agrupa en vez de hacer cola (una cola
        # retrasa el puntero y se siente como "cámara lenta"). Los cambios de botones salen siempre.
        self.agrupar = True
        self.pend = [0, 0, 0, 0]
        self.botones_env = 0
        self.t_env = 0.0
        self.por_paquete = 0     # bytes que ocupa un reporte en la cola (se mide al enviar)

    # ---- transporte (lo implementa cada plataforma)
    @property
    def conectado(self):
        raise NotImplementedError

    def _transmitir(self, datos):
        """Envía un mensaje HIDP ya armado. True si salió (o se perdió sin cortar la conexión)."""
        raise NotImplementedError

    def cola(self):
        """Bytes todavía sin entregar a la radio, o -1 si no se puede saber."""
        return -1

    # ---- reportes
    def enviar(self, reporte):
        ok = self._transmitir(b"\xa1" + reporte)
        if ok:
            STATS["enviados"] += 1
        return ok

    def teclado(self, mods, teclas):
        return self.enviar(protocolo.reporte_teclado(mods, teclas))

    def consumo(self, uso):
        return self.enviar(protocolo.reporte_consumo(uso))

    @property
    def pendiente(self):
        return any(self.pend)

    def descartar_pendiente(self):
        self.pend = [0, 0, 0, 0]

    def raton(self, botones, dx=0, dy=0, rueda=0, pan=0):
        if not self.agrupar:
            return self.raton_inmediato(botones, dx, dy, rueda, pan)
        if botones != self.botones_env:          # clic: primero lo pendiente, luego el cambio, sin esperas
            self.vaciar(forzar=True)
            self.botones_env = botones
            return self.raton_inmediato(botones, dx, dy, rueda, pan)
        for i, v in enumerate((dx, dy, rueda, pan)):
            self.pend[i] += v
        return self.vaciar()

    def vaciar(self, forzar=False):
        """Envía el movimiento acumulado si el canal está libre (o si `forzar`)."""
        if not self.pendiente:
            return True
        if not forzar:
            ahora = time.monotonic()
            if ahora - self.t_env < self.INTERVALO_MIN:
                return True
            q = self.cola()
            STATS["cola"] = max(STATS["cola"], q)
            limite = self.EN_CAMINO * self.por_paquete if self.por_paquete else 0
            espera = ahora - self.t_env
            # Con la cola medible se espera a que haya sitio (no se acumula retraso); si no se puede medir,
            # se limita el ritmo. Nunca se retiene más de RETENCION_MAX: el puntero no puede congelarse.
            if espera < self.RETENCION_MAX and ((q > limite) if q >= 0 else (espera < self.ESPERA_MAX)):
                STATS["agrupados"] += 1
                return True
        dx, dy, rueda, pan = self.pend
        self.pend = [0, 0, 0, 0]
        return self.raton_inmediato(self.botones_env, dx, dy, rueda, pan)

    def raton_inmediato(self, botones, dx=0, dy=0, rueda=0, pan=0):
        """Envía ya, sin agrupar (y mide cuánto ocupa un reporte en la cola)."""
        self.t_env = time.monotonic()
        antes = self.cola() if self.agrupar else -1
        ok = True
        for r in protocolo.reportes_raton(botones, dx, dy, rueda, pan, self.boot):
            if not self.enviar(r):
                ok = False
                break
        if antes == 0:           # con la cola vacía, lo que hay ahora es exactamente un reporte
            q = self.cola()
            if q > 0:
                self.por_paquete = q if not self.por_paquete else min(self.por_paquete, q)
        return ok

    def reiniciar(self):
        """Estado limpio para una conexión nueva."""
        self.boot = False
        self.pend, self.botones_env = [0, 0, 0, 0], 0
