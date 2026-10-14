#!/usr/bin/env python3
"""borde_bt: el teclado y el trackpad de la laptop como teclado/mouse Bluetooth de varias tablets y celulares,
saltando entre pantallas por los bordes.

Uso (como root):  sudo python3 borde_bt.py [comando]     (ver: python3 borde_bt.py --help)
El código está en el paquete `bordebt/` (ver README.md, sección Arquitectura).
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from bordebt.cli import main  # noqa: E402

if __name__ == "__main__":
    main()
