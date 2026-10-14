"""BlueZ por D-Bus: adaptador, perfil HID (registro SDP) y agente de emparejamiento."""
import sys
import threading
import time

try:
    import dbus
    import dbus.mainloop.glib
    import dbus.service
    from gi.repository import GLib
except ImportError as ex:
    sys.exit("Falta un módulo (%s). Instala: sudo apt install python3-dbus python3-gi" % ex)

from bordebt.caracteristicas.hid_bluetooth import protocolo

ErrorBT = dbus.DBusException


class PerfilHID(dbus.service.Object):
    @dbus.service.method("org.bluez.Profile1", in_signature="", out_signature="")
    def Release(self):
        pass  # BlueZ libera el perfil al cerrar: nada que limpiar

    @dbus.service.method("org.bluez.Profile1", in_signature="oha{sv}", out_signature="")
    def NewConnection(self, path, fd, props):
        pass  # las conexiones se atienden con sockets L2CAP propios (l2cap.py)

    @dbus.service.method("org.bluez.Profile1", in_signature="o", out_signature="")
    def RequestDisconnection(self, path):
        pass  # ídem


class AgenteBT(dbus.service.Object):
    """Acepta el emparejamiento sin códigos (solo se registra en el modo 'pair')."""
    I = "org.bluez.Agent1"

    @dbus.service.method(I, in_signature="", out_signature="")
    def Release(self):
        pass  # sin estado que limpiar

    @dbus.service.method(I, in_signature="o", out_signature="s")
    def RequestPinCode(self, dev):
        return "0000"

    @dbus.service.method(I, in_signature="o", out_signature="u")
    def RequestPasskey(self, dev):
        return dbus.UInt32(0)

    @dbus.service.method(I, in_signature="ouq", out_signature="")
    def DisplayPasskey(self, dev, passkey, entered):
        print("Código: %06d" % passkey)

    @dbus.service.method(I, in_signature="os", out_signature="")
    def DisplayPinCode(self, dev, pin):
        print("PIN:", pin)

    @dbus.service.method(I, in_signature="ou", out_signature="")
    def RequestConfirmation(self, dev, passkey):
        print("Aceptando emparejamiento (código %06d)" % passkey)

    @dbus.service.method(I, in_signature="o", out_signature="")
    def RequestAuthorization(self, dev):
        pass  # se autoriza (retornar sin error = aceptar)

    @dbus.service.method(I, in_signature="os", out_signature="")
    def AuthorizeService(self, dev, uuid):
        pass  # ídem

    @dbus.service.method(I, in_signature="", out_signature="")
    def Cancel(self):
        pass  # el emparejamiento se canceló desde el otro lado


class BlueZ:
    def __init__(self):
        dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)
        self.bus = dbus.SystemBus()
        om = dbus.Interface(self.bus.get_object("org.bluez", "/"), "org.freedesktop.DBus.ObjectManager")
        objs = om.GetManagedObjects()
        self.adaptador = next((p for p, ifs in objs.items() if "org.bluez.Adapter1" in ifs), None)
        if not self.adaptador:
            sys.exit("No encontré un adaptador Bluetooth.")
        self.props = dbus.Interface(self.bus.get_object("org.bluez", self.adaptador),
                                    "org.freedesktop.DBus.Properties")
        threading.Thread(target=GLib.MainLoop().run, daemon=True).start()

    @property
    def id_adaptador(self):
        return self.adaptador.rsplit("/", 1)[-1]          # p. ej. "hci0"

    def poner(self, clave, valor, intentos=20):
        """Cambia una propiedad del adaptador; si BlueZ está ocupado con otro cambio, reintenta."""
        for i in range(intentos):
            try:
                if self.leer(clave) == valor:
                    return
                self.props.Set("org.bluez.Adapter1", clave, valor)
                return
            except dbus.DBusException as ex:
                if ex.get_dbus_name() not in ("org.bluez.Error.Busy", "org.bluez.Error.InProgress",
                                              "org.bluez.Error.NotReady") or i == intentos - 1:
                    raise
                time.sleep(0.3)

    def leer(self, clave):
        return self.props.Get("org.bluez.Adapter1", clave)

    def encendido(self):
        return bool(self.leer("Powered"))

    def clase(self):
        return int(self.leer("Class"))

    def nombre_visible(self):
        return str(self.leer("Alias"))

    def encender(self):
        try:
            self.poner("Powered", dbus.Boolean(True))
            for _ in range(20):          # esperar a que termine de encender
                if self.leer("Powered"):
                    return
                time.sleep(0.25)
        except dbus.DBusException as ex:
            sys.exit("No se pudo encender el Bluetooth (%s). Actívalo en Ajustes o con: rfkill unblock bluetooth"
                     % (ex.get_dbus_message() or ex.get_dbus_name()))

    def visible(self, activar):
        """Emparejable + visible (o lo contrario), con mensaje claro si BlueZ no responde."""
        try:
            if activar:
                self.poner("Pairable", dbus.Boolean(True))
                self.poner("DiscoverableTimeout", dbus.UInt32(180))
            self.poner("Discoverable", dbus.Boolean(activar))
        except dbus.DBusException as ex:
            if not activar:
                return
            sys.exit("BlueZ no dejó poner la laptop visible (%s).\n"
                     "Cierra la ventana de Configuración > Bluetooth de Ubuntu, espera unos segundos y reintenta.\n"
                     "Si sigue: sudo systemctl restart bluetooth" % (ex.get_dbus_message() or ex.get_dbus_name()))

    def registrar_perfil(self):
        PerfilHID(self.bus, "/org/bluez/hidborde")
        mgr = dbus.Interface(self.bus.get_object("org.bluez", "/org/bluez"), "org.bluez.ProfileManager1")
        opts = {"ServiceRecord": protocolo.SDP_RECORD, "Role": "server",
                "RequireAuthentication": False, "RequireAuthorization": False, "AutoConnect": False}
        try:
            mgr.RegisterProfile("/org/bluez/hidborde", protocolo.HID_UUID, opts)
        except dbus.DBusException as ex:
            sys.exit("BlueZ rechazó el perfil HID (%s). ¿Ejecutaste 'setup'?" % ex.get_dbus_message())

    def registrar_agente(self):
        AgenteBT(self.bus, "/org/bluez/hidborde_agente")
        am = dbus.Interface(self.bus.get_object("org.bluez", "/org/bluez"), "org.bluez.AgentManager1")
        am.RegisterAgent("/org/bluez/hidborde_agente", "NoInputNoOutput")
        am.RequestDefaultAgent("/org/bluez/hidborde_agente")

    def _dev(self, mac):
        ruta = "%s/dev_%s" % (self.adaptador, mac.replace(":", "_"))
        return dbus.Interface(self.bus.get_object("org.bluez", ruta), "org.freedesktop.DBus.Properties")

    def confiar(self, mac):
        try:
            self._dev(mac).Set("org.bluez.Device1", "Trusted", dbus.Boolean(True))
        except dbus.DBusException:
            pass  # si no se puede marcar como confiable, el emparejamiento igual funciona

    def alias(self, mac):
        try:
            return str(self._dev(mac).Get("org.bluez.Device1", "Alias"))
        except dbus.DBusException:
            return mac

    def emparejado(self, mac):
        try:
            return bool(self._dev(mac).Get("org.bluez.Device1", "Paired"))
        except dbus.DBusException:
            return False
