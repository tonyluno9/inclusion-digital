# Diseño visual — INCLUSION

Identidad visual de la app unificada (señas → subtítulos y avatar en una sola ventana).

## Estilo

- **Tono:** cálido, claro, accesible. Moderno y sobrio, sin infantilizar.
- **Tema:** oscuro por defecto (la cámara y el avatar resaltan sobre fondo oscuro), con buen contraste para leer
  subtítulos grandes (RNF-05).
- **Fuente:** [Lexend](https://fonts.google.com/specimen/Lexend) (licencia OFL). Diseñada para leer con facilidad, con
  formas abiertas y legibles en tamaños grandes. Pesos: 400 texto, 600 títulos y botones, 700 subtítulos grandes.
  No se genera con IA: se descarga del repositorio oficial `google/fonts`.

| Uso | Color |
|---|---|
| Fondo | `#0F1724` (azul marino profundo) |
| Superficie (tarjetas, paneles) | `#1A2333` |
| Principal (detección, botones) | `#2EC4B6` (turquesa) |
| Avatar | `#7C5CFF` (violeta) |
| Grabando / alerta | `#FF6B6B` (coral) |
| Aviso de encuadre | `#FFA53C` (naranja) |
| Acento cálido | `#FFC857` (ámbar) |
| Texto | `#F4F6FA` (casi blanco), secundario `#9AA4B5` |

## Imágenes que se generan

Solo 5, con **Nano Banana 2.1** en calidad **1K** y una sola generación por imagen (sin reintentos). Los íconos y las ilustraciones van en una sola imagen cada uno y después se recortan.
Ninguna imagen lleva texto: los modelos de imagen deforman las letras, y el texto lo pone la app con Lexend.

| Archivo | Para qué | Tamaño |
|---|---|---|
| `logo.png` | Ícono de la ventana, pantalla de inicio, encabezado | 1K, 1:1 |
| `iconos.png` | Hoja de 20 íconos (5 × 4): botones y menús | 1K, 5:4 |
| `fondo_avatar.png` | Escenario donde se ve el avatar | 1K, 16:9 |
| `fondo_inicio.png` | Pantalla de bienvenida | 1K, 16:9 |
| `ilustraciones.png` | 4 ilustraciones (2 × 2): bienvenida, encuadre, sin cámara, entrenando | 1K, 1:1 |

Los prompts exactos están en [`prompts/imagenes.json`](prompts/imagenes.json). Para generarlas, ver
[`prompts/PROMPT_POWERSHELL.md`](prompts/PROMPT_POWERSHELL.md). Salen en `generadas/`.

### Después de generarlas (lo hace la app, no la persona)

- **Íconos:** la hoja se corta en 20 celdas iguales. Cada ícono es negro sobre blanco, así que se convierte en una
  máscara y se pinta del color que toque (sirve para tema claro y oscuro). Si la hoja sale desalineada o con íconos de
  estilos distintos, se usa en su lugar un set libre de íconos de línea (Lucide, licencia ISC).
- **Logo e ilustraciones:** el fondo blanco se vuelve transparente.
- **Fondos:** a 1K se ven suaves en pantalla grande; se escalan a la ventana con un ligero desenfoque, que en un fondo
  no se nota.
