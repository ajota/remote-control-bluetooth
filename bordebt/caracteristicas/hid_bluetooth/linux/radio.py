"""Política de radio en Linux (hciconfig/hcitool): modo de ahorro 'sniff' y QoS por dispositivo."""
import re
import subprocess
import threading

from bordebt.comun.diagnostico import dbg


class Radio:
    """En sniff el dispositivo solo escucha la radio cada cierto intervalo y los reportes llegan en ráfagas
    (puntero a saltos). Se desactiva SOLO en el dispositivo que se está usando; los demás pueden dormir y
    así no le quitan turnos de radio al activo. Al volver a uno dormido, Linux lo despierta con el primer
    reporte. Al activo además se le pide QoS (consultas más frecuentes)."""

    LATENCIA_US = 7500    # cada cuánto pedimos que el dispositivo nos consulte (por defecto suele ser 25 ms)

    def __init__(self, id_adaptador, macs):
        self.hci = id_adaptador
        self.macs = list(macs)
        self.con = self.sin = None
        self.qos = True

    def preparar(self):
        try:
            out = subprocess.run(["hciconfig", self.hci, "lp"], capture_output=True, text=True).stdout
            m = re.search(r"Link policy:\s*(.*)", out)
            pol = m.group(1).split() if m else []
        except (OSError, subprocess.SubprocessError) as ex:
            print("Aviso: no pude leer la política Bluetooth (%s); el movimiento puede ir a saltos." % ex)
            return
        if not pol:
            return
        if "SNIFF" not in pol:            # quizás quedó así por una ejecución anterior interrumpida
            pol = pol + ["SNIFF"]
            subprocess.run(["hciconfig", self.hci, "lp", ",".join(pol)], capture_output=True)
        self.con = ",".join(pol)
        self.sin = ",".join(p for p in pol if p != "SNIFF") or "RSWITCH"
        dbg("política Bluetooth: activo=%s, inactivos=%s" % (self.sin, self.con))

    def _conexion(self, mac):
        """(handle, rol) de la conexión con `mac` según `hcitool con`, o (None, None)."""
        out = subprocess.run(["hcitool", "-i", self.hci, "con"], capture_output=True, text=True).stdout
        m = re.search(r"%s handle (\d+).*?lm (\w+)" % re.escape(mac), out, re.I)
        return (int(m.group(1)), m.group(2)) if m else (None, None)

    def pedir_qos(self, mac):
        """HCI QoS_Setup: pide al dispositivo que nos consulte cada LATENCIA_US. En Bluetooth quien dirige la
        conexión (la tablet o el celular) decide cuándo podemos enviar; por defecto suele ser cada 25 ms, y
        eso se siente como latencia y limita a ~40 reportes/s. Es lo que hacen los mouses Bluetooth."""
        handle, rol = self._conexion(mac)
        if handle is None:
            return

        def le(v, n):
            return ["%02x" % ((v >> (8 * i)) & 0xFF) for i in range(n)]
        params = le(handle, 2) + ["00", "02"] + le(1000, 4) + le(0, 4) + le(self.LATENCIA_US, 4) + le(0xFFFFFFFF, 4)
        r = subprocess.run(["hcitool", "-i", self.hci, "cmd", "0x02", "0x0007"] + params,
                           capture_output=True, text=True)
        dbg("QoS %s (handle %d, la laptop es %s): consultas cada %.1f ms %s" % (
            mac, handle, rol, self.LATENCIA_US / 1000.0, "pedido" if r.returncode == 0 else "rechazado"))

    def aplicar(self, mac_activo):
        """Activo sin sniff y con QoS; el resto con sniff. En segundo plano: no frena la entrada."""
        orden = [(m, self.sin if m == mac_activo else self.con) for m in self.macs] if self.con else []

        def hilo():
            for mac, pol in orden:
                subprocess.run(["hcitool", "-i", self.hci, "lp", mac, pol], capture_output=True)
            if mac_activo and self.qos:
                self.pedir_qos(mac_activo)
        threading.Thread(target=hilo, daemon=True).start()

    def restaurar(self):
        if self.con:
            for mac in self.macs:
                subprocess.run(["hcitool", "-i", self.hci, "lp", mac, self.con], capture_output=True)
            self.con = None
