# Sitio informativo de K'ab T'aan

Sitio estático (HTML, CSS y JavaScript, sin compilar nada) que explica el proyecto a jueces y visitantes de
Infomatrix. Se publica en GitHub Pages con [`.github/workflows/pages.yml`](../.github/workflows/pages.yml).

## Verlo en tu computadora

Los módulos de JavaScript no cargan con doble clic sobre `index.html` (el navegador los bloquea en `file://`).
Abre una terminal en esta carpeta y corre un servidor local:

```powershell
cd sitio
python -m http.server 8780 --bind 127.0.0.1
```

Luego abre <http://127.0.0.1:8780>.

## Qué hay en cada sección

| # | Sección | Qué muestra |
|---|---|---|
| — | Portada | Logo, nombre, significado y un subtítulo como el de la app |
| 01 | El problema | Tres situaciones cotidianas y cifras de INEGI (ENADID 2023) y de la LGIPD, con enlace a la fuente |
| 02 | La solución | Las dos direcciones (seña → texto y voz; texto o voz → avatar) y el aviso de que no sustituye a un intérprete |
| 03 | Cómo funciona | Diagrama animado en 10 pasos que cambia al bajar (`js/proceso.js`, `js/figura.js`) |
| 04 | El avatar en vivo | El personaje de la app con three.js y el mismo retargeting (`js/avatar-sitio.js`, `js/retarget.js`), movimientos de muestra (`js/gestos.js`) y «Imítame» con la cámara (`js/imitame.js`) |
| 05 | Funciones | Traducir, Aprender, Diccionario, Entrenar, Avatar, escenarios y capturas reales de la app |
| 06 | Resultados | Exactitud con su letra chica, rendimiento, pruebas, stack y arquitectura |
| 07 | Privacidad y ética | Qué se guarda, qué sale a internet y qué falta (validación con la comunidad Sorda) |
| 08 | Identidad maya | El nombre, la greca escalonada, el logo y un convertidor a numerales mayas (`js/maya.js`) |
| 09 | Próximos pasos | Línea de tiempo |
| 10 | Equipo y créditos | **Datos por llenar** (ver abajo) |

## Llenar los datos del equipo

En `index.html`, busca el comentario `EQUIPO: LLENA AQUÍ LOS DATOS`. Cambia cada texto entre corchetes
(`[Nombre completo]`, `[Nombre de la escuela]`, etc.) y borra la clase `por-llenar` de esa etiqueta para que deje de
verse marcada en ámbar. Para quitar una tarjeta, borra su `<li>` completo.

## Publicar en GitHub Pages

1. En GitHub: **Settings → Pages → Build and deployment → Source: GitHub Actions** (solo una vez).
2. Une esta rama a `main`. Cada cambio en `sitio/` que llegue a `main` vuelve a publicar el sitio.
   También se puede lanzar a mano desde la pestaña **Actions → Sitio web (GitHub Pages) → Run workflow**.
3. El sitio queda en `https://<usuario>.github.io/<repositorio>/`. Si la dirección es otra, cambia `og:url` y
   `og:image` en `index.html` (la vista previa al compartir el enlace usa esas dos URL).

Antes de publicar, el workflow corre [`../.github/revisar_sitio.py`](../.github/revisar_sitio.py), que revisa que no
falte ningún archivo enlazado.

## Recursos

- Copiados de la app (`app/web/assets/`) y convertidos a WebP: portada, fondos, escenarios, tutorial, insignias,
  categorías, estados, íconos, el personaje `personaje.glb` y su `personaje_reposo.json`.
- `js/retarget.js` es una copia exacta de `app/web/js/retarget.js`. Si cambia en la app, cópialo de nuevo.
- `vendor/three/` es three.js r160 (licencia MIT), el mismo de la app.
- `assets/fuentes/Lexend-latin.woff`: Lexend (SIL Open Font License, `OFL.txt`) recortada a caracteres latinos.
- `assets/img/sitio/`: 6 ilustraciones nuevas generadas con Nano Banana 2.1 (WaveSpeedAI, 1K, una sola generación
  cada una). Prompts en [`../diseno/prompts/sitio_web.json`](../diseno/prompts/sitio_web.json), originales y
  manifiesto en `../diseno/generadas/sitio_web/`.
- `assets/img/app/`: capturas de la versión nueva de la app corriendo con un video de prueba; la imagen de la cámara
  y el nombre de quien grabó el dataset están difuminados.
- `assets/img/compartir.jpg`: imagen de 1200 × 630 para la vista previa en redes.

## Lo que el sitio no incluye a propósito

- Ningún dato personal: ni el dataset, ni `model.pkl`, ni los clips del avatar grabados por una persona, ni correos.
- Ninguna foto de personas reales.
- «Imítame» descarga MediaPipe para web (de jsDelivr) y sus modelos (de Google) **solo si el visitante lo pide**;
  el video de su cámara no sale de su navegador.
