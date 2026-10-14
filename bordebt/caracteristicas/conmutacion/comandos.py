"""Comando `run`: arma la conmutación con los adaptadores de la plataforma y corre el bucle."""
import atexit
import sys
import time

from bordebt import plataforma
from bordebt.comun import bucle, diagnostico
from bordebt.comun.config import COMANDO
from bordebt.comun.disposicion import LADO_ES, construir_vecinos
from bordebt.caracteristicas.conmutacion.destinos import DestinoLocal, DestinoRemoto
from bordebt.caracteristicas.conmutacion.motor import Motor
from bordebt.caracteristicas.conmutacion.reposo import Reposo


def registrar(sub):
    sub.add_parser("run", help="ejecutar (por defecto)").set_defaults(func=cmd_run)


def cmd_run(a, cfg):
    plataforma.requiere_privilegios()
    devs = cfg["devices"]
    if not devs:
        sys.exit("No hay dispositivos. Empareja uno: %s pair tablet --side derecha" % COMANDO)
    try:
        vec = construir_vecinos(devs)
    except ValueError as ex:
        sys.exit(str(ex))
    bt = plataforma.adaptador("hid_bluetooth")
    entrada = plataforma.adaptador("entrada")
    sistema = plataforma.adaptador("conmutacion")
    energia = plataforma.adaptador("energia")

    w, h = sistema.tamano_pantalla(cfg.get("screen"))
    bz = bt.BlueZ()
    bz.encender()
    bz.registrar_perfil()
    enlaces = {d["mac"].upper(): bt.Enlace(d["mac"]) for d in devs}
    gestor = bt.GestorBT(enlaces, seguro=cfg["secure"], reintento=cfg["reconnect"],
                         reintento_max=cfg["reconnect_max"], intentos=cfg["reconnect_tries"])
    radio = bt.Radio(bz.id_adaptador, enlaces)
    radio.qos = cfg.get("qos", True)
    if not cfg.get("allow_sniff", False):
        radio.preparar()
        atexit.register(radio.restaurar)

    puntero = sistema.PunteroUinput()
    local = DestinoLocal(puntero, w, h, cfg["margin"])
    remotos = {d["name"]: DestinoRemoto(d, enlaces[d["mac"].upper()], cfg) for d in devs}
    motor = Motor(vec, local, remotos, gestor, radio=radio)
    motor.speed, motor.remote_speed, motor.remote_accel = cfg["speed"], cfg["remote_speed"], cfg["remote_accel"]
    captura = entrada.Captura(motor, motor.tecla, cfg)
    motor.teclado_local = captura.teclado_local
    motor.entradas = captura.interpretes
    gestor.al_cambiar = motor.enlace_cambio
    monitor = energia.MonitorEnergia(getattr(bz, "bus", None))
    reposo = Reposo(motor, gestor, captura, puntero, pausar_pantalla=cfg["pause_screen_off"],
                    mantener_despierta=cfg["keep_awake"])
    captura.capturar()

    print("Pantalla de la laptop: %dx%d" % (w, h))
    for d in devs:
        print("  '%s' a la %s de '%s'" % (d["name"], LADO_ES[d["side"]], d["of"]))
        if d.get("width", 0) < 300 or d.get("height", 0) < 300:
            print("  AVISO: '%s' no está bien calibrado (%sx%s): saltará en lugares equivocados.\n"
                  "         Ejecuta: %s calibrate %s" % (d["name"], d.get("width", "?"), d.get("height", "?"),
                                                         COMANDO, d["name"]))
    print("Listo. Empuja el cursor contra un borde para saltar. Ctrl+Alt+F12 alterna, Ctrl+Alt+Esc sale.")
    for mac in enlaces:
        gestor.reconectar(mac, forzar=True)
    try:
        while not motor.salir:
            ahora = time.monotonic()
            motor.tick(ahora)
            reposo.tick(ahora, monitor.pantalla_encendida(ahora), monitor.durmiendo, monitor.despertares)
            gestor.tick(ahora)
            manejadores = captura.fuentes()
            manejadores.update(gestor.fds())
            manejadores.update(monitor.fds())
            bucle.esperar(manejadores, min(motor.espera(ahora), reposo.espera()))
            diagnostico.resumen(getattr(motor.t, "enlace", None))
    except KeyboardInterrupt:
        pass  # Ctrl+C: salir limpiamente
    finally:
        try:
            motor.t.soltar()
            motor.soltar_teclas_locales()
            local.mostrar()
        except OSError:
            pass  # dispositivo ya cerrado
        captura.liberar()
        puntero.cerrar()
        gestor.cerrar()
        radio.restaurar()
        print("\nFin.")
