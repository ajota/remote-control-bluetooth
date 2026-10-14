"""Característica: emular un teclado + mouse Bluetooth (HID) ante tablets y celulares.

- protocolo.py : descriptor HID, registro SDP, formato de los reportes y respuestas de control (puro).
- enlace.py    : un enlace con un anfitrión: reportes y agrupación del movimiento cuando la radio no da
                 abasto (puro; el transporte lo pone cada plataforma).
- servicio.py  : casos de uso comunes (conectar con un dispositivo, atender sus peticiones).
- reconexion.py: cuándo volver a buscar un dispositivo desconectado (espera creciente y pausa; puro).
- linux/       : BlueZ (D-Bus), sockets L2CAP y política de radio (hciconfig/hcitool).

Contrato que debe cumplir cada plataforma (módulo `<plataforma>/__init__.py`):
  BlueZ()                      encender(), registrar_perfil(), registrar_agente(), visible(bool),
                               confiar(mac), alias(mac), nombre_visible(), id_adaptador,
                               encendido(), clase(), emparejado(mac)
  GestorBT(enlaces, seguro, reintento, desconocido, reintento_max, intentos)
                               fds() -> {fd: manejador}, reconectar(mac, forzar), tick(ahora), cerrar(),
                               pausar(), reanudar(),
                               al_cambiar(enlace, conectado)
  Enlace(mac)                  subclase de enlace.Enlace
  Radio(id_adaptador, macs)    preparar(), aplicar(mac_activo), restaurar(), qos
"""
