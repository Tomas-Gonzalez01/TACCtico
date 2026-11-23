"""Genera los notebooks portables de análisis y entrenamiento sin datos privados."""

from pathlib import Path

import nbformat as nb

ROOT = Path(__file__).resolve().parents[1]
BOOTSTRAP = """from pathlib import Path
import os, sys
# Ejecutá desde el repositorio clonado. En Colab: cloná el GitHub público y entrá en su carpeta.
ROOT = next(p for p in [Path.cwd(), *Path.cwd().parents] if (p / "data_public/actual/manifest.json").is_file())
os.chdir(ROOT)
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "n8n/python"))
print(ROOT.name)
"""


def write(relative, title, cells):
    notebook = nb.v4.new_notebook(
        cells=[nb.v4.new_markdown_cell(title), nb.v4.new_code_cell(BOOTSTRAP), *cells]
    )
    notebook.metadata.kernelspec = {"name": "python3", "display_name": "Python 3", "language": "python"}
    path = ROOT / "colabs" / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    nb.validate(notebook)
    nb.write(notebook, path)


if __name__ == "__main__":
    write(
        "analytics/analisis_dataset.ipynb",
        "# Análisis del dataset real de TACCtico\n"
        "Captura 14/11/2026. Para preparar el entorno: `pip install -r requirements-ml.txt`. "
        "Este notebook usa solo el CSV autorizado. El crudo y la limpieza completa permanecen en n8n.",
        [
            nb.v4.new_code_cell("""import pandas as pd
df = pd.read_csv(ROOT / "data_public/actual/mercadolibre_validado.csv")
display(df.groupby("insumo").agg(publicaciones=("id_publicacion", "count"), vendedores=("vendedor", "nunique")))
print("Capturas:", sorted(df.capturado_en.str[:10].unique()))
"""),
            nb.v4.new_code_cell("""from tacctico_etl.ml_model import clean_record
rows = df.fillna("").to_dict("records")
print("Elegibles:", sum(clean_record(r)[0] is not None for r in rows))
display(df[["precio_publicado", "gramos_totales", "unidades"]].describe())
"""),
            nb.v4.new_markdown_cell(
                "Las 37 presentaciones dudosas no se completan con ML. Los precios atípicos no son etiquetas humanas de error."
            ),
        ],
    )
    write(
        "training/entrenamiento.ipynb",
        "# Entrenamiento y evaluación de TACCtico\n"
        "Preparación: `pip install -r requirements-ml.txt`. Semilla 42. Se reserva una prueba por grupos antes de seleccionar modelos. "
        "El entrenamiento usa datos reales. Las perturbaciones del detector son una prueba separada de robustez.",
        [
            nb.v4.new_code_cell("""from train_ml import train
# Salida separada: explorar no reemplaza el modelo desplegado ni el lote vigente.
report = train(ROOT / "data_public/actual/mercadolibre_validado.csv", ROOT / "tmp/modelo_reproducido")
"""),
            nb.v4.new_code_cell("""import pandas as pd
reference = report["referencia_precio"]
display(pd.DataFrame({"Modelo seleccionado": reference["prueba_reservada"],
                      "Mediana por insumo": reference["baseline_mediana_por_insumo"]}))
print(report["particion"])
print(report["anomalias"])
"""),
            nb.v4.new_markdown_cell(
                "Accuracy y precisión del detector quedan sin calcular: no hay etiquetas humanas. "
                "La prueba reservada no se reutiliza para ajustar parámetros. "
                "La referencia tiene error y no es una cotización ni un pronóstico temporal."
            ),
        ],
    )
    print("Notebooks de análisis y entrenamiento creados y validados.")
