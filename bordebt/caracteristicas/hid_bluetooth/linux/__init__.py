"""Adaptador Linux de hid_bluetooth: BlueZ (D-Bus), sockets L2CAP y política de radio."""
from bordebt.caracteristicas.hid_bluetooth.linux.bluez import BlueZ, ErrorBT
from bordebt.caracteristicas.hid_bluetooth.linux.l2cap import EnlaceL2CAP as Enlace, GestorBT, psm_libre
from bordebt.caracteristicas.hid_bluetooth.linux.radio import Radio

__all__ = ["BlueZ", "ErrorBT", "Enlace", "GestorBT", "psm_libre", "Radio"]
