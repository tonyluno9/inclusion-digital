# Requerimientos — INCLUSION

Esta carpeta define **qué debe cumplir** el sistema. El código vive en [`../app/`](../app/).
Cada cambio al proyecto debe mantener estos requerimientos o actualizarlos aquí primero.

| Documento | Contenido |
|---|---|
| [01_vision_y_alcance.md](01_vision_y_alcance.md) | Problema, usuarios, alcance de la versión actual y lo que queda fuera |
| [02_requerimientos_funcionales.md](02_requerimientos_funcionales.md) | Qué hace el sistema (RF-xx) con criterios de aceptación |
| [03_requerimientos_no_funcionales.md](03_requerimientos_no_funcionales.md) | Rendimiento, precisión, privacidad, accesibilidad, robustez (RNF-xx) |
| [04_vocabulario_y_datos.md](04_vocabulario_y_datos.md) | Señas soportadas, protocolo de grabación y formato del dataset |
| [05_verificacion.md](05_verificacion.md) | Cómo se verifica cada requerimiento: pruebas automáticas y prueba manual con cámara |

## Convenciones

- **IDs estables:** `RF-07`, `RNF-03`. No se reutilizan; si uno se elimina se marca *Retirado*.
- **Prioridad:** **Debe** (obligatorio para considerar el sistema funcional), **Debería** (importante, puede esperar una iteración), **Podría** (deseable).
- **Estado:** ✅ cumplido y verificado · 🟡 implementado, falta verificar con cámara o con datos reales · ⏳ pendiente. Se lleva en la matriz de [05_verificacion.md](05_verificacion.md).
- Las pruebas automáticas citan el ID que verifican en su docstring, por ejemplo `"""RF-03: ..."""`.

## Cómo iterar

1. Si la idea cambia el comportamiento, primero agrega o edita el requerimiento aquí.
2. Implementa en `app/` y agrega la prueba que lo verifica.
3. Actualiza el estado y la matriz de [05_verificacion.md](05_verificacion.md).
4. Corre `python -m unittest discover -s tests -t .` dentro de `app/` antes de hacer commit.
