"""Tipos de argumento de línea de comandos compartidos por varias características."""
import argparse

from bordebt.comun.disposicion import normalizar_lado, normalizar_mac


def lado(valor):
    try:
        return normalizar_lado(valor)
    except ValueError as ex:
        raise argparse.ArgumentTypeError(str(ex))


def mac(valor):
    try:
        return normalizar_mac(valor)
    except ValueError as ex:
        raise argparse.ArgumentTypeError(str(ex))
