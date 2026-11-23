# Cómo leer el código de TACCtico

## Relación con el ejemplo docente

La estructura conserva las mismas responsabilidades del ejemplo; el actor propio está escrito en Python.

| Elemento del ejemplo | Ubicación en TACCtico |
| --- | --- |
| Fuente del actor | [actor_apify/src/main.py](../actor_apify/src/main.py), con entrada en [__main__.py](../actor_apify/src/__main__.py). Es el actor de inferencia; el scraper externo tiene su [referencia separada](../apify/README.md). |
| Configuración, contenedor y contratos | [.actor/actor.json](../.actor/actor.json), [Dockerfile](../actor_apify/Dockerfile), [entrada](../actor_apify/input_schema.json) y [salida](../actor_apify/output_schema.json). |
| Dependencias del actor | [actor_apify/requirements.txt](../actor_apify/requirements.txt) y [paquete ETL compartido](../n8n/python/pyproject.toml). |
| Análisis y entrenamiento | [Análisis](../colabs/analytics/analisis_dataset.ipynb), [entrenamiento](../colabs/training/entrenamiento.ipynb) y [script reproducible](../scripts/train_ml.py). |
| Datos crudos y procesados | Crudo privado en Drive y almacenamiento local; resultados autorizados en [data_public/actual/](../data_public/actual/). |
| ETL y preparación | [pipeline.py](../n8n/python/tacctico_etl/pipeline.py), [kiara_etl.py](../n8n/python/tacctico_etl/kiara_etl.py) y [app_adapter.py](../n8n/python/tacctico_etl/app_adapter.py). |
| Inferencia y evaluación | [ml_model.py](../n8n/python/tacctico_etl/ml_model.py), [modelos y reportes](../n8n/python/tacctico_etl/models/) e [informe ML](MODELO_ML.md). |
| Automatización | [n8n/README.md](../n8n/README.md), flujos importables y sus generadores. |
| Instalación, pruebas y consumo | [README principal](../README.md), comandos al final de esta guía y [registro de ejecución](evidencias/apify-inferencia-20261123.json). |

Los archivos de árboles entrenados, flujos JSON, imágenes y resultados son artefactos. Para entender las reglas conviene leer sus módulos y generadores, en lugar de revisar números del modelo o una exportación de n8n línea por línea.

## Recorrido recomendado

1. [Inicio de Streamlit](../app/streamlit_app.py): configuración, encabezado, navegación y selección del lote.
2. [Contrato de datos](../app/purchase_data.py): lectura del CSV, publicaciones y presentaciones.
3. [Motor de comparación](../app/purchase_engine.py): cantidad necesaria, redondeo a presentaciones completas, sobrante y selección de ofertas.
4. [Plan por presupuesto](../app/recipe_plan.py): cuántos lotes de una receta alcanzan con un presupuesto, eligiendo por insumo la presentación más barata que cubre los gramos necesarios.
5. [Presupuesto](../app/budget.py): importes decimales, IVA, envío y cargos pendientes.
6. [Interacciones de la lista](../app/budget_view.py) y [PDF](../app/budget_pdf.py): selección de productos y generación del documento.
7. [Lote y actualización](../app/data_release.py): descarga, verificación de integridad y respaldo local.
8. [Limpieza de n8n](../n8n/python/tacctico_etl/pipeline.py): validación del CSV crudo, selección de Kiara y contrato de salida.
9. [Entrenamiento](../scripts/train_ml.py): división por grupos, comparación de modelos y evaluación reservada.
10. [Inferencia compartida](../n8n/python/tacctico_etl/ml_model.py) y [actor de Apify](../actor_apify/src/main.py): aplicar el modelo entrenado y registrar la ejecución.
11. [Señales en la aplicación](../app/ml_view.py): consultar los resultados del mismo lote desde catálogo y presupuesto.

## Responsabilidades

| Carpeta o archivo | Responsabilidad |
| --- | --- |
| `app/catalog_view.py` | Presentación de tabla y tarjetas; conserva precios numéricos para ordenar. |
| `app/purchase_view.py` | Controles para comparar por cantidad, proveedor o presupuesto de una receta. |
| `app/recipe_plan.py` | Reglas del plan por presupuesto: ofertas comparables, lotes que alcanzan, sobrante y referencia de la oferta mediana. Sin dependencia de Streamlit. |
| `app/release_view.py` | Un mismo lote para catálogo, presupuesto y dashboard. |
| `app/offer_picker.js` | Botón y doble clic para agregar una oferta a la lista. |
| `app/assets/navigation.js` | Fundido al navegar; manejo de cambios rápidos y teclado. |
| `app/assets/tokens.css`, `theme.css`, `offers.css` | Colores, tipografía, tamaños y estilos de la aplicación. |
| `scripts/importar_mercadolibre.py` | Importación al contrato validado. |
| `scripts/ingest.py` | Historial en SQLite, duplicados y conflictos. |
| `n8n/flujo_drive_plantilla.json` | Flujo importable principal; usa destinos de ejemplo. |
| `n8n/flujo_publicador_plantilla.json` | Subflujo importable de subida y comprobación de archivos. |
| `n8n/generar_*.py` | Construcción de los flujos portables a partir de código legible. |
| `n8n/python/tacctico_etl/` | Limpieza, métricas, adaptación al contrato y almacenamiento. |
| `n8n/python/tacctico_etl/ml_model.py` | Validación e inferencia sobre los árboles entrenados exportados a JSON; verifica la huella del modelo. |
| `scripts/train_ml.py` | Separación por grupos, selección de modelos dentro del entrenamiento, evaluación reservada y exportación. |
| `app/ml_view.py` | Señales del mismo lote y referencia de precios, sin entrenar en la web ni alterar las compras. |
| `actor_apify/` | Actor propio de inferencia, contratos y Dockerfile. |
| `colabs/` | Notebooks portables de análisis y entrenamiento con el CSV público. |
| `data_public/actual/` | Resultados finales autorizados; no es código de extracción. |
| `apify/README.md` | Scraper de karamelo: referencia confirmada y evidencia histórica pendiente. |

## Criterios de lectura y mantenimiento

- La interfaz se separa de las reglas de cálculo y del acceso a los datos.
- Los importes se calculan con `Decimal`; los textos de precios se formatean al mostrarlos.
- Los valores desconocidos se mantienen como pendientes; no se inventan IVA, envío ni cantidades.
- Los generadores mantienen el código del flujo fuera de una exportación privada de n8n. Los JSON pueden importarse y los Python permiten revisar su construcción.
- Se usa sangría de cuatro espacios y formato uniforme con Ruff. La configuración está en [pyproject.toml](../pyproject.toml).
- Los archivos originales de `n8n/python/tacctico_etl/` se conservan: su contenido participa en la huella de las reglas y en la trazabilidad del lote. No se reformatean automáticamente ni se cambia el HTML de Kiara durante esta revisión.
- Las credenciales, el CSV crudo, el almacenamiento de n8n y sus copias de seguridad quedan fuera de Git.

## Verificar antes de subir cambios

Desde la raíz, con Python 3.12:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe -m ruff format --check app scripts actor_apify n8n
.\.venv\Scripts\python.exe -m ruff check app scripts actor_apify n8n --select E9,F63,F7,F82
.\.venv\Scripts\python.exe -m unittest discover -s scripts -p "test_*.py"
.\.venv\Scripts\python.exe -m unittest discover -s n8n -p "test_*.py"
.\.venv\Scripts\python.exe scripts/validar_demo.py
node --check app/assets/navigation.js
```

Para aplicar el mismo formato, reemplazá `ruff format --check` por `ruff format`. Node.js se necesita solo para comprobar la sintaxis de JavaScript; la demo se ejecuta con Python.

El formateo de esta entrega se comprueba comparando la estructura de Python antes y después, además de ejecutar las pruebas. Los cambios de estilo no deben alterar las fórmulas ni los resultados de compra.
