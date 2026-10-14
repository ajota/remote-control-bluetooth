"""Puertos: lo que la conmutación necesita de la plataforma. Cada sistema operativo los implementa."""
from typing import Optional, Protocol


class PunteroLocal(Protocol):
    """El puntero de la laptop, controlado en coordenadas absolutas (para saber siempre dónde está)."""

    def mover_a(self, fx: float, fy: float) -> None:
        """Posición como fracción del escritorio (0..1)."""

    def esconder(self) -> None:
        """Dejarlo donde menos se vea (si el sistema no permite ocultarlo)."""

    def despertar(self) -> None:
        """Un movimiento imperceptible que el escritorio cuente como actividad (no apagar la pantalla)."""

    def boton(self, boton: str, valor: int) -> None:
        """'L', 'R', 'M', 'S' o 'E'; 1 presionado, 0 suelto."""

    def scroll(self, vertical: float, horizontal: float) -> None:
        """En pasos de rueda (pueden ser fraccionarios)."""

    def cerrar(self) -> None:
        """Liberar el dispositivo."""


class TecladoLocal(Protocol):
    """El teclado de la laptop cuando la laptop es el destino activo."""

    def reenviar(self, evento) -> None:
        """Entregar a la laptop una tecla capturada (entrada.eventos.EventoTecla)."""

    def soltar_todo(self) -> None:
        """Soltar las teclas que la laptop crea presionadas (al irnos a otro dispositivo)."""

    def presionar(self, uso: int, valor: int) -> None:
        """Presionar/soltar una tecla por su uso HID (p. ej. Ctrl para el zoom)."""

    def gesto(self, direccion: str) -> None:
        """Gesto de 3 dedos en la laptop, con el atajo equivalente del escritorio."""


class Conexiones(Protocol):
    def reconectar(self, mac: str, forzar: bool = False) -> None:
        """Intentar (re)conectar con un dispositivo."""

    def pausar(self) -> None:
        """Cerrar los enlaces y no aceptar ni buscar conexiones (reposo)."""

    def reanudar(self) -> None:
        """Volver a conectar con todos de inmediato."""


class CapturaLocal(Protocol):
    """La captura del teclado y el trackpad de la laptop (para el reposo)."""

    def pausar(self) -> None:
        """Soltarlos: que vayan directo al sistema."""

    def retomar(self) -> bool:
        """Volver a capturarlos. False (sin hacer nada) si hay teclas o botones presionados."""


class Radio(Protocol):
    def aplicar(self, mac_activo: Optional[str]) -> None:
        """Ajustar la radio para el dispositivo activo (None = la laptop)."""
