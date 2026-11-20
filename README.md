# TACCtico

Compará ofertas de insumos sin TACC y armá el presupuesto de tu negocio con presentaciones completas, cantidades y precios de Mercado Libre Argentina. Incluye catálogo, lista de compras, PDF y el dashboard de abastecimiento de Kiara.

[Abrir TACCtico online](https://tacctico-portafolio-ucn4pkoeemkzx9fowx7ktt.streamlit.app/)

## Entrega y revisión del código

- [Checklist contra la consigna de GitHub](docs/ENTREGA_GITHUB.md), con evidencias y pendientes.
- [Guía para leer el código](docs/CODIGO.md), responsabilidades y verificación del formato.
- [Flujos importables de n8n, código Python e instalación](n8n/README.md).
- [Make: prototipo anterior, captura real e historial](make/README.md).
- [Apify: autoría externa y datos que falta recuperar](apify/README.md).

### Evidencias de automatización

![Flujo real instalado en n8n](docs/evidencias/n8n-flujo-real.jpg)

Captura del editor de n8n del 19/11/2026. El código y las plantillas importables están en `n8n/`; durante esta revisión no se ejecutó el flujo.

![Make: webhook y subida a Drive](docs/evidencias/make-escenario-historico.jpg)

El prototipo de Make fue reemplazado por n8n. Su captura muestra el escenario inactivo y la ejecución exitosa del 14/11/2026 a las 20:19:47. No se lanzó una corrida nueva.

Se puede consultar sin cuenta. La versión procesada el **19/11/2026** tiene **372 publicaciones reales**, con precios de la captura del **14/11/2026**. El análisis estadístico usa **330** publicaciones útiles sin precios atípicos. La fecha de procesamiento no actualiza los precios de la captura.

La interfaz muestra precios en formato argentino, nombres de insumos legibles y «Sin dato» cuando falta información. El catálogo usa una tabla en escritorio y tarjetas paginadas en celular. En el presupuesto, la cantidad aparece antes de los filtros opcionales; la lista queda visible en escritorio y una barra de resumen permite volver a ella en celular. Esa barra conserva el aviso de cargos pendientes.

El encabezado verde y el logo permanecen visibles también en **Dashboard**. Las secciones cambian con un fundido breve de 180 ms y los desplegables usan un puntero de selección, conservando la búsqueda por teclado. La navegación por teclado responde de inmediato y se respeta el movimiento reducido. El dashboard de Kiara, sus datos, gráficos y métricas, y los cálculos del presupuesto conservan su comportamiento.

## Probarlo

1. En **Catálogo**, comprobá las 372 publicaciones. Buscá por título o insumo y escribí un mínimo o máximo de precio. Un extremo vacío no impone límite. Abrí la publicación original para revisar su detalle.
2. En **Arma tu presupuesto → Por cantidad → Peso (kg o g)**, elegí **Polvo hornear**. En **Acotar ofertas → Publicaciones para comparar**, seleccioná `MLA3573151270`, `MLA1824200300` y `MLA3325209494`.
3. En gramos, con `250` se recomienda la presentación de **ARS 3.509,00**. Con `1.000` se recomienda la de **ARS 6.639,00** para cubrir 1 kg. Los importes corresponden a mercadería de la captura.
4. Pulsá **Agregar a la lista** o hacé doble clic en una oferta. Podés sumar varias publicaciones del mismo tipo de insumo y editar sus cantidades por separado. Agregar otra vez la misma publicación actualiza su cantidad. **Vaciar lista** pide confirmación antes de quitar todos los productos, cantidades, IVA y envíos del presupuesto. **Cancelar** o cerrar la pregunta conserva la lista. Revisá presentaciones enteras, peso recibido y sobrante. Completá IVA y envío solo si están confirmados. Descargá el **presupuesto PDF**, con logo, detalle por proveedor, cantidades, importes y enlaces. Si falta un cargo, muestra **Importe conocido** y los pendientes.
5. En **Dashboard**, probá los filtros de insumo, formato, vendedor y envío. Revisá los ejemplos de pan, pizza y budín. Las brechas frente a la mediana son estimaciones, no ahorros observados. Los tiempos, frecuencia y valor por hora son supuestos editables.
6. **Actualizar datos** consulta el último lote completo. Si cambió, comienza una lista vacía para usar sus precios. Si falla, conserva la versión disponible y el presupuesto. La fecha está debajo de la navegación; su ayuda muestra la versión.

Para cantidades usá formato argentino: `1` = un kilo; `1.000` = mil; `1,5` = uno y medio. Las presentaciones sin confirmar no se usan en comparaciones de cantidades. Los precios atípicos quedan fuera de las recomendaciones automáticas. El envío anunciado en la captura no garantiza el costo de envío de un pedido actual.

## Ejecutar en tu computadora

Desde la raíz del repositorio, con Python 3.12:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m streamlit run app/streamlit_app.py --server.address 127.0.0.1
```

[Abrir demo local](http://127.0.0.1:8501). Mantené abierta la terminal; Ctrl+C la detiene. En macOS/Linux usá `.venv/bin/python`.

La app consulta el puntero público configurado en `data_public/conexion.json` (o `TACCTICO_MANIFEST_ID`) y verifica la huella del paquete antes de usarlo. `data_public/actual/` conserva el mismo lote como respaldo si Drive no responde. No requiere claves de Google, n8n, Apify ni Make. El CSV anterior de 363 publicaciones permanece como referencia histórica y no alimenta el lote actual.

## Cómo se actualizan los datos

```mermaid
flowchart LR
    A[CSV crudo en Drive] --> B[n8n: limpieza de Kiara]
    B --> C[CSV + métricas + dashboard]
    C --> D[Subir o reutilizar y verificar]
    D --> E[Actualizar vigente]
    E --> F[Catálogo, presupuesto y dashboard]
```

n8n descarga las 591 publicaciones originales. La selección útil produce 347 filas; 25 publicaciones relevantes sin presentación resoluble se conservan en el catálogo: 372. El análisis excluye 17 atípicos de la selección útil: 330. El catálogo marca 37 presentaciones para revisión. No se fuerza un conteo fijo para futuras capturas.

El lote reúne CSV, métricas y HTML con una identidad común. Los archivos de cada lote son inmutables y se verifica tamaño/MD5 en Drive y SHA-256 en la app. El puntero vigente se actualiza al final. Repetir una ejecución reutiliza los archivos. La ejecución real de subida, repetición y lectura sin cuenta se comprobó el 19/11/2026.

La página consulta resultados ya generados; no ejecuta scraping ni n8n al abrirse. La captura puede provenir de una exportación de Apify. Make corresponde a una etapa anterior reemplazada por este flujo. No se calcula una tendencia con una sola captura. El historial recibido se conserva localmente en el proceso de ingesta.

## Esquema y procedencia

El [CSV del lote incluido](data_public/actual/mercadolibre_validado.csv) usa UTF-8, comas y una fila por publicación, con 31 columnas:

| Campos | Uso |
| --- | --- |
| `id_publicacion`, `titulo`, `url`, `fuente` | Identificación, título, enlace y origen. |
| `precio_publicado`, `moneda`, `capturado_en` | Importe publicado en ARS y captura UTC ISO 8601. |
| `insumo`, `marca`, `vendedor`, `tipo_vendedor`, `vendedor_id` | Clasificación e identificación comercial. |
| `gramos_unidad`, `unidades`, `es_pack`, `gramos_totales`, `precio_100g` | Presentación y referencia de precio. |
| `fuente_peso`, `peso_discrepa`, `outlier_precio`, `revision_presentacion` | Procedencia de la medida y alertas. |
| `tiene_promo`, `descuento_pct`, `precio_anterior`, `envio`, `promocion` | Condiciones de referencia de la captura. |
| `categoria`, `nombre_ficha`, `linea`, `sabor`, `rnpa` | Datos complementarios de la ficha. |

Los archivos `metricas.json`, `calidad.json` y `manifest.json` documentan métodos, supuestos, conteos e integridad. El dashboard conserva el diseño final de Kiara y recalcula sus datos sobre el mismo lote. Sus estadísticas normalizadas no sustituyen la comprobación de presentación, disponibilidad y cargos para un pedido concreto.

El equipo autorizó publicar estos resultados finales del Capstone. El dataset crudo, rechazos, credenciales y carpetas privadas no forman parte de esta distribución. Las referencias por hora se identifican como supuestos del equipo; no como valores salariales oficiales.

## Verificar la instalación

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s scripts -p "test_*.py"
.\.venv\Scripts\python.exe scripts/validar_demo.py
```

Los casos comprueban cálculos, acciones de la lista, cambio de lote, conservación del presupuesto ante un fallo y carga del catálogo con búsqueda. Las interacciones reales del dashboard y del selector de ofertas también se revisaron en el navegador. Los datos artificiales se limitan a pruebas.

## Fuentes y licencias

- Publicaciones de [Mercado Libre Argentina](https://www.mercadolibre.com.ar/), con sus enlaces y fecha de captura. [Términos del programa de desarrolladores](https://developers.mercadolibre.com.ar/es_ar/es-ar-terminos-y-condiciones).
- [Streamlit](https://streamlit.io/terms-of-use) usa Apache 2.0; [pandas](https://github.com/pandas-dev/pandas/blob/v2.3.3/LICENSE) y [ReportLab](https://pypi.org/project/reportlab/5.1.0/) usan licencias BSD.
- El equipo debe confirmar la licencia de su código antes de agregar un `LICENSE` con permisos de reutilización.
