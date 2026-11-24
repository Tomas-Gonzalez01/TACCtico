"""Construye la alternativa de carga por formulario sin modificar las reglas ETL."""

import argparse
import json
from pathlib import Path
import uuid

ROOT = Path(__file__).resolve().parent


VALIDATE_CSV_JS = """const items = $input.all();
if (!items.length) throw new Error('El CSV está vacío.');
const required = ['idPublicacion','articuloTitulo','nuevoPrecio','Moneda','zProductoLink','Tiempo'];
const missing = required.filter(key => !items.some(item => Object.prototype.hasOwnProperty.call(item.json, key)));
if (missing.length) throw new Error('Faltan columnas: ' + missing.join(', '));
return items;"""


RUN_ETL_PY = """from tacctico_etl import ejecutar
resultado = ejecutar(_items)
if not resultado["publicable"]:
    raise ValueError("Hay filas rechazadas. Revisá rechazados.csv en la carpeta del lote. El dataset vigente no cambió.")
return [{"json": resultado}]"""


def node(name, kind, x, parameters, version=2):
    return {
        "name": name,
        "type": "n8n-nodes-base." + kind,
        "typeVersion": version,
        "id": str(uuid.uuid5(uuid.NAMESPACE_URL, "tacctico-etl/" + name)),
        "position": [x, 0],
        "parameters": parameters,
    }


def build():
    flow_nodes = [
        node(
            "Cargar CSV crudo",
            "formTrigger",
            0,
            {
                "formTitle": "TACCtico — Limpiar dataset",
                "formDescription": "Subí el CSV crudo de Mercado Libre. El flujo genera el dataset compatible con TACCtico.",
                "formFields": {
                    "values": [
                        {
                            "fieldLabel": "dataset",
                            "fieldType": "file",
                            "multipleFiles": False,
                            "acceptFileTypes": ".csv",
                            "requiredField": True,
                        }
                    ]
                },
                "options": {},
            },
            2.6,
        ),
        node(
            "Leer publicaciones",
            "extractFromFile",
            240,
            {"binaryPropertyName": "dataset", "options": {}},
            1.2,
        ),
        node(
            "Validar archivo",
            "code",
            480,
            {
                "mode": "runOnceForAllItems",
                "jsCode": VALIDATE_CSV_JS,
            },
        ),
        node(
            "Limpiar y guardar lote",
            "code",
            720,
            {
                "mode": "runOnceForAllItems",
                "language": "pythonNative",
                "pythonCode": RUN_ETL_PY,
            },
        ),
        node(
            "CSV listo para TACCtico",
            "readWriteFile",
            960,
            {
                "operation": "read",
                "fileSelector": "=/files/lotes/{{ $json.lote }}/mercadolibre_validado.csv",
                "options": {
                    "fileName": "mercadolibre_validado.csv",
                    "mimeType": "text/csv",
                    "dataPropertyName": "dataset_limpio",
                },
            },
            1,
        ),
    ]
    flow_nodes[0]["webhookId"] = "tacctico-dataset-limpio"
    flow_nodes.append(
        node(
            "Cómo usar",
            "stickyNote",
            260,
            {
                "content": "## Dataset limpio para TACCtico\n1. Ejecutá el flujo y cargá el CSV crudo en el formulario.\n2. Revisá el resumen de Limpiar y guardar lote.\n3. Descargá dataset_limpio desde el último nodo.\n\nCada lote queda en n8n/storage/lotes e incluye CSV, métricas y dashboard. Repetir el mismo archivo reutiliza el lote. Si falla un control, se conserva el vigente.\n\nEsta alternativa carga un archivo local. Para publicar en Drive, usá el flujo principal y su subflujo publicador.",
                "height": 300,
                "width": 740,
            },
            1,
        )
    )
    flow_nodes[-1]["position"] = [180, 240]
    flow = {
        "name": "TACCtico — Dataset limpio",
        "active": False,
        "nodes": flow_nodes,
        "connections": {
            left["name"]: {"main": [[{"node": right["name"], "type": "main", "index": 0}]]}
            for left, right in zip(flow_nodes[:4], flow_nodes[1:5])
        },
        "settings": {"executionOrder": "v1", "binaryMode": "separate"},
        "pinData": {},
    }
    return flow


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=ROOT)
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    (args.output_dir / "flujo_dataset_limpio.json").write_text(
        json.dumps(build(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print("Flujo por formulario generado sin credenciales.")


if __name__ == "__main__":
    main()
