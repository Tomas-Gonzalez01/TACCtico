"""Entrenamiento reproducible con datos reales; reserva grupos antes de seleccionar modelo."""

import argparse
import csv
import hashlib
import json
import platform
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "n8n/python"))

import joblib
import numpy as np
import sklearn
from sklearn.ensemble import IsolationForest, RandomForestRegressor
from sklearn.feature_extraction import DictVectorizer
from sklearn.linear_model import Ridge
from sklearn.metrics import mean_absolute_error, r2_score
from sklearn.model_selection import GroupKFold, GroupShuffleSplit
from sklearn.pipeline import make_pipeline
from tacctico_etl.ml_model import (
    MODEL_DIR,
    anomaly_features,
    clean_record,
    normalized,
    reference_features,
)


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def make_reference(name):
    regressor = (
        Ridge(alpha=10)
        if name == "ridge"
        else RandomForestRegressor(
            n_estimators=120, max_depth=9, min_samples_leaf=3, random_state=42, n_jobs=1
        )
    )
    return make_pipeline(DictVectorizer(sparse=False), regressor)


def export_tree(estimator):
    tree = estimator.tree_
    return {
        "left": tree.children_left.tolist(),
        "right": tree.children_right.tolist(),
        "feature": tree.feature.tolist(),
        "threshold": tree.threshold.tolist(),
        "value": tree.value[:, 0, 0].tolist(),
        "samples": tree.n_node_samples.tolist(),
    }


def export_portable(reference, detector, center, selected):
    regression = reference.steps[-1][1]
    ref = {"algorithm": selected, "features": reference.steps[0][1].vocabulary_}
    if selected == "ridge":
        ref.update(coef=regression.coef_.tolist(), intercept=float(regression.intercept_))
    else:
        ref["trees"] = [export_tree(tree) for tree in regression.estimators_]
    return {
        "schema_version": 1,
        "centers": center,
        "reference": ref,
        "isolation": {
            "offset": float(detector.offset_),
            "max_samples": int(detector.max_samples_),
            "trees": [
                {**export_tree(t), "columns": cols.tolist()}
                for t, cols in zip(detector.estimators_, detector.estimators_features_)
            ],
        },
    }


def centers(rows):
    return {
        i: [
            float(np.median([np.log(r[k]) for r in rows if r["insumo"] == i]))
            for k in ("precio_kg", "gramos_totales")
        ]
        for i in sorted({r["insumo"] for r in rows})
    }


def metrics(actual, predicted):
    return {
        "mae_ars_por_kg": float(mean_absolute_error(actual, predicted)),
        "mediana_error_porcentual": float(np.median(np.abs(predicted / actual - 1)) * 100),
        "r2": float(r2_score(actual, predicted)),
    }


def train(source, output=MODEL_DIR):
    started = time.perf_counter()
    with source.open(encoding="utf-8-sig", newline="") as f:
        original = list(csv.DictReader(f))
    rows = [clean_record(r)[0] for r in original]
    rows = [r for r in rows if r is not None]
    # El mismo título normalizado, o ficha de marca, no puede aparecer en ambos conjuntos.
    groups = np.array(
        [
            normalized(r.get("marca"))
            + "/"
            + normalized(r.get("rnpa") or r.get("nombre_ficha") or r["titulo"])
            for r in rows
        ]
    )
    indices = np.arange(len(rows))
    train_idx, test_idx = next(
        GroupShuffleSplit(n_splits=1, test_size=0.2, random_state=42).split(indices, groups=groups)
    )
    assert not set(groups[train_idx]) & set(groups[test_idx])
    training = [rows[i] for i in train_idx]
    testing = [rows[i] for i in test_idx]
    assert {r["insumo"] for r in testing} <= {r["insumo"] for r in training}
    cv_results = {}
    cv = list(GroupKFold(n_splits=4).split(train_idx, groups=groups[train_idx]))
    for name in ("ridge", "random_forest"):
        errors = []
        for fit, validation in cv:
            fit_rows, val_rows = [[training[i] for i in ix] for ix in (fit, validation)]
            candidate = make_reference(name)
            candidate.fit(reference_features(fit_rows), np.log([r["precio_kg"] for r in fit_rows]))
            predicted_log = candidate.predict(reference_features(val_rows))
            errors.extend(np.abs(predicted_log - np.log([r["precio_kg"] for r in val_rows])))
        cv_results[name] = {"mae_log_cv": float(np.mean(errors))}
    selected = min(cv_results, key=lambda k: cv_results[k]["mae_log_cv"])
    reference = make_reference(selected)
    reference.fit(reference_features(training), np.log([r["precio_kg"] for r in training]))
    predicted = np.exp(reference.predict(reference_features(testing)))
    actual = np.array([r["precio_kg"] for r in testing])
    base = {
        i: float(np.median([r["precio_kg"] for r in training if r["insumo"] == i]))
        for i in {r["insumo"] for r in training}
    }
    baseline = np.array([base[r["insumo"]] for r in testing])
    selected_metrics, baseline_metrics = metrics(actual, predicted), metrics(actual, baseline)

    # Evaluación separada de anomalías: no hay etiquetas humanas de precios erróneos.
    center_train = centers(training)
    detector = IsolationForest(n_estimators=160, contamination=0.05, random_state=42, n_jobs=1)
    detector.fit(anomaly_features(training, center_train))
    natural_flags = detector.predict(anomaly_features(testing, center_train)) == -1
    stress = [{**r, "precio_kg": r["precio_kg"] * factor} for r in testing for factor in (0.05, 20)]
    stress_flags = detector.predict(anomaly_features(stress, center_train)) == -1
    report = {
        "schema_version": 1,
        "fecha": "2026-11-23",
        "semilla": 42,
        "dataset_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
        "filas_catalogo": len(original),
        "filas_elegibles": len(rows),
        "excluidas_por_validacion": len(original) - len(rows),
        "particion": {
            "entrenamiento": len(training),
            "prueba_reservada": len(testing),
            "grupos_entrenamiento": len(set(groups[train_idx])),
            "grupos_prueba": len(set(groups[test_idx])),
            "grupos_compartidos": 0,
            "regla": "Marca + RNPA/ficha; si faltan, título normalizado.",
            "ids_prueba": [r["id_publicacion"] for r in testing],
        },
        "referencia_precio": {
            "seleccionado": selected,
            "validacion_solo_entrenamiento": cv_results,
            "prueba_reservada": selected_metrics,
            "baseline_mediana_por_insumo": baseline_metrics,
            "mejora_mae_vs_baseline_pct": (
                1 - selected_metrics["mae_ars_por_kg"] / baseline_metrics["mae_ars_por_kg"]
            )
            * 100,
        },
        "anomalias": {
            "algoritmo": "IsolationForest",
            "contaminacion_operativa": 0.05,
            "alertas_en_prueba_real": int(natural_flags.sum()),
            "casos_reales_prueba": len(testing),
            "sensibilidad_perturbaciones_controladas": float(stress_flags.mean()),
            "casos_perturbados": len(stress),
            "factores_precio_prueba": [0.05, 20],
            "accuracy_real": None,
            "precision_real": None,
            "limite": "Sin etiquetas humanas no se informa accuracy ni precisión. La prueba perturbada es de robustez, no exactitud comercial.",
        },
        "captura": sorted({r["capturado_en"][:10] for r in rows}),
        "versiones": {
            "sklearn": sklearn.__version__,
            "numpy": np.__version__,
            "python": platform.python_version(),
        },
        "limitaciones": [
            "Una sola fecha; no pronostica precios futuros.",
            "No confirma stock, IVA, envío ni condición sin TACC.",
            "Una alerta puede corresponder a una oferta legítima.",
            "Los parámetros se seleccionan con CV interna; la prueba reservada se usa una sola vez.",
        ],
    }
    # Tras evaluar, la versión de producción se reajusta con todos los casos elegibles.
    reference.fit(reference_features(rows), np.log([r["precio_kg"] for r in rows]))
    center_all = centers(rows)
    detector.fit(anomaly_features(rows, center_all))
    output.mkdir(parents=True, exist_ok=True)
    joblib.dump(
        {"isolation": detector, "reference": reference, "centers": center_all},
        output / "precios.joblib",
        compress=3,
    )
    write_json(output / "precios.json", export_portable(reference, detector, center_all, selected))
    model_sha = hashlib.sha256((output / "precios.json").read_bytes()).hexdigest()
    report["entrenamiento_segundos"] = time.perf_counter() - started
    metadata = {
        "schema_version": 1,
        "modelo_id": "tacctico-precios-1-" + model_sha[:12],
        "sha256_modelo": model_sha,
        "sha256_joblib": hashlib.sha256((output / "precios.joblib").read_bytes()).hexdigest(),
        "dataset_sha256": report["dataset_sha256"],
        "captura": report["captura"],
        "filas_entrenamiento_final": len(rows),
        "evaluacion_resumen": report["referencia_precio"],
        "versiones": report["versiones"],
    }
    write_json(output / "metadata.json", metadata)
    write_json(output / "evaluacion.json", report)
    # Las predicciones de prueba se guardan aparte para una revisión independiente.
    write_json(
        output / "prueba_reservada.json",
        [
            {
                "id_publicacion": r["id_publicacion"],
                "insumo": r["insumo"],
                "real_kg": float(y),
                "estimado_kg": float(p),
                "baseline_kg": float(b),
            }
            for r, y, p, b in zip(testing, actual, predicted, baseline)
        ],
    )
    print(
        json.dumps(
            {
                "modelo": metadata["modelo_id"],
                "elegibles": len(rows),
                "prueba": len(testing),
                "referencia": report["referencia_precio"],
                "anomalias": report["anomalias"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--csv", type=Path, default=ROOT / "data_public/actual/mercadolibre_validado.csv")
    parser.add_argument("--output", type=Path, default=MODEL_DIR)
    args = parser.parse_args()
    train(args.csv, args.output)
