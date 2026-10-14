"""Cálculo de la calibración a partir de las rondas medidas."""
import re

TOLERANCIA = 0.15       # diferencia relativa máxima para considerar dos rondas iguales
MINIMO = 300            # unidades: una pantalla más chica indica un Enter prematuro


def proporcion(texto):
    """'2000x1200' o '16:10' -> alto/ancho. ValueError si no tiene ese formato."""
    m = re.fullmatch(r"\s*(\d+(?:\.\d+)?)\s*[x:×/]\s*(\d+(?:\.\d+)?)\s*", texto)
    if not m or float(m.group(1)) <= 0:
        raise ValueError("Formato inválido: usa ANCHOxALTO (p.ej. 2000x1200) o una proporción (p.ej. 16:10).")
    return float(m.group(2)) / float(m.group(1))


def parecidas(m1, m2):
    """Dos rondas (ancho, alto, ...) coinciden en ancho y alto."""
    return all(abs(m1[i] - m2[i]) <= TOLERANCIA * max(m1[i], m2[i]) for i in (0, 1))


def combinar(medidas):
    """Rondas [(ancho, alto, aceleración, respuesta lenta)] -> (ancho, alto, aceleración, respuesta lenta,
    hubo_acuerdo). Usa las dos rondas más parecidas; si ni esas coinciden, la mediana de cada valor."""
    pares = [(i, j) for i in range(len(medidas)) for j in range(i + 1, len(medidas))]
    i, j = min(pares, key=lambda p: abs(medidas[p[0]][0] - medidas[p[1]][0]) / max(medidas[p[0]][0], medidas[p[1]][0]))
    acuerdo = parecidas(medidas[i], medidas[j])
    if acuerdo:
        elegidas = [medidas[i], medidas[j]]
    else:
        elegidas = [tuple(sorted(m[k] for m in medidas)[len(medidas) // 2] for k in range(4))]
    prom = [sum(m[k] for m in elegidas) / len(elegidas) for k in range(4)]
    return (round(prom[0]), round(prom[1]), round(min(6.0, max(0.5, prom[2])), 2),
            round(min(1.5, max(0.2, prom[3])), 2), acuerdo)
