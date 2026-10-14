"""Política de reconexión: cuándo volver a buscar un dispositivo desconectado (pura, sin sockets).

Buscar un dispositivo (paging) ocupa la radio varios segundos; en chips que comparten antena con el WiFi
(como los Intel) eso frena la red de toda la laptop. Por eso la espera entre intentos crece con cada fallo
y, tras varios seguidos, se deja de buscar en segundo plano hasta que el usuario intente saltar a él, el
dispositivo se conecte solo o se pierda una conexión que sí estaba funcionando.
"""


class Reintentos:
    def __init__(self, base=20, maximo=300, intentos=6):
        self.base, self.maximo, self.intentos = base, max(maximo, base), intentos
        self.fallos, self.ultimo = {}, {}

    def espera(self, mac):
        """Segundos entre intentos en segundo plano: base, 2×base, 4×base... hasta `maximo`."""
        n = self.fallos.get(mac, 0)
        return min(self.base * 2 ** min(max(n - 1, 0), 16), self.maximo)

    def en_pausa(self, mac):
        """Tras `intentos` fallos seguidos ya no se busca en segundo plano (0 = nunca se pausa)."""
        return bool(self.intentos) and self.fallos.get(mac, 0) >= self.intentos

    def toca(self, mac, ahora):
        """True si corresponde un intento en segundo plano."""
        return not self.en_pausa(mac) and ahora - self.ultimo.get(mac, -1e9) >= self.espera(mac)

    def intento(self, mac, ahora):
        self.ultimo[mac] = ahora

    def fallo(self, mac):
        """Registra un intento fallido. Devuelve los fallos seguidos."""
        self.fallos[mac] = self.fallos.get(mac, 0) + 1
        return self.fallos[mac]

    def exito(self, mac):
        """Conectado (o se perdió una conexión que funcionaba): vuelve a buscarse con la espera base."""
        self.fallos.pop(mac, None)
