# Prompt para Claude en PowerShell: imágenes de la app completa de K'ab T'aan

Copia todo lo que está debajo de la línea y pégalo en Claude Code, abierto en PowerShell en
`C:\Users\Angel Perez\Downloads\inclusion\repo`.

---

Genera las 9 imágenes de `diseno/prompts/app_completa.json` con WaveSpeedAI. Son las imágenes de la versión completa
de la app: íconos nuevos, insignias de logros, tutorial de bienvenida, categorías del diccionario, estados, portada y
3 escenarios para el avatar. Todo está preparado y el script ya se probó con la API simulada.

**Reglas que no se pueden romper:**
- Modelo **Nano Banana 2.1** y calidad **1K** como máximo. Nunca 2K ni 4K.
- Cada imagen lleva sus **imágenes de referencia** (campo `referencias` del JSON), así que va por el modo de
  **edición** de Nano Banana 2.1 (`google/nano-banana-2.1/edit`), igual que el logo versión 2. Las referencias se
  suben con la carga directa de WaveSpeedAI, una sola vez cada archivo.
- **Una sola generación por imagen: 9 en total.** Nada de variantes ni reintentos, aunque alguna no salga perfecta.
  Si el envío de una tarea falla y no produjo imagen, no la reenvíes por tu cuenta: anota el error y pregúntame.
- La clave está en la variable de entorno `WAVESPEED_API_KEY`. Si no existe, pídeme que la defina yo en la terminal
  (`$env:WAVESPEED_API_KEY = "..."`) y espera. Nunca la escribas en un archivo ni la muestres en la salida.
- No toques nada fuera de `diseno/` y no hagas commits.

**Pasos:**
1. Lee `diseno/prompts/app_completa.json`: qué es cada imagen (`para_que`), su prompt, sus `referencias` y su
   lista de `revision`.
2. Ejecuta, una sola vez:
   ```powershell
   python diseno/herramientas/generar_imagenes.py diseno/prompts/app_completa.json
   ```
   Las imágenes y su `manifest.json` quedan en `diseno/generadas/app_completa/`. Si una imagen ya existe, la salta,
   así que volver a correrlo nunca genera dos veces la misma.
3. Mira cada imagen y compárala con su campo `revision`. Anota lo que no cumpla en el `manifest.json` (campos
   `revision_estado` y `revision_notas`), sin regenerar nada. Pon atención a: el número de elementos de cada
   cuadrícula y su orden, que no haya texto, y que las manos tengan 5 dedos.
4. Crea `diseno/generadas/app_completa/galeria.html`: cada imagen grande junto a su(s) referencia(s), con su
   `para_que` y tus notas. Las hojas en cuadrícula (íconos 5 × 4, insignias 3 × 3, bienvenida 2 × 2, categorías
   3 × 2, estados 2 × 2) muéstralas también con líneas guía encima, para ver si cada elemento cae dentro de su celda.
   Ábrela en el navegador.
5. Al final, resume en la terminal: cuántas imágenes salieron bien, cuáles tienen problemas (sin regenerarlas) y
   cuánto costó, si se sabe (unos 0.04 USD por imagen; unos 0.40 USD en total).
