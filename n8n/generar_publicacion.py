"""Genera flujos que publican CSV, paquete y un puntero vigente al final."""

import copy
import json
from pathlib import Path
import uuid
from generar_flujo_drive import generar, node

ROOT = Path(__file__).resolve().parent


def chain(nodes):
    return {
        a["name"]: {"main": [[{"node": b["name"], "type": "main", "index": 0}]]}
        for a, b in zip(nodes, nodes[1:])
    }


def target(name):
    return {"node": name, "type": "main", "index": 0}


def conditional(name, value, x):
    return node(
        name,
        "if",
        x,
        {
            "conditions": {
                "options": {"caseSensitive": True, "typeValidation": "strict", "version": 2},
                "conditions": [
                    {
                        "id": "exists",
                        "leftValue": value,
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


def web_access(prefix, x):
    remember = node(prefix + " — preparar acceso", "code", x, {"jsCode": "return $input.all();"})
    permissions = node(
        prefix + " — consultar acceso",
        "httpRequest",
        x + 240,
        {
            "url": "=https://www.googleapis.com/drive/v3/files/{{ $json.drive_id || $json.id_vigente }}/permissions?fields=permissions(id,type,role)&supportsAllDrives=true",
            "authentication": "predefinedCredentialType",
            "nodeCredentialType": "googleDriveOAuth2Api",
            "options": {},
        },
        4.2,
    )
    ready = node(
        prefix + " — evaluar acceso",
        "code",
        x + 480,
        {
            "jsCode": "const previo=$('"
            + remember["name"]
            + "').first().json; return [{json:{...previo,publico:($input.first().json.permissions||[]).some(p=>p.type==='anyone'&&p.role==='reader')}}];"
        },
    )
    choose = conditional(prefix + " — ¿lectura pública lista?", "={{ $json.publico }}", x + 720)
    share = node(
        prefix + " — habilitar solo lectura",
        "googleDrive",
        x + 960,
        {
            "resource": "file",
            "operation": "share",
            "fileId": {"__rl": True, "mode": "id", "value": "={{ $json.drive_id || $json.id_vigente }}"},
            "permissionsUi": {
                "permissionsValues": {"role": "reader", "type": "anyone", "allowFileDiscovery": False}
            },
            "options": {},
        },
        3,
    )
    share["position"][1] = 160
    done = node(
        prefix + " — acceso listo",
        "code",
        x + 1200,
        {"jsCode": "return [{json:{...$('" + remember["name"] + "').first().json,publico:true}}];"},
    )
    connections = chain([remember, permissions, ready, choose])
    connections[choose["name"]] = {"main": [[target(done["name"])], [target(share["name"])]]}
    connections[share["name"]] = {"main": [[target(done["name"])]]}
    return [remember, permissions, ready, choose, share, done], connections


def build(folder="ID_CARPETA_SALIDA", source="ID_CSV_CRUDO", child_id="ID_SUBFLUJO", publico=False):
    folder_ref = {"__rl": True, "mode": "id", "value": folder}
    begin = node("Archivo a publicar", "executeWorkflowTrigger", 0, {"inputSource": "passthrough"}, 1.1)
    search = node(
        "Buscar archivo del lote",
        "googleDrive",
        240,
        {
            "resource": "fileFolder",
            "operation": "search",
            "searchMethod": "query",
            "queryString": "=name = '{{ $json.nombre }}' and '" + folder + "' in parents and trashed = false",
            "limit": 2,
            "filter": {},
            "options": {"fields": ["*"]},
        },
        3,
    )
    search["alwaysOutputData"] = True
    check = node(
        "Verificar si existe",
        "code",
        480,
        {
            "jsCode": """const esperado=$('Archivo a publicar').first().json;
const files=$input.all().filter(x=>x.json.id);
if(files.length>1) throw new Error('Hay más de un archivo con el nombre del lote. No se modifica ninguno.');
if(files.length && (files[0].json.md5Checksum!==esperado.md5 || Number(files[0].json.size)!==esperado.bytes))
  throw new Error('El archivo existente no coincide con el contenido esperado.');
return [{json:{...esperado,existe:!!files.length,...(files.length?{drive_id:files[0].json.id,enlace:files[0].json.webViewLink}:{})}}];"""
        },
    )
    choose = conditional("¿Archivo existente?", "={{ $json.existe }}", 720)
    existing = node("Archivo reutilizado", "code", 960, {"jsCode": "return $input.all();"})
    existing["position"][1] = -120
    read = node(
        "Leer salida local",
        "readWriteFile",
        960,
        {
            "operation": "read",
            "fileSelector": "={{ $json.ruta }}",
            "options": {
                "fileName": "={{ $json.nombre }}",
                "mimeType": "={{ $json.mime }}",
                "dataPropertyName": "archivo",
            },
        },
        1,
    )
    read["position"][1] = 140
    upload = node(
        "Subir archivo nuevo",
        "googleDrive",
        1200,
        {
            "resource": "file",
            "operation": "upload",
            "inputDataFieldName": "archivo",
            "name": "={{ $('Archivo a publicar').first().json.nombre }}",
            "driveId": {"__rl": True, "mode": "list", "value": "My Drive"},
            "folderId": folder_ref,
            "options": {"simplifyOutput": False},
        },
        3,
    )
    upload["position"][1] = 140
    verify = node(
        "Archivo subido verificado",
        "code",
        1440,
        {
            "jsCode": """const e=$('Archivo a publicar').first().json,a=$input.first().json;
if(!a.id||a.name!==e.nombre||a.md5Checksum!==e.md5||Number(a.size)!==e.bytes) throw new Error('La subida no superó el control de integridad.');
return [{json:{...e,existe:false,drive_id:a.id,enlace:a.webViewLink}}];"""
        },
    )
    verify["position"][1] = 140
    child_nodes = [begin, search, check, choose, existing, read, upload, verify]
    connections = chain([begin, search, check, choose])
    connections[choose["name"]] = {"main": [[target(existing["name"])], [target(read["name"])]]}
    connections.update(chain([read, upload, verify]))
    child = {
        "name": "TACCtico — Guardar archivo verificado",
        "active": False,
        "nodes": child_nodes,
        "connections": connections,
        "settings": {"executionOrder": "v1", "binaryMode": "separate"},
        "pinData": {},
    }
    if publico:
        extra, links = web_access("Resultados", 1680)
        child["nodes"].extend(extra)
        child["connections"].update(links)
        for end in (existing, verify):
            child["connections"][end["name"]] = {"main": [[target(extra[0]["name"])]]}

    parent = generar(source, folder)
    nodes = parent["nodes"][:5]
    nodes[4]["parameters"]["pythonCode"] = """from tacctico_etl import ejecutar
resultado = ejecutar(_items, publicar=False)
if not resultado["publicable"]:
    raise ValueError("El lote tiene filas rechazadas; el vigente se conserva.")
return [{"json":resultado}]"""
    prepare = node(
        "Preparar archivos del lote",
        "code",
        1200,
        {"jsCode": "return $input.first().json.archivos_publicar.map(archivo=>({json:archivo}));"},
    )
    publish = node(
        "Guardar archivos verificados",
        "executeWorkflow",
        1440,
        {
            "source": "database",
            "workflowId": {"__rl": True, "mode": "id", "value": child_id},
            "mode": "each",
            "options": {"waitForSubWorkflow": True},
        },
        1.3,
    )
    prepare_pointer = node(
        "Preparar vigente",
        "code",
        1680,
        {
            "jsCode": """const archivos=$input.all().map(x=>x.json);
if(archivos.length!==2||new Set(archivos.map(x=>x.tipo)).size!==2) throw new Error('Faltan archivos verificados.');
const resumen=$('Limpiar y guardar lote').first().json;
if(archivos.some(x=>x.lote!==resumen.lote||!x.drive_id)) throw new Error('Los archivos no pertenecen al mismo lote.');
const campos=['tipo','lote','nombre','bytes','md5','sha256','drive_id','enlace'];
const porTipo=Object.fromEntries(archivos.map(x=>[x.tipo,Object.fromEntries(campos.map(k=>[k,x[k]]))]));
const vigente={schema_version:1,lote:resumen.lote,version_reglas:resumen.version_reglas,
  publicaciones:resumen.publicaciones_tacctico,archivos:porTipo};
const bytes=Buffer.from(JSON.stringify(vigente,null,2)+'\\n','utf8');
const md5=require('crypto').createHash('md5').update(bytes).digest('hex');
return [{json:{lote:resumen.lote,vigente,md5,bytes:bytes.length},binary:{archivo:{data:bytes.toString('base64'),mimeType:'application/json',fileName:'tacctico_vigente.json'}}}];"""
        },
    )
    search_pointer = node(
        "Buscar puntero vigente",
        "googleDrive",
        1920,
        {
            "resource": "fileFolder",
            "operation": "search",
            "searchMethod": "query",
            "queryString": "name = 'tacctico_vigente.json' and '"
            + folder
            + "' in parents and trashed = false",
            "limit": 2,
            "filter": {},
            "options": {"fields": ["*"]},
        },
        3,
    )
    search_pointer["alwaysOutputData"] = True
    decide = node(
        "Preparar actualización del vigente",
        "code",
        2160,
        {
            "jsCode": """const files=$input.all().filter(x=>x.json.id);
if(files.length>1) throw new Error('Hay más de un puntero vigente. Se conserva el anterior.');
const original=$('Preparar vigente').first();
return [{json:{...original.json,existe:!!files.length,id_vigente:files[0]?.json.id||''},binary:original.binary}];"""
        },
    )
    choose_pointer = conditional("¿Existe vigente?", "={{ $json.existe }}", 2400)
    update = node(
        "Actualizar vigente",
        "googleDrive",
        2640,
        {
            "resource": "file",
            "operation": "update",
            "fileId": {"__rl": True, "mode": "id", "value": "={{ $json.id_vigente }}"},
            "changeFileContent": True,
            "inputDataFieldName": "archivo",
            "options": {"fields": ["*"]},
        },
        3,
    )
    update["position"][1] = -120
    create = node(
        "Crear vigente",
        "googleDrive",
        2640,
        {
            "resource": "file",
            "operation": "upload",
            "inputDataFieldName": "archivo",
            "name": "tacctico_vigente.json",
            "folderId": folder_ref,
            "driveId": {"__rl": True, "mode": "list", "value": "My Drive"},
            "options": {"simplifyOutput": False},
        },
        3,
    )
    create["position"][1] = 140
    check_pointer = node(
        "Verificar vigente",
        "code",
        2880,
        {
            "jsCode": """const a=$input.first().json,e=$('Preparar vigente').first().json;
if(!a.id||a.md5Checksum!==e.md5||Number(a.size)!==e.bytes) throw new Error('No se pudo verificar el puntero vigente.');
return [{json:{...e.vigente,id_vigente:a.id,enlace_vigente:a.webViewLink,estado:'publicado_en_drive'}}];"""
        },
    )
    confirm = node(
        "Confirmar lote en TACCtico local",
        "code",
        3120,
        {
            "language": "pythonNative",
            "pythonCode": 'from tacctico_etl import confirmar_publicacion\nreturn [{"json":confirmar_publicacion(_items[0]["json"])}] ',
        },
    )
    main = [*nodes, prepare, publish, prepare_pointer, search_pointer, decide, choose_pointer]
    parent["connections"] = chain(main)
    parent["connections"][choose_pointer["name"]] = {
        "main": [[target(update["name"])], [target(create["name"])]]
    }
    parent["connections"].update(
        {
            update["name"]: {"main": [[target(check_pointer["name"])]]},
            create["name"]: {"main": [[target(check_pointer["name"])]]},
            check_pointer["name"]: {"main": [[target(confirm["name"])]]},
        }
    )
    note = node(
        "Guía del flujo",
        "stickyNote",
        400,
        {
            "content": "## Actualización controlada\nEjecutá este flujo con Docker abierto. Descarga el crudo, genera el CSV, las métricas y el dashboard de Kiara y publica los archivos verificados. El vigente se actualiza al final.\n\nSi un control falla, se conserva el vigente anterior. Repetir un lote reutiliza los archivos. No ejecutar corridas simultáneas.\n\nLa lectura pública de los resultados requiere autorización del equipo; la carpeta conserva sus permisos.",
            "width": 950,
            "height": 270,
        },
        1,
    )
    note["position"] = [300, 380]
    parent["nodes"] = [*main, update, create, check_pointer, confirm, note]
    if publico:
        extra, links = web_access("Vigente", 3120)
        confirm["position"] = [4560, 0]
        parent["nodes"].extend(extra)
        parent["connections"].update(links)
        parent["connections"][check_pointer["name"]] = {"main": [[target(extra[0]["name"])]]}
        parent["connections"][extra[-1]["name"]] = {"main": [[target(confirm["name"])]]}
        note["parameters"]["content"] += (
            "\n\nTomás autorizó lectura pública del CSV, paquete final y puntero para la web. No comparte la carpeta ni el crudo."
        )
    return parent, child


if __name__ == "__main__":
    config_path = ROOT / "backups/drive_destinos.json"
    config = json.loads(config_path.read_text(encoding="utf-8"))
    config.setdefault("publicador_id", uuid.uuid4().hex[:16])
    config_path.write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8")
    portable_parent, portable_child = build()
    for name, content in (
        ("flujo_drive_plantilla.json", portable_parent),
        ("flujo_publicador_plantilla.json", portable_child),
    ):
        (ROOT / name).write_text(json.dumps(content, ensure_ascii=False, indent=2), encoding="utf-8")
    parent, child = build(
        config["carpeta_salida"],
        config["archivo_crudo"],
        config["publicador_id"],
        config.get("acceso_publico", False),
    )
    parent["id"], child["id"] = config["workflow_id"], config["publicador_id"]
    previous = json.loads((ROOT / "backups/drive_inicio_19.json").read_text(encoding="utf-8"))[0]
    credential = next(n["credentials"] for n in previous["nodes"] if n.get("credentials"))
    for flow in (parent, child):
        for item in flow["nodes"]:
            if item["type"] in ("n8n-nodes-base.googleDrive", "n8n-nodes-base.httpRequest"):
                item["credentials"] = copy.deepcopy(credential)
    (ROOT / "backups/flujos_publicacion.json").write_text(
        json.dumps([child, parent], ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print("Flujo principal:", parent["id"], "Publicador:", child["id"])
