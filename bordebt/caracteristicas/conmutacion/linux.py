"""Adaptador Linux de conmutación: puntero absoluto uinput y resolución lógica del escritorio."""
import glob
import os
import re
import subprocess
import sys
import time

try:
    import evdev
    from evdev import ecodes as e
except ImportError as ex:
    sys.exit("Falta un módulo (%s). Instala: sudo apt install python3-evdev" % ex)

BOTONES = {"L": e.BTN_LEFT, "R": e.BTN_RIGHT, "M": e.BTN_MIDDLE, "S": e.BTN_SIDE, "E": e.BTN_EXTRA}
REL_WHEEL_HI_RES = getattr(e, "REL_WHEEL_HI_RES", 0x0b)
REL_HWHEEL_HI_RES = getattr(e, "REL_HWHEEL_HI_RES", 0x0c)


class PunteroUinput:
    """Mouse virtual ABSOLUTO (puerto PunteroLocal): en Wayland ningún programa puede leer la posición del
    cursor, pero si nosotros la fijamos, la sabemos siempre."""
    MAX = 65535

    def __init__(self):
        caps = {e.EV_KEY: list(BOTONES.values()),
                e.EV_ABS: [(e.ABS_X, evdev.AbsInfo(0, 0, self.MAX, 0, 0, 0)),
                           (e.ABS_Y, evdev.AbsInfo(0, 0, self.MAX, 0, 0, 0))],
                e.EV_REL: [e.REL_WHEEL, e.REL_HWHEEL, REL_WHEEL_HI_RES, REL_HWHEEL_HI_RES]}
        self.ui = evdev.UInput(caps, name="borde_bt puntero")
        self.av = self.ah = 0.0
        self.lv = self.lh = 0
        self.x = self.y = self.MAX // 2
        time.sleep(0.3)   # dar tiempo al compositor a registrar el dispositivo

    def mover_a(self, fx, fy):
        self.x, self.y = round(fx * self.MAX), round(fy * self.MAX)
        self.ui.write(e.EV_ABS, e.ABS_X, self.x)
        self.ui.write(e.EV_ABS, e.ABS_Y, self.y)
        self.ui.syn()

    def despertar(self):
        """Ida y vuelta mínima (menos de un píxel): el escritorio la cuenta como actividad y no apaga la
        pantalla, y no se ve."""
        for x in (self.x - 32 if self.x >= 32 else self.x + 32, self.x):
            self.ui.write(e.EV_ABS, e.ABS_X, x)
            self.ui.syn()

    def esconder(self):
        """Wayland no permite ocultar el cursor: se deja en la esquina inferior derecha, donde solo asoma
        la punta (1 px)."""
        self.mover_a(1.0, 1.0)

    def scroll(self, v, h):
        """Rueda de alta resolución (120 = un paso) y, al completar pasos, la rueda clásica."""
        self.av += v * 120
        self.ah += h * 120
        iv, ih = int(self.av), int(self.ah)
        self.av -= iv
        self.ah -= ih
        for hi, lo, val, attr in ((REL_WHEEL_HI_RES, e.REL_WHEEL, iv, "lv"),
                                  (REL_HWHEEL_HI_RES, e.REL_HWHEEL, ih, "lh")):
            if val:
                self.ui.write(e.EV_REL, hi, val)
                acc = getattr(self, attr) + val
                pasos = int(acc / 120)
                if pasos:
                    self.ui.write(e.EV_REL, lo, pasos)
                setattr(self, attr, acc - pasos * 120)
        if iv or ih:
            self.ui.syn()

    def boton(self, b, valor):
        self.ui.write(e.EV_KEY, BOTONES[b], valor)
        self.ui.syn()

    def cerrar(self):
        self.ui.close()


def tamano_pantalla(fija=None):
    """Resolución lógica del escritorio (px). `fija` = 'ANCHOxALTO' de la configuración, si la hay."""
    if fija:
        w, h = fija.lower().split("x")
        return int(w), int(h)
    user = os.environ.get("SUDO_USER")
    uid = os.environ.get("SUDO_UID", str(os.getuid()))
    env = ["env", "DISPLAY=:0"]
    auth = glob.glob("/run/user/%s/.mutter-Xwaylandauth.*" % uid)
    if auth:
        env.append("XAUTHORITY=" + auth[0])
    cmd = (["sudo", "-u", user] if user and os.geteuid() == 0 else []) + env + ["xrandr", "--current"]
    try:
        out = subprocess.run(cmd, capture_output=True, text=True, timeout=5).stdout
        m = re.search(r"current (\d+) x (\d+)", out)
        if m:
            return int(m.group(1)), int(m.group(2))
    except (OSError, subprocess.SubprocessError):
        pass  # sin xrandr: valor por defecto
    print("No pude detectar la resolución; uso 1920x1080 (ajusta con: config --screen WxH)")
    return 1920, 1080
