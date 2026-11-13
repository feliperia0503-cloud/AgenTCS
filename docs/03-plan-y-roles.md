# 03 · Plan de trabajo y roles

> Ajustar los bloques a la duración real de la hackathon. Regla de oro: **tener el camino feliz completo
> funcionando de punta a punta lo antes posible**, aunque sea feo, y después mejorar cada fase.

## Alcance
- **Producto:** copiloto agnóstico de lenguaje (ADR-003): núcleo + Spec neutral + adaptadores.
- **Par 1 (de punta a punta primero):** COBOL (amortización francesa) → Java 21 + Spring Boot 3.
- **Par 2 (prueba de agnosticismo):** PL/SQL (liquidación de siniestros) → TypeScript + Node.
- **Par 3 (si hay tiempo):** C# .NET Framework legacy → C# .NET 8 (o cualquier destino ya construido).
- **En la demo:** el usuario elige origen y destino en la UI; se muestra la matriz de packs disponibles.
- Regla: un par nuevo solo se empieza cuando el anterior pasa el 100% de equivalencia.

## Roles (asignar nombres)
| Rol | Responsabilidades | Criterios que más impacta |
|---|---|---|
| **A · Núcleo IA y adaptadores** | Contratos (Spec neutral, interfaces), LangGraph, agentes, extracción de reglas, packs de origen (parse/classify) y destino (scaffold/generación), autocorrección | 2, 3, 4 |
| **B · Verificación y plataforma** | Programas legacy de ejemplo por lenguaje + datos sintéticos, runners de origen (GnuCOBOL, Oracle Free), harness de destino, comparador neutral, niveles de oráculo, calidad/seguridad, Docker | **1**, 5, 8 |
| **C · Experiencia, docs y pitch** | UI (wizard, vista comparativa, HITL, tablero), plantillas de documentación e informe ejecutivo, guion de demo, video de respaldo, prueba con usuario externo | 6, 7, 9, 10 |

## Orden de ejecución
### Bloque 0 — Arranque (todos juntos, corto)
- [ ] Crear repo Git con la estructura del README y `.gitignore` (incluye `.env`).
- [ ] Instalar herramientas ([04-stack-skills-instalacion.md](04-stack-skills-instalacion.md)).
- [ ] Acordar los **contratos**: `Spec` neutral, `NeutralType`, `Rule`, `AnalysisResult`, `Case`/`CaseOutput`, `VerificationReport` e interfaces `SourceAdapter`/`TargetAdapter` (skill `language-adapters`).
- [ ] B escribe el `AMORTIZA.cbl` y confirma que **compila y corre en GnuCOBOL**.

### Bloque 1 — Camino feliz mínimo (prioridad absoluta)
- [ ] A: pipeline lineal (sin UI) código → Spec neutral → Java, usando adaptadores `cobol` y `java`.
- [ ] B: runner COBOL → `expected.json`; harness Java → `actual.json`; comparador neutral.
- [ ] C: esqueleto de UI con las 8 fases y datos falsos.
- [ ] **Hito 1:** COBOL → Java pasa el 100% de equivalencia en al menos 10 casos.
- [ ] **Hito 2:** PL/SQL → TypeScript con el **mismo núcleo** (solo adaptadores nuevos) pasa el 100%.

### Bloque 2 — Profundidad
- [ ] A: LangGraph con `interrupt` para HITL; autocorrección; trazabilidad línea a línea; confianza por regla.
- [ ] B: casos borde + entrada inválida; cobertura ≥80/70; ArchUnit; Semgrep + gitleaks; enmascaramiento demostrable (poner un secreto falso en el COBOL y mostrar que se oculta).
- [ ] C: conectar la UI al backend real; aprobación/ajuste de reglas; tablero de métricas.

### Bloque 3 — Empaquetado y demo
- [ ] `docker compose up` desde cero en una máquina limpia.
- [ ] Documentador genera: matriz de trazabilidad, ADRs, OpenAPI, reportes, informe ejecutivo de 1 página.
- [ ] Ensayar la demo ≥3 veces con cronómetro (≤10 min).
- [ ] Grabar la ejecución completa (contingencia).
- [ ] Prueba con un usuario externo al equipo sin ayuda (criterio 9).

### Bloque 4 — Extras si sobra tiempo
- [ ] Par 3 (.NET legacy), pack de RPG con oráculo nivel C, mutación, Gherkin ejecutable.

## Riesgos y mitigación
| Riesgo | Mitigación |
|---|---|
| El LLM traduce mal los redondeos | Tabla de mapeo de tipos en RAG + golden master + reintento con el caso que falló |
| Se cae la conexión/API en la demo | Video pregrabado + caché de respuestas del LLM por hash de prompt (modo "replay") |
| La demo es en otra máquina | Todo en un contenedor; imagen exportada (`agentcs-demo.tar`) o Codespaces (ADR-002) |
| Alcance excesivo | PL/SQL solo después del hito del Bloque 1 |
| Las API keys se filtran al repo | `.env` en `.gitignore` + gitleaks en pre-commit |
