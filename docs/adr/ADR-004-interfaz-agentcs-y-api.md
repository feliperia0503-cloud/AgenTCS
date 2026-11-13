# ADR-004 · Interfaz AgenTCS (React + Vite) y API FastAPI

- **Estado:** Aceptado
- **Fecha:** 2026-11-13
- **Reemplaza:** la decisión de UI de ADR-001 (Streamlit)

## Contexto
El equipo construyó un prototipo de interfaz, **AgenTCS — Migration Studio** (React + Vite), con sistema
de diseño propio (DESIGN.md), la ruta de migración por estaciones, selección de destino, reglas con
evidencia y pantalla de pruebas, pero con datos simulados. La experiencia de usuario pesa 10% en los
criterios técnicos y 33,33% en "Interactivo y fácil de usar"; Streamlit no alcanza ese nivel.

## Decisión
- **Frontend:** AgenTCS pasa a `ui/` como interfaz definitiva. Versiones fijadas en `package-lock.json`.
- **Backend:** API FastAPI en `copilot/api/`:
  - `service.py`: lógica independiente del framework (probada sin servidor).
  - `app.py`: rutas HTTP; también sirve `ui/dist` en el mismo origen.
  - `demo.py`: modo demo con datos sintéticos que cumplen los contratos y valores esperados calculados
    por una implementación de referencia (oráculo nivel C, declarado).
- **Contrato UI ↔ API:** los modelos de `copilot/contracts` (JSON Schema en `contracts/schemas/`).
  `ui/src/api/adapters.js` traduce los contratos a la forma de los componentes de AgenTCS.
- **Errores:** toda respuesta de error trae `code`, `message` y `action` (acción sugerida), sin trazas
  ni contenido del usuario.
- **Modos:** `AGENTCS_MODE=demo` (por defecto, sin LLM) y `real` (pipeline con adaptadores y LLM).
- **Despliegue:** Dockerfile multi-etapa (Node compila la UI → imagen Python/runtimes). Un solo
  contenedor, un solo puerto (8000).

## Endpoints
| Método | Ruta | Uso |
|---|---|---|
| GET | `/api/health` | Estado y modo |
| GET | `/api/languages` | Packs de origen y destino disponibles |
| POST | `/api/runs` | Crear ejecución (multipart: `files[]`, `target_language`, `source_language?`, `domain?`, `demo?`) |
| GET | `/api/runs/{id}` | `RunState` completo (fases, reglas, verificación, código generado) |
| POST | `/api/runs/{id}/rules/{rule_id}/decision` | HITL: `approve` / `adjust` / `reject` con `by`, `comment`, `changes` |
| POST | `/api/runs/{id}/approve` | Aprobar la especificación completa → diseño, generación, verificación |
| GET | `/api/runs/{id}/verification` | Reporte actual + intentos previos + gates fallidos |
| GET | `/api/runs/{id}/package` | Paquete de migración (.zip) |

## Consecuencias
- (+) La UI se integra ya contra el modo demo, sin esperar al pipeline real.
- (+) El mismo contrato sirve para demo y real: cambiar de modo no toca la UI.
- (−) Dos ecosistemas (Node + Python); se mitiga con la build multi-etapa y el Dev Container.
- (−) Las ejecuciones se procesan de forma síncrona; si el pipeline real tarda, se pasa a tareas en
  segundo plano con sondeo de `/api/runs/{id}` (la UI ya sondea).
