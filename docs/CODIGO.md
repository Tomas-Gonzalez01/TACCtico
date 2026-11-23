# Cómo leer el código de TACCtico

## Recorrido recomendado

1. [Inicio de Streamlit](../app/streamlit_app.py): configuración, encabezado, navegación y selección del lote.
2. [Contrato de datos](../app/purchase_data.py): lectura del CSV, publicaciones y presentaciones.
3. [Motor de comparación](../app/purchase_engine.py): cantidad necesaria, redondeo a presentaciones completas, sobrante y selección de ofertas.
4. [Plan por presupuesto](../app/recipe_plan.py): cuántos lotes de una receta alcanzan con un presupuesto, eligiendo por insumo la presentación más barata que cubre los gramos necesarios.
5. [Presupuesto](../app/budget.py): importes decimales, IVA, envío y cargos pendientes.
6. [Interacciones de la lista](../app/budget_view.py) y [PDF](../app/budget_pdf.py): selección de productos y generación del documento.
7. [Lote y actualización](../app/data_release.py): descarga, verificación de integridad y respaldo local.
8. [Limpieza de n8n](../n8n/python/tacctico_etl/pipeline.py): validación del CSV crudo, selección de Kiara y contrato de salida.

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
| `apify/README.md` | Autoría del actor externo y referencia que falta completar. |
| `make/README.md` | Antecedente del prototipo reemplazado por n8n. |

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
.\.venv\Scripts\python.exe -m ruff format --check app scripts n8n
.\.venv\Scripts\python.exe -m unittest discover -s scripts -p "test_*.py"
.\.venv\Scripts\python.exe -m unittest discover -s n8n -p "test_*.py"
.\.venv\Scripts\python.exe scripts/validar_demo.py
node --check app/assets/navigation.js
```

Para aplicar el mismo formato, reemplazá `ruff format --check` por `ruff format`. Node.js se necesita solo para comprobar la sintaxis de JavaScript; la demo se ejecuta con Python.

El formateo de esta entrega se comprueba comparando la estructura de Python antes y después, además de ejecutar las pruebas. Los cambios de estilo no deben alterar las fórmulas ni los resultados de compra.
