import time
import unittest

import tests  # noqa: F401
from tests.dobles import ConexionesFalsas, EnlaceFalso, PunteroFalso, RadioFalsa, TecladoFalso, cfg, esperar
from bordebt.comun.disposicion import construir_vecinos
from bordebt.caracteristicas.conmutacion.destinos import DestinoLocal, DestinoRemoto
from bordebt.caracteristicas.conmutacion.motor import Motor
from bordebt.caracteristicas.entrada.eventos import EventoTecla

DEVS = [{"name": "tablet", "mac": "AA:AA:AA:AA:AA:01", "side": "right", "of": "laptop", "width": 1000, "height": 600},
        {"name": "cel", "mac": "AA:AA:AA:AA:AA:02", "side": "left", "of": "laptop", "width": 400, "height": 800},
        {"name": "cel2", "mac": "AA:AA:AA:AA:AA:03", "side": "right", "of": "tablet", "width": 400, "height": 800}]


def armar(cel_conectado=False):
    c = cfg()
    enl = {d["name"]: EnlaceFalso(d["mac"]) for d in DEVS}
    enl["cel"].on = cel_conectado
    puntero = PunteroFalso()
    local = DestinoLocal(puntero, 1000, 500, 25)
    remotos = {d["name"]: DestinoRemoto(d, enl[d["name"]], c) for d in DEVS}
    m = Motor(construir_vecinos(DEVS), local, remotos, ConexionesFalsas(), TecladoFalso(), RadioFalsa())
    return m, enl, puntero


def empujar(m, dx, dy, pasos=200):
    antes = m.activo
    for _ in range(pasos):
        m.movimiento(dx, dy)
        time.sleep(0.004)
        if m.activo != antes:
            return


class Saltos(unittest.TestCase):
    def test_recorrido_en_cadena_y_vuelta(self):
        m, enl, puntero = armar()
        m.pant["laptop"].p.y = 200
        empujar(m, 20, 0)
        self.assertEqual(m.activo, "tablet")
        self.assertTrue(puntero.escondido)                     # cursor de la laptop escondido
        empujar(m, 30, 0)
        self.assertEqual(m.activo, "cel2")
        empujar(m, -30, 0)
        self.assertEqual(m.activo, "tablet")
        empujar(m, -30, 0)
        self.assertEqual(m.activo, "laptop")
        self.assertEqual(m.pant["laptop"].p.x, 1000)           # reaparece en el borde por el que volvió

    def test_dispositivo_desconectado_es_pared(self):
        m, enl, _ = armar()
        empujar(m, -40, 0, 60)
        self.assertEqual(m.activo, "laptop")
        self.assertIn("AA:AA:AA:AA:AA:02", m.conexiones.pedidas)

    def test_desconexion_del_activo_vuelve_a_la_laptop(self):
        m, enl, _ = armar()
        empujar(m, 20, 0)
        m.enlace_cambio(enl["tablet"], False)
        self.assertEqual(m.activo, "laptop")

    def test_radio_activa_solo_el_destino(self):
        m, enl, _ = armar()
        empujar(m, 20, 0)
        self.assertEqual(m.radio.activos[-1], "AA:AA:AA:AA:AA:01")


class Entradas(unittest.TestCase):
    def test_entrada_atomica_y_altura_tras_aparcar(self):
        m, enl, _ = armar()
        t = m.pant["tablet"]
        empujar(m, 20, 0)
        self.assertEqual(len(enl["tablet"].enviados), 1)     # primera entrada: un solo reporte
        r = enl["tablet"].ratones()[0]
        self.assertTrue(r[2] <= -3000 and r[3] == 0)         # altura desconocida: no se toca
        m.cambiar("laptop", "right", 0.5)
        enl["tablet"].enviados.clear()
        m.cambiar("tablet", "left", 0.25)
        rs = enl["tablet"].ratones()
        self.assertEqual(len(rs), 1)
        self.assertEqual(rs[0][3], round(0.25 * 600 - 600))  # borde + altura en el mismo reporte
        self.assertAlmostEqual(t.p.y, 150)

    def test_salida_esconde_primero_con_un_solo_reporte(self):
        m, enl, _ = armar()
        m.cambiar("tablet", "left", 0.5)
        m.movimiento(5, 0)
        enl["tablet"].enviados.clear()
        m.cambiar("laptop", "right", 0.5)
        self.assertEqual([r[1:4] for r in enl["tablet"].ratones()], [(0, 4000, 4000)])

    def test_salida_arrastrando_suelta_antes(self):
        m, enl, _ = armar()
        m.cambiar("tablet", "left", 0.5)
        m.boton("L", 1)
        enl["tablet"].enviados.clear()
        m.cambiar("laptop", "right", 0.5)
        self.assertEqual([r[1:4] for r in enl["tablet"].ratones()], [(0, 0, 0), (0, 4000, 4000)])

    def test_esconder_tras_conectar_y_cancelar_al_entrar(self):
        m, enl, _ = armar()
        m.enlace_cambio(enl["tablet"], True)
        self.assertEqual(enl["tablet"].enviados, [])          # nada al instante
        esperar(1.2, m.tick)
        self.assertEqual(len(enl["tablet"].ratones()), 2)    # a los 0.5 y 1.0 s
        m.cambiar("tablet", "left", 0.5)
        n = len(enl["tablet"].enviados)
        esperar(1.0, m.tick)
        self.assertEqual(len(enl["tablet"].enviados), n)     # cancelado al entrar


class Teclado(unittest.TestCase):
    def test_laptop_reenvia_y_dispositivo_recibe_hid(self):
        m, enl, _ = armar()
        m.tecla(EventoTecla(0x04, 1, nativo=30))
        self.assertIn((0x04, 1), m.teclado_local.reenviadas)
        m.cambiar("tablet", "left", 0.5)
        m.tecla(EventoTecla(0x05, 1, nativo=48))
        self.assertEqual(enl["tablet"].teclados()[-1], bytes([1, 0, 0, 5, 0, 0, 0, 0, 0]))

    def test_atajo_ctrl_alt_f12_cicla(self):
        m, enl, _ = armar()
        for uso, nat in ((0xE0, 29), (0xE2, 56)):
            m.tecla(EventoTecla(uso, 1, nativo=nat))
        m.tecla(EventoTecla(0x45, 1, nativo=88))
        self.assertEqual(m.activo, "tablet")
        self.assertEqual(m.teclado_local.soltado, 1)         # se soltaron las teclas de la laptop
        m.tecla(EventoTecla(0x45, 0, nativo=88))              # la F12 tragada no llega a nadie
        self.assertEqual(enl["tablet"].teclados(), [])

    def test_gestos_y_zoom(self):
        m, enl, _ = armar()
        m.gesto("arriba")
        self.assertEqual(m.teclado_local.gestos, ["arriba"])
        m.cambiar("tablet", "left", 0.5)
        m.gesto("izquierda")
        self.assertEqual(enl["tablet"].consumos(), [0x224, 0])
        m.pellizco(2)
        m.pellizco_fin()
        mods = [r[1] for r in enl["tablet"].teclados()]
        self.assertEqual(mods, [1, 0])                        # Ctrl presionado y suelto


class GananciaRemota(unittest.TestCase):
    def test_compensa_solo_lo_que_falta(self):
        m, enl, _ = armar()
        c = cfg()
        m.pant["tab"] = DestinoRemoto({"name": "tab", "side": "left", "accel": 1.95}, enl["tablet"], c)
        m.pant["mov"] = DestinoRemoto({"name": "mov", "side": "left", "accel": 0.89, "slow_gain": 0.5},
                                      enl["cel"], c)
        m.activo = "tab"
        self.assertAlmostEqual(m.px_por_mm(10), 10.0)
        self.assertLess(m.px_por_mm(300), 10.5)               # la tablet ya acelera: casi nada
        m.activo = "mov"
        self.assertGreater(m.px_por_mm(5), 18)                # frena lo lento: se refuerza
        self.assertGreater(m.px_por_mm(300), 20)              # no acelera: se completa


class Salto(unittest.TestCase):
    """El puntero real (dispositivo simulado con aceleración) debe estar en el borde al saltar."""

    def _sesion(self, acel_real, acel_modelo, idas):
        c = cfg()
        d = {"name": "t", "side": "left", "width": 2535, "height": 1628, "accel": acel_modelo}

        class Host(EnlaceFalso):
            def raton_inmediato(s, b, dx=0, dy=0, *a):
                s.x = 0 if dx < -5000 else (r.p.w if dx > 5000 else s.x)
                return True

            def raton(s, b, dx=0, dy=0, *a):
                v = r.v_host
                k = 1 if v <= 500 else 1 + min(1, (v - 500) / 2500) * (acel_real - 1)
                s.x = min(max(s.x + dx * k, 0), r.p.w)
                return True
        h = Host()
        r = DestinoRemoto(d, h, c)
        h.x = r.p.w
        r.entrar("right", 0.5)
        for _ in range(idas):
            for _ in range(40):
                r.mover(-15, 0, {"right"})
                time.sleep(0.006)
            for _ in range(40):
                r.mover(15, 0, {"right"})
                time.sleep(0.006)
        for _ in range(40):
            r.mover(-15, 0, {"right"})
            time.sleep(0.006)
        extra = 0
        for _ in range(2000):
            if h.x >= r.p.w:
                extra += 5
            if r.mover(5, 0, {"right"}):
                return h.x, extra
            time.sleep(0.006)
        return None, None

    def test_no_salta_antes_del_borde(self):
        for real, modelo in ((3, 2.5), (2, 3)):
            x, _ = self._sesion(real, modelo, 2)
            self.assertIsNotNone(x)
            self.assertGreaterEqual(x, 2535 * 0.97, (real, modelo))

    def test_empuje_extra_no_crece_con_el_uso(self):
        _, corto = self._sesion(1.95, 1.95, 2)
        _, largo = self._sesion(1.95, 1.95, 15)
        self.assertLess(largo, 300)
        self.assertLess(abs(largo - corto), 100)


if __name__ == "__main__":
    unittest.main()
