"""Característica: interpretar el trackpad (toques, arrastre, scroll, pellizco, gestos de 3 dedos).

Es lógica pura: recibe cuadros `entrada.eventos.CuadroTactil` y llama a un objeto de acciones con:
  movimiento(dx, dy), scroll(v, h), boton(b, valor), clic(b), pellizco(pasos), pellizco_fin(),
  gesto(direccion), px_por_mm(velocidad) y el atributo ultimo_tecleo.
"""
