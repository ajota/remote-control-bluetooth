"""Protocolo HID sobre Bluetooth (HIDP): descriptor, registro SDP, reportes y respuestas de control.

Todo es independiente del sistema operativo: solo construye y entiende bytes.
"""
import struct

PSM_CTRL, PSM_INTR = 17, 19
HID_UUID = "00001124-0000-1000-8000-00805f9b34fb"

BOTONES = {"L": 1, "R": 2, "M": 4, "S": 8, "E": 16}   # bits del reporte de mouse

# Usos de la página "Consumer" (teclas multimedia y de sistema)
INICIO, ATRAS = 0x223, 0x224


def _descriptor():
    kb = bytes([  # Report ID 1: teclado (boot compatible) con LEDs
        0x05, 0x01, 0x09, 0x06, 0xA1, 0x01, 0x85, 0x01,
        0x05, 0x07, 0x19, 0xE0, 0x29, 0xE7, 0x15, 0x00, 0x25, 0x01,
        0x75, 0x01, 0x95, 0x08, 0x81, 0x02,
        0x95, 0x01, 0x75, 0x08, 0x81, 0x01,
        0x05, 0x08, 0x19, 0x01, 0x29, 0x05, 0x95, 0x05, 0x75, 0x01, 0x91, 0x02,
        0x95, 0x01, 0x75, 0x03, 0x91, 0x01,
        0x95, 0x06, 0x75, 0x08, 0x15, 0x00, 0x25, 0x65,
        0x05, 0x07, 0x19, 0x00, 0x29, 0x65, 0x81, 0x00,
        0xC0])
    ms = bytes([  # Report ID 2: mouse 5 botones, X/Y 16 bits, rueda y desplazamiento horizontal
        0x05, 0x01, 0x09, 0x02, 0xA1, 0x01, 0x85, 0x02,
        0x09, 0x01, 0xA1, 0x00,
        0x05, 0x09, 0x19, 0x01, 0x29, 0x05, 0x15, 0x00, 0x25, 0x01,
        0x95, 0x05, 0x75, 0x01, 0x81, 0x02,
        0x95, 0x01, 0x75, 0x03, 0x81, 0x01,
        0x05, 0x01, 0x09, 0x30, 0x09, 0x31, 0x16, 0x01, 0x80, 0x26, 0xFF, 0x7F,
        0x75, 0x10, 0x95, 0x02, 0x81, 0x06,
        0x09, 0x38, 0x15, 0x81, 0x25, 0x7F, 0x75, 0x08, 0x95, 0x01, 0x81, 0x06,
        0x05, 0x0C, 0x0A, 0x38, 0x02, 0x15, 0x81, 0x25, 0x7F, 0x75, 0x08, 0x95, 0x01, 0x81, 0x06,
        0xC0, 0xC0])
    cc = bytes([  # Report ID 3: teclas multimedia (volumen, reproducir, inicio, atrás...)
        0x05, 0x0C, 0x09, 0x01, 0xA1, 0x01, 0x85, 0x03,
        0x15, 0x00, 0x26, 0xFF, 0x03, 0x19, 0x00, 0x2A, 0xFF, 0x03,
        0x75, 0x10, 0x95, 0x01, 0x81, 0x00,
        0xC0])
    return kb + ms + cc


DESCRIPTOR = _descriptor()

SDP_RECORD = """<?xml version="1.0" encoding="UTF-8" ?>
<record>
 <attribute id="0x0001"><sequence><uuid value="0x1124"/></sequence></attribute>
 <attribute id="0x0004"><sequence>
  <sequence><uuid value="0x0100"/><uint16 value="0x0011"/></sequence>
  <sequence><uuid value="0x0011"/></sequence></sequence></attribute>
 <attribute id="0x0005"><sequence><uuid value="0x1002"/></sequence></attribute>
 <attribute id="0x0006"><sequence><uint16 value="0x656e"/><uint16 value="0x006a"/><uint16 value="0x0100"/></sequence></attribute>
 <attribute id="0x0009"><sequence><sequence><uuid value="0x1124"/><uint16 value="0x0100"/></sequence></sequence></attribute>
 <attribute id="0x000d"><sequence><sequence>
  <sequence><uuid value="0x0100"/><uint16 value="0x0013"/></sequence>
  <sequence><uuid value="0x0011"/></sequence></sequence></sequence></attribute>
 <attribute id="0x0100"><text value="Laptop Teclado y Mouse"/></attribute>
 <attribute id="0x0101"><text value="Teclado y mouse"/></attribute>
 <attribute id="0x0102"><text value="Linux"/></attribute>
 <attribute id="0x0200"><uint16 value="0x0100"/></attribute>
 <attribute id="0x0201"><uint16 value="0x0111"/></attribute>
 <attribute id="0x0202"><uint8 value="0xc0"/></attribute>
 <attribute id="0x0203"><uint8 value="0x00"/></attribute>
 <attribute id="0x0204"><boolean value="true"/></attribute>
 <attribute id="0x0205"><boolean value="true"/></attribute>
 <attribute id="0x0206"><sequence><sequence><uint8 value="0x22"/><text encoding="hex" value="%s"/></sequence></sequence></attribute>
 <attribute id="0x0207"><sequence><sequence><uint16 value="0x0409"/><uint16 value="0x0100"/></sequence></sequence></attribute>
 <attribute id="0x020b"><uint16 value="0x0100"/></attribute>
 <attribute id="0x020c"><uint16 value="0x0c80"/></attribute>
 <attribute id="0x020d"><boolean value="true"/></attribute>
 <attribute id="0x020e"><boolean value="false"/></attribute>
</record>
""" % DESCRIPTOR.hex()


def reporte_teclado(mods, teclas):
    k = (list(teclas) + [0] * 6)[:6]
    return struct.pack("BBB6B", 1, mods, 0, *k)


def reporte_consumo(uso):
    return struct.pack("<BH", 3, uso)


def reportes_raton(botones, dx, dy, rueda=0, pan=0, boot=False):
    """Reportes de mouse para ese movimiento (varios si excede el rango de un reporte)."""
    lim = 127 if boot else 32767
    while True:
        cx, cy = max(-lim, min(lim, dx)), max(-lim, min(lim, dy))
        cr, cp = max(-127, min(127, rueda)), max(-127, min(127, pan))
        if boot:
            yield struct.pack("<Bbbb", 2, botones, cx, cy)
        else:
            yield struct.pack("<BBhhbb", 2, botones, cx, cy, cr, cp)
        dx, dy, rueda, pan = dx - cx, dy - cy, rueda - cr, pan - cp
        if not (dx or dy or rueda or pan):
            return


def responder_control(datos, boot):
    """Responde a una petición HIDP del canal de control.
    Devuelve (respuesta o None, nuevo valor de boot, seguir conectado)."""
    tipo, param = datos[0] >> 4, datos[0] & 0x0F
    if tipo == 0x1:                           # HID_CONTROL
        return None, boot, param != 5         # 5 = virtual cable unplug
    if tipo == 0x4:                           # GET_REPORT
        rid = datos[1] if len(datos) > 1 else 0
        vacio = {1: bytes(8), 2: bytes(3 if boot else 7), 3: bytes(2)}
        if (param & 3) == 1 and rid in vacio:
            return bytes([0xA1, rid]) + vacio[rid], boot, True
        return b"\x02", boot, True            # ERR_INVALID_REPORT_ID
    if tipo in (0x5, 0x7, 0x9):               # SET_REPORT / SET_PROTOCOL / SET_IDLE
        if tipo == 0x7:
            boot = (param & 1) == 0
        return b"\x00", boot, True
    if tipo == 0x6:                           # GET_PROTOCOL
        return bytes([0xA0, 0 if boot else 1]), boot, True
    if tipo == 0x8:                           # GET_IDLE
        return b"\xa0\x00", boot, True
    if tipo in (0x0, 0xA):
        return None, boot, True
    return b"\x03", boot, True                # ERR_UNSUPPORTED_REQUEST
