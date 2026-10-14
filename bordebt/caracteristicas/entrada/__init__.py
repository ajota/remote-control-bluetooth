"""Característica: capturar el teclado, el trackpad y los mouses físicos de la laptop.

- eventos.py : eventos neutros que entrega cualquier plataforma (códigos HID estándar, medidas en mm).
- linux.py   : evdev (captura exclusiva), teclado virtual uinput para la laptop y LEDs.

Contrato de cada plataforma (`<plataforma>.py`):
  Captura(acciones, al_teclear, cfg)   fuentes() -> {fd: manejador}, capturar(), liberar(), nombres,
                                       pausar(), retomar() -> bool (puerto CapturaLocal de conmutacion),
                                       teclado_local (puerto TecladoLocal de conmutacion), interpretes
  nombres_dispositivos()               -> (teclados, punteros) para diagnóstico
"""
