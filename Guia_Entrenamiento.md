# 📘 Guía Maestra: Entrenamiento de IA para Lengua de Señas

Esta guía detalla los estándares de calidad necesarios para recolectar datos de alta fidelidad. Un dataset limpio es la diferencia entre una IA que "adivina" y una IA que "entiende".

---

## 1. 🏗️ Preparación del Escenario (Entorno)

### 💡 Iluminación
*   **Luz Frontal:** Asegúrate de que la fuente de luz esté detrás de la cámara o a los lados, iluminando tu cara y manos de forma uniforme.
*   **Evita Contraluces:** No grabes con una ventana o luz brillante detrás de ti; esto convertirá tu cuerpo en una sombra y MediaPipe perderá el rastro.
*   **Sin Sombras Fuertes:** Las sombras proyectadas sobre el rostro pueden engañar al detector de expresiones faciales.

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

## 3. ⏱️ El Proceso de Grabación Manual

El sistema actual utiliza **Remuestreo Dinámico (Interpolación)**. Esto significa que la IA siempre verá 30 fotogramas, sin importar cuánto dure tu grabación real.

### 🔴 Instrucciones de Captura:
1.  Presiona **'t'** para asignar el nombre de la seña.
2.  Ponte en posición **antes** de empezar.
3.  Presiona **Espacio** para INICIAR (el sistema solo empezará a contar cuando detecte tus manos).
4.  Realiza la seña a tu ritmo natural.
5.  Presiona **Espacio** para TERMINAR inmediatamente después de finalizar el movimiento.

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

## 5. 😊 Marcadores No Manuales (Expresiones)

En la Lengua de Señas, la cara es el "tono de voz".
*   **Coherencia:** Si grabas una seña de "Pregunta", asegúrate de fruncir el ceño (**ENOJADO/SERIO**) durante toda la grabación.
*   **Enfásis:** Usa el detector de ánimo en la esquina superior derecha para verificar que tus labios y cejas están transmitiendo la emoción correcta antes de presionar Espacio.

---

## 6. 🛠️ Ciclo de Mejora Continua

1.  **Graba:** Recolecta al menos 20 muestras por palabra.
2.  **Entrena:** Cierra `main.py` y ejecuta `train_model.py`.
3.  **Prueba:** Abre `main.py` en modo DETECCIÓN.
4.  **Limpia:** Si una palabra se confunde con otra, usa `clear_word.py` para borrar la conflictiva y vuelve a grabarla con más precisión.

---
*Documento generado para el Proyecto INCLUSION - Visión Inteligente.*
