"""Comandos `list` y `config`."""
from bordebt.comun.config import guardar
from bordebt.comun.disposicion import LADO_ES

NUMERICOS = (("speed", float), ("remote_speed", float), ("remote_accel", float), ("mouse_speed", float),
             ("margin", int), ("remote_margin", int), ("remote_dwell", float), ("remote_caution", float),
             ("scroll_mm", float), ("align_rate", float), ("reconnect", int),
             ("reconnect_max", int), ("reconnect_tries", int))
BOOLEANOS = ("natural_scroll", "tap", "align", "secure", "allow_sniff", "hide_remote_pointer", "qos",
             "pause_screen_off", "keep_awake")


def registrar(sub):
    sub.add_parser("list", help="ver la configuración").set_defaults(func=cmd_list)
    s = sub.add_parser("config", help="ajustes generales")
    s.add_argument("--screen", help="resolución lógica de la laptop, p.ej. 1744x981")
    for clave, tipo in NUMERICOS:
        s.add_argument("--" + clave.replace("_", "-"), dest=clave, type=tipo)
    for clave in BOOLEANOS:
        s.add_argument("--" + clave.replace("_", "-"), dest=clave, action="store_true", default=None)
        s.add_argument("--no-" + clave.replace("_", "-"), dest=clave, action="store_false")
    s.set_defaults(func=cmd_config)


def cmd_list(a, cfg):
    print("Configuración:", a.config)
    print("laptop  %s" % (cfg.get("screen") or "(resolución automática)"))
    for d in cfg["devices"]:
        print("  %-10s %s  a la %-9s de %-10s %sx%s  gain=%s" % (
            d["name"], d["mac"], LADO_ES[d["side"]], d["of"],
            d.get("width", "?"), d.get("height", "?"), d.get("gain", 1.0)))
    if not cfg["devices"]:
        print("  (sin dispositivos)")
    ajustes = {k: v for k, v in cfg.items() if k not in ("devices", "screen")}
    print("Ajustes:", ", ".join("%s=%s" % kv for kv in ajustes.items()))


def cmd_config(a, cfg):
    for clave in ["screen"] + [c for c, _ in NUMERICOS] + list(BOOLEANOS):
        valor = getattr(a, clave)
        if valor is not None:
            cfg[clave] = valor
    guardar(a.config, cfg)
