"""Inferencia versionada: anomalías y referencia de precio de la captura.

Solo carga el artefacto propio incluido en el paquete, después de comprobar su SHA.
No acepta modelos externos ni ejecuta entrenamiento al abrir la aplicación.
"""

from functools import lru_cache
import hashlib
import json
import math
from pathlib import Path
import re
import unicodedata

import numpy as np

MODEL_DIR = Path(__file__).with_name("models")
INGREDIENTS = {
    "chips_chocolate",
    "levadura",
    "polvo_hornear",
    "premezcla_budin",
    "premezcla_pan",
    "premezcla_pizza",
    "premezcla_universal",
}


def normalized(value):
    text = unicodedata.normalize("NFKD", str(value or "").casefold())
    text = "".join(c for c in text if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]+", " ", text).strip()


def number(value):
    if isinstance(value, bool):
        return None
    try:
        result = float(value)
        return result if math.isfinite(result) and result > 0 else None
    except (TypeError, ValueError):
        return None


def clean_record(row):
    """Una presentación dudosa nunca se convierte en un peso estimado por ML."""
    review = row.get("revision_presentacion")
    if review is not None and str(review).strip().casefold() not in {"", "nan", "none"}:
        return None, "presentacion_sin_confirmar"
    if str(row.get("peso_discrepa", "")).casefold() in {"true", "1"}:
        return None, "peso_discrepante"
    ingredient = str(row.get("insumo", ""))
    if ingredient not in INGREDIENTS:
        return None, "insumo_no_conocido"
    if row.get("moneda") != "ARS":
        return None, "moneda_no_admitida"
    price, grams, units = [number(row.get(k)) for k in ("precio_publicado", "gramos_totales", "unidades")]
    if None in (price, grams, units) or not units.is_integer():
        return None, "importe_o_presentacion_invalidos"
    unit_weight = number(row.get("gramos_unidad"))
    if unit_weight is not None and not math.isclose(unit_weight * units, grams, rel_tol=1e-6):
        return None, "peso_y_unidades_inconsistentes"
    return {
        **row,
        "insumo": ingredient,
        "precio_publicado": price,
        "gramos_totales": grams,
        "unidades": units,
        "precio_kg": price * 1000 / grams,
    }, None


def reference_features(rows):
    return [
        {
            "insumo": r["insumo"],
            "marca": normalized(r.get("marca")),
            "log_gramos": math.log(r["gramos_totales"]),
            "log_unidades": math.log(r["unidades"]),
        }
        for r in rows
    ]


def anomaly_features(rows, centers):
    return np.array(
        [
            [
                math.log(r["precio_kg"]) - centers[r["insumo"]][0],
                math.log(r["gramos_totales"]) - centers[r["insumo"]][1],
                math.log(r["unidades"]),
            ]
            for r in rows
        ],
        dtype=float,
    )


@lru_cache(maxsize=1)
def load_model():
    metadata = json.loads((MODEL_DIR / "metadata.json").read_text(encoding="utf-8"))
    payload = (MODEL_DIR / "precios.json").read_bytes()
    if hashlib.sha256(payload).hexdigest() != metadata["sha256_modelo"]:
        raise ValueError("El modelo no coincide con su versión verificada")
    return json.loads(payload), metadata


def tree_values(tree, features):
    """Evalúa los árboles entrenados exportados, sin pickle ni código ejecutable."""
    nodes = np.zeros(len(features), dtype=int)
    left, right = np.array(tree["left"]), np.array(tree["right"])
    split, threshold = np.array(tree["feature"]), np.array(tree["threshold"])
    depths = np.zeros(len(features), dtype=float)
    for _ in range(len(left)):
        active = np.flatnonzero(left[nodes] != -1)
        if not len(active):
            return nodes, depths
        current = nodes[active]
        goes_left = features[active, split[current]] <= threshold[current]
        nodes[active] = np.where(goes_left, left[current], right[current])
        depths[active] += 1
    raise ValueError("Árbol de inferencia inválido")


def average_path(samples):
    samples = np.asarray(samples, dtype=float)
    result = np.zeros_like(samples)
    result[samples == 2] = 1
    mask = samples > 2
    result[mask] = 2 * (np.log(samples[mask] - 1) + np.euler_gamma) - 2 * (samples[mask] - 1) / samples[mask]
    return result


def predict_portable(model, rows):
    vectorizer = model["reference"]["features"]
    feature_dicts = reference_features(rows)
    features = np.zeros((len(rows), len(vectorizer)), dtype=float)
    for i, data in enumerate(feature_dicts):
        for key, value in data.items():
            name = key + "=" + value if isinstance(value, str) else key
            if name in vectorizer:
                features[i, vectorizer[name]] = 1 if isinstance(value, str) else value
    reference = model["reference"]
    if reference["algorithm"] == "ridge":
        predicted = features @ np.array(reference["coef"]) + reference["intercept"]
    else:
        # scikit-learn recorre árboles con entradas float32.
        features = features.astype(np.float32)
        predicted = np.zeros(len(rows), dtype=float)
        for tree in reference["trees"]:
            nodes, _ = tree_values(tree, features)
            predicted += np.array(tree["value"])[nodes]
        predicted /= len(reference["trees"])
    anomaly = anomaly_features(rows, model["centers"]).astype(np.float32)
    depths = np.zeros(len(rows), dtype=float)
    for tree in model["isolation"]["trees"]:
        nodes, levels = tree_values(tree, anomaly[:, tree["columns"]])
        depths += levels + average_path(np.array(tree["samples"])[nodes])
    denominator = len(model["isolation"]["trees"]) * float(
        average_path([model["isolation"]["max_samples"]])[0]
    )
    scores = -np.exp2(-depths / denominator)
    return scores - model["isolation"]["offset"], np.exp(predicted)


def infer_rows(rows):
    if not isinstance(rows, list) or not rows or len(rows) > 2000:
        raise ValueError("La inferencia requiere entre 1 y 2000 publicaciones")
    if any(not isinstance(r, dict) or not str(r.get("id_publicacion", "")).strip() for r in rows):
        raise ValueError("Cada publicación debe tener un identificador")
    ids = [str(r["id_publicacion"]) for r in rows]
    if len(set(ids)) != len(ids):
        raise ValueError("La inferencia no admite identificadores duplicados")
    model, metadata = load_model()
    results, accepted = {}, []
    for source in rows:
        row, reason = clean_record(source)
        if row is None:
            results[str(source["id_publicacion"])] = {"estado": "sin_evaluar", "motivo": reason}
        else:
            accepted.append(row)
    if accepted:
        margins, references = predict_portable(model, accepted)
        for row, margin, reference in zip(accepted, margins, references):
            if not math.isfinite(float(reference)) or reference <= 0:
                raise ValueError("El modelo produjo una referencia inválida")
            results[str(row["id_publicacion"])] = {
                "estado": "evaluado",
                "revisar": bool(margin < 0),
                "puntaje_anomalia": round(float(-margin), 8),
                "precio_referencia_kg": round(float(reference), 2),
                "precio_publicado_kg": round(row["precio_kg"], 2),
                "diferencia_referencia_pct": round((row["precio_kg"] / reference - 1) * 100, 2),
            }
    return {
        "schema_version": 1,
        "modelo_id": metadata["modelo_id"],
        "sha256_modelo": metadata["sha256_modelo"],
        "captura_entrenamiento": metadata["captura"],
        "publicaciones_evaluadas": len(accepted),
        "sin_evaluar": len(rows) - len(accepted),
        "para_revisar": sum(r.get("revisar", False) for r in results.values()),
        "metodo": "Isolation Forest; referencia de precio supervisada. El puntaje no es una probabilidad.",
        "evaluacion": metadata["evaluacion_resumen"],
        "predicciones": results,
    }
