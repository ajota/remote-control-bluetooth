"""Disposición de las pantallas: qué dispositivo está a qué lado de cuál."""
import re

LADOS = ("left", "right", "top", "bottom")
OPUESTO = {"left": "right", "right": "left", "top": "bottom", "bottom": "top"}
LADO_ES = {"left": "izquierda", "right": "derecha", "top": "arriba", "bottom": "abajo"}
ALIAS_LADO = dict({v: k for k, v in LADO_ES.items()}, **{k: k for k in LADOS})


def normalizar_lado(valor):
    """'derecha' / 'right' -> 'right'. ValueError si no es un lado."""
    try:
        return ALIAS_LADO[valor.lower()]
    except KeyError:
        raise ValueError("lado inválido: %s (derecha/izquierda/arriba/abajo)" % valor)


def normalizar_mac(valor):
    if not re.fullmatch(r"([0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2}", valor):
        raise ValueError("MAC inválida: %s" % valor)
    return valor.upper()


def construir_vecinos(devs):
    """{pantalla: {lado: pantalla_vecina}} validando que no haya dos en el mismo borde."""
    nombres = {"laptop"} | {d["name"] for d in devs}
    vec = {n: {} for n in nombres}
    for d in devs:
        if d["of"] not in nombres or d["of"] == d["name"]:
            raise ValueError("'%s' está al lado de '%s', que no existe" % (d["name"], d["of"]))
        for pant, lado, otra in ((d["of"], d["side"], d["name"]), (d["name"], OPUESTO[d["side"]], d["of"])):
            if vec[pant].get(lado, otra) != otra:
                raise ValueError("A la %s de '%s' ya está '%s' (puedes encadenar con --of)" %
                                 (LADO_ES[lado], pant, vec[pant][lado]))
            vec[pant][lado] = otra
    return vec
