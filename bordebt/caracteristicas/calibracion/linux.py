"""Terminal en Linux (sirve igual para macOS): la entrada estándar se vigila con select junto al Bluetooth."""
import sys
import termios


def descriptor_entrada():
    return sys.stdin.fileno()


def descartar_entrada():
    """Ignora los Enter presionados antes de tiempo."""
    try:
        termios.tcflush(sys.stdin, termios.TCIFLUSH)
    except (termios.error, OSError, ValueError):
        pass  # sin terminal (p. ej. entrada redirigida): no hay nada que descartar
