# Avatar de INCLUSION en Blender

Add-on de un solo archivo: `inclusion_avatar.py` (RF-21, RF-22 y RF-23, ver `requerimientos/06_avatar.md`).
Probado en Blender 5.2.

## Instalar
- **Como add-on:** Edit > Preferences > Add-ons > flecha del menú > *Install from Disk* y elegir `inclusion_avatar.py`; activarlo.
- **Sin instalar:** abrir el archivo en el *Text Editor* y pulsar *Run Script* (se registra solo).

El panel aparece en la vista 3D, barra lateral (`N`), pestaña **INCLUSION**.

## Personaje

`personaje/avatar_inclusion.blend` trae el personaje listo: conectado, con la textura dentro y una cámara que encuadra
el torso. Ábrelo con el add-on instalado (o deja que Blender ejecute el script que trae dentro). Para regenerarlo desde el
FBX: `blender -b --factory-startup --python blender/crear_escena.py`.

Con otro archivo: importa el FBX del personaje y pulsa **Conectar personaje** (busca un rig con un perfil conocido;
hoy, el de Tripo). **Pose de descanso** lo devuelve a la pose T.

## Uso en vivo con la app
1. En Blender: **Crear puntos** (colección `INCLUSION_Puntos`: 33 puntos del cuerpo + 21 por mano, con un esqueleto de líneas).
2. **Escuchar en vivo** (por defecto `127.0.0.1:5005`). El panel muestra "Escuchando" y los frames recibidos.
3. En la app presiona `a` para entrar al modo avatar: los puntos y el personaje conectado siguen a la persona. Si un lado no se detecta, se queda quieto.
4. **Detener** libera el puerto. Con "Importar clips automáticamente" activo, cada clip que la app guarda se importa solo.

## Importar clips
**Importar clip** abre un `.json` de `app/data/avatar/`. Los puntos reciben la acción `puntos_<palabra>` (un slot por punto) y el personaje conectado, la acción `seña_<palabra>` con la rotación de sus huesos. Van a los fps de la escena desde el "Frame de inicio" y se ajusta el rango de la escena. Reimportar la misma palabra reemplaza las acciones.

## Pendiente
Reproducir frases encadenando clips (RF-24) y contactos exactos con IK (RF-25).

## Prueba
`blender -b --factory-startup --python-exit-code 1 --python blender/tests/test_inclusion_avatar.py`
`blender -b --factory-startup --python-exit-code 1 --python blender/tests/test_retarget.py`
(o `cd app && python -m unittest discover -s tests -t .`, que la ejecuta si encuentra Blender).
