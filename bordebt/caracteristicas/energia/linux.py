"""Energía en Linux: pantalla apagada (DPMS del kernel, sirve en X11 y Wayland) y suspensión (logind)."""
import glob
import os


class MonitorEnergia:
    """La pantalla se consulta en sysfs (sin depender de la sesión gráfica del usuario, que no es la de
    root). La suspensión llega como señal D-Bus en el hilo de GLib de BlueZ; se avisa al bucle principal
    por una tubería para que la atienda en su propio hilo."""

    INTERVALO = 1.0      # s entre lecturas de la pantalla
    CONECTORES = "/sys/class/drm/card*-*"

    def __init__(self, bus=None):
        self.durmiendo, self.despertares = False, 0
        self._encendida, self._t_leida = True, -1e9
        self.rp, self.wp = os.pipe()
        os.set_blocking(self.rp, False)
        if bus is not None:
            try:
                bus.add_signal_receiver(self._al_dormir, signal_name="PrepareForSleep",
                                        dbus_interface="org.freedesktop.login1.Manager",
                                        bus_name="org.freedesktop.login1", path="/org/freedesktop/login1")
            except Exception as ex:      # sin logind: solo se pausa con la pantalla apagada
                print("Aviso: no podré detectar la suspensión (%s)." % ex)

    def _al_dormir(self, empieza):
        if not empieza:
            self.despertares += 1
        self.durmiendo = bool(empieza)
        os.write(self.wp, b"x")

    def fds(self):
        return {self.rp: self._vaciar}

    def _vaciar(self):
        try:
            os.read(self.rp, 512)
        except BlockingIOError:
            pass  # ya se había leído el aviso

    def pantalla_encendida(self, ahora):
        """True si alguna pantalla conectada está encendida (o si no se puede saber)."""
        if ahora - self._t_leida >= self.INTERVALO:
            self._t_leida = ahora
            estados = []
            for conector in glob.glob(self.CONECTORES):
                try:
                    with open(os.path.join(conector, "status")) as f:
                        if f.read().strip() != "connected":
                            continue
                    with open(os.path.join(conector, "dpms")) as f:
                        estados.append(f.read().strip() == "On")
                except OSError:
                    continue  # conector sin esos archivos
            self._encendida = any(estados) or not estados
        return self._encendida
