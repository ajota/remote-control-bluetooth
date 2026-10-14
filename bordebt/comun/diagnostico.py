"""Diagnóstico (--debug): mensajes y un resumen por segundo de lo que entra (trackpad) y sale (Bluetooth)."""
import time

DEBUG = False
STATS = {"eventos": 0, "frames": 0, "dedos": 0, "mx": 0.0, "my": 0.0, "enviados": 0, "timeouts": 0,
         "perdidos": 0, "desfases": 0, "cola": 0, "agrupados": 0}
_t_resumen = [0.0]


def activar():
    global DEBUG
    DEBUG = True


def dbg(msg):
    if DEBUG:
        print("[debug] " + msg, flush=True)


def resumen(enlace=None):
    """Una línea por segundo con lo que entra (trackpad) y lo que sale (Bluetooth)."""
    ahora = time.monotonic()
    if not DEBUG or ahora - _t_resumen[0] < 1.0:
        return
    _t_resumen[0] = ahora
    modo = ("boot" if enlace.boot else "report") if enlace and enlace.conectado else "-"
    dbg("trackpad: %d eventos, %d cuadros, dedos=%d, movimiento=(%+.0f, %+.0f), perdidos=%d, desfases=%d | "
        "BT: %d reportes, %d agrupados, cola máx %d B, %d timeouts, protocolo=%s" % (
            STATS["eventos"], STATS["frames"], STATS["dedos"], STATS["mx"], STATS["my"], STATS["perdidos"],
            STATS["desfases"], STATS["enviados"], STATS["agrupados"], STATS["cola"], STATS["timeouts"], modo))
    for k in STATS:
        if k != "dedos":
            STATS[k] = 0
