# Instrucciones para generar las imágenes (Claude en PowerShell)

Eres una sesión de Claude Code abierta en PowerShell en la carpeta del proyecto INCLUSION
(`C:\Users\Angel Perez\Downloads\inclusion\repo`). Tu único trabajo: generar las 5 imágenes de
`diseno/prompts/imagenes.json` con la API de **WaveSpeedAI** (wavespeed.ai) y dejarlas en `diseno/generadas/` para que
la persona las revise. No toques nada fuera de `diseno/` y no hagas commits.

## 1. La clave de la API

- Usa la variable de entorno `WAVESPEED_API_KEY`. Si no existe, pídele a la persona que la defina ella misma en esa
  terminal (`$env:WAVESPEED_API_KEY = "..."`) y espera.
- Nunca escribas la clave en un archivo, en el script, en el manifiesto ni en la salida de la terminal.

## 2. Revisa la API antes de usarla

- Consulta la documentación vigente de WaveSpeedAI (https://wavespeed.ai/docs): cómo se envía una tarea de
  texto a imagen, cómo se consulta el resultado y cómo se descarga.
- **Modelo obligatorio: Nano Banana 2.1**, en su versión de texto a imagen. Busca en la documentación su identificador
  exacto en WaveSpeedAI. No uses otro modelo; si no lo encuentras, detente y avísale a la persona.
- **Calidad: 1K como máximo** (la opción de resolución "1K", o lados de hasta 1024 px). Nunca pidas 2K ni 4K.
- Usa el mismo modelo y la misma calidad para las 5 imágenes.

## 3. Escribe un script reproducible

Crea `diseno/herramientas/generar_imagenes.py` (Python 3.10; usa `requests` o `urllib`, y `Pillow`, que ya están
instalados). El script:

1. Lee `diseno/prompts/imagenes.json`.
2. Para cada imagen arma el prompt final con `estilo_comun` + `prompt`. Si el modelo acepta prompt negativo, usa
   `negativo_comun`; si no, no lo agregues al texto.
3. Pide la proporción `aspecto` con calidad 1K (los campos `ancho` × `alto` son la referencia, máximo 1024 px).
   Guarda la imagen tal como la entrega el modelo, sin escalar ni recortar; si su tamaño o proporción real no
   coincide, solo anótalo en el manifiesto.
4. Envía la tarea, espera el resultado consultando cada pocos segundos (con un límite de tiempo) y descarga la imagen.
5. Guarda `diseno/generadas/<archivo>` en PNG.
6. Antes de enviar cada tarea, comprueba si `diseno/generadas/<archivo>` ya existe; si existe, sáltala. Así, si el
   script se interrumpe y se vuelve a correr, nunca se genera dos veces la misma imagen.
7. Escribe `diseno/generadas/manifest.json` con: modelo, prompt final, tamaño pedido y real, fecha, id de la tarea y
   costo si la API lo informa. Nunca la clave.

## 4. Genera: una sola vez cada imagen

- **Exactamente una generación por imagen: 5 en total.** No hagas variantes ni reintentos, aunque una imagen no salga
  perfecta. Esto lo decidió la persona para controlar el costo.
- Si una tarea falla por un error de la API (por ejemplo, de red o de saldo) y no produjo ninguna imagen, no la vuelvas
  a enviar por tu cuenta: anota el error y pregúntale a la persona.
- Después mira cada imagen y compárala con su campo `revision` del JSON. Anota lo que no cumpla en el manifiesto y en
  la galería, sin regenerarla. Del resto se encarga la otra sesión al integrarlas.

## 5. Para que la persona revise

- Crea `diseno/generadas/galeria.html`: las 5 imágenes grandes, cada una con su nombre, para qué es (`para_que`) y la
  lista de revisión (`revision`). Ábrela en el navegador al terminar.
- Al final, resume en la terminal:
  - qué modelo usaste;
  - qué imágenes salieron bien;
  - cuáles tienen problemas (sin regenerarlas);
  - cuánto costó, si se sabe.
