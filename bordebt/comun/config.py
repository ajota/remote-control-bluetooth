"""Configuración persistente (JSON): ajustes generales y dispositivos."""
import json
import os
import sys

from bordebt.comun.disposicion import construir_vecinos

COMANDO = "sudo python3 borde_bt.py"   # cómo se invoca, para los mensajes de ayuda

DEFAULTS = {
    "screen": None,          # "1744x981" (px lógicos); None = detectar
    "speed": 1.0,            # sensibilidad del trackpad
    "mouse_speed": 1.0,      # sensibilidad de mouses externos
    "margin": 25,            # px de empuje extra contra el borde de la laptop para saltar
    "remote_margin": 60,     # unidades de empuje extra en el borde de un dispositivo
    "remote_dwell": 0.05,    # s de empuje continuo contra el borde de un dispositivo para saltar
    "remote_caution": 0.15,  # prudencia del modelo remoto (0 = ninguna; más = salto más tardío)
    "natural_scroll": True,
    "scroll_mm": 2.5,        # mm de desplazamiento con dos dedos por "paso" de rueda
    "tap": True,             # tocar para hacer clic
    "remote_speed": 10.0,    # unidades por mm de dedo hacia los dispositivos, en movimientos lentos
    "remote_accel": 2.0,     # aceleración total deseada en dispositivos (se completa si el dispositivo acelera menos)
    "align": False,          # (obsoleto) ya no se alinea la altura al entrar
    "align_rate": 400,       # (obsoleto)
    "reconnect": 20,         # s entre intentos de reconexión (se duplica con cada fallo...)
    "reconnect_max": 300,    # ...hasta este máximo en s
    "reconnect_tries": 6,    # fallos seguidos tras los que se deja de buscar en segundo plano (0 = nunca)
    "secure": True,          # exigir enlace cifrado (dispositivo emparejado)
    "allow_sniff": False,    # permitir el modo de ahorro "sniff" del Bluetooth (más batería, movimiento a saltos)
    "hide_remote_pointer": True,   # ocultar el puntero del dispositivo al salir de él
    "qos": True,             # pedir al dispositivo activo que nos consulte cada 7.5 ms (menos latencia)
    "pause_screen_off": True,  # pausar (soltar Bluetooth, teclado y trackpad) con la pantalla apagada
    "keep_awake": True,      # que la laptop no apague la pantalla ni se suspenda mientras usas un dispositivo
    "devices": [],
}


def ruta_config():
    """Archivo de configuración del usuario (el que llamó a sudo, si se usó sudo)."""
    if sys.platform == "win32":
        return os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")), "borde_bt", "borde_bt.json")
    user = os.environ.get("SUDO_USER")
    if user:
        import pwd
        home = pwd.getpwnam(user).pw_dir
    else:
        home = os.path.expanduser("~")
    return os.path.join(home, ".config", "borde_bt.json")


def cargar(ruta):
    cfg = json.loads(json.dumps(DEFAULTS))
    if os.path.exists(ruta):
        with open(ruta) as f:
            cfg.update(json.load(f))
    for d in cfg["devices"]:
        d.setdefault("of", "laptop")
    return cfg


def guardar(ruta, cfg):
    os.makedirs(os.path.dirname(ruta), exist_ok=True)
    with open(ruta, "w") as f:
        json.dump(cfg, f, indent=2, ensure_ascii=False)
    if os.environ.get("SUDO_UID") and hasattr(os, "chown"):
        os.chown(ruta, int(os.environ["SUDO_UID"]), int(os.environ["SUDO_GID"]))
    print("Guardado en", ruta)


def buscar_dispositivo(cfg, nombre):
    for d in cfg["devices"]:
        if d["name"] == nombre:
            return d
    sys.exit("No existe el dispositivo '%s'. Mira 'list'." % nombre)


def validar(cfg):
    try:
        construir_vecinos(cfg["devices"])
    except ValueError as ex:
        sys.exit(str(ex))
