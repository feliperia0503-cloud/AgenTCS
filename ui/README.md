# AgenTCS — Migration Studio (interfaz de AgenTCS)

Interfaz del copiloto. React 19 + Vite 8. Diseño en [DESIGN.md](DESIGN.md) y producto en [PRODUCT.md](PRODUCT.md).

## Desarrollo
Requiere la API corriendo en el puerto 8000 (ver README raíz).

```bash
cd ui
npm ci          # versiones fijadas en package-lock.json
npm run dev     # http://localhost:5173  — /api se redirige a http://localhost:8000
```
Otra URL de API: `AGENTCS_API_URL=http://host:puerto npm run dev`.

## Producción
`npm run build` genera `dist/`. En Docker, FastAPI sirve `dist/` y `/api` desde el mismo origen (http://localhost:8000).

## Conexión con la API
- `src/api/client.js`: llamadas a la API (crear ejecución, consultar estado, decidir reglas, aprobar, verificación, paquete). Los errores traen `code`, `message` y `action` (acción sugerida para el usuario).
- `src/api/adapters.js`: convierte los contratos (`Rule`, `VerificationReport`, `RunState`) a la forma que ya usan las vistas (`demoRules`, `testRows`, progreso de la ruta).

## Pendiente para reemplazar el modo maqueta (rol C)
1. `startMigration` → `api.createRun(...)` y sondear `api.getRun(id)` para el progreso real (`toRouteProgress`).
2. `demoRules` → `run.spec.rules.map(toUiRule)`; botones aprobar / ajustar / rechazar → `api.decideRule`.
3. Botón para aprobar la especificación → `api.approveSpec`.
4. `testRows` → `toUiTestRows(run.verification)`, mostrar nivel de oráculo y diferencias.
5. Carga de archivos legacy (además de la URL del repositorio).
6. Vista lado a lado: `run.files` (legacy sanitizado) ↔ regla ↔ `run.generated_files`.
7. Enmascaramiento visible (`run.sanitization`) y descarga del paquete (`api.packageUrl`).

El inicio de sesión es demostrativo; no se usan credenciales reales.
