# Actualización controlada de Mercado Libre

> Registro histórico de la etapa Make y del lote anterior de 363 publicaciones. El recorrido vigente y sus 372 publicaciones están documentados en [n8n](../n8n/README.md). Las instrucciones de esta página no actualizan el dashboard actual.

El flujo procesa cada CSV a pedido. El lote vigente toma `dataset_util.csv`, una selección de 363 publicaciones de la captura original de Mercado Libre. El importador cruza ID, título, precio y URL con `dataset_final.csv` del mismo lote para conservar la fecha de captura y la moneda. Los duplicados con la misma fecha y datos contradictorios se rechazan.

## Ejecutar en Windows

Desde la carpeta de TACCtico:

```powershell
python scripts/importar_mercadolibre.py "$env:USERPROFILE/Downloads/dataset_util.csv" data_real/mercadolibre_validado.csv --original "$env:USERPROFILE/Downloads/dataset_final.csv"
```

El resultado incluye los campos de captura, presentación y revisión descriptos en el [esquema del README](../README.md#esquema-del-csv-validado-de-mercado-libre). El archivo de salida está excluido de Git. La validación local del 16/11/2026 confirmó 363 publicaciones, con sus fechas y precios originales. La carga del lote depurado a Drive está pendiente de prueba.

## Evidencia de pruebas del 14/11/2026

| Prueba | Resultado |
| --- | --- |
| CSV de Kiara | 591 publicaciones válidas guardadas, 0 duplicados |
| Dos filas ficticias con el mismo identificador | Quedó una publicación con el precio de la captura más reciente |
| Repetición del lote anterior | Resultado idéntico |
| Fallo controlado con un precio inválido | Código de salida 1 y mensaje con la línea. El CSV válido anterior conservó el mismo contenido |
| Carga real por Make a Drive | `mercadolibre_2026-11-14_201943.csv` contiene 591 identificadores únicos. El archivo descargado de Drive coincide byte por byte con el CSV validado localmente |

## Escenario de Make

[TACCtico · Prueba de guardado en Drive](https://us2.make.com/2685453/scenarios/7041254/edit) recibe cada lote por **Webhooks → Custom webhook** y lo guarda con **Google Drive → Upload a File** en la carpeta **SALIDA DE TACCtico**. Para una carga manual, dejá el escenario en **Inactive** y usá **Run once**.

- El webhook recibe `lote` y `csv_validado` como texto JSON. La clave se envía en el encabezado `x-make-apikey`.
- En **Upload a File**, el nombre es `mercadolibre_` + la ficha `lote` del webhook + `.csv`. En **Data**, aplicá `toBinary()` a la ficha `csv_validado` del webhook.
- El control de encabezados, filas y duplicados se aplica en el script antes del envío. El fallo controlado de la tabla se verificó localmente.

## Validar y enviar un lote desde PowerShell

Desde la carpeta de TACCtico, pegá el bloque completo. Usá la URL del webhook del escenario y su clave. Cuando PowerShell indique **Run once**, pulsalo en Make, esperá a que quede escuchando y apretá **Enter** en PowerShell.

```powershell
& {
    $entrada = Join-Path $env:USERPROFILE "Downloads\dataset_util.csv"
    $original = Join-Path $env:USERPROFILE "Downloads\dataset_final.csv"
    $salida = "data_real\mercadolibre_validado.csv"

    python .\scripts\importar_mercadolibre.py $entrada $salida --original $original
    if ($LASTEXITCODE -ne 0) {
        throw "La validación falló. Revisá el mensaje de arriba."
    }

    $rutaCsv = (Resolve-Path -LiteralPath $salida -ErrorAction Stop).Path
    $csv = [System.IO.File]::ReadAllText($rutaCsv, [System.Text.Encoding]::UTF8)

    $url = Read-Host "Pegá la URL del webhook"
    $secreto = Read-Host "Pegá la clave del webhook" -AsSecureString
    $clave = [pscredential]::new("make", $secreto).GetNetworkCredential().Password
    $lote = Get-Date -Format "yyyy-MM-dd_HHmmss"

    $body = @{
        lote         = $lote
        csv_validado = $csv
    } | ConvertTo-Json -Compress

    Read-Host "Pulsá Run once en Make. Cuando quede esperando, volvé acá y apretá Enter" | Out-Null

    $solicitud = @{
        Uri         = $url
        Method      = "Post"
        Headers     = @{ "x-make-apikey" = $clave }
        ContentType = "application/json; charset=utf-8"
        Body        = [System.Text.Encoding]::UTF8.GetBytes($body)
        ErrorAction = "Stop"
    }

    Invoke-RestMethod @solicitud
    Write-Host "Revisá la ejecución en Make y buscá mercadolibre_$lote.csv en Drive."
}
```

`ReadAllText` lee el CSV como texto puro para que el JSON lleve únicamente el contenido del archivo. En la corrida fallida, PowerShell había agregado metadatos de la ruta y Make recibió una colección que **Upload a File** rechazó.

Confirmá que **Upload a File** termine en verde en el historial de Make, donde también figura el consumo de créditos. En Drive debe aparecer el CSV del lote. La demo de Streamlit carga la copia local de `data_real/mercadolibre_validado.csv`.
