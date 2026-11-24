# Datos y procedencia

[Volver al proyecto](../README.md)

## Lote disponible

Los precios corresponden a la captura del **14/11/2026**; el procesamiento del **23/11/2026** no los convierte en precios actuales.

| Resultado | Publicaciones |
| --- | ---: |
| Captura original de entrada | 591 |
| Selección útil | 347 |
| Catálogo publicado | 372 |
| Análisis sin los 17 precios atípicos de la selección útil | 330 |
| Evaluadas por el modelo | 335 |
| Presentaciones pendientes de confirmar, sin evaluar por ML | 37 |

El catálogo conserva 25 publicaciones relevantes adicionales que no tienen una presentación resoluble. No se fuerza un número fijo de salida para futuras capturas.

El [scraper externo](../apify/README.md), el [proceso de actualización](../n8n/README.md) y el [modelo propio](MODELO_ML.md) tienen sus contratos y limitaciones documentados por separado.

## Esquema del CSV


El [CSV del lote incluido](../data_public/actual/mercadolibre_validado.csv) usa UTF-8, comas y una fila por publicación, con 31 columnas:

| Campos | Uso |
| --- | --- |
| `id_publicacion`, `titulo`, `url`, `fuente` | Identificación, título, enlace y origen. |
| `precio_publicado`, `moneda`, `capturado_en` | Importe publicado en ARS y captura UTC ISO 8601. |
| `insumo`, `marca`, `vendedor`, `tipo_vendedor`, `vendedor_id` | Clasificación e identificación comercial. |
| `gramos_unidad`, `unidades`, `es_pack`, `gramos_totales`, `precio_100g` | Presentación y referencia de precio. |
| `fuente_peso`, `peso_discrepa`, `outlier_precio`, `revision_presentacion` | Procedencia de la medida y alertas. |
| `tiene_promo`, `descuento_pct`, `precio_anterior`, `envio`, `promocion` | Condiciones de referencia de la captura. |
| `categoria`, `nombre_ficha`, `linea`, `sabor`, `rnpa` | Datos complementarios de la ficha. |

Los archivos `metricas.json`, `calidad.json` y `manifest.json` documentan métodos, supuestos, conteos e integridad. El dashboard conserva el diseño final del equipo y recalcula sus datos sobre el mismo lote. Sus estadísticas normalizadas no sustituyen la comprobación de presentación, disponibilidad y cargos para un pedido concreto.

`data_public/actual/` también es el respaldo de la demo cuando Drive no responde. Se comprueba el manifiesto antes de cargarlo; si una actualización local queda incompleta, se vuelve a este lote verificado. No se incluye una segunda copia del CSV de 363 publicaciones. Los datos artificiales de `scripts/fixtures/` se usan únicamente para comprobar el historial y los duplicados en las pruebas.

El equipo autorizó publicar estos resultados finales del Capstone. El dataset crudo, rechazos, credenciales y carpetas privadas no forman parte de esta distribución. Las referencias por hora se identifican como supuestos del equipo; no como valores salariales oficiales.

## Fuentes y licencias


- Publicaciones de [Mercado Libre Argentina](https://www.mercadolibre.com.ar/), con sus enlaces y fecha de captura. [Términos del programa de desarrolladores](https://developers.mercadolibre.com.ar/es_ar/es-ar-terminos-y-condiciones).
- [Streamlit](https://streamlit.io/terms-of-use) usa Apache 2.0; [pandas](https://github.com/pandas-dev/pandas/blob/v2.3.3/LICENSE) y [ReportLab](https://pypi.org/project/reportlab/5.1.0/) usan licencias BSD.
- El equipo debe confirmar la licencia de su código antes de agregar un `LICENSE` con permisos de reutilización.
