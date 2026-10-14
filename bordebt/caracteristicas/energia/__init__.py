"""Característica: saber si la pantalla está apagada o el equipo se va a suspender (para pausar).

- linux.py : estado de la pantalla (DPMS en sysfs) y suspensión (señal PrepareForSleep de logind).

Contrato de cada plataforma (`<plataforma>.py`):
  MonitorEnergia(bus)   pantalla_encendida(ahora) -> bool, durmiendo (bool), despertares (int, crece con
                        cada vuelta de una suspensión), fds() -> {fd: manejador}
"""
