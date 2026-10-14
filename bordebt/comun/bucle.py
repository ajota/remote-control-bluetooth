"""Bucle de eventos mínimo sobre descriptores (select). Válido en Linux y macOS; Windows necesitará su
propia implementación (allí select solo admite sockets)."""
import select
import time


def esperar(manejadores, timeout):
    """Espera hasta `timeout` s y llama al manejador de cada descriptor listo. Devuelve los listos."""
    listos, _, _ = select.select(list(manejadores), [], [], max(0.0, timeout))
    for fd in listos:
        h = manejadores.get(fd)
        if h:
            h()
    return listos


def atender(fuentes, segundos):
    """Atiende los descriptores que da `fuentes()` durante `segundos`."""
    fin = time.monotonic() + segundos
    while time.monotonic() < fin:
        esperar(fuentes(), fin - time.monotonic())
