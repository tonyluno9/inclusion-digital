# INCLUSION — Reconocimiento de Lengua de Señas Mexicana

Herramienta de apoyo para conversaciones cortas entre una persona Sorda que seña en LSM y una persona oyente:
reconoce señas con la webcam y las muestra como texto y voz; lo que dice el interlocutor aparece como texto y un
avatar 3D lo dice en señas.

| Carpeta | Contenido |
|---|---|
| [`app/`](app/) | La aplicación: código, interfaz, pruebas y scripts de instalación. Empieza por [app/README.md](app/README.md) |
| [`requerimientos/`](requerimientos/) | Qué debe cumplir el sistema, cómo se verifica y el estado de cada requerimiento |
| [`blender/`](blender/) | El personaje del avatar y el add-on de Blender ([blender/README.md](blender/README.md)) |
| [`diseno/`](diseno/) | Identidad visual: paleta, fuente, prompts de las imágenes y cómo se convierten en recursos |
| [`sitio/`](sitio/) | Sitio informativo para Infomatrix (estático, se publica en GitHub Pages). Ver [sitio/README.md](sitio/README.md) |

Inicio rápido en Windows: doble clic en `app/instalar.bat` y después en `app/iniciar.bat`, que abre la app en su
propia ventana (traducir, entrenar y avatar). La versión anterior, con la ventana de OpenCV: `app/iniciar_clasico.bat`.
