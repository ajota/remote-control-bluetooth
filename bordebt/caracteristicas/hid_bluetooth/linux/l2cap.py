"""Transporte HID en Linux: sockets L2CAP (canales de control 17 e interrupción 19)."""
import fcntl
import os
import queue
import socket
import struct
import sys
import termios
import threading
import time

from bordebt.comun.config import COMANDO
from bordebt.comun.diagnostico import STATS, dbg
from bordebt.caracteristicas.hid_bluetooth import protocolo
from bordebt.caracteristicas.hid_bluetooth.enlace import Enlace
from bordebt.caracteristicas.hid_bluetooth.reconexion import Reintentos

SOL_BLUETOOTH, BT_SECURITY, BT_SECURITY_MEDIUM = 274, 4, 2


def socket_l2cap(seguro):
    s = socket.socket(socket.AF_BLUETOOTH, socket.SOCK_SEQPACKET, socket.BTPROTO_L2CAP)
    if seguro:
        try:
            s.setsockopt(SOL_BLUETOOTH, BT_SECURITY, struct.pack("BB", BT_SECURITY_MEDIUM, 0))
        except OSError:
            pass  # sin cifrado obligatorio: el enlace funciona igual
    return s


def psm_libre(psm=protocolo.PSM_CTRL):
    """True si nadie ocupa el canal HID (por ejemplo, el plugin 'input' de bluetoothd)."""
    s = socket_l2cap(False)
    try:
        s.bind((socket.BDADDR_ANY, psm))
        return True
    except OSError:
        return False
    finally:
        s.close()


class EnlaceL2CAP(Enlace):
    """Enlace HID sobre dos sockets L2CAP."""

    def __init__(self, mac):
        super().__init__(mac)
        self.ctrl = self.intr = None

    @property
    def conectado(self):
        return self.intr is not None

    def adjuntar(self, ctrl, intr):
        self.cerrar(avisar=False)
        for s in (ctrl, intr):
            s.settimeout(0.3)
        self.ctrl, self.intr = ctrl, intr
        self.reiniciar()

    def cerrar(self, avisar=True):
        estaba = self.conectado
        for s in (self.ctrl, self.intr):
            try:
                if s:
                    s.close()
            except OSError:
                pass  # ya estaba cerrado
        self.ctrl = self.intr = None
        if estaba and avisar and self.al_cerrar:
            self.al_cerrar(self)

    def _transmitir(self, datos):
        if not self.intr:
            return False
        try:
            self.intr.send(datos)
            return True
        except socket.timeout:
            STATS["timeouts"] += 1
            return True  # anfitrión lento: se pierde un paquete, no la conexión
        except OSError:
            self.cerrar()
            return False

    def cola(self):
        """En sockets Bluetooth, TIOCOUTQ devuelve el espacio LIBRE del búfer (no lo pendiente, como en
        TCP), así que lo pendiente es el tamaño del búfer menos ese valor."""
        try:
            libre = struct.unpack("i", fcntl.ioctl(self.intr.fileno(), termios.TIOCOUTQ, b"\0" * 4))[0]
            total = self.intr.getsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF)
            return max(0, total - libre)
        except (OSError, AttributeError, ValueError):
            return -1

    def manejar_ctrl(self):
        """Responde a las peticiones HIDP del anfitrión. False si se cerró."""
        try:
            d = self.ctrl.recv(1024)
        except socket.timeout:
            return True
        except OSError:
            d = b""
        if not d:
            return False
        dbg("control del host: %s" % d.hex())
        resp, self.boot, seguir = protocolo.responder_control(d, self.boot)
        if resp:
            try:
                self.ctrl.send(resp)
            except OSError:
                pass  # si no se puede responder, el anfitrión reintentará o cerrará
        return seguir

    def manejar_intr(self):
        """Descarta reportes de salida (LEDs). False si se cerró."""
        try:
            d = self.intr.recv(1024)
            dbg("interrupción del host: %s" % d.hex())
            return bool(d)
        except socket.timeout:
            return True
        except OSError:
            return False


class GestorBT:
    """Escucha conexiones entrantes, reconecta en segundo plano y atiende los canales."""

    def __init__(self, enlaces, seguro=True, reintento=20, desconocido=None, reintento_max=300, intentos=6):
        self.enlaces = enlaces
        self.seguro, self.desconocido = seguro, desconocido
        self.reintentos = Reintentos(reintento, reintento_max, intentos)
        self.al_cambiar = None
        self.srv = {}
        for psm in (protocolo.PSM_CTRL, protocolo.PSM_INTR):
            s = socket_l2cap(seguro)
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                s.bind((socket.BDADDR_ANY, psm))
            except OSError as ex:
                sys.exit("No pude usar el PSM %d (%s). El plugin 'input' de bluetoothd lo ocupa: "
                         "ejecuta una vez '%s setup'." % (psm, ex.strerror, COMANDO))
            s.listen(5)
            self.srv[s] = psm
        self.medio = {}
        self.resultados = queue.Queue()
        self.rp, self.wp = os.pipe()
        os.set_blocking(self.rp, False)
        self.en_curso = set()
        self.pausado = False
        for en in enlaces.values():
            en.al_cerrar = self._cerrado

    def fds(self):
        m = {s.fileno(): (lambda s=s: self._aceptar(s)) for s in self.srv}
        m[self.rp] = self._resultados
        for en in self.enlaces.values():
            if en.conectado:
                m[en.ctrl.fileno()] = lambda en=en, s=en.ctrl: self._atender(en, s, en.manejar_ctrl)
                m[en.intr.fileno()] = lambda en=en, s=en.intr: self._atender(en, s, en.manejar_intr)
        return m

    @staticmethod
    def _atender(en, sock, manejar):
        """Ambos canales pueden estar listos en la misma vuelta del bucle: si atender uno cerró (o
        reemplazó) el enlace, el otro manejador ya apunta a un socket viejo y no debe ejecutarse."""
        if sock is not en.ctrl and sock is not en.intr:
            return
        manejar() or en.cerrar()

    def _aceptar(self, srv):
        try:
            sock, info = srv.accept()
        except OSError:
            return
        addr = info[0].upper()
        canales = self.medio.setdefault(addr, {})
        if self.srv[srv] in canales:
            canales[self.srv[srv]].close()
        canales[self.srv[srv]] = sock
        if len(canales) == 2:
            del self.medio[addr]
            self._adjuntar(addr, canales[protocolo.PSM_CTRL], canales[protocolo.PSM_INTR])

    def _adjuntar(self, addr, ctrl, intr):
        en = self.enlaces.get(addr)
        if en is None and self.desconocido and self.desconocido(addr):
            en = self.enlaces[addr] = EnlaceL2CAP(addr)
            en.al_cerrar = self._cerrado
        if en is None or self.pausado:
            if en is None:
                print("Conexión de %s ignorada: no está configurado (usa 'pair' o 'add')." % addr)
            ctrl.close()
            intr.close()
            return
        en.adjuntar(ctrl, intr)
        self.reintentos.exito(addr)
        if self.al_cambiar:
            self.al_cambiar(en, True)

    def _cerrado(self, en):
        self.reintentos.exito(en.mac)       # se perdió una conexión que funcionaba: buscarlo pronto
        if self.al_cambiar:
            self.al_cambiar(en, False)

    def reconectar(self, mac, forzar=False):
        """Intenta conectar en segundo plano. Sin `forzar` respeta la espera creciente y la pausa; con
        `forzar` (el usuario quiere saltar a ese dispositivo) intenta ya."""
        ahora = time.monotonic()
        en = self.enlaces.get(mac)
        if not en or en.conectado or mac in self.en_curso or self.pausado:
            return
        if not forzar and not self.reintentos.toca(mac, ahora):
            return
        self.reintentos.intento(mac, ahora)
        self.en_curso.add(mac)
        threading.Thread(target=self._hilo_conectar, args=(mac,), daemon=True).start()

    def _hilo_conectar(self, mac):
        c = i = None
        try:
            c, i = socket_l2cap(self.seguro), socket_l2cap(self.seguro)
            c.settimeout(10)
            i.settimeout(10)
            c.connect((mac, protocolo.PSM_CTRL))
            i.connect((mac, protocolo.PSM_INTR))
            self.resultados.put((mac, c, i, None))
        except OSError as ex:
            for s in (c, i):
                if s:
                    s.close()
            self.resultados.put((mac, None, None, ex))
        os.write(self.wp, b"x")

    def _resultados(self):
        try:
            os.read(self.rp, 512)
        except BlockingIOError:
            pass  # ya se había leído el aviso
        while not self.resultados.empty():
            mac, c, i, err = self.resultados.get()
            self.en_curso.discard(mac)
            en = self.enlaces[mac]
            if c is None:
                n = self.reintentos.fallo(mac)
                if n == 1:
                    print("No se pudo conectar a %s (%s). Reintentaré." % (mac, err.strerror or err))
                elif n == self.reintentos.intentos:
                    print("%s no responde tras %d intentos: dejo de buscarlo para no ocupar la radio. Empuja "
                          "el cursor hacia él o conéctalo desde el dispositivo para reintentar." % (mac, n))
            elif en.conectado:      # ya entró por conexión entrante
                c.close()
                i.close()
            else:
                self._adjuntar(mac, c, i)

    def tick(self, ahora):
        for mac in self.enlaces:
            self.reconectar(mac)

    def pausar(self):
        """Reposo: cierra los enlaces y no acepta ni busca conexiones (la radio queda libre)."""
        self.pausado = True
        for en in self.enlaces.values():
            en.cerrar()

    def reanudar(self):
        """Fin del reposo (o vuelta de una suspensión): conectar con todos ya, con la espera base."""
        self.pausado = False
        for mac in self.enlaces:
            self.reintentos.exito(mac)
            self.reconectar(mac, forzar=True)

    def cerrar(self):
        for en in self.enlaces.values():
            en.cerrar(avisar=False)
        for s in self.srv:
            s.close()
