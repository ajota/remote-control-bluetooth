"""Eventos de entrada independientes del sistema operativo.

Las teclas usan los códigos HID estándar (los mismos que viajan por Bluetooth), así la lógica no conoce los
códigos propios de cada sistema. El trackpad se describe en milímetros, cuadro a cuadro.
"""
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

# Usos HID de la página de teclado que usa la lógica
USO_ESC, USO_F12, USO_PAGEUP, USO_PAGEDOWN = 0x29, 0x45, 0x4B, 0x4E
USO_CTRL_IZQ, USO_META_IZQ = 0xE0, 0xE3
MOD_CTRL, MOD_ALT = 0x11, 0x44          # bits de modificador (izquierdo | derecho)


def es_modificador(uso):
    return uso is not None and 0xE0 <= uso <= 0xE7


def bit_modificador(uso):
    return 1 << (uso - 0xE0)


@dataclass
class EventoTecla:
    uso: Optional[int]        # uso HID (página teclado, o consumo si `consumo`); None si no tiene equivalente
    valor: int                # 1 presionada, 0 soltada, 2 repetición automática
    consumo: bool = False     # tecla multimedia/de sistema (página Consumer)
    nativo: object = None     # código propio de la plataforma (para reenviarlo a la laptop)
    origen: object = None     # de qué teclado físico vino


@dataclass
class CuadroTactil:
    """Estado del trackpad en un instante."""
    t: float                                   # tiempo (monotónico)
    dedos: int                                 # dedos en CONTACTO
    x: Optional[float]                         # mm desde la esquina superior izquierda (dedo principal)
    y: Optional[float]
    ancho: float                               # tamaño del trackpad en mm
    alto: float
    puntos: List[Tuple[float, float]] = field(default_factory=list)   # (x, y) en mm de cada dedo
    presion: bool = False                      # se presionó el clickpad en este cuadro
    suelta: bool = False                       # se soltó el clickpad
    botones: List[Tuple[str, int]] = field(default_factory=list)      # botones físicos dedicados
    resinc: bool = False                       # se perdieron eventos: no comparar con el cuadro anterior
