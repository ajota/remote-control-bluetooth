"""Comandos `setup` y `status`."""
import sys
import time

from bordebt import plataforma
from bordebt.comun.config import COMANDO
from bordebt.comun.disposicion import LADO_ES, construir_vecinos


def registrar(sub):
    s = sub.add_parser("setup", help="preparar bluetoothd (una vez)")
    s.add_argument("--deshacer", action="store_true")
    s.set_defaults(func=cmd_setup)
    sub.add_parser("status", help="comprobar que todo esté listo (Bluetooth, teclado, dispositivos)") \
        .set_defaults(func=cmd_status)


def cmd_setup(a, cfg):
    plataforma.requiere_privilegios()
    plataforma.adaptador("preparacion").aplicar(a.deshacer)
    time.sleep(2)   # dar tiempo a que el adaptador vuelva a aparecer
    if a.deshacer:
        print("Restaurado: bluetoothd vuelve a su configuración normal.")
        return
    print("\nVerificando...")
    if comprobar(cfg, solo_bluetooth=True):
        print("\nListo: bluetoothd sin el plugin 'input' y con clase de teclado+mouse.")
        print("Nota: mientras tanto la laptop no puede usar teclados/mouses Bluetooth propios.")
        print("Para revertir: %s setup --deshacer" % COMANDO)
    else:
        sys.exit("\nLa configuración no quedó completa; revisa los puntos marcados con [FALTA].")


def cmd_status(a, cfg):
    comprobar(cfg)


def comprobar(cfg, solo_bluetooth=False):
    """Revisa que todo esté listo e imprime cada punto. True si no falta nada."""
    faltas = []

    def linea(ok, texto, ayuda=None):
        print(("  [OK]    " if ok else "  [FALTA] ") + texto)
        if not ok:
            faltas.append(texto)
            if ayuda:
                print("          -> " + ayuda)

    print("Bluetooth")
    en_marcha = plataforma.adaptador("preparacion").comprobar_sistema(linea)
    bt = plataforma.adaptador("hid_bluetooth")
    bz = None
    if en_marcha:
        try:
            bz = bt.BlueZ()
            linea(bz.encendido(), "Adaptador encendido", "actívalo en Configuración > Bluetooth")
            clase = bz.clase()
            linea((clase >> 8) & 0x1F == 0x05, "Se anuncia como teclado/mouse (clase 0x%06x)" % clase,
                  "%s setup   (si ya lo hiciste: sudo systemctl restart bluetooth)" % COMANDO)
            print("          Nombre visible para las tablets: '%s'" % bz.nombre_visible())
        except (bt.ErrorBT, SystemExit) as ex:
            linea(False, "Adaptador Bluetooth accesible (%s)" % ex)
            bz = None
    if solo_bluetooth:
        return not faltas

    print("Teclado y trackpad")
    if plataforma.es_admin():
        teclados, punteros = plataforma.adaptador("entrada").nombres_dispositivos()
        linea(bool(teclados), "Teclado: %s" % (", ".join(teclados) or "ninguno"))
        linea(bool(punteros), "Puntero: %s" % (", ".join(punteros) or "ninguno"))
    else:
        print("  (ejecuta con sudo para revisar teclado, trackpad y canales HID)")

    print("Dispositivos")
    if not cfg["devices"]:
        linea(False, "Al menos un dispositivo configurado", COMANDO + " pair tablet --side derecha")
    try:
        construir_vecinos(cfg["devices"])
    except ValueError as ex:
        linea(False, "Disposición válida: %s" % ex)
    for d in cfg["devices"]:
        print("  %s (%s), a la %s de %s" % (d["name"], d["mac"], LADO_ES[d["side"]], d["of"]))
        if bz:
            linea(bz.emparejado(d["mac"]), "  emparejado",
                  "%s pair %s --side %s" % (COMANDO, d["name"], LADO_ES[d["side"]]))
        linea(d.get("width", 0) >= 300 and d.get("height", 0) >= 300,
              "  calibrado (%sx%s)" % (d.get("width", "?"), d.get("height", "?")),
              "%s calibrate %s   (falta o la medida es demasiado pequeña)" % (COMANDO, d["name"]))
    n = len(faltas)
    print("\n" + ("Todo listo." if not n else ("Falta 1 punto." if n == 1 else "Faltan %d puntos." % n)))
    return not faltas
