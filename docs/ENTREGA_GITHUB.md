# Revisión de la entrega en GitHub

Fecha de revisión: **19/11/2026**. Repositorio público: [TACCtico portafolio](https://github.com/Tomas-Gonzalez01/tacctico-portafolio). [Abrir la aplicación](https://tacctico-portafolio-ucn4pkoeemkzx9fowx7ktt.streamlit.app/).

## Contra la consigna

| Requisito | Evidencia y estado |
| --- | --- |
| Proyecto actualizado en GitHub | Aplicación, dependencias, instrucciones, resultados autorizados y pruebas. |
| Código n8n | [Flujo principal importable](../n8n/flujo_drive_plantilla.json), [subflujo de publicación](../n8n/flujo_publicador_plantilla.json), [alternativa por formulario](../n8n/flujo_dataset_limpio.json). |
| Código que ejecutan los nodos | [Paquete Python del ETL](../n8n/python/tacctico_etl/) y generadores `n8n/generar_*.py`; no depende de una captura de pantalla para revisarlo. |
| Instalación de n8n y conexión | [Docker y uso del flujo](../n8n/README.md), [conectar Drive](../n8n/CONECTAR_DRIVE.md), [compose](../n8n/compose.yaml). Las plantillas requieren conexiones y destinos propios. |
| Legibilidad | [Mapa del código](CODIGO.md), funciones separadas por responsabilidad, formato uniforme y comandos de verificación. |
| Make, como etapa anterior | [Registro del prototipo y captura real](../make/README.md), con el historial exitoso del 14/11. |
| Código y procedencia de Apify | [Estado de Apify](../apify/README.md). **Pendiente identificar el actor externo y comprobar si su fuente está disponible para entregar.** |

**Queda un pendiente frente a la consigna:** identificar el actor externo de Apify y comprobar si su fuente puede entregarse. El código propio, los flujos de n8n y la captura real de Make están disponibles. Las capturas muestran configuraciones reales y no se atribuye al equipo el código de un actor de terceros.

## Qué debe aportar el equipo para cerrar los pendientes

1. Kiara debe abrir la captura de Apify y copiar nombre, URL, autor del actor, configuración de entrada sin secretos y referencia a la ejecución original.
2. Si el proveedor publica su fuente, revisar sus permisos e incluir el enlace o el código permitido. Si no ofrece la fuente, consultar a la docente cómo documentar el uso de un actor externo frente al requisito de «subir el código de Apify».
3. Juan mantiene a su cargo la captura final del dashboard y el video funcional.

## Capturas de automatización

![Flujo instalado de n8n](evidencias/n8n-flujo-real.jpg)

Editor del flujo n8n instalado, capturado el 19/11/2026. Esta revisión de la configuración no ejecutó el flujo ni publicó otro lote. Los JSON portables omiten conexiones personales y la habilitación automática de lectura pública; requieren configuración propia, tal como explica el README de n8n.

![Make: prototipo anterior e historial](evidencias/make-escenario-historico.jpg)

La captura de Make muestra el escenario real y el historial de éxito del 14/11; permanece inactivo después de la migración a n8n.

## Qué se verifica sin usar créditos

Las pruebas locales cubren presupuesto, IVA, envío, packs, sobrantes, lista de compras, importación, historial, publicación de lotes e integridad. Revisan el catálogo real y que el dashboard conserve el HTML de Kiara. El formateo se comprueba con Ruff y comparando la estructura de Python antes y después.

En la revisión del 19/11 pasaron **30 pruebas de aplicación/importación y 14 de n8n** en ambos repositorios. El catálogo validó sus 372 publicaciones reales. La estructura de los 25 archivos Python revisados antes del formateo se conservó; los datos publicados y el código de reglas ETL original no se modificaron.

No hace falta ejecutar Make ni volver a scrapear para revisar el código. Las pruebas de publicación usan destinos simulados y no suben archivos reales a Drive. El CSV crudo, las credenciales y el almacenamiento privado de n8n quedan excluidos.
