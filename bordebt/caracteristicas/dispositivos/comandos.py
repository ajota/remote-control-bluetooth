"""Comandos `pair`, `add`, `set` y `remove`."""
import sys
import time

from bordebt import plataforma
from bordebt.comun import argumentos, bucle
from bordebt.comun.config import COMANDO, buscar_dispositivo, guardar, validar
from bordebt.comun.disposicion import LADO_ES
from bordebt.caracteristicas.hid_bluetooth import servicio


def registrar(sub):
    s = sub.add_parser("pair", help="emparejar un dispositivo nuevo")
    s.add_argument("nombre")
    s.add_argument("--side", type=argumentos.lado, required=True, help="derecha/izquierda/arriba/abajo")
    s.add_argument("--of", default="laptop", help="pantalla vecina (por defecto laptop)")
    s.set_defaults(func=cmd_pair)

    s = sub.add_parser("add", help="agregar un dispositivo ya emparejado")
    s.add_argument("nombre")
    s.add_argument("mac", type=argumentos.mac)
    s.add_argument("--side", type=argumentos.lado, required=True)
    s.add_argument("--of", default="laptop")
    s.set_defaults(func=cmd_add)

    s = sub.add_parser("set", help="cambiar lado, tamaño o sensibilidad de un dispositivo")
    s.add_argument("nombre")
    s.add_argument("--mac", type=argumentos.mac)
    s.add_argument("--side", type=argumentos.lado)
    s.add_argument("--of")
    s.add_argument("--width", type=int, help="ancho de su pantalla en unidades (lo mide 'calibrate')")
    s.add_argument("--height", type=int)
    s.add_argument("--gain", type=float, help="multiplicador de velocidad del puntero en ese dispositivo")
    s.add_argument("--scroll", type=float, help="multiplicador de scroll en ese dispositivo")
    s.add_argument("--accel", type=float, help="aceleración del puntero del dispositivo (3 = Android "
                                              "típico, 1 = sin aceleración)")
    s.set_defaults(func=cmd_set)

    s = sub.add_parser("remove", help="quitar un dispositivo")
    s.add_argument("nombre")
    s.set_defaults(func=cmd_remove)


def cmd_pair(a, cfg):
    plataforma.requiere_privilegios()
    devs = [d for d in cfg["devices"] if d["name"] != a.nombre]
    nuevo = {"name": a.nombre, "mac": None, "side": a.side, "of": a.of}
    cfg["devices"] = devs + [nuevo]
    validar(cfg)
    conocidas = {d["mac"].upper() for d in devs}

    bz = servicio.preparar_adaptador(agente=True)
    bz.visible(True)
    encontrado = []

    def desconocido(addr):
        if addr in conocidas or encontrado:
            return False
        encontrado.append(addr)
        return True

    gestor = servicio.bt().GestorBT({}, seguro=cfg["secure"], desconocido=desconocido)
    print("Visible como '%s' durante 3 minutos." % bz.nombre_visible())
    print("En '%s' abre Ajustes > Bluetooth, busca ese nombre y empareja." % a.nombre)
    print("(Si ya estaba emparejado con una versión anterior del script, olvídalo primero allí.)")
    limite = time.monotonic() + 180
    try:
        while not encontrado and time.monotonic() < limite:
            bucle.esperar(gestor.fds(), 1.0)
    except KeyboardInterrupt:
        pass  # cancelado por el usuario
    finally:
        bz.visible(False)
    if not encontrado:
        sys.exit("No se conectó ningún dispositivo nuevo. Si se emparejó pero no conectó, busca su MAC con\n"
                 "  bluetoothctl devices Paired\ny agrégalo con: %s add %s <MAC> --side %s"
                 % (COMANDO, a.nombre, LADO_ES[a.side]))
    mac = encontrado[0]
    bz.confiar(mac)
    nuevo["mac"] = mac
    print("Emparejado: %s (%s)" % (bz.alias(mac), mac))
    gestor.cerrar()
    guardar(a.config, cfg)
    print("Siguiente paso: %s calibrate %s" % (COMANDO, a.nombre))


def cmd_add(a, cfg):
    cfg["devices"] = [d for d in cfg["devices"] if d["name"] != a.nombre]
    cfg["devices"].append({"name": a.nombre, "mac": a.mac, "side": a.side, "of": a.of})
    validar(cfg)
    guardar(a.config, cfg)


def cmd_set(a, cfg):
    d = buscar_dispositivo(cfg, a.nombre)
    for campo in ("mac", "side", "of", "width", "height", "gain", "scroll", "accel"):
        if getattr(a, campo) is not None:
            d[campo] = getattr(a, campo)
    validar(cfg)
    guardar(a.config, cfg)


def cmd_remove(a, cfg):
    buscar_dispositivo(cfg, a.nombre)
    cfg["devices"] = [d for d in cfg["devices"] if d["name"] != a.nombre]
    validar(cfg)
    guardar(a.config, cfg)
