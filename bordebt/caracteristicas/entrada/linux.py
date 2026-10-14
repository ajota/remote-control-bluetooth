"""Adaptador Linux de entrada: evdev (captura exclusiva) y teclado virtual uinput para la laptop."""
import os
import struct
import sys
import time

try:
    import evdev
    from evdev import ecodes as e
except ImportError as ex:
    sys.exit("Falta un módulo (%s). Instala: sudo apt install python3-evdev" % ex)

from bordebt.comun.diagnostico import STATS
from bordebt.caracteristicas.entrada.eventos import (CuadroTactil, EventoTecla, USO_CTRL_IZQ, USO_META_IZQ,
                                                     USO_PAGEDOWN, USO_PAGEUP)
from bordebt.caracteristicas.gestos.interprete import InterpreteTactil

# ---------------------------------------------------------------- códigos evdev -> HID
MODS = {e.KEY_LEFTCTRL: 0xE0, e.KEY_LEFTSHIFT: 0xE1, e.KEY_LEFTALT: 0xE2, e.KEY_LEFTMETA: 0xE3,
        e.KEY_RIGHTCTRL: 0xE4, e.KEY_RIGHTSHIFT: 0xE5, e.KEY_RIGHTALT: 0xE6, e.KEY_RIGHTMETA: 0xE7}

TECLAS = {}
for _i, _c in enumerate("ABCDEFGHIJKLMNOPQRSTUVWXYZ"):
    TECLAS[getattr(e, "KEY_" + _c)] = 4 + _i
for _i in range(1, 10):
    TECLAS[getattr(e, "KEY_%d" % _i)] = 29 + _i
TECLAS[e.KEY_0] = 39
for _n, _u in [("ENTER", 40), ("ESC", 41), ("BACKSPACE", 42), ("TAB", 43),
               ("SPACE", 44), ("MINUS", 45), ("EQUAL", 46), ("LEFTBRACE", 47),
               ("RIGHTBRACE", 48), ("BACKSLASH", 49), ("SEMICOLON", 51),
               ("APOSTROPHE", 52), ("GRAVE", 53), ("COMMA", 54), ("DOT", 55),
               ("SLASH", 56), ("CAPSLOCK", 57), ("SYSRQ", 70), ("SCROLLLOCK", 71),
               ("PAUSE", 72), ("INSERT", 73), ("HOME", 74), ("PAGEUP", 75),
               ("DELETE", 76), ("END", 77), ("PAGEDOWN", 78), ("RIGHT", 79),
               ("LEFT", 80), ("DOWN", 81), ("UP", 82), ("NUMLOCK", 83),
               ("KPSLASH", 84), ("KPASTERISK", 85), ("KPMINUS", 86), ("KPPLUS", 87),
               ("KPENTER", 88), ("KP0", 98), ("KPDOT", 99), ("102ND", 100),
               ("COMPOSE", 101)]:
    TECLAS[getattr(e, "KEY_" + _n)] = _u
for _i in range(1, 10):
    TECLAS[getattr(e, "KEY_KP%d" % _i)] = 88 + _i
for _i in range(1, 13):
    TECLAS[getattr(e, "KEY_F%d" % _i)] = 57 + _i
TECLAS.update(MODS)

CONSUMO = {e.KEY_VOLUMEUP: 0xE9, e.KEY_VOLUMEDOWN: 0xEA, e.KEY_MUTE: 0xE2,
           e.KEY_PLAYPAUSE: 0xCD, e.KEY_NEXTSONG: 0xB5, e.KEY_PREVIOUSSONG: 0xB6,
           e.KEY_STOPCD: 0xB7, e.KEY_BRIGHTNESSUP: 0x6F, e.KEY_BRIGHTNESSDOWN: 0x70,
           e.KEY_HOMEPAGE: 0x223, e.KEY_BACK: 0x224, e.KEY_SEARCH: 0x221}

HID_A_EVDEV = {u: c for c, u in TECLAS.items()}

BOTON_DE_CODIGO = {e.BTN_LEFT: "L", e.BTN_RIGHT: "R", e.BTN_MIDDLE: "M", e.BTN_SIDE: "S", e.BTN_EXTRA: "E"}
REL_WHEEL_HI_RES = getattr(e, "REL_WHEEL_HI_RES", 0x0b)
REL_HWHEEL_HI_RES = getattr(e, "REL_HWHEEL_HI_RES", 0x0c)
DEDOS = {e.BTN_TOOL_FINGER: 1, e.BTN_TOOL_DOUBLETAP: 2, e.BTN_TOOL_TRIPLETAP: 3,
         e.BTN_TOOL_QUADTAP: 4, getattr(e, "BTN_TOOL_QUINTTAP", 0x148): 5}


def evento_tecla(codigo, valor, origen=None):
    """Traduce una tecla evdev a un evento neutro (códigos HID)."""
    if codigo in CONSUMO:
        return EventoTecla(CONSUMO[codigo], valor, consumo=True, nativo=codigo, origen=origen)
    return EventoTecla(TECLAS.get(codigo), valor, nativo=codigo, origen=origen)


# ---------------------------------------------------------------- descubrimiento
def buscar_dispositivos():
    teclados, trackpads, ratones = [], [], []
    for ruta in evdev.list_devices():
        d = evdev.InputDevice(ruta)
        if d.name.startswith("borde_bt") or e.INPUT_PROP_DIRECT in d.input_props():
            d.close()
            continue  # nuestros dispositivos virtuales y pantallas táctiles
        caps = d.capabilities()
        teclas = caps.get(e.EV_KEY, [])
        absx = [a[0] for a in caps.get(e.EV_ABS, [])]
        if e.KEY_A in teclas and e.KEY_SPACE in teclas:
            teclados.append(d)
        elif e.ABS_X in absx and e.BTN_TOUCH in teclas and e.BTN_TOOL_FINGER in teclas:
            trackpads.append(d)
        elif e.REL_X in caps.get(e.EV_REL, []) and e.BTN_LEFT in teclas:
            ratones.append(d)
        else:
            d.close()
    return teclados, trackpads, ratones


def nombres_dispositivos():
    teclados, trackpads, ratones = buscar_dispositivos()
    nombres = ([d.name for d in teclados], [d.name for d in trackpads + ratones])
    for d in teclados + trackpads + ratones:
        d.close()
    return nombres


def leer(dev):
    """Eventos disponibles del dispositivo; None si se desconectó."""
    try:
        eventos = list(dev.read())
    except BlockingIOError:
        return []
    except OSError:
        return None
    STATS["eventos"] += len(eventos)
    return eventos


# ---------------------------------------------------------------- teclado
class Teclados:
    """Teclados físicos capturados. Sus teclas se entregan como EventoTecla; para la laptop se reenvían a un
    teclado virtual (clon) que el escritorio usa normalmente. Implementa el puerto TecladoLocal."""

    def __init__(self, devs, al_teclear):
        self.devs, self.al_teclear = devs, al_teclear
        self.clones = {}       # ruta del teclado físico -> [uinput, teclas presionadas, físico]
        for d in devs:
            ui = evdev.UInput.from_device(d, name="borde_bt " + d.name)
            self.clones[d.path] = [ui, set(), d]

    def _leer(self, d):
        ui, _, _ = self.clones[d.path]
        for ev in leer(d) or []:
            if ev.type == e.EV_KEY:
                self.al_teclear(evento_tecla(ev.code, ev.value, d.path))
            else:
                ui.write(ev.type, ev.code, ev.value)   # SYN/MSC: inocuos aunque la laptop no esté activa

    def _leds(self, ui, fisico):
        """El compositor escribe los LEDs (Bloq Mayús) al teclado virtual; los pasamos al físico."""
        try:
            datos = os.read(ui.fd, 24 * 32)
        except (BlockingIOError, OSError):
            return
        tam = struct.calcsize("llHHi")
        for off in range(0, len(datos) - tam + 1, tam):
            _, _, tipo, cod, val = struct.unpack_from("llHHi", datos, off)
            if tipo == e.EV_LED:
                try:
                    fisico.set_led(cod, val)
                except OSError:
                    pass  # LED no disponible: no es crítico

    def fuentes(self):
        m = {}
        for d in self.devs:
            ui = self.clones[d.path][0]
            m[d.fd] = lambda d=d: self._leer(d)
            m[ui.fd] = lambda ui=ui, d=d: self._leds(ui, d)
        return m

    # ---- puerto TecladoLocal
    def reenviar(self, evento):
        ui, presionadas, _ = self.clones[evento.origen]
        ui.write(e.EV_KEY, evento.nativo, evento.valor)
        if evento.valor == 1:
            presionadas.add(evento.nativo)
        elif evento.valor == 0:
            presionadas.discard(evento.nativo)

    def soltar_todo(self):
        for ui, presionadas, _ in self.clones.values():
            for c in presionadas:
                ui.write(e.EV_KEY, c, 0)
            if presionadas:
                ui.syn()
            presionadas.clear()

    def _primero(self):
        return next(iter(self.clones.values()))[0] if self.clones else None

    def presionar(self, uso, valor):
        ui = self._primero()
        if ui and uso in HID_A_EVDEV:
            ui.write(e.EV_KEY, HID_A_EVDEV[uso], valor)
            ui.syn()

    GESTOS = {"arriba": (USO_META_IZQ,),                   # GNOME: vista de actividades
              "izquierda": (USO_META_IZQ, USO_PAGEDOWN),   # escritorio siguiente
              "derecha": (USO_META_IZQ, USO_PAGEUP)}       # escritorio anterior

    def gesto(self, direccion):
        """Deslizar con tres dedos en la laptop: los gestos nativos no llegan (el trackpad está capturado),
        así que se envían sus atajos de teclado."""
        ui = self._primero()
        usos = self.GESTOS.get(direccion)
        if not ui or not usos:
            return
        for u in usos:
            ui.write(e.EV_KEY, HID_A_EVDEV[u], 1)
        ui.syn()
        for u in reversed(usos):
            ui.write(e.EV_KEY, HID_A_EVDEV[u], 0)
        ui.syn()

    def cerrar(self):
        for ui, _, _ in self.clones.values():
            ui.close()


# ---------------------------------------------------------------- trackpad
class Touchpad:
    """Traduce los eventos evdev de un touchpad a CuadroTactil (mm, dedos en contacto)."""

    def __init__(self, dev, al_cuadro):
        self.dev, self.al_cuadro = dev, al_cuadro
        ax, ay = dev.absinfo(e.ABS_X), dev.absinfo(e.ABS_Y)
        self.rx = ax.resolution or max(1, ax.max - ax.min) / 100.0
        self.ry = ay.resolution or max(1, ay.max - ay.min) / 65.0
        self.x0, self.y0 = ax.min, ay.min
        self.ancho, self.alto = (ax.max - ax.min) / self.rx, (ay.max - ay.min) / self.ry
        self.x = self.y = None
        self.herr = {}
        self.toca_ev = False
        self.slots, self.slot = {}, 0
        self.presion = self.suelta = False
        self.botones = []
        self.descartando = self.resinc = self.abs_cuadro = False
        try:
            self.con_contacto = e.BTN_TOUCH in dev.capabilities().get(e.EV_KEY, [])
        except (OSError, AttributeError):
            self.con_contacto = True

    def evento(self, ev):
        if self.descartando:
            if ev.type == e.EV_SYN and ev.code == e.SYN_REPORT:
                self.descartando = False
                self._resincronizar()
            return
        if ev.type == e.EV_SYN and ev.code == getattr(e, "SYN_DROPPED", 3):
            STATS["perdidos"] += 1      # el kernel descartó eventos: el estado guardado ya no es fiable
            self.descartando = True
            return
        if ev.type == e.EV_KEY:
            if ev.code in DEDOS:
                self.herr[ev.code] = ev.value
            elif ev.code == e.BTN_TOUCH:
                self.toca_ev = bool(ev.value)
            elif ev.code == e.BTN_LEFT:          # clickpad: qué botón es lo decide el intérprete
                if ev.value == 1:
                    self.presion = True
                elif ev.value == 0:
                    self.suelta = True
            elif ev.code in (e.BTN_RIGHT, e.BTN_MIDDLE) and ev.value in (0, 1):
                self.botones.append((BOTON_DE_CODIGO[ev.code], ev.value))
        elif ev.type == e.EV_ABS:
            if ev.code == e.ABS_X:
                self.x, self.abs_cuadro = ev.value, True
            elif ev.code == e.ABS_Y:
                self.y, self.abs_cuadro = ev.value, True
            elif ev.code == e.ABS_MT_SLOT:
                self.slot = ev.value
            elif ev.code == e.ABS_MT_TRACKING_ID:
                if ev.value < 0:
                    self.slots.pop(self.slot, None)
                else:
                    self.slots[self.slot] = [None, None]
            elif ev.code in (e.ABS_MT_POSITION_X, e.ABS_MT_POSITION_Y):
                self.slots.setdefault(self.slot, [None, None])[ev.code == e.ABS_MT_POSITION_Y] = ev.value
        elif ev.type == e.EV_SYN and ev.code == e.SYN_REPORT:
            self.al_cuadro(self._cuadro(time.monotonic()))
            self.abs_cuadro = self.presion = self.suelta = self.resinc = False
            self.botones = []

    def resincronizar(self):
        """Tras una pausa sin leer: los eventos de ese rato ya los atendió el sistema; partir de cero."""
        self.descartando = False
        self._resincronizar()

    def _resincronizar(self):
        """Lee del kernel la posición actual y avisa que no se compare con el cuadro anterior."""
        try:
            self.x, self.y = self.dev.absinfo(e.ABS_X).value, self.dev.absinfo(e.ABS_Y).value
        except (OSError, AttributeError):
            pass  # se usará la última posición conocida
        self.slots.clear()      # se rellenan con las próximas posiciones
        self.resinc = True

    def _contar_dedos(self):
        """Dedos que TOCAN el touchpad. El contacto lo da BTN_TOUCH; BTN_TOOL_* solo dice cuántos dedos hay,
        y en touchpads con detección de proximidad (hover, como los Elan) siguen activos con el dedo flotando:
        un toque parecería no terminar nunca. Se pregunta al kernel en cada cuadro por si se perdió algo."""
        def contar(herramientas, toca):
            n = max([v for c, v in DEDOS.items() if herramientas(c)] or [0])
            if not self.con_contacto:            # touchpad sin BTN_TOUCH: solo queda BTN_TOOL_*
                return n or (1 if self.abs_cuadro else 0)
            return max(n, 1) if toca else 0
        por_eventos = contar(lambda c: self.herr.get(c), self.toca_ev)
        try:
            teclas = set(self.dev.active_keys())
        except (OSError, AttributeError):
            return por_eventos
        n = contar(lambda c: c in teclas, e.BTN_TOUCH in teclas)
        if n != por_eventos:
            STATS["desfases"] += 1
            self.herr = {c: int(c in teclas) for c in DEDOS}
            self.toca_ev = e.BTN_TOUCH in teclas
        return n

    def _mm(self, x, y):
        return (x - self.x0) / self.rx, (y - self.y0) / self.ry

    def _cuadro(self, ahora):
        xm, ym = self._mm(self.x, self.y) if self.x is not None and self.y is not None else (None, None)
        puntos = [self._mm(*p) for p in self.slots.values() if None not in p]
        return CuadroTactil(ahora, self._contar_dedos(), xm, ym, self.ancho, self.alto, puntos,
                            self.presion, self.suelta, list(self.botones), self.resinc)


# ---------------------------------------------------------------- mouse externo
class Raton:
    """Mouse externo (USB/receptor): se reenvía tal cual al destino activo."""

    def __init__(self, dev, acciones, factor):
        self.m, self.k = acciones, factor
        rels = dev.capabilities().get(e.EV_REL, [])
        self.hires, self.hhires = REL_WHEEL_HI_RES in rels, REL_HWHEEL_HI_RES in rels
        self.dx = self.dy = self.v = self.h = 0.0

    def evento(self, ev):
        if ev.type == e.EV_REL:
            if ev.code == e.REL_X:
                self.dx += ev.value
            elif ev.code == e.REL_Y:
                self.dy += ev.value
            elif ev.code == e.REL_WHEEL and not self.hires:
                self.v += ev.value
            elif ev.code == REL_WHEEL_HI_RES:
                self.v += ev.value / 120.0
            elif ev.code == e.REL_HWHEEL and not self.hhires:
                self.h += ev.value
            elif ev.code == REL_HWHEEL_HI_RES:
                self.h += ev.value / 120.0
        elif ev.type == e.EV_KEY and ev.code in BOTON_DE_CODIGO and ev.value in (0, 1):
            self.m.boton(BOTON_DE_CODIGO[ev.code], ev.value)
        elif ev.type == e.EV_SYN and ev.code == e.SYN_REPORT:
            if self.dx or self.dy:
                self.m.movimiento(self.dx * self.k, self.dy * self.k)
            if self.v or self.h:
                self.m.scroll(self.v, self.h)
            self.dx = self.dy = self.v = self.h = 0.0


# ---------------------------------------------------------------- captura completa
class Captura:
    """Todo lo que se captura de la laptop: teclados, trackpads (interpretados) y mouses. Implementa el
    puerto CapturaLocal de conmutacion (pausar/retomar para el reposo)."""

    ESPERA_TECLAS = 3.0     # s máximos esperando a que se suelten las teclas para retomar la captura

    def __init__(self, acciones, al_teclear, cfg):
        teclados, trackpads, ratones = buscar_dispositivos()
        if not teclados or not (trackpads or ratones):
            sys.exit("No encontré teclado y trackpad.")
        self.teclado_local = Teclados(teclados, al_teclear)
        self.interpretes = []
        self.lectores = []      # (dispositivo, función por evento)
        self.touchpads = []
        for d in trackpads:
            it = InterpreteTactil(acciones, cfg)
            self.interpretes.append(it)
            tp = Touchpad(d, it.cuadro)
            self.touchpads.append(tp)
            self.lectores.append((d, tp.evento))
        for d in ratones:
            self.lectores.append((d, Raton(d, acciones, cfg["mouse_speed"]).evento))
        self.devs = teclados + [d for d, _ in self.lectores]
        self.nombres = [d.name for d in self.devs]
        self.pausada, self._t_retomar = False, None

    def _leer(self, d, fn):
        evs = leer(d)
        if evs is None:
            print("Dispositivo desconectado:", d.name)
            self.lectores = [x for x in self.lectores if x[0] is not d]
            return
        for ev in evs:
            fn(ev)

    def fuentes(self):
        if self.pausada:
            return {}
        m = self.teclado_local.fuentes()
        m.update({d.fd: (lambda d=d, fn=fn: self._leer(d, fn)) for d, fn in self.lectores})
        return m

    def capturar(self):
        time.sleep(0.3)   # dar tiempo al escritorio a registrar los teclados virtuales
        for d in self.devs:
            try:
                d.grab()
                print("Usando:", d.name)
            except OSError as ex:
                print("No pude tomar %s (%s)" % (d.name, ex))

    def pausar(self):
        """Reposo: el teclado y el trackpad van directo al sistema y no se leen hasta retomar()."""
        for d in self.devs:
            try:
                d.ungrab()
            except OSError:
                pass  # ya liberado (p. ej. desconectado)
        self.pausada, self._t_retomar = True, None

    def _presionado(self):
        """¿Hay teclas o botones presionados, o un dedo en el trackpad? (BTN_TOOL_* no cuenta: sigue activo
        con el dedo flotando en algunos touchpads.)"""
        for d in self.devs:
            try:
                if any(c not in DEDOS for c in d.active_keys()):
                    return True
            except OSError:
                continue  # dispositivo desconectado
        return False

    def retomar(self):
        """Vuelve a capturar. Espera (False) mientras haya algo presionado: si se capturara a mitad de una
        pulsación, el sistema no vería soltarse la tecla y la daría por pegada. Tras ESPERA_TECLAS captura
        igual (una tecla que el kernel cree siempre presionada no debe impedirlo)."""
        ahora = time.monotonic()
        if self._t_retomar is None:
            self._t_retomar = ahora
        if self._presionado() and ahora - self._t_retomar < self.ESPERA_TECLAS:
            return False
        for d in self.devs:
            try:
                d.grab()
            except OSError as ex:
                print("No pude tomar %s (%s)" % (d.name, ex))
        for d in self.devs:          # lo que llegó durante la pausa ya lo atendió el sistema
            while leer(d):
                pass
        for tp in self.touchpads:
            tp.resincronizar()
        self.pausada, self._t_retomar = False, None
        return True

    def liberar(self):
        for d in self.devs:
            try:
                d.ungrab()
            except OSError:
                pass  # ya liberado (p. ej. desconectado)
        self.teclado_local.cerrar()
