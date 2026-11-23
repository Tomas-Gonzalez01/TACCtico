# TACCtico: actor propio de inferencia

Ejecuta los modelos entrenados del equipo sobre el CSV validado real. **No es el scraper externo de Kiara** y no realiza nuevas capturas. Su código, contratos, dependencias y modelo se entregan completos en este repositorio.

## Ejecutar

Desde la raíz del repositorio, con Docker:

```powershell
docker build -f actor_apify/Dockerfile -t tacctico-inferencia .
docker run --rm tacctico-inferencia
```

La ejecución sin entrada usa las 372 publicaciones autorizadas incluidas en la imagen. Procesa las 335 con presentación válida y deja 37 sin evaluar. Para conservar los resultados locales, montá una carpeta propia en `/actor/storage`. Con Apify CLI, `apify run` usa la configuración `.actor/actor.json`; primero instalá las dependencias de `actor_apify/requirements.txt` y el paquete `n8n/python`. El modo Docker es la reproducción recomendada.

Para desplegar, importá este repositorio público en Apify y usá `actor_apify/Dockerfile` con contexto en la raíz. El actor usa CPU; no requiere GPU ni entrenamiento durante la ejecución.

## Entrada y salida

Sin argumentos: `{"usar_dataset_incluido": true}`. Alternativa: `{"usar_dataset_incluido": false, "publicaciones": [...]}`.

Cada publicación requiere `id_publicacion`, `insumo`, `moneda: "ARS"`, `precio_publicado`, `gramos_totales` y `unidades`. `revision_presentacion` impide calcular sobre pesos dudosos. Los importes y pesos deben ser positivos y finitos; las unidades, enteras. Una moneda o insumo no admitidos quedan sin evaluar. Se rechazan lotes vacíos, más de 2000 filas o identificadores duplicados.

| Salida | Tipo | Significado |
| --- | --- | --- |
| `modelo_id`, `sha256_modelo` | string | Identidad del modelo propio verificado. |
| `predicciones.<id>.estado` | string | `evaluado` o `sin_evaluar`. |
| `revisar` | boolean | Señal para comprobar la publicación; no bloquea compras. |
| `puntaje_anomalia` | number | Margen negativo de Isolation Forest. Mayor que cero señala revisión. **No es probabilidad ni confianza calibrada.** |
| `precio_referencia_kg` | number | Referencia supervisada en ARS/kg de la captura. |
| `diferencia_referencia_pct` | number | Diferencia entre el precio publicado por kg y la referencia. |
| `motivo` | string | Motivo por el cual no se evaluó una fila. |
| `ejecucion` | object | Segundos de inferencia, CPU y memoria RSS observados. |

`OUTPUT` en el almacén clave-valor contiene el contrato completo. El dataset de salida contiene una fila por publicación. Los esquemas de entrada y enlaces de salida están junto a este README.

## Evaluación y costos

Ver [modelo, evaluación y límites](../docs/MODELO_ML.md). Las métricas de regresión se calculan sobre 55 publicaciones de prueba reservadas por grupos. No se atribuye accuracy al detector sin etiquetas humanas. La prueba de perturbaciones controladas se informa por separado y no equivale a precisión sobre ofertas reales.

El gasto histórico de scraping no es costo de inferencia. El costo de una ejecución en Apify se toma de `usageTotalUsd` y la duración total de su registro, incluidos arranque y almacenamiento. Las mediciones locales no se presentan como costos de la nube. No se activa una suscripción ni se hacen scraping o llamadas a actores externos desde este actor.
