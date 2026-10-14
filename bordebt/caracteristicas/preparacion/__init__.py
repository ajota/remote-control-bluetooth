"""Característica: preparar el sistema (`setup`) y comprobar que todo esté listo (`status`).

- comandos.py : comprobaciones comunes (adaptador, dispositivos, teclado y trackpad).
- linux.py    : servicio bluetoothd (systemd), /etc/bluetooth/main.conf, rfkill.

Contrato de cada plataforma: aplicar(deshacer), comprobar_sistema(linea) -> bool (servicio en marcha).
"""
