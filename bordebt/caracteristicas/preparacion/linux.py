"""Preparación en Linux: bluetoothd sin los plugins 'input' y 'hostname', y clase de teclado+mouse."""
import glob
import os
import re
import socket
import subprocess
import sys

from bordebt import plataforma
from bordebt.comun.config import COMANDO

OVERRIDE = "/etc/systemd/system/bluetooth.service.d/borde_bt.conf"
MAINCONF = "/etc/bluetooth/main.conf"
MARCA = "# borde_bt: clase teclado+mouse"


def aplicar(deshacer=False):
    lineas = open(MAINCONF).read().splitlines() if os.path.exists(MAINCONF) else ["[General]"]
    limpias, saltar = [], False
    for linea in lineas:                       # quita lo que hayamos puesto antes
        if saltar and re.match(r"(Class|Name) = ", linea):
            continue
        saltar = linea == MARCA
        if saltar:
            continue
        limpias.append(linea[len("#borde_bt# "):] if linea.startswith("#borde_bt# ") else linea)
    if deshacer:
        if os.path.exists(OVERRIDE):
            os.remove(OVERRIDE)
        nuevas = limpias
    else:
        bluetoothd = next((p for p in ("/usr/libexec/bluetooth/bluetoothd", "/usr/lib/bluetooth/bluetoothd")
                           if os.path.exists(p)), None)
        if not bluetoothd:
            sys.exit("No encontré el ejecutable de bluetoothd.")
        os.makedirs(os.path.dirname(OVERRIDE), exist_ok=True)
        # Sin 'input' (ocupa los PSM 17/19) ni 'hostname' (impone la clase "Laptop" según el chasis).
        with open(OVERRIDE, "w") as f:
            f.write("[Service]\nExecStart=\nExecStart=%s -P input,hostname\n" % bluetoothd)
        # Sin el plugin hostname el nombre visible sería "BlueZ"; lo fijamos al nombre del equipo.
        propias = [MARCA, "Class = 0x000540", "Name = %s" % socket.gethostname()]
        nuevas, seccion = [], None
        for linea in limpias:
            if linea.strip().startswith("["):
                seccion = linea.strip()
            if seccion == "[General]" and re.match(r"\s*(Class|Name)\s*=", linea):
                linea = "#borde_bt# " + linea
            nuevas.append(linea)
            if linea.strip() == "[General]":
                nuevas += propias
        if "[General]" not in (x.strip() for x in nuevas):
            nuevas = ["[General]"] + propias + nuevas
    print("1/3 %s %s" % ("Quitado" if deshacer else "Escrito", OVERRIDE))
    with open(MAINCONF, "w") as f:
        f.write("\n".join(nuevas) + "\n")
    print("2/3 %s la clase en %s" % ("Restaurada" if deshacer else "Configurada", MAINCONF))
    print("3/3 Reiniciando el servicio Bluetooth...")
    subprocess.run(["systemctl", "daemon-reload"], check=False)
    r = subprocess.run(["systemctl", "restart", "bluetooth"], check=False)
    if r.returncode != 0:
        sys.exit("No se pudo reiniciar bluetooth. Revisa: journalctl -u bluetooth -n 30")


def _args_bluetoothd():
    for comm in glob.glob("/proc/[0-9]*/comm"):
        try:
            if open(comm).read().strip() == "bluetoothd":
                return open(comm[:-4] + "cmdline").read().split("\0")
        except OSError:
            pass  # el proceso terminó mientras se recorría /proc
    return None


def plugins_quitados(args):
    """Plugins desactivados con -P/--noplugin en la línea de comandos de bluetoothd."""
    quitados = set()
    for i, x in enumerate(args):
        if x in ("-P", "--noplugin") and i + 1 < len(args):
            quitados |= set(args[i + 1].split(","))
        elif x.startswith(("-P", "--noplugin=")):
            quitados |= set(x.split("=", 1)[-1].replace("-P", "", 1).split(","))
    return quitados


def comprobar_sistema(linea):
    """Comprueba la preparación del sistema. Devuelve True si el servicio Bluetooth está en marcha."""
    bloqueado = False
    for tipo in glob.glob("/sys/class/rfkill/*/type"):
        if open(tipo).read().strip() == "bluetooth":
            base = os.path.dirname(tipo)
            bloqueado |= any(open(os.path.join(base, f)).read().strip() == "1"
                             for f in ("soft", "hard") if os.path.exists(os.path.join(base, f)))
    linea(not bloqueado, "Bluetooth no bloqueado", "rfkill unblock bluetooth")
    linea(os.path.exists(OVERRIDE), "Archivo %s" % OVERRIDE, COMANDO + " setup")
    try:
        conf = open(MAINCONF).read()
    except OSError:
        conf = ""
    linea(re.search(r"(?m)^Class\s*=\s*0x000540", conf) is not None,
          "Class = 0x000540 en %s" % MAINCONF, COMANDO + " setup")
    args = _args_bluetoothd()
    if args is None:
        linea(False, "Servicio bluetoothd en ejecución", "sudo systemctl start bluetooth")
        return False
    linea({"input", "hostname"} <= plugins_quitados(args),
          "bluetoothd corre sin los plugins 'input' y 'hostname' (%s)" % " ".join(a for a in args if a),
          "%s setup   (si ya lo hiciste: sudo systemctl restart bluetooth)" % COMANDO)
    if plataforma.es_admin():
        linea(plataforma.adaptador("hid_bluetooth").psm_libre(), "Canales HID (PSM 17/19) libres",
              "los ocupa el plugin 'input' u otra copia de este script en ejecución")
    return True
