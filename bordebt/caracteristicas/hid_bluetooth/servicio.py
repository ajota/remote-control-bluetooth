"""Casos de uso comunes de Bluetooth para varias características (calibrar, probar, emparejar)."""
import sys
import time

from bordebt import plataforma
from bordebt.comun import bucle
from bordebt.comun.config import buscar_dispositivo


def bt():
    """Adaptador Bluetooth de la plataforma actual."""
    return plataforma.adaptador("hid_bluetooth")


def preparar_adaptador(agente=False):
    """Enciende el adaptador y registra el perfil HID (y el agente de emparejamiento si se pide)."""
    plat = bt()
    bz = plat.BlueZ()
    bz.encender()
    bz.registrar_perfil()
    if agente:
        bz.registrar_agente()
    return bz


def conectar_uno(cfg, nombre):
    """Conecta con un solo dispositivo configurado. Devuelve (dispositivo, enlace, gestor)."""
    d = buscar_dispositivo(cfg, nombre)
    plat = bt()
    preparar_adaptador()
    en = plat.Enlace(d["mac"])
    gestor = plat.GestorBT({en.mac: en}, seguro=cfg["secure"], reintento=5)
    print("Esperando conexión con '%s' (enciende su Bluetooth y desbloquéalo)..." % nombre)
    limite = time.monotonic() + 60
    while not en.conectado and time.monotonic() < limite:
        gestor.tick(time.monotonic())
        bucle.esperar(gestor.fds(), 0.5)
    if not en.conectado:
        sys.exit("No se conectó.")
    print("Conectado.")
    return d, en, gestor


def atender(gestor, segundos):
    """Atiende las peticiones del anfitrión durante un rato."""
    bucle.atender(gestor.fds, segundos)
