"""Característica: conmutar entre pantallas por los bordes (comando `run`).

- pantalla.py : modelo de una pantalla, recorte en bordes y empuje para saltar (puro).
- destinos.py : la laptop (puntero local) y cada dispositivo Bluetooth con su modelo calibrado (puro).
- motor.py    : enruta teclado y puntero al destino activo y decide los saltos (puro).
- reposo.py   : pausa con la pantalla apagada o en suspensión; laptop despierta mientras usas un dispositivo (puro).
- puertos.py  : lo que esta característica necesita de la plataforma.
- linux.py    : puntero absoluto uinput y resolución de la pantalla.
- comandos.py : el comando `run`, que arma todo con los adaptadores de la plataforma.
"""
