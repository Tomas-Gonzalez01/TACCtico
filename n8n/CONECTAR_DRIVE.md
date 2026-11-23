# Conectar Google Drive con n8n local

Estado de esta instalación: conexión de Google autorizada y seleccionada en los
nodos Drive y consultas de permisos de ambos flujos. Ya se comprobó la descarga,
limpieza, primera subida, reutilización y lectura pública de los resultados finales.
Las instrucciones siguientes sirven para reproducir la conexión en otra instalación
o renovarla. Cada instalación de n8n necesita su propia autorización de Google;
las conexiones de otras aplicaciones no se transfieren automáticamente.

En la instalación de Tomás ya se creó el proyecto **TACCtico n8n**, se habilitó
Google Drive API, se configuró la app OAuth en modo de prueba y se creó el cliente
web con la redirección local indicada abajo. Los detalles de la cuenta y del
proyecto quedan en `backups/drive_destinos.json`, excluido de Git. No repetir
la creación del proyecto ni del cliente: los pasos 6–8 ya se completaron.
El ID y el secreto del cliente no se guardan en esta documentación.

## Cuenta a usar

Elegí una cuenta que pueda abrir el CSV original y crear archivos en la carpeta
de salida. No hace falta publicar la carpeta ni permitir que cualquiera la edite.
Si la carpeta pertenece a otra persona, esa persona debe dar acceso de editor
a la cuenta elegida, o usar su propia cuenta al conectar n8n.

## Preparar la conexión de Google

n8n instalado en Docker usa OAuth personalizado. Google pide un proyecto y una
aplicación OAuth; el botón de inicio de sesión directo sin esta preparación es
una función de n8n Cloud. [Instrucciones oficiales de n8n](https://docs.n8n.io/integrations/builtin/credentials/google/oauth-single-service/).

1. Entrá en [Google Cloud Console](https://console.cloud.google.com/) con la cuenta elegida. Si ya existe un proyecto con Google Drive API, podés usarlo; de lo contrario, creá uno llamado `TACCtico n8n`.
2. En **APIs y servicios → Biblioteca**, habilitá **Google Drive API**.
3. En **Google Auth Platform**, configurá una aplicación `TACCtico n8n`. Para cuentas personales, seleccioná audiencia externa y agregá tu correo como usuario de prueba. El usuario debe revisar y aceptar personalmente las políticas que Google muestre.
4. Creá un cliente OAuth de tipo **Aplicación web**. Registrá esta URI de redirección exacta:

   ```text
   http://localhost:5678/rest/oauth2-credential/callback
   ```

   Google admite localhost para esta conexión; no hace falta exponer n8n a Internet ni configurar reenvío de puertos.

5. En n8n, abrí **TACCtico — Drive a dataset limpio → Descargar CSV crudo de Drive → Connect to Google Drive**.
6. Copiá el **Client ID** y el **Client Secret** directamente desde Google a los campos de n8n. No los pegues en el chat, README, archivos del repositorio ni capturas.
7. Completá **Sign in with Google** con la cuenta que tiene acceso a ambos destinos y revisá los permisos solicitados. Guardá la conexión.
8. Seleccioná esa misma conexión en todos los nodos de Google Drive del flujo principal y del subflujo **Guardar archivo verificado**. Si habilitaste publicación pública con autorización, usala también en las consultas de permisos HTTP. Guardá los flujos.

Una app externa en modo de prueba puede requerir volver a autorizar después
de siete días. Estas instrucciones usan la instalación local actual de n8n.

## Primera ejecución con autorización

1. Pulsá **Execute workflow** en el flujo Drive.
2. Verificá la salida de **Confirmar lote en TACCtico local**: estado `listo`, lote, cantidad y referencias de los archivos.
3. Abrí el enlace y confirmá que el CSV quedó en la carpeta de salida elegida.
4. Ejecutá nuevamente el mismo lote una sola vez para comprobar la rama **Archivo reutilizado** en el subflujo: no debe aparecer otro CSV ni paquete idéntico.

La ejecución completa, primera subida real y reutilización se verificaron el
19/11/2026. El permiso público se limita al CSV, paquete de análisis y puntero;
no se concede acceso público a la carpeta ni a la entrada cruda.
