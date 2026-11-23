# Apify: procedencia de la captura

Para la extracción en Apify que Kiara aportó al dataset se utilizó **Mercadolibre Scraper (español castellano)**, del desarrollador **karamelo**. Tomás confirmó la referencia el **23/11/2026** y se verificaron el nombre y la autoría en la ficha pública. Es un actor de un tercero; no fue desarrollado por el equipo.

- [Ficha del scraper](https://apify.com/karamelo/mercadolibre-scraper-espanol-castellano).
- [Esquema de entrada del proveedor](https://apify.com/karamelo/mercadolibre-scraper-espanol-castellano/input-schema).
- Identificador público: `karamelo/mercadolibre-scraper-espanol-castellano`.

## Estado para la entrega

| Elemento | Estado |
| --- | --- |
| Servicio y fuente | Apify; publicaciones de Mercado Libre Argentina. |
| Autoría | Actor externo del desarrollador karamelo, identificado el 23/11/2026. |
| Nombre, URL e identificador del actor | Confirmados; se enlazan arriba. |
| Configuración histórica y enlace a la ejecución de Kiara | Todavía no recibidos. Deben excluir tokens y credenciales. |
| Código fuente del scraper | No incluido en este repositorio. No se localizó un enlace al fuente público en la ficha revisada. |

La identificación del scraper queda confirmada. El esquema enlazado describe su entrada actual; **no demuestra qué parámetros, versión ni ejecución usó Kiara para la captura histórica**. Esos datos deben recuperarse del registro original, sin atribuirle otras corridas de la cuenta.

La ficha del proveedor no sustituye el código fuente solicitado para la entrega. Si se obtiene el fuente externo, hay que comprobar su licencia antes de redistribuirlo. Mientras tanto se documenta la dependencia externa y se entrega íntegramente el código propio de ETL e inferencia.

La prueba prevista con *Shopify & WooCommerce Products Scraper – Any Store* fue cancelada. No se presenta ese actor como origen del dataset real.

## Código propio que sí se entrega

Desde el 23/11 también se entrega el [actor propio de inferencia ML](../actor_apify/README.md), con fuente, Dockerfile, esquemas y modelo entrenado. Ese código cubre la inferencia del equipo; **es distinto del scraper de karamelo** y no se presenta como su código fuente.

La limpieza y el análisis se ejecutan en n8n con estos archivos del equipo:

- [Entrada del proceso](../n8n/python/tacctico_etl/__init__.py).
- [Validación y limpieza](../n8n/python/tacctico_etl/pipeline.py).
- [Funciones del notebook de Kiara](../n8n/python/tacctico_etl/kiara_etl.py).
- [Métricas y preparación del dashboard](../n8n/python/tacctico_etl/analytics.py).
- [Historial de lotes y publicación](../n8n/python/tacctico_etl/storage.py).

Este código está disponible para revisión, pero no es el código del actor externo de scraping. El flujo vigente toma el CSV crudo ya existente en Drive y no lanza Apify ni consume nuevos créditos al abrir TACCtico.
