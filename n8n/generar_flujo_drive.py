"""Prepara el flujo Drive. La credencial OAuth se selecciona dentro de n8n."""

import copy
import uuid

from generar_flujo import build as build_form


def node(name, kind, x, parameters, version=2):
    return {
        "name": name,
        "type": "n8n-nodes-base." + kind,
        "typeVersion": version,
        "id": str(uuid.uuid5(uuid.NAMESPACE_URL, "tacctico-drive/" + name)),
        "position": [x, 0],
        "parameters": parameters,
    }


def generar(archivo="ID_DEL_CSV_CRUDO", carpeta="ID_CARPETA_SALIDA"):
    base = build_form()
    transforms = copy.deepcopy(base["nodes"][1:4])
    for i, item in enumerate(transforms):
        item["position"] = [(i + 2) * 240, 0]
    start = node("Iniciar limpieza desde Drive", "manualTrigger", 0, {}, 1)
    download = node(
        "Descargar CSV crudo de Drive",
        "googleDrive",
        240,
        {
            "resource": "file",
            "operation": "download",
            "fileId": {"__rl": True, "mode": "id", "value": archivo},
            "options": {"binaryPropertyName": "dataset"},
        },
        3,
    )
    search = node(
        "Buscar este lote en la carpeta",
        "googleDrive",
        1200,
        {
            "resource": "fileFolder",
            "operation": "search",
            "searchMethod": "query",
            "queryString": "=name = '{{ $('Limpiar y guardar lote').first().json.nombre_remoto }}' and '"
            + carpeta
            + "' in parents and trashed = false",
            "returnAll": False,
            "limit": 2,
            "filter": {},
            "options": {"fields": ["*"]},
        },
        3,
    )
    search["alwaysOutputData"] = True
    check = node(
        "Comprobar si ya está guardado",
        "code",
        1440,
        {
            "jsCode": """const lote = $('Limpiar y guardar lote').first().json;
const encontrados = $input.all().filter(item => item.json.id);
if (encontrados.length > 1) throw new Error('Hay dos archivos para este lote. Revisá la carpeta antes de continuar.');
if (encontrados.length === 1) {
  const archivo = encontrados[0].json;
  if (archivo.md5Checksum !== lote.archivo_md5 || Number(archivo.size) !== lote.archivo_bytes)
    throw new Error('El archivo de Drive tiene el mismo nombre pero distinto contenido. No se sobrescribió.');
  return [{json: {...lote, ya_existe: true, drive_file_id: archivo.id, enlace: archivo.webViewLink}}];
}
return [{json: {...lote, ya_existe: false}}];""",
            "mode": "runOnceForAllItems",
        },
    )
    conditional = node(
        "¿El lote ya existe?",
        "if",
        1680,
        {
            "conditions": {
                "options": {"caseSensitive": True, "leftValue": "", "typeValidation": "strict", "version": 2},
                "conditions": [
                    {
                        "id": "lote-existente",
                        "leftValue": "={{ $json.ya_existe }}",
                        "rightValue": "",
                        "operator": {"type": "boolean", "operation": "true", "singleValue": True},
                    }
                ],
                "combinator": "and",
            },
            "options": {},
        },
        2.2,
    )
    ready = copy.deepcopy(base["nodes"][4])
    ready["position"] = [1920, 160]
    upload = node(
        "Guardar CSV limpio en Drive",
        "googleDrive",
        2160,
        {
            "resource": "file",
            "operation": "upload",
            "inputDataFieldName": "dataset_limpio",
            "name": "={{ $('Limpiar y guardar lote').first().json.nombre_remoto }}",
            "driveId": {"__rl": True, "mode": "list", "value": "My Drive"},
            "folderId": {"__rl": True, "mode": "id", "value": carpeta},
            "options": {"simplifyOutput": False},
        },
        3,
    )
    upload["position"][1] = 160
    verify = node(
        "Verificar salida en Drive",
        "code",
        2400,
        {
            "jsCode": """const lote = $('Limpiar y guardar lote').first().json;
const archivo = $input.first().json;
if (!archivo.id || archivo.name !== lote.nombre_remoto || archivo.md5Checksum !== lote.archivo_md5 || Number(archivo.size) !== lote.archivo_bytes)
  throw new Error('La subida no superó la verificación de integridad. Revisá la salida antes de usarla.');
return [{json: {estado: 'listo_en_drive', lote: lote.lote, publicaciones: lote.publicaciones_tacctico,
  presentaciones_por_revisar: lote.presentaciones_por_revisar, drive_file_id: archivo.id,
  enlace: archivo.webViewLink, archivo_sha256: lote.archivo_sha256}}];""",
            "mode": "runOnceForAllItems",
        },
    )
    verify["position"][1] = 160
    done = node(
        "Lote existente verificado",
        "code",
        1920,
        {
            "jsCode": "return $input.all().map(item => ({json: {...item.json, estado: 'ya_guardado_en_drive'}}));"
        },
    )
    done["position"][1] = -140
    ordered = [start, download, *transforms, search, check, conditional, ready, upload, verify, done]
    chain = [start, download, *transforms, search, check, conditional]
    connections = {
        left["name"]: {"main": [[{"node": right["name"], "type": "main", "index": 0}]]}
        for left, right in zip(chain, chain[1:])
    }
    connections[conditional["name"]] = {
        "main": [
            [{"node": done["name"], "type": "main", "index": 0}],
            [{"node": ready["name"], "type": "main", "index": 0}],
        ]
    }
    for left, right in ((ready, upload), (upload, verify)):
        connections[left["name"]] = {"main": [[{"node": right["name"], "type": "main", "index": 0}]]}
    note = node(
        "Conexión pendiente",
        "stickyNote",
        240,
        {
            "content": "## Drive → dataset limpio\nSeleccioná la misma credencial de Google Drive en los tres nodos amarillos: descargar, buscar y guardar. La cuenta debe poder leer el CSV y editar la carpeta de salida.\n\nNo ejecutes dos corridas simultáneas. Se consulta el nombre y se verifica la huella del CSV antes de reutilizarlo. Cada lote se guarda con nombre propio; no se reemplazan archivos anteriores.\n\nLa limpieza es local, dentro de n8n. EDA y métricas quedan fuera de esta etapa.",
            "height": 300,
            "width": 900,
        },
        1,
    )
    note["position"] = [400, 340]
    return {
        "name": "TACCtico — Drive a dataset limpio",
        "active": False,
        "nodes": [*ordered, note],
        "connections": connections,
        "settings": {"executionOrder": "v1", "binaryMode": "separate"},
        "pinData": {},
    }
