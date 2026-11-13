# 08 — Coordinación entre máquinas

Cada máquina actualiza **solo su fila** al terminar una tarea. Los pedidos a otra máquina van en la
sección de pedidos, nunca como cambios directos a archivos ajenos.

## Estado

| Máquina | Rol | Rama | Hecho | En curso | Bloqueado por |
|---|---|---|---|---|---|
| A | Origen, oráculo, Dockerfile | — | — | — | — |
| B | Verificación de punta a punta y destinos | `maquina-b/nivel-b-reportes` | Ronda 1 (en main): `.gitattributes`, `samples/`, fix enteros pack C#, anti-SSRF, `.sql`→`plsql`, caché versionable. Ronda 2: **oráculo nivel B** (`POST /api/runs/{id}/expected` y CLI `--expected`; los pares son los casos y el oráculo), **paquete** con `reports/executive-summary.md` (1 página por corrida), `reports/security.md/.json` (gitleaks + Semgrep con reglas locales, sin internet; si falta una herramienta se declara escaneo incompleto). 126 pruebas pasan, 7 omitidas (sin cobc/fpc/mono/.NET/FastAPI/semgrep locales). | — | Corridas reales C-3 (las ejecuta C). |
| C | Interfaz y documentación | `maquina-c/ux-docs` | Finalizado: UI de verificación, informe ejecutivo, guion de demo y guía/plantilla de prueba externa. Build Vite verde; 72 pruebas pasan en Docker. | — | — |

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

### C-3 · Corridas reales de B (las ejecuta la Máquina C, que tiene Docker) — HACER DESPUÉS del último cambio de prompts
La caché en `output/llm_cache` es de una corrida vieja (COBOL→Python, antes de ADR-007): con los prompts actuales
no coincide y el modo replay fallaría. Regenerarla al final. Requiere `.env` con la API key (nunca en git).
Una corrida por destino; si llega al 100 %, no repetirla.
```powershell
docker compose build
docker compose run --rm copilot python -m pytest -q
docker compose run --rm copilot python -m copilot.engine migrate --source samples/cobol/INTMORA.cbl --target java --auto-approve
docker compose run --rm copilot python -m copilot.engine migrate --source samples/cobol/PAGOMIN.cbl --target typescript --auto-approve
docker compose run --rm copilot python -m copilot.engine migrate --source samples/cobol/INTMORA.cbl --target csharp --auto-approve
docker compose run --rm -e AGENTCS_LLM_REPLAY=1 copilot python -m copilot.engine migrate --source samples/cobol/INTMORA.cbl --target java --auto-approve
```
Cada corrida deja `output/runs/<id>/package.zip` con `reports/executive-summary.md`: de ahí salen los datos
`[PENDIENTE]` de `docs/informe-ejecutivo.md`. Si una corrida no llega al 100 %, enviar a B la salida de consola.

### C-4 · Interfaz para el nivel B (dueña: Máquina C)
Agregar en la pantalla de reglas (antes de "Aprobar especificación") un campo opcional "Pares esperados (.json)"
que haga `POST /api/runs/{id}/expected` (multipart, campo `file`). Respuesta: `{pairs, validated_against_spec, note}`;
errores con `code/message/action` (`PAIRS_INVALID`, `PAIRS_MISMATCH`, `PAIRS_TOO_LATE`). Formato en `samples/README.md`.

### A-4 · Dockerfile: runtimes que declara ADR-007 (dueña: Máquina A)
El ADR-007 dice que la imagen agrega `php-cli`, `fp-compiler` y `mono-runtime`, pero el Dockerfile de `main`
solo instala `gnucobol` y `mono-mcs`. Sin ellos, Delphi y PHP caen siempre a nivel C dentro de Docker.

### C-3 · Corridas reales de B (las ejecuta la Máquina C, que tiene Docker) — HACER DESPUÉS del último cambio de prompts
La caché en `output/llm_cache` es de una corrida vieja (COBOL→Python, antes de ADR-007): con los prompts actuales
no coincide y el modo replay fallaría. Regenerarla al final. Requiere `.env` con la API key (nunca en git).
Una corrida por destino; si llega al 100 %, no repetirla.
```powershell
docker compose build
docker compose run --rm copilot python -m pytest -q
docker compose run --rm copilot python -m copilot.engine migrate --source samples/cobol/INTMORA.cbl --target java --auto-approve
docker compose run --rm copilot python -m copilot.engine migrate --source samples/cobol/PAGOMIN.cbl --target typescript --auto-approve
docker compose run --rm copilot python -m copilot.engine migrate --source samples/cobol/INTMORA.cbl --target csharp --auto-approve
docker compose run --rm -e AGENTCS_LLM_REPLAY=1 copilot python -m copilot.engine migrate --source samples/cobol/INTMORA.cbl --target java --auto-approve
```
Cada corrida deja `output/runs/<id>/package.zip` con `reports/executive-summary.md`: de ahí salen los datos
`[PENDIENTE]` de `docs/informe-ejecutivo.md`. Si una corrida no llega al 100 %, enviar a B la salida de consola.

### C-4 · Interfaz para el nivel B (dueña: Máquina C)
Agregar en la pantalla de reglas (antes de "Aprobar especificación") un campo opcional "Pares esperados (.json)"
que haga `POST /api/runs/{id}/expected` (multipart, campo `file`). Respuesta: `{pairs, validated_against_spec, note}`;
errores con `code/message/action` (`PAIRS_INVALID`, `PAIRS_MISMATCH`, `PAIRS_TOO_LATE`). Formato en `samples/README.md`.

### A-4 · Dockerfile: runtimes que declara ADR-007 (dueña: Máquina A)
El ADR-007 dice que la imagen agrega `php-cli`, `fp-compiler` y `mono-runtime`, pero el Dockerfile de `main`
solo instala `gnucobol` y `mono-mcs`. Sin ellos, Delphi y PHP caen siempre a nivel C dentro de Docker.

### C-1 · Interfaz (dueña: Máquina C) — informativo
Nuevos códigos de error en la ingesta: `REPO_HOST_BLOCKED` y `REPO_HOST_UNRESOLVED`. Llegan con `message`
y `action` como los demás; no requieren cambios si la UI ya muestra ambos campos.

## Acuerdos

- La caché del LLM se indexa por modelo + prompt. La demo en modo replay debe usar el **mismo**
  `AGENTCS_MODEL` con el que se grabó la caché.
- Antes de cada merge a `main`: `git pull --rebase origin main` y `uv run pytest` en verde, pegando la salida.
