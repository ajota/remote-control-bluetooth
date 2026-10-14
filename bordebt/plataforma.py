"""Elige los adaptadores del sistema operativo actual.

Cada característica que depende del sistema operativo tiene un módulo (o paquete) por plataforma con el
mismo nombre que `NOMBRE`: `linux`, y en el futuro `windows` y `macos`. La lógica de la característica no
importa nunca esos módulos directamente: los pide aquí.
"""
import importlib
import os
import sys

NOMBRE = {"linux": "linux", "darwin": "macos", "win32": "windows"}.get(sys.platform, sys.platform)


def adaptador(caracteristica):
    """Módulo de la plataforma actual para `caracteristica` (p. ej. 'entrada' o 'hid_bluetooth')."""
    paquete = "bordebt.caracteristicas.%s" % caracteristica
    try:
        return importlib.import_module("%s.%s" % (paquete, NOMBRE))
    except ModuleNotFoundError as ex:
        if ex.name and ex.name.startswith(paquete):
            sys.exit("borde_bt todavía no soporta '%s' en %s (falta %s.%s)." % (caracteristica, NOMBRE, paquete, NOMBRE))
        raise


def es_admin():
    if NOMBRE == "windows":
        import ctypes
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    return os.geteuid() == 0


def requiere_privilegios():
    """Las funciones de bajo nivel (Bluetooth, capturar el teclado) necesitan administrador."""
    if not es_admin():
        sys.exit("Ejecuta como administrador." if NOMBRE == "windows" else
                 "Ejecuta con sudo (necesita Bluetooth de bajo nivel y acceso al teclado/trackpad).")
