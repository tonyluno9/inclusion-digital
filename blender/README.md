# Avatar de INCLUSION en Blender

Add-on de un solo archivo: `inclusion_avatar.py` (RF-21 y RF-22, ver `requerimientos/06_avatar.md`).
Probado en Blender 5.2.

## Instalar
- **Como add-on:** Edit > Preferences > Add-ons > flecha del menú > *Install from Disk* y elegir `inclusion_avatar.py`; activarlo.
- **Sin instalar:** abrir el archivo en el *Text Editor* y pulsar *Run Script* (se registra solo).

El panel aparece en la vista 3D, barra lateral (`N`), pestaña **INCLUSION**.

## Uso en vivo con la app
1. En Blender: **Crear puntos** (colección `INCLUSION_Puntos`: 33 puntos del cuerpo + 21 por mano, con un esqueleto de líneas).
2. **Escuchar en vivo** (por defecto `127.0.0.1:5005`). El panel muestra "Escuchando" y los frames recibidos.
3. En la app presiona `a` para entrar al modo avatar: los puntos siguen a la persona. Si un lado no se detecta, sus puntos se quedan quietos.
4. **Detener** libera el puerto. Con "Importar clips automáticamente" activo, cada clip que la app guarda se importa solo.

## Importar clips
**Importar clip** abre un `.json` de `app/data/avatar/`. Se crea una acción `seña_<palabra>` (una sola, con un slot por punto), a los fps de la escena desde el "Frame de inicio", y se ajusta el rango de la escena. Reimportar la misma palabra reemplaza la acción. Los frames sin detección no llevan keyframe.

## Pendiente
Conectar los puntos al rig del personaje (RF-23, etapa A3) es la siguiente etapa.

## Prueba
`blender -b --factory-startup --python-exit-code 1 --python blender/tests/test_inclusion_avatar.py`
(o `cd app && python -m unittest discover -s tests -t .`, que la ejecuta si encuentra Blender).
