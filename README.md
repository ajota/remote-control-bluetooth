# borde_bt

Usa el teclado y el trackpad de tu laptop Ubuntu como teclado y mouse Bluetooth de una o varias tablets o celulares. Para pasar de una pantalla a otra solo llevas el cursor hasta el borde, como si fueran monitores extra.

- Cada dispositivo se ubica a la **derecha, izquierda, arriba o abajo** de la laptop, o de otro dispositivo (cadena: laptop → tablet → celular).
- Al empujar el cursor contra ese borde, el control pasa al dispositivo y su puntero aparece en el borde que mira hacia la laptop.
- En el dispositivo, al llevar el puntero contra el borde por donde entró, el control vuelve a la laptop a la altura equivalente. Funciona en ambos sentidos todas las veces.
- Todos los dispositivos quedan conectados a la vez. Si uno se desconecta, su borde se comporta como una pared normal y el script intenta reconectarlo (cada vez más espaciado; tras varios fallos espera a que empujes el cursor hacia él).
- Con la pantalla de la laptop apagada o el equipo en suspensión, el script se pausa: suelta el Bluetooth (la radio queda libre) y deja el teclado y el trackpad directo para la laptop. Al encender la pantalla se reanuda y reconecta solo. Mientras usas un dispositivo, la laptop no apaga la pantalla ni se suspende por inactividad.

## Requisitos

- Ubuntu (probado para GNOME 46 en Wayland; también debería funcionar en X11).
- Adaptador Bluetooth.
- Python 3 y permisos de administrador (`sudo`).
- Tablets o celulares con Bluetooth que acepten teclados y mouses (Android, iPadOS, etc.).

## Manual de usuario paso a paso

Sigue los pasos en orden. Al final de cada uno se indica qué deberías ver para saber que salió bien. Los pasos 1 a 3 se hacen **una sola vez**. Los pasos 4 a 7 se repiten **por cada tablet o celular**. El paso 9 es el uso diario.

### Paso 0. Abrir una terminal en la carpeta del script

Abre una terminal (`Ctrl+Alt+T`) y entra a la carpeta donde está `borde_bt.py`:

```bash
cd ~/Documentos/demos
```

Todos los comandos de este manual se ejecutan desde esa carpeta.

### Paso 1. Instalar las dependencias

```bash
sudo apt install python3-evdev python3-dbus python3-gi
```

Escribe tu contraseña cuando la pida.

✅ **Deberías ver:** que `apt` termina sin errores.

### Paso 2. Encender el Bluetooth de la laptop

Actívalo en **Configuración → Bluetooth**, o desde la terminal:

```bash
rfkill unblock bluetooth
```

✅ **Deberías ver:** el interruptor de Bluetooth encendido en la Configuración de Ubuntu.

### Paso 3. Preparar el servicio Bluetooth

```bash
sudo python3 borde_bt.py setup
```

Este paso cambia dos cosas en el sistema:

- Arranca `bluetoothd` sin el plugin `input`, que ocupa los canales HID que necesita el script (PSM 17 y 19).
- Arranca `bluetoothd` sin el plugin `hostname`, que obliga a la laptop a anunciarse como "computadora portátil".
- Hace que la laptop se anuncie como teclado y mouse (`Class = 0x000540` en `/etc/bluetooth/main.conf`) y conserva su nombre (`Name = <nombre del equipo>`).

El comando muestra cada paso (`1/3`, `2/3`, `3/3`) y al final verifica el resultado automáticamente.

✅ **Deberías ver:** todas las líneas de la verificación con `[OK]` y al final `Listo: bluetoothd sin el plugin 'input' y con clase de teclado+mouse.`

**Comprobarlo en cualquier momento:**

```bash
sudo python3 borde_bt.py status
```

Revisa el Bluetooth, el teclado y el trackpad, y los dispositivos configurados. Marca cada punto con `[OK]` o `[FALTA]` e indica el comando que lo arregla. Por ejemplo, cuando la preparación no se aplicó:

```text
Bluetooth
  [OK]    Bluetooth no bloqueado
  [FALTA] Archivo /etc/systemd/system/bluetooth.service.d/borde_bt.conf
          -> sudo python3 borde_bt.py setup
  [FALTA] bluetoothd corre sin el plugin 'input' (/usr/libexec/bluetooth/bluetoothd)
          -> sudo python3 borde_bt.py setup   (si ya lo hiciste: sudo systemctl restart bluetooth)
  [FALTA] Se anuncia como teclado/mouse (clase 0x7c010c)
          Nombre visible para las tablets: 'NOMBRE-DE-TU-LAPTOP'
```

Si prefieres revisarlo a mano:

| Qué revisar | Comando | Resultado correcto |
| --- | --- | --- |
| Servicio sin plugins `input` y `hostname` | `ps -o args -C bluetoothd` | `/usr/libexec/bluetooth/bluetoothd -P input,hostname` |
| Tipo de dispositivo | `hciconfig -a \| grep "Device Class"` | `Peripheral` (no `Computer`) |
| Archivo de servicio | `cat /etc/systemd/system/bluetooth.service.d/borde_bt.conf` | contiene `-P input,hostname` |

> **Importante:** mientras esta configuración esté activa, la laptop **no puede usar sus propios teclados o mouses Bluetooth**. Para revertirla en cualquier momento:
>
> ```bash
> sudo python3 borde_bt.py setup --deshacer
> ```

### Paso 4. Decidir dónde va cada dispositivo

Piensa dónde vas a poner físicamente cada tablet o celular respecto a la laptop. Esa posición determina por qué borde pasa el cursor. Por ejemplo:

```text
 ┌─────────┐   ┌──────────┐   ┌────────┐   ┌─────────┐
 │ celular │ ← │  laptop  │ → │ tablet │ → │ celular2│
 └─────────┘   └──────────┘   └────────┘   └─────────┘
  izquierda                    derecha      derecha de
  de laptop                    de laptop    la tablet
```

- Lados válidos: `derecha`, `izquierda`, `arriba`, `abajo`.
- Cada borde de cada pantalla admite **un solo** dispositivo. Si quieres dos del mismo lado, pon el segundo al lado del primero con `--of`, como `celular2` en el dibujo.
- Elige un nombre corto para cada uno, sin espacios (por ejemplo `tablet`, `celular`).

### Paso 5. Emparejar el dispositivo

1. En la laptop, ejecuta el comando con el nombre y el lado que elegiste:

   ```bash
   sudo python3 borde_bt.py pair tablet --side derecha
   ```

   Para un dispositivo que va al lado de otro dispositivo (y no de la laptop):

   ```bash
   sudo python3 borde_bt.py pair celular2 --side derecha --of tablet
   ```

2. ✅ **Deberías ver:** `Visible como 'NOMBRE-DE-TU-LAPTOP' durante 3 minutos.` Ese es el nombre que vas a buscar en la tablet.

3. En la tablet o el celular, antes de que pasen los 3 minutos:
   - **Android:** Ajustes → Dispositivos conectados → **Vincular nuevo dispositivo** → toca `NOMBRE-DE-TU-LAPTOP` → acepta.
   - **iPad / iPhone:** Ajustes → Bluetooth → en "Otros dispositivos" toca `NOMBRE-DE-TU-LAPTOP` → acepta.

   Si aparece un código para confirmar, acéptalo: la laptop lo acepta sola.

4. ✅ **Deberías ver en la laptop:** `Emparejado: <nombre de la tablet> (AA:BB:CC:DD:EE:FF)` y `Guardado en ...`.

**Antes de emparejar:** si la tablet ya estuvo vinculada alguna vez con la laptop (como computadora normal o con otra versión del script), borra ese vínculo **en ambos lados**. Si no, las claves viejas no coinciden y la tablet muestra *"An error occurred during pairing"* o *"No se pudo vincular"*.

1. En la laptop, busca la tablet y bórrala:

   ```bash
   bluetoothctl devices Paired
   bluetoothctl remove AA:BB:CC:DD:EE:01     # la MAC de tu tablet
   ```

2. En la tablet, en sus ajustes Bluetooth, toca `NOMBRE-DE-TU-LAPTOP` → **Olvidar** / **Desvincular**.

**Si no funciona:**

- Asegúrate de que el comando `pair` siga corriendo en la laptop mientras emparejas. Es el que acepta la solicitud.
- Ejecuta `sudo python3 borde_bt.py status`: todo lo de la sección Bluetooth debe estar en `[OK]`, en especial *"Se anuncia como teclado/mouse"*.
- Si se vincula pero el script dice `No se conectó ningún dispositivo nuevo`, busca su MAC y agrégala a mano:

  ```bash
  bluetoothctl devices Paired
  sudo python3 borde_bt.py add tablet AA:BB:CC:DD:EE:FF --side derecha
  ```

### Paso 6. Calibrar la pantalla del dispositivo

El script necesita saber qué tan grande es la pantalla del dispositivo para detectar sus bordes. La calibración es **automática**: el script mueve el puntero de la tablet solo, despacio y a velocidad constante, y tú solo avisas cuándo toca el borde.

1. Pon el dispositivo en la orientación en que lo vas a usar (horizontal o vertical) y desbloquéalo.
2. En la laptop, ejecuta:

   ```bash
   sudo python3 borde_bt.py calibrate tablet
   ```

3. **No toques el trackpad.** En cada ronda hay 4 pasadas. En cada una el puntero sale de la esquina superior izquierda y tú presionas **Enter** en la terminal en el instante en que toca el borde:
   1. Avanza **lento hacia la derecha**: Enter al tocar el borde derecho.
   2. Avanza **lento hacia abajo**: Enter al tocar el borde inferior.
   3. Avanza **muy lento hacia la derecha**: Enter al tocar el borde derecho. Mide si el dispositivo frena los movimientos suaves (muchos Android lo hacen).
   4. Avanza **a saltos rápidos hacia la derecha**: Enter al tocar el borde derecho. Mide cuánto acelera los movimientos rápidos.
4. Se repite una segunda ronda (en total, uno o dos minutos según el tamaño de la pantalla). Si las dos rondas no coinciden, se hace una tercera para desempatar y se usan las dos más parecidas. Si ni así coinciden, se guarda la mediana con un aviso.
5. ✅ **Deberías ver:** `Pantalla de 'tablet': #### x #### unidades, aceleración #.##, respuesta lenta #.##` y `Guardado en ...`. Si el dispositivo frena los movimientos lentos o no acelera los rápidos, también lo dice. El script lo compensa **automáticamente** para que todos los dispositivos respondan igual a la velocidad de tu dedo.

> Durante la calibración el puntero **no salta** a la laptop al llegar al borde: este paso solo mide la pantalla. El salto entre pantallas funciona en el paso 9.

**Más rápido si conoces la resolución.** Si sabes la resolución de la pantalla (aparece en las especificaciones del modelo) o su proporción, indícala **en la orientación en que la usas**. El alto se calcula y se omite la pasada vertical:

```bash
sudo python3 borde_bt.py calibrate tablet --resolucion 2000x1200   # horizontal
sudo python3 borde_bt.py calibrate tablet --resolucion 16:10       # solo la proporción
```

La resolución no reemplaza la pasada horizontal: cuántas unidades del mouse equivalen a un píxel depende de la versión de Android y de la velocidad del puntero configurada en la tablet, y solo se sabe midiendo.

Repite la calibración si giras el dispositivo.

**Cómo decide el salto desde la tablet.** La tablet no informa dónde está su puntero, así que el script lo calcula con la medida y la aceleración de la calibración. Para no saltar antes de tiempo:

- Calcula con prudencia: al ir hacia el borde de salida supone que la tablet avanzó un poco menos, y al alejarte, un poco más. Esa prudencia está limitada (como máximo el 2.5 % de la pantalla), para que tras navegar un buen rato no haya que empujar cada vez más para volver.
- Exige que **sigas empujando contra el borde durante 50 ms**. Un deslizamiento rápido que se detiene no basta.

Si al usarlo notas que:

- **salta antes de llegar al borde**, aumenta la espera o la prudencia: `sudo python3 borde_bt.py config --remote-dwell 0.1` o `--remote-caution 0.25`
- **tienes que empujar mucho para volver**, redúcelas: `config --remote-dwell 0.02 --remote-caution 0.05`

### Paso 7. Configurar el teclado del dispositivo

En la tablet, elige como distribución del teclado físico la **misma que tiene la laptop** (por ejemplo, *Español (Latinoamérica)*):

- **Android:** Ajustes → Sistema → Idiomas y entrada → **Teclado físico** → `NOMBRE-DE-TU-LAPTOP` → Español (Latinoamérica).
- **iPad / iPhone:** Ajustes → General → Teclado → **Teclado físico** → Español (Latinoamérica).

Esta opción solo aparece mientras la tablet está conectada al script, así que hazlo durante el paso 6 o el paso 9.

✅ **Deberías ver:** que la ñ, los acentos y los símbolos salen igual que en la laptop.

### Paso 8. Repetir con los demás dispositivos y revisar

Repite los pasos 5 a 7 con cada tablet o celular. Luego revisa la configuración y el estado:

```bash
sudo python3 borde_bt.py list
sudo python3 borde_bt.py status
```

`status` debe terminar con `Todo listo.`

✅ **Deberías ver:** cada dispositivo con su MAC, su lado y su tamaño (no `?x?`). Por ejemplo:

```text
  tablet     AA:BB:CC:DD:EE:01  a la derecha   de laptop     1520x910  gain=1.0
  celular    AA:BB:CC:DD:EE:02  a la izquierda de laptop     780x1650  gain=1.0
```

Para cambiar algo después, sin volver a emparejar:

```bash
sudo python3 borde_bt.py set tablet --side izquierda   # mover la tablet al otro lado
```

### Paso 9. Usarlo (cada vez)

1. Enciende el Bluetooth de la laptop y de los dispositivos y desbloquéalos.
2. Ejecuta:

   ```bash
   sudo python3 borde_bt.py
   ```

3. ✅ **Deberías ver:** `Usando: ...` con el teclado y el trackpad, la lista de dispositivos y su ubicación, y luego `Conectado: 'tablet'` por cada dispositivo que se conecte. Puede tardar unos segundos.
4. **Prueba el salto:** lleva el cursor contra el borde donde está la tablet y empuja un poco más. Debe aparecer `>>> Control en 'tablet'` y el puntero en la tablet. Lo que escribas va ahora a la tablet. El cursor de la laptop se esconde en la esquina inferior derecha de su pantalla, donde solo asoma la punta (Wayland no permite ocultarlo del todo).
5. **Prueba el regreso:** en la tablet, lleva el puntero contra el borde que da a la laptop y empuja un poco más. Debe aparecer `<<< Control en la LAPTOP` y el cursor reaparece en el borde de la laptop, a la altura equivalente.

   Al entrar a la tablet, su puntero aparece contra el borde por donde entraste, a la misma altura relativa que tenía el cursor en la laptop. Al salir, el puntero de la tablet se esconde en su esquina inferior derecha, donde solo asoma la punta. Si en la tablet el puntero se siente muy rápido o muy lento, ajústalo con `sudo python3 borde_bt.py config --remote-speed 7` (más lento) o `--remote-speed 14` (más rápido).
6. Si el puntero se pierde, usa `Ctrl+Alt+F12` para pasar de una pantalla a otra sin usar los bordes.
7. Para terminar: `Ctrl+Alt+Esc`, o `Ctrl+C` en la terminal. El teclado y el trackpad vuelven a funcionar normalmente en la laptop.

| Atajo | Acción |
| --- | --- |
| `Ctrl+Alt+F12` | Pasar al siguiente dispositivo conectado (o volver a la laptop) |
| `Ctrl+Alt+Esc` | Cerrar el script |
| `Ctrl+C` en la terminal | Cerrar el script |

### Paso 10. Desinstalar (opcional)

Para dejar la laptop como estaba:

```bash
sudo python3 borde_bt.py setup --deshacer
rm ~/.config/borde_bt.json
```

En cada tablet, olvida `NOMBRE-DE-TU-LAPTOP` en sus ajustes Bluetooth.

## Gestos del trackpad

Mientras el script corre, interpreta él mismo el trackpad y envía el resultado a la pantalla activa. Los gestos funcionan igual en la laptop y en las tablets:

| Gesto | Acción |
| --- | --- |
| Mover un dedo | Mover el puntero |
| Tocar con 1 dedo | Clic izquierdo (seleccionar o activar, sin presionar el trackpad) |
| Tocar con 2 dedos | Clic derecho (menú de opciones) |
| Tocar con 3 dedos | Clic medio |
| Tocar, volver a tocar y mantener el dedo | Arrastrar (se suelta al levantar el dedo) |
| Presionar el trackpad | Clic izquierdo |
| Presionar la **esquina inferior derecha** | Clic derecho (menú de opciones) |
| Presionar con 2 dedos (fuera de la franja inferior) | Clic derecho |
| Deslizar 2 dedos | Scroll vertical y horizontal |
| Pellizcar con 2 dedos (separar / juntar) | Acercar / alejar (zoom), enviado como Ctrl + rueda |
| Deslizar 3 dedos hacia arriba | Tablet: **Inicio** · Laptop: vista de actividades de GNOME |
| Deslizar 3 dedos a la izquierda o derecha | Tablet: **Atrás** · Laptop: escritorio siguiente / anterior |

El zoom con Ctrl + rueda funciona en navegadores y en la mayoría de apps de documentos e imágenes. Algunas apps no lo soportan. Mientras corre el script, los gestos nativos de GNOME no están disponibles (el trackpad lo maneja el script); por eso los de 3 dedos en la laptop se envían como sus atajos de teclado.

Al empezar a escribir, el trackpad ignora los toques durante un momento para no reaccionar a la palma.

## Comandos

| Comando | Descripción |
| --- | --- |
| `setup [--deshacer]` | Preparar (o restaurar) el servicio Bluetooth |
| `pair NOMBRE --side LADO [--of VECINO]` | Emparejar un dispositivo nuevo |
| `add NOMBRE MAC --side LADO [--of VECINO]` | Agregar un dispositivo ya emparejado |
| `calibrate NOMBRE [--resolucion WxH]` | Medir la pantalla de un dispositivo (con la resolución, se omite la pasada vertical) |
| `set NOMBRE [opciones]` | Cambiar `--side`, `--of`, `--mac`, `--width`, `--height`, `--gain`, `--scroll` o `--accel` |
| `remove NOMBRE` | Quitar un dispositivo |
| `list` | Ver dispositivos y ajustes |
| `status` | Comprobar que todo esté listo; dice qué falta y cómo arreglarlo |
| `test NOMBRE` | Mover el puntero del dispositivo solo (sin trackpad) para saber si el Bluetooth funciona |
| `--debug` (con cualquier comando) | Mostrar cada segundo lo que llega del trackpad y lo que se envía por Bluetooth |
| `config [opciones]` | Ajustes generales (tabla siguiente) |
| `run` | Ejecutar (es lo que hace el script si no le das ningún comando) |

Ejemplos:

```bash
sudo python3 borde_bt.py set tablet --side izquierda      # mover la tablet al otro lado
sudo python3 borde_bt.py set tablet --gain 1.3            # puntero más rápido en la tablet
sudo python3 borde_bt.py config --speed 1.2 --no-tap      # trackpad más rápido, sin tocar para clic
```

### Ajustes generales (`config`)

| Opción | Por defecto | Descripción |
| --- | --- | --- |
| `--screen WxH` | automático | Resolución lógica de la laptop (p. ej. `1744x981`) |
| `--speed` | 1.0 | Sensibilidad del trackpad en la laptop |
| `--remote-speed` | 10 | Velocidad del trackpad en los dispositivos en movimientos lentos. Por dispositivo: `set NOMBRE --gain` |
| `--remote-accel` | 2.0 | Aceleración total en los dispositivos. Si un dispositivo acelera menos (según la calibración), el script completa la diferencia; si ya acelera lo suficiente, no añade nada |
| `--mouse-speed` | 1.0 | Sensibilidad de mouses externos |
| `--margin` | 25 | Píxeles de empuje extra contra el borde de la laptop para saltar |
| `--remote-margin` | 60 | Empuje extra contra el borde de un dispositivo para volver |
| `--remote-dwell` | 0.05 | Segundos de empuje continuo contra el borde de un dispositivo para volver |
| `--remote-caution` | 0.15 | Prudencia del cálculo de posición en el dispositivo (más = salto más tardío, nunca temprano) |
| `--natural-scroll` / `--no-natural-scroll` | activado | Dirección del scroll |
| `--scroll-mm` | 2.5 | Milímetros de deslizamiento por paso de scroll |
| `--tap` / `--no-tap` | activado | Tocar para hacer clic |
| `--reconnect` | 20 | Segundos entre intentos de reconexión de un dispositivo desconectado. La espera se duplica con cada fallo |
| `--reconnect-max` | 300 | Espera máxima entre intentos (segundos) |
| `--reconnect-tries` | 6 | Fallos seguidos tras los que se deja de buscar al dispositivo (buscarlo ocupa la radio y, en laptops donde WiFi y Bluetooth comparten antena, frena la red). Se vuelve a intentar al empujar el cursor hacia él, si él se conecta o si se cae una conexión que funcionaba. `0` = buscar siempre |
| `--secure` / `--no-secure` | activado | Exigir conexión cifrada (solo dispositivos emparejados) |
| `--allow-sniff` / `--no-allow-sniff` | desactivado | Permitir el modo de ahorro "sniff" también en el dispositivo que estás usando. Desactivado = movimiento más fluido en el activo; los inactivos siempre pueden ahorrar. Se restaura al salir |
| `--qos` / `--no-qos` | activado | Pedir al dispositivo activo que consulte a la laptop cada 7.5 ms (por defecto suele ser cada 25 ms): menos latencia y más reportes por segundo |
| `--hide-remote-pointer` / `--no-hide-remote-pointer` | activado | Al salir de un dispositivo, esconder su puntero en la esquina inferior derecha (solo asoma la punta) |
| `--pause-screen-off` / `--no-pause-screen-off` | activado | Pausar con la pantalla de la laptop apagada: se desconecta el Bluetooth y el teclado y el trackpad quedan solo para la laptop. Se reanuda al encender la pantalla. En suspensión siempre se pausa |
| `--keep-awake` / `--no-keep-awake` | activado | Mientras usas un dispositivo, evitar que la laptop apague la pantalla o se suspenda por inactividad (el escritorio no ve ese uso). Deja de hacerlo tras 1 minuto sin tocar el teclado ni el trackpad |

La configuración se guarda en `~/.config/borde_bt.json`.

## Limitaciones

- **Ajustes y gestos de GNOME:** mientras corre el script no se aplican los ajustes de touchpad de GNOME (velocidad, scroll natural) ni sus gestos de 3 y 4 dedos. Wayland no permite que un programa lea la posición del cursor, así que el script controla el puntero de la laptop para saber cuándo tocas un borde.
- **Precisión en los dispositivos:** como el dispositivo no informa dónde está su puntero, el script lleva un modelo de su pantalla. Cada vez que entras, empuja el puntero contra el borde de entrada para que modelo y puntero queden alineados. Aun así, con la aceleración del puntero del dispositivo puede desviarse un poco: a veces hay que empujar un poco más para volver, o el salto ocurre unos píxeles antes de llegar al borde. Ajústalo con `--remote-margin` o volviendo a calibrar.
- **Dispositivos de entrada nuevos:** los teclados o mouses que conectes con el script ya corriendo no se detectan; reinícialo.
- **Bordes ocupados:** cada borde de cada pantalla admite un solo vecino. Para poner más dispositivos del mismo lado, encadénalos con `--of`.

## Solución de problemas

| Problema | Solución |
| --- | --- |
| No sé si algo quedó bien configurado | `sudo python3 borde_bt.py status` |
| La tablet dice *"An error occurred during pairing"* | Borra el vínculo viejo en ambos lados (ver el paso 5), confirma con `status` que todo esté en `[OK]` y repite `pair` |
| `status` marca *"Se anuncia como teclado/mouse"* aunque ya hiciste `setup` | Vuelve a ejecutar `sudo python3 borde_bt.py setup` (las versiones nuevas también desactivan el plugin `hostname`) |
| `org.bluez.Error.Busy` o *"BlueZ no dejó poner la laptop visible"* | Cierra Configuración → Bluetooth de Ubuntu, espera unos segundos y repite. Si sigue: `sudo systemctl restart bluetooth` |
| El puntero aparece en la tablet pero no se mueve con el trackpad | 1) `sudo python3 borde_bt.py test tablet`: si el puntero se mueve solo, el Bluetooth funciona. 2) `sudo python3 borde_bt.py --debug calibrate tablet` y mueve el dedo: las líneas `[debug]` muestran si llegan eventos del trackpad (`eventos`, `movimiento`) y si salen reportes (`BT: N reportes`) |
| En un dispositivo el puntero va más rápido o más lento que el dedo | Solo ese dispositivo: `set celular --gain 1.5` (más rápido) o `--gain 0.7` (más lento). Todos: `config --remote-speed 14` o `7` |
| Los movimientos rápidos se quedan cortos (o se pasan) en los dispositivos | `config --remote-accel 3` (más aceleración) o `1.5` (menos) |
| El puntero de un dispositivo va "en cámara lenta" o sigue moviéndose después de detener el dedo | Es retraso del Bluetooth (sobre todo con varios dispositivos conectados). El script ya agrupa el movimiento cuando el enlace no da abasto; con `--debug` verás `agrupados` > 0 y `cola máx` en esos momentos. Acercar los dispositivos a la laptop o desconectar audífonos Bluetooth libera la radio |
| El puntero de un dispositivo se mueve a saltos o por momentos lento | Con varios dispositivos conectados, la radio Bluetooth se reparte. El script desactiva el modo de ahorro solo en el dispositivo que usas y deja dormir a los demás para que no le quiten turnos de radio (con `--debug` verás `política Bluetooth: activo=RSWITCH,HOLD, inactivos=RSWITCH,HOLD,SNIFF`). Si sigue, apaga el Bluetooth de los que no uses o usa WiFi de 5 GHz |
| El puntero queda visible en el dispositivo al volver a la laptop | Se esconde en la esquina inferior derecha del dispositivo (solo asoma la punta) y desaparece del todo tras unos segundos sin uso |
| Se siente latencia entre el dedo y el puntero del dispositivo | En Bluetooth, el dispositivo decide cada cuánto consulta a la laptop (suele ser cada 25 ms, unos 40 reportes/s). El script le pide que lo haga cada 7.5 ms (`--debug` muestra `QoS ... pedido`). Si `BT: N reportes` sigue muy por debajo de `cuadros`, el dispositivo no aceptó la petición |
| `No pude usar el PSM 17` | Ejecuta `sudo python3 borde_bt.py setup` |
| `No se pudo encender el Bluetooth` | Actívalo en Ajustes o con `rfkill unblock bluetooth` |
| El cursor de la laptop no se mueve | Sal con `Ctrl+Alt+Esc` o `Ctrl+C` en la terminal y revisa los mensajes |
| La resolución detectada es incorrecta | `sudo python3 borde_bt.py config --screen 1920x1080` |
| Teclas o símbolos equivocados en la tablet | Revisa la distribución de teclado configurada en la tablet |
| El dispositivo no conecta tras actualizar el script | Olvídalo en sus ajustes Bluetooth y vuelve a usar `pair` |
| El salto de regreso es impreciso | Recalibra con `calibrate`. Si salta antes del borde: `config --remote-dwell 0.1`; si cuesta mucho volver: `config --remote-dwell 0.02 --remote-caution 0.05` |

## Arquitectura

El código está organizado en **módulos por característica** (*vertical slices*): cada carpeta de `bordebt/caracteristicas/` contiene todo lo de una funcionalidad. Dentro de cada característica, la **lógica pura** está separada de los **adaptadores por sistema operativo**, para que el mismo sistema pueda funcionar en Windows y macOS agregando solo adaptadores.

```text
borde_bt.py                      lanzador (se usa igual: sudo python3 borde_bt.py ...)
bordebt/
  cli.py                         línea de comandos: cada característica registra sus comandos
  plataforma.py                  detecta el sistema operativo y carga el adaptador de cada característica
  comun/                         núcleo compartido mínimo, sin dependencias del sistema
    config.py                    configuración JSON y valores por defecto
    disposicion.py               lados, vecinos y validación de la disposición de pantallas
    diagnostico.py               --debug y estadísticas
    bucle.py                     espera de eventos (select)
    argumentos.py                tipos de argumento compartidos
  caracteristicas/
    conmutacion/                 bordes y saltos entre pantallas (comando run)
      pantalla.py, destinos.py, motor.py, reposo.py      lógica pura
      puertos.py                 lo que necesita de la plataforma (puntero y teclado de la laptop...)
      linux.py                   puntero absoluto uinput, resolución de pantalla
      comandos.py                run: arma todo con los adaptadores de la plataforma
    entrada/                     capturar teclado, trackpad y mouses físicos
      eventos.py                 eventos neutros: teclas en códigos HID, trackpad en milímetros
      linux.py                   evdev, teclado virtual uinput, LEDs
    energia/                     pantalla apagada y suspensión (linux.py: DPMS en sysfs, logind)
    gestos/                      interpretar el trackpad (toques, arrastre, scroll, pellizco, 3 dedos)
      interprete.py              lógica pura
    hid_bluetooth/               emular teclado + mouse Bluetooth
      protocolo.py, enlace.py    descriptor HID, reportes, agrupación del movimiento (puro)
      servicio.py                conectar con un dispositivo, atender sus peticiones
      reconexion.py              cuándo volver a buscar un dispositivo desconectado (espera creciente, pausa)
      linux/                     BlueZ (D-Bus), sockets L2CAP, política de radio (hcitool)
    calibracion/                 calibrate y test (medidas.py puro, linux.py: terminal)
    dispositivos/                pair, add, set, remove
    configuracion/               list, config
    preparacion/                 setup y status (linux.py: systemd, main.conf, rfkill)
tests/                           pruebas (python3 -m unittest)
```

### Reglas de dependencia

- **Solo** los archivos `linux.py` y las carpetas `linux/` importan librerías del sistema operativo (evdev, D-Bus, sockets Bluetooth, termios, hcitool...). Todo lo demás es Python estándar.
- La lógica nunca importa un adaptador directamente: lo pide con `plataforma.adaptador("<característica>")`, que carga `<característica>/<sistema>.py` (`linux`, `windows` o `macos`).
- El teclado viaja por la lógica con **códigos HID estándar** (los mismos que van por Bluetooth) y el trackpad en **milímetros**, no con los códigos de cada sistema.
- Las características se comunican a través de sus módulos públicos: por ejemplo, `conmutacion` usa `gestos.interprete`, `entrada.eventos` y `hid_bluetooth.enlace`.

Para comprobar la primera regla:

```bash
grep -rlE "^\s*(import|from) (evdev|dbus|gi|fcntl|termios|socket)\b|ecodes" bordebt | grep -v /linux
```

No debe mostrar nada.

### Agregar Windows o macOS

Cada característica que depende del sistema documenta en su `__init__.py` el **contrato** que debe cumplir su adaptador. Para portar a un sistema nuevo hay que crear, con el nombre `windows` o `macos`:

| Característica | Qué implementar | En Linux |
| --- | --- | --- |
| `entrada` | `Captura` (capturar teclado/trackpad/mouse y entregar `EventoTecla` y `CuadroTactil`), `nombres_dispositivos()` | evdev + uinput |
| `conmutacion` | `PunteroUinput` equivalente (puerto `PunteroLocal`), `tamano_pantalla()` | uinput absoluto, xrandr |
| `hid_bluetooth` | `BlueZ`, `GestorBT`, `Enlace`, `Radio`, `psm_libre()` | BlueZ D-Bus, L2CAP, hcitool |
| `calibracion` | `descriptor_entrada()`, `descartar_entrada()` | termios |
| `preparacion` | `aplicar(deshacer)`, `comprobar_sistema(linea)` | systemd, main.conf |

La lógica (saltos, modelo de cada dispositivo, gestos, calibración, protocolo HID) no cambia. Además, `comun/bucle.py` usa `select`, que en Windows solo admite sockets: allí necesitará su propia versión.

> En Windows y macOS, emular un teclado/mouse Bluetooth no es tan directo como en Linux (sus pilas Bluetooth no permiten registrar el perfil HID de dispositivo de forma estándar). Es probable que haga falta un adaptador USB Bluetooth dedicado o una pila alternativa; la arquitectura deja ese trabajo aislado en `hid_bluetooth/<sistema>/`.

### Pruebas

```bash
python3 -m unittest discover -s tests -t .
```

- Prueban la lógica **sin hardware, sin root y sin Bluetooth**, con dobles de los puertos (`tests/dobles.py`): saltos entre pantallas, entradas y salidas de un solo reporte, teclado, gestos, modelo de aceleración, agrupación del movimiento y calibración.
- `test_adaptadores_linux.py` prueba los adaptadores de Linux con dispositivos simulados (requiere `python3-evdev`).
- `test_integracion.py` ejecuta el comando `run` completo con adaptadores simulados.
