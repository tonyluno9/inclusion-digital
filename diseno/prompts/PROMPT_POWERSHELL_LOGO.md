# Prompt para Claude en PowerShell: logo de K'ab T'aan

Copia todo lo que está debajo de la línea y pégalo en Claude Code, abierto en PowerShell en
`C:\Users\Angel Perez\Downloads\inclusion\repo`.

---

Genera los 3 conceptos de logo del proyecto **K'ab T'aan** con WaveSpeedAI. Todo está preparado; solo hay que
correrlo y revisar.

**Reglas que no se pueden romper:**
- Modelo **Nano Banana 2.1** y calidad **1K** como máximo. Nunca 2K ni 4K.
- **Una sola generación por imagen: 3 en total.** Nada de variantes ni reintentos, aunque alguna no salga perfecta.
  Si el envío de una tarea falla y no produjo imagen, no la reenvíes por tu cuenta: anota el error y pregúntame.
- La clave está en la variable de entorno `WAVESPEED_API_KEY`. Si no existe, pídeme que la defina yo en la terminal
  (`$env:WAVESPEED_API_KEY = "..."`) y espera. Nunca la escribas en un archivo ni la muestres en la salida.
- No toques nada fuera de `diseno/` y no hagas commits.

**Pasos:**
1. Lee `diseno/prompts/logo_kab_taan.json` para saber qué se pide en cada imagen.
2. Ejecuta, una sola vez:
   ```powershell
   python diseno/herramientas/generar_imagenes.py diseno/prompts/logo_kab_taan.json
   ```
   Es el mismo script que ya generó las imágenes de la app. Ahora recibe el JSON como argumento y guarda las imágenes
   y su `manifest.json` en `diseno/generadas/logo_kab_taan/`. Si una imagen ya existe, la salta, así que volver a
   correrlo nunca genera dos veces la misma.
3. Mira cada imagen y compárala con su campo `revision` del JSON. Anota lo que no cumpla en el `manifest.json`
   (campos `revision_estado` y `revision_notas`), sin regenerar nada.
4. Crea `diseno/generadas/logo_kab_taan/galeria.html`: los 3 conceptos grandes, lado a lado, con su nombre, `para_que`
   y tus notas de revisión. Debajo de cada uno, muestra también el mismo símbolo en tamaño pequeño (64 px y 32 px) y
   sobre fondo azul marino `#0F1724`, para que se vea cómo queda como ícono y en modo oscuro. Ábrela en el navegador.
5. Al final, resume en la terminal: qué modelo usaste, cómo salió cada concepto, cuál recomiendas y por qué, y cuánto
   costó, si se sabe (precio publicado: 0.04 USD por imagen a 1K, unos 0.12 USD en total).
