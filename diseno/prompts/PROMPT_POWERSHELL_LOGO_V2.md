# Prompt para Claude en PowerShell: logo de K'ab T'aan, versión 2 (detalles mayas)

Copia todo lo que está debajo de la línea y pégalo en Claude Code, abierto en PowerShell en
`C:\Users\Angel Perez\Downloads\inclusion\repo`.

---

Genera 2 versiones mejoradas del logo **K'ab T'aan** con WaveSpeedAI, **editando** el concepto que elegí
(`diseno/generadas/logo_kab_taan/concepto_dialogo.png`: mano sólida, mano de puntos y estrella en medio). Se le
agregan detalles mayas para que no se vea vacío. Todo está preparado.

**Reglas que no se pueden romper:**
- Modelo **Nano Banana 2.1** en su modo de **edición** (imagen de referencia + instrucciones) y calidad **1K** como
  máximo. Nunca 2K ni 4K.
- **Una sola generación por imagen: 2 en total.** Nada de variantes ni reintentos, aunque alguna no salga perfecta.
  Si el envío de una tarea falla y no produjo imagen, no la reenvíes por tu cuenta: anota el error y pregúntame.
- Si Nano Banana 2.1 no tiene modo de edición en WaveSpeedAI, **detente y pregúntame**. No lo cambies por texto a
  imagen ni por otro modelo.
- La clave está en la variable de entorno `WAVESPEED_API_KEY`. Si no existe, pídeme que la defina yo en la terminal
  (`$env:WAVESPEED_API_KEY = "..."`) y espera. Nunca la escribas en un archivo ni la muestres en la salida.
- No toques nada fuera de `diseno/` y no hagas commits.

**Pasos:**
1. Lee `diseno/prompts/logo_kab_taan_v2.json` (trae `"modo": "edicion"` y la imagen de `referencia`).
2. **Antes de gastar nada**, revisa en la documentación de WaveSpeedAI (https://wavespeed.ai/docs) el modo de edición
   de Nano Banana 2.1:
   - su identificador exacto (en el script está como `MODELO_EDICION = "google/nano-banana-2.1/edit"`);
   - cómo recibe la imagen de referencia (en el script va en el campo `images` como data URI en base64). Si pide una
     URL en vez de base64, usa el endpoint de subida de archivos de WaveSpeedAI que diga la documentación;
   - qué campos acepta (resolución, proporción, formato).

   Ajusta solo lo necesario en `diseno/herramientas/generar_imagenes.py` para que coincida. El modo de texto a imagen
   tiene que seguir funcionando igual.
3. Ejecuta, una sola vez:
   ```powershell
   python diseno/herramientas/generar_imagenes.py diseno/prompts/logo_kab_taan_v2.json
   ```
   Guarda las imágenes y su `manifest.json` en `diseno/generadas/logo_kab_taan_v2/`. Si una imagen ya existe, la
   salta.
4. Mira cada imagen y compárala con su campo `revision` del JSON. Anota lo que no cumpla en el `manifest.json`
   (campos `revision_estado` y `revision_notas`), sin regenerar nada.
5. Crea `diseno/generadas/logo_kab_taan_v2/galeria.html` con la referencia original y las 2 versiones nuevas lado a
   lado, cada una grande y también en 64 px, 32 px y sobre fondo azul marino `#0F1724`. Ábrela en el navegador.
6. Al final, resume en la terminal: qué modelo y endpoint usaste, cómo salió cada versión, cuál recomiendas y cuánto
   costó, si se sabe.
