# Guía de uso de TACCtico

[Abrir la aplicación](https://tacctico-portafolio-ucn4pkoeemkzx9fowx7ktt.streamlit.app/) · [Volver al proyecto](../README.md)

## Recorrido por la aplicación

1. En **Catálogo**, comprobá las 372 publicaciones. Buscá por título o insumo y escribí un mínimo o máximo de precio. Un extremo vacío no impone límite. Abrí la publicación original para revisar su detalle.
2. En **Arma tu presupuesto → Por cantidad → Peso (kg o g)**, elegí **Polvo hornear**. En **Acotar ofertas → Publicaciones para comparar**, seleccioná `MLA3573151270`, `MLA1824200300` y `MLA3325209494`.
3. En gramos, con `250` se recomienda la presentación de **ARS 3.509,00**. Con `1.000` se recomienda la de **ARS 6.639,00** para cubrir 1 kg. Los importes corresponden a mercadería de la captura.
4. Pulsá **Agregar a la lista** o hacé doble clic en una oferta. Podés sumar varias publicaciones del mismo tipo de insumo y editar sus cantidades por separado. Agregar otra vez la misma publicación actualiza su cantidad. **Vaciar lista** pide confirmación antes de quitar todos los productos, cantidades, IVA y envíos del presupuesto. **Cancelar** o cerrar la pregunta conserva la lista. Revisá presentaciones enteras, peso recibido y sobrante. Completá IVA y envío solo si están confirmados. Descargá el **presupuesto PDF**, con logo, detalle por proveedor, cantidades, importes y enlaces. Si falta un cargo, muestra **Importe conocido** y los pendientes.
5. En **Dashboard**, probá los filtros de insumo, formato, vendedor y envío. Revisá los ejemplos de pan, pizza y budín. Las brechas frente a la mediana son estimaciones, no ahorros observados. Los tiempos, frecuencia y valor por hora son supuestos editables.
6. **Actualizar datos** consulta el último lote completo. Si cambió, comienza una lista vacía para usar sus precios. Si falla, conserva la versión disponible y el presupuesto. La fecha está debajo de la navegación; su ayuda muestra la versión.

Para cantidades usá formato argentino: `1` = un kilo; `1.000` = mil; `1,5` = uno y medio. Las presentaciones sin confirmar no se usan en comparaciones de cantidades. Los precios atípicos quedan fuera de las recomendaciones automáticas. El envío anunciado en la captura no garantiza el costo de envío de un pedido actual.

### ROI del dashboard

El ROI considera el ahorro anual estimado en compras menos el costo anual de datos, dividido por ese costo. Usa el promedio simple del ahorro por lote de las recetas disponibles, multiplicado por los lotes mensuales del escenario y por 12. El ahorro de tiempo se muestra por separado y no aumenta el ROI.

Los valores iniciales son supuestos editables del equipo: **USD 15 por actualización**, **12 actualizaciones al año** y **ARS 1.701 por USD**, equivalentes a **ARS 306.180 anuales**. Los USD 15 provienen del gasto acumulado informado de Apify, incluidas pruebas; usarlos por actualización es un escenario, no un costo recurrente medido. El cambio es una referencia aportada por el equipo, no una cotización en vivo. No se incluyen trabajo, electricidad ni otros costos no cuantificados. Un costo cero muestra el beneficio neto y deja el porcentaje sin calcular; los campos vacíos no se interpretan como cero.

La plantilla de n8n y `metricas.json` conservan los mismos supuestos. Las pruebas de `scripts/test_dashboard_roi.py` comprueban las cuentas, los valores faltantes y la integridad del HTML publicado.

## Planificar una receta por presupuesto

En **Arma tu presupuesto → ¿Cómo querés calcular? → Por presupuesto**, elegí **Pan**, **Pizza** o **Budín** e ingresá cuánto podés gastar en mercadería. **Ajustar receta** permite cambiar los gramos de cada insumo por lote y el máximo de lotes a planificar (20 inicialmente). Un lote es una preparación con esas cantidades; los ejemplos no son recetas completas validadas. Revisá la etiqueta de la premezcla y tu receta para determinar si requiere otros ingredientes.

El plan elige una publicación por insumo y compra presentaciones completas de hasta 5 kg. Excluye publicaciones sin peso confirmado, en revisión o con precio atípico. Muestra lotes cubiertos, importe de mercadería, costo de compra por lote, dinero restante y sobrantes de producto. No mezcla varias publicaciones del mismo insumo para optimizar una receta. La búsqueda usa costos decimales y evita recorrer uno a uno todos los lotes del límite.

Ejemplos verificados con la captura del **14/11/2026**, usando las cantidades iniciales:

| Receta | Presupuesto | Lotes | Mercadería | Dinero restante |
| --- | --- | --- | --- | --- |
| Pan | ARS 40.000,00 | 9 | ARS 37.285,00 | ARS 2.715,00 |
| Pizza | ARS 20.000,00 | 9 | ARS 18.815,00 | ARS 1.185,00 |
| Budín | ARS 20.000,00 | 6 | ARS 19.649,00 | ARS 351,00 |

Pan usa 500 g de premezcla y 10 g de levadura por lote; Pizza, 250 g de premezcla; Budín, 250 g de premezcla y 50 g de chips de chocolate. Con ARS 8.000 para Pan, la app avisa que no alcanza y muestra la compra mínima de un lote por ARS 10.495,00, sin permitir agregar ese plan. Con ARS 40.000, la referencia de comprar la oferta central por precio/kg de cada insumo cubriría 4 lotes de Pan. Es una referencia estadística; no es una compra ni un ahorro observado.

**Agregar esta compra a mi lista** incorpora las publicaciones y cantidades al presupuesto y al PDF. Conserva las demás compras y actualiza la cantidad si una publicación ya estaba agregada. El monto ingresado corresponde al plan de esa receta, no al total de una lista que ya tenía otros productos.

Los cálculos cubren solo los insumos listados: no incluyen otros ingredientes ni agregan IVA o envío sin confirmar. Esos cargos se revisan en la lista y pueden cambiar el importe final. El máximo de lotes es un límite de planificación editable; el dataset no contiene vencimientos y el plan no estima conservación, stock ni disponibilidad actual.

