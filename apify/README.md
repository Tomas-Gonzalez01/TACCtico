# Apify: procedencia de la captura

La captura de Mercado Libre fue obtenida por Kiara con un **actor de un tercero**, según la confirmación de Tomás del 19/11/2026. No fue desarrollado por el equipo. El nombre, enlace y autor exactos todavía no están disponibles en el material recibido.

## Estado para la entrega

| Elemento | Estado |
| --- | --- |
| Servicio y fuente | Apify; publicaciones de Mercado Libre Argentina. |
| Autoría | Actor externo; proveedor pendiente de identificar. |
| Nombre, URL e identificador del actor | Pendientes de recuperar de la cuenta de Kiara. |
| Configuración de entrada y enlace a una ejecución | Pendientes. Deben excluir tokens y credenciales. |
| Código fuente del actor | No disponible en este repositorio. No se afirma que el equipo lo haya escrito. |

Para cerrar el requisito de «subir el código de Apify», Kiara debe recuperar la ficha del actor y comprobar si su fuente está publicada y permite redistribución. Si el proveedor no entrega el código, corresponde aclararlo con la docente y presentar la referencia y la configuración autorizada. **Una referencia al servicio no equivale al código fuente solicitado.**

La prueba prevista con *Shopify & WooCommerce Products Scraper – Any Store* fue cancelada. No se presenta ese actor como origen del dataset real.

## Código propio que sí se entrega

La limpieza y el análisis se ejecutan en n8n con estos archivos del equipo:

- [Entrada del proceso](../n8n/python/tacctico_etl/__init__.py).
- [Validación y limpieza](../n8n/python/tacctico_etl/pipeline.py).
- [Funciones del notebook de Kiara](../n8n/python/tacctico_etl/kiara_etl.py).
- [Métricas y preparación del dashboard](../n8n/python/tacctico_etl/analytics.py).
- [Historial de lotes y publicación](../n8n/python/tacctico_etl/storage.py).

Este código está disponible para revisión, pero no es el código del actor externo de scraping. El flujo vigente toma el CSV crudo ya existente en Drive y no lanza Apify ni consume nuevos créditos al abrir TACCtico.
