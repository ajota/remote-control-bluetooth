"""borde_bt: el teclado y el trackpad de la laptop como teclado/mouse Bluetooth de varias tablets y
celulares, saltando entre pantallas por los bordes.

Arquitectura: módulos por característica (vertical slices) en `caracteristicas/`. Cada característica
contiene su lógica pura y, aparte, sus adaptadores por sistema operativo (`linux.py` o `linux/`), que
`plataforma.adaptador()` elige al ejecutar. `comun/` es el núcleo compartido mínimo, sin dependencias
del sistema operativo.
"""
