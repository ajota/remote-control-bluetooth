"""Reposo: pausa con la pantalla apagada o el equipo suspendido, y mantiene despierta la laptop mientras se
usa un dispositivo (el escritorio no ve ese uso: el teclado y el trackpad van por Bluetooth, así que sin
esto apagaría la pantalla, y con batería suspendería el equipo, en plena sesión con la tablet).

En pausa: el control vuelve a la laptop, se cierran los enlaces Bluetooth sin buscar a nadie (radio libre)
y se suelta la captura del teclado y el trackpad, que van directo al sistema (el script queda fuera del
camino). Al reanudar se retoma la captura solo sin teclas presionadas (si no, el sistema se quedaría con
una tecla pegada) y se reconecta a todos de inmediato.
"""


class Reposo:
    INACTIVO = 60.0     # s sin usar el teclado/trackpad tras los que ya no se mantiene despierta la laptop
    TOQUE = 30.0        # s entre "toques" al puntero para que el escritorio no cuente inactividad
    REINTENTO = 0.2     # s entre intentos de retomar la captura mientras haya teclas presionadas

    def __init__(self, motor, conexiones, captura, puntero, pausar_pantalla=True, mantener_despierta=True):
        self.motor, self.conexiones, self.captura, self.puntero = motor, conexiones, captura, puntero
        self.pausar_pantalla, self.mantener = pausar_pantalla, mantener_despierta
        self.pausado = self.retomando = False
        self.despertares = 0
        self.t_toque = -1e9

    def debe_pausar(self, ahora, pantalla, durmiendo):
        if durmiendo:
            return True
        if pantalla or not self.pausar_pantalla:
            return False
        # Pantalla apagada usando un dispositivo: solo si de verdad se dejó de usar (si no, es el escritorio
        # que no vio actividad, por ejemplo con `keep_awake` desactivado).
        return self.motor.activo == "laptop" or ahora - self.motor.ultima_actividad > self.INACTIVO

    def tick(self, ahora, pantalla, durmiendo, despertares=0):
        if despertares != self.despertares:
            self.despertares = despertares
            if not self.pausado and not durmiendo:
                self.conexiones.reanudar()      # la suspensión cortó los enlaces: reconectar ya
        debe = self.debe_pausar(ahora, pantalla, durmiendo)
        if debe and not self.pausado:
            self._pausar("Suspensión" if durmiendo else "Pantalla apagada")
        elif not debe and self.pausado:
            self._reanudar()
        elif not self.pausado:
            self._mantener_despierta(ahora)

    def _pausar(self, motivo):
        if self.motor.activo != "laptop":
            self.motor.cambiar("laptop", None, 0, mostrar=False)   # mover el puntero encendería la pantalla
        self.motor.soltar_teclas_locales()
        self.motor.t.soltar()
        self.conexiones.pausar()
        self.captura.pausar()
        self.pausado, self.retomando = True, False
        print("%s: en pausa (Bluetooth desconectado; teclado y trackpad solo para la laptop)." % motivo)

    def _reanudar(self):
        if not self.captura.retomar():
            self.retomando = True           # hay teclas presionadas: reintentar en un momento
            return
        self.pausado = self.retomando = False
        self.conexiones.reanudar()
        print("Reanudado: reconectando los dispositivos...")

    def _mantener_despierta(self, ahora):
        if (self.mantener and self.motor.activo != "laptop"
                and ahora - self.motor.ultima_actividad < self.INACTIVO and ahora - self.t_toque >= self.TOQUE):
            self.t_toque = ahora
            self.puntero.despertar()

    def espera(self):
        """Cuánto puede dormir el bucle por cuenta del reposo."""
        return self.REINTENTO if self.retomando else 1.0
