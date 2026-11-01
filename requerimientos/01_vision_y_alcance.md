# 01 · Visión y alcance

## Problema

Las personas Sordas que se comunican en Lengua de Señas Mexicana (LSM) encuentran barreras
en interacciones cotidianas con personas oyentes que no conocen LSM (recepción, ventanilla,
consultorio, aula). INCLUSION es una herramienta de apoyo para conversaciones cortas cara a cara:
traduce señas a texto y voz, y la voz del interlocutor a texto.

> No sustituye a un intérprete de LSM. Es un apoyo para frases cortas y de cortesía.

## Usuarios

| Usuario | Necesidad | Implicaciones |
|---|---|---|
| **Persona Sorda (señante)** | Que el oyente entienda sus señas; leer lo que el oyente dice | Toda la retroalimentación debe ser **visual**; el texto del interlocutor debe ser grande y estar a la vista |
| **Persona oyente (interlocutor)** | Escuchar o leer lo que se seña; hablar de forma natural | Voz clara (TTS); subtítulo grande; voz a texto (STT) |
| **Entrenador / desarrollador** | Grabar señas, entrenar y medir el modelo | Flujo de grabación rápido, sin consola; métricas honestas |

## Escenario principal

1. Laptop con webcam frente a la persona Sorda, a 0.8–1.2 m, en un lugar iluminado.
2. La persona levanta las manos, hace una seña y las baja.
3. La app muestra la palabra en grande, la dice en voz alta y la agrega al historial.
4. Tras una pausa de ~2.5 s, la app une las palabras en una oración natural, la muestra y la dice.
5. El interlocutor responde hablando; la app muestra su respuesta como texto (si STT está activo).

## Alcance de esta versión

- Reconocimiento de **señas aisladas** (una seña entre manos arriba y manos abajo) del vocabulario de [04_vocabulario_y_datos.md](04_vocabulario_y_datos.md).
- Aplicación de escritorio en Python (Windows prioritario).
- Grabación de dataset, entrenamiento y evaluación dentro del mismo proyecto.
- Servicios en línea opcionales: voz (gTTS), oración natural (Claude), voz a texto (Google).

## Fuera de alcance (por ahora)

- Reconocimiento de **señas continuas** sin bajar las manos y gramática de LSM completa.
- Deletreo manual (alfabeto dactilológico).
- Marcadores no manuales (expresión facial, movimiento de cabeza).
- Traducción de español a LSM con avatar.
- App móvil (existe la exportación a TFLite como base, ver RF-16).
