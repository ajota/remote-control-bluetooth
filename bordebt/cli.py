"""Línea de comandos: cada característica registra sus propios comandos."""
import argparse
import sys

from bordebt.comun import config, diagnostico
from bordebt.caracteristicas.calibracion import comandos as calibracion
from bordebt.caracteristicas.configuracion import comandos as configuracion
from bordebt.caracteristicas.conmutacion import comandos as conmutacion
from bordebt.caracteristicas.dispositivos import comandos as dispositivos
from bordebt.caracteristicas.preparacion import comandos as preparacion

CARACTERISTICAS = (conmutacion, preparacion, dispositivos, configuracion, calibracion)


def construir_parser():
    ap = argparse.ArgumentParser(prog="borde_bt",
                                 description="Teclado y trackpad de la laptop como dispositivo Bluetooth "
                                             "para varias tablets/celulares, con salto por bordes.")
    ap.add_argument("--config", default=config.ruta_config(), help="archivo de configuración")
    sub = ap.add_subparsers(dest="cmd")
    for c in CARACTERISTICAS:
        c.registrar(sub)
    return ap


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if "--debug" in argv:   # se acepta en cualquier posición
        argv.remove("--debug")
        diagnostico.activar()
    a = construir_parser().parse_args(argv)
    cfg = config.cargar(a.config)
    (getattr(a, "func", None) or conmutacion.cmd_run)(a, cfg)
