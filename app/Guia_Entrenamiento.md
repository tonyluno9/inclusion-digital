# 📘 Guía Maestra: Entrenamiento de IA para Lengua de Señas

Esta guía detalla los estándares de calidad necesarios para recolectar datos de alta fidelidad. Un dataset limpio es la diferencia entre una IA que "adivina" y una IA que "entiende".

---

## 1. 🏗️ Preparación del Escenario (Entorno)

### 💡 Iluminación
*   **Luz Frontal:** Asegúrate de que la fuente de luz esté detrás de la cámara o a los lados, iluminando tu cara y manos de forma uniforme.
*   **Evita Contraluces:** No grabes con una ventana o luz brillante detrás de ti; esto convertirá tu cuerpo en una sombra y MediaPipe perderá el rastro.
*   **Sin Sombras Fuertes:** Las sombras sobre las manos hacen que MediaPipe pierda puntos de los dedos.

### 🖼️ Fondo (Background)
*   **Neutralidad:** Usa un fondo liso si es posible (pared blanca, gris o azul).
*   **Orden:** Evita fondos con mucho movimiento o muchos objetos, ya que esto puede causar "ruido" en la detección de los puntos de las manos.

---

## 2. 🧘 Postura y Posicionamiento

### 👤 Uso de la Silueta (HUD)
El programa muestra una guía blanca en pantalla. Debes alinearte de la siguiente forma:
*   **Cabeza:** Debe encajar dentro del círculo superior.
*   **Hombros:** Deben alinearse con la elipse horizontal.
*   **Distancia:** Siéntate a unos **80cm - 1.2m** de la cámara. Debes capturar desde la coronilla hasta el ombligo (Medio Cuerpo).

> [!IMPORTANT]
> Mantener siempre la misma distancia es crucial. Aunque el sistema normaliza los datos, la perspectiva cambia si te acercas o te alejas demasiado, lo que afecta la precisión.

---

## 3. ⏱️ El Proceso de Grabación

Cada seña empieza cuando **levantas las manos** y termina cuando **las bajas**. El sistema la recorta y la lleva a 30 fotogramas, sin importar cuánto dure. Es exactamente lo mismo que hace al detectar, por eso es importante grabar igual que como vas a usarlo.

### 🔴 Instrucciones de Captura:
1.  Presiona **'t'** y escribe en la ventana el nombre de la seña y tu nombre (puedes usar acentos y ñ). Con **'h'** ves todas las teclas.
2.  Ponte en posición con las **manos abajo** (fuera de cuadro o sobre las piernas).
3.  Presiona **Espacio** para activar la grabación.
4.  Levanta las manos, haz la seña a tu ritmo natural y **baja las manos** al terminar. La pantalla destella en **verde** cuando se guarda y en **rojo** si fue muy corta (también suena un beep).
5.  Repite el paso 4 las veces que quieras: cada seña se guarda sola.
6.  Si una salió mal, presiona **'z'** para deshacerla. **Espacio** pausa la grabación.

> [!IMPORTANT]
> Entre seña y seña baja las manos al menos medio segundo; si no, el sistema las junta en una sola.
> Las manos apoyadas muy abajo (en la mesa o las piernas) no cuentan como seña, aunque se vean.
> Antes de cada seña deja que el sistema te vea los hombros con las manos abajo: de ahí toma la referencia de tu cuerpo.

---

## 4. 🧠 Estrategia de Entrenamiento (Dataset)

Para que la IA sea "robusta", no grabes lo mismo 20 veces. Graba **variaciones**:

| Tipo de Muestra | Cantidad Sugerida | Propósito |
| :--- | :--- | :--- |
| **Velocidad Normal** | 10 muestras | La base del reconocimiento. |
| **Velocidad Lenta** | 5 muestras | Ayuda a la IA a entender la trayectoria exacta. |
| **Velocidad Rápida** | 5 muestras | Captura la seña en una conversación fluida. |
| **Micro-ángulos** | 5 muestras | Gira levemente el cuerpo a izq/der (5-10 grados). |

---

## 5. 👥 Varias Personas

Un modelo entrenado con una sola persona funciona bien con esa persona y mal con las demás.
*   Graba con **al menos 3 personas** distintas (cada una escribe su nombre al presionar 't').
*   No hace falta grabar "en espejo": el entrenamiento ya genera la versión para personas zurdas.

> [!NOTE]
> La versión actual usa las manos y los brazos (hombros, codos y muñecas). Las expresiones faciales todavía no se toman en cuenta.
> Si grabaste muestras antes de que la app leyera los codos, se conservan, pero conviene regrabarlas.

---

## 6. 🧍 Grabar movimientos para el avatar

El avatar no se entrena: copia tus movimientos grabados, uno por palabra.
1.  En Blender: abre el add-on (`blender/inclusion_avatar.py`), **Crear puntos** y **Escuchar en vivo**.
2.  En la app: **'a'**, escribe la palabra. Los puntos de Blender te siguen en vivo.
3.  **Espacio**, haz la seña una vez, con calma y bien hecha, y baja las manos: destello verde = guardado.
4.  Si no te gustó, vuelve a hacerla (reemplaza la anterior) o **'z'** para deshacer.

*   Una toma limpia por palabra basta: aquí importa la calidad, no la cantidad.
*   Que se vean tus hombros, codos y manos completos; de frente a la cámara.
*   Empieza y termina con los brazos abajo, quieto: así la animación arranca y acaba en reposo.

**Si al sistema le cuesta detectar tu cuerpo** (el personaje se queda quieto o los brazos saltan):
*   Aléjate hasta que se vean **la cabeza, los hombros, los codos y la cintura**. Muy cerca de la cámara, el
    modelo tiene que adivinar el cuerpo y se equivoca.
*   Luz de frente y pareja; nada brillante detrás de ti (ventana, lámpara). Una habitación oscura o a contraluz
    es la causa más común.
*   Ropa que contraste con el fondo: camisa oscura en pared clara o al revés, y mangas que dejen ver dónde está el codo.
*   El modelo de cuerpo se elige en `config.py` (`POSE_MODEL`): `full` por defecto; `heavy` detecta un poco mejor
    pero en este equipo es demasiado lento para el modo en vivo.

---

## 7. 🛠️ Ciclo de Mejora Continua

1.  **Graba:** Recolecta al menos 20 muestras por palabra y por persona.
2.  **Entrena:** Presiona **'e'** en la app, o ejecuta `python train_model.py` para ver además la precisión con personas que el modelo no vio.
3.  **Prueba:** Presiona **'d'** para el modo DETECCIÓN.
4.  **Limpia:** Si una palabra se confunde con otra, bórrala con **'x'** y vuelve a grabarla con más precisión.

---
*Documento generado para el Proyecto INCLUSION - Visión Inteligente.*
