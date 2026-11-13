# 08 — Coordinación entre máquinas

Cada máquina actualiza **solo su fila** al terminar una tarea. Los pedidos a otra máquina van en la
sección de pedidos, nunca como cambios directos a archivos ajenos.

## Estado

| Máquina | Rol | Rama | Hecho | En curso | Bloqueado por |
|---|---|---|---|---|---|
| A | Origen, oráculo, Dockerfile | — | — | — | — |
| B | Verificación de punta a punta y destinos | `maquina-b/e2e-real` | (1) `.gitattributes` LF. (2) `samples/` con 3 programas sintéticos (COBOL INTMORA y PAGOMIN, PL/SQL comisión) y casos de referencia. (5a) Pack C# revisado: enteros llegaban como `decimal` al código generado (corregido), fechas/enums en el arnés, se excluyen `Tests/` y `Program.cs`, sin servidores de compilación. (6) Anti-SSRF en `sources.py` (localhost, IPs privadas, 169.254.x.x, CGNAT, IP fijada con `curloptResolve`, sin redirecciones). `.sql` con PL/SQL se detecta como `plsql`. `.gitignore` permite `output/llm_cache/`. Pruebas: 100 pasan, 2 omitidas (C# y HTTP sin .NET/FastAPI local). | (3) Corrida real Java → TypeScript con `samples/`. (4) Commit de la caché. (5b) C# dentro de Docker. | Nada por el Dockerfile (C-0 resuelto por C). Riesgo abierto C-2 si la corrida pasa por el proxy de TCS. |
| C | Interfaz y documentación | `maquina-c/ux-docs` | Finalizado: UI y documentación; fallback demo sin bloquear la entrada real de repositorio/archivos; TLS de runtime; errores del proveedor accionables; ejecución generada sin privilegios y con entorno filtrado. Validación final: build Vite verde, 116 pruebas pasan (2 omitidas), contrato API 8/8, handshake TLS 1.3 y demo E2E 6/6 con paquete HTTP 200. | — | — |

## Pedidos a otras máquinas

### C-0 · Dockerfile — RESUELTO por la Máquina C (typescript@5, decimal.js, NODE_PATH, precalentamiento .NET)
La versión de `main` instala `typescript` sin versión y no instala `decimal.js`. El pack TypeScript compila
el código generado contra `decimal.js` global y declara la herramienta como faltante si no está.
Agregar, conservando los certificados del proxy:

```dockerfile
RUN NODE_EXTRA_CA_CERTS=/etc/ssl/certs/ca-certificates.crt npm install -g typescript@5 decimal.js@10
ENV NODE_PATH=/usr/local/lib/node_modules
# Precalienta .NET para verificar C# sin red durante la demo
RUN dotnet new console -o /tmp/warm --no-restore >/dev/null && dotnet build /tmp/warm -v q >/dev/null && rm -rf /tmp/warm
```
Versión fija para que la verificación sea reproducible (con TypeScript 6 ya apareció el error TS5101).

### A-2 · Imagen exportada y caché del LLM
`.dockerignore` excluye `output/`. Con `docker compose` no importa (se monta `./output`), pero una imagen
exportada con `docker save` y usada en otra máquina **sin el repo** no tendrá la caché y el modo replay
fallará. Opciones: copiar `output/llm_cache/` a la imagen o documentar que la demo siempre se corre desde
el repo con el volumen.

### A-3 · Proxy corporativo
`sources.py` ahora valida por DNS que el repositorio sea público antes de clonar. Detrás de un proxy sin DNS
directo, la validación devuelve `REPO_HOST_UNRESOLVED` (el usuario puede subir un .zip). Si la demo se hace
detrás del proxy de TCS, avisar a B para ajustar.

### C-2 · Certificados del proxy en tiempo de ejecución — RESUELTO por la Máquina C
La imagen final conserva los certificados corporativos y define `SSL_CERT_FILE` y `REQUESTS_CA_BUNDLE`
contra el almacén del sistema. Se verificó desde el contenedor un handshake TLS 1.3 con el proveedor sin
desactivar la validación. El cliente también limita tiempo y reintentos mediante
`AGENTCS_LLM_TIMEOUT_S` y `AGENTCS_LLM_MAX_RETRIES`, con errores y acciones explícitas para la UI.

### C-1 · Interfaz (dueña: Máquina C) — informativo
Nuevos códigos de error en la ingesta: `REPO_HOST_BLOCKED` y `REPO_HOST_UNRESOLVED`. Llegan con `message`
y `action` como los demás; no requieren cambios si la UI ya muestra ambos campos.

## Acuerdos

- La caché del LLM se indexa por modelo + prompt. La demo en modo replay debe usar el **mismo**
  `AGENTCS_MODEL` con el que se grabó la caché.
- Antes de cada merge a `main`: `git pull --rebase origin main` y `uv run pytest` en verde, pegando la salida.
