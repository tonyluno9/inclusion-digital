# 04 · Vocabulario y datos

## Vocabulario inicial (v1)

Señas de cortesía y saludo de LSM, tomadas del dataset original del proyecto:

| # | Etiqueta (`label`) | Texto mostrado | Notas |
|---|---|---|---|
| 1 | `hola` | Hola | |
| 2 | `adios` | Adiós | |
| 3 | `bienvenido` | Bienvenido | |
| 4 | `buenos dias` | Buenos días | Seña compuesta: se graba como una sola seña |
| 5 | `buenas tardes` | Buenas tardes | Seña compuesta |
| 6 | `buenas noches` | Buenas noches | Seña compuesta |
| 7 | `gracias` | Gracias | |
| 8 | `de nada` | De nada | El dataset viejo usa `denada` |
| 9 | `por favor` | Por favor | |
| 10 | `perdon` | Perdón | |
| 11 | `mucho gusto` | Mucho gusto | |

- Las etiquetas se guardan en minúsculas. Se aceptan acentos y ñ (UTF-8); el texto mostrado y hablado es la etiqueta tal cual.
- Para agregar una seña nueva basta con grabarla (RF-09) y reentrenar (RF-11); se debe agregar aquí.

## Protocolo de grabación

Detalle práctico en [`app/Guia_Entrenamiento.md`](../app/Guia_Entrenamiento.md). Mínimos para cumplir RNF-02:

| Aspecto | Mínimo |
|---|---|
| Personas distintas | 3 (ideal 5+, distintas complexiones; incluir al menos una persona zurda) |
| Muestras por seña y persona | 20 (10 ritmo normal, 5 lento, 5 rápido) |
| Distancia | 0.8–1.2 m, cabeza y hombros visibles |
| Postura inicial y final | Manos abajo, fuera de cuadro o sobre las piernas |
| Iluminación | Frontal, sin contraluz |
| Fondos / lugares | Al menos 2 distintos |

## Formato del dataset (`app/data/dataset_v2.csv`)

- CSV UTF-8 con encabezado: `label, person, f0 … f4409`.
- Cada fila es una seña: **30 frames × 147 valores crudos**, aplanados por frame.
- Valores por frame:
  - `[0:63]` mano izquierda, 21 puntos × (x, y, z)
  - `[63:126]` mano derecha, 21 puntos × (x, y, z)
  - `[126:135]` nariz, hombro izquierdo, hombro derecho × (x, y, z)
  - `[135:147]` codo izquierdo, codo derecho, muñeca izquierda, muñeca derecha (del cuerpo) × (x, y, z)
- Izquierda y derecha son las de la persona.
- `x` e `y` en unidades de la altura de la imagen (x multiplicada por ancho/alto); `z` de la mano relativa a la muñeca.
- Mano o punto del cuerpo ausente → ceros.
- **Formato anterior** (135 valores, sin codos): la app lo respalda en `data/backups/` y lo convierte al abrirlo
  (codos en cero); `train_model.py` también lo lee. Conviene regrabar esas señas para que el modelo aprenda los brazos.
- Las features del modelo se calculan desde estos valores crudos (`app/modules/landmarks.py`), por lo que se pueden cambiar sin regrabar.

## Clips del avatar

Un archivo JSON por palabra en `app/data/avatar/` con el movimiento 3D. Formato en [06_avatar.md](06_avatar.md).

## Dataset anterior

`app/data/legacy/dataset_v1.csv` (1 570 muestras, 1 persona + espejo) usa features relativas a la muñeca sin posición
corporal. No es compatible con el modelo actual; se conserva como referencia y para pruebas de regresión del segmentador.
