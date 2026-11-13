# AgenTCS — Copiloto de Modernización y Descubrimiento de Código Legacy

Hackathon AI Friday · TCS
Equipo: Juan Bastidas · Felipe Rincón · Dairon Rodríguez

## Qué construimos
Un copiloto multiagente **agnóstico de lenguaje**: toma código legacy en cualquier lenguaje (COBOL,
PL/SQL, RPG, VB6, .NET Framework, Java antiguo…), lo convierte en una **especificación neutral** (reglas de
negocio con trazabilidad a líneas, modelo de dominio, contrato de E/S y casos de prueba), la somete a
aprobación humana y genera código en el lenguaje moderno elegido (Java/Spring, TypeScript/Node, C#/.NET 8,
Python) con arquitectura limpia. **Demuestra la equivalencia funcional** ejecutando el legacy y el código
nuevo con los mismos casos sintéticos, declarando el nivel de evidencia (oráculo A/B/C).

Cada lenguaje es un adaptador (`copilot/languages/<id>/`): agregar uno nuevo no toca el núcleo.
Primer par construido: COBOL → Java. Segundo par para demostrar agnosticismo: PL/SQL → TypeScript.

## Mapa de la documentación
| Documento | Contenido |
|---|---|
| [docs/01-reto-resumen.md](docs/01-reto-resumen.md) | Resumen del reto, reglas duras y condiciones habilitantes |
| [docs/02-arquitectura.md](docs/02-arquitectura.md) | Arquitectura de la solución, agentes, flujo de 8 fases |
| [docs/03-plan-y-roles.md](docs/03-plan-y-roles.md) | Reparto de trabajo entre los 3 y orden de ejecución |
| [docs/04-stack-skills-instalacion.md](docs/04-stack-skills-instalacion.md) | Qué instalar: herramientas, skills de Claude Code, MCP, librerías |
| [docs/05-checklist-evaluacion.md](docs/05-checklist-evaluacion.md) | Checklist contra cada criterio de evaluación y su peso |
| [docs/06-guion-demo.md](docs/06-guion-demo.md) | Guion de demo de 10 minutos + plan de contingencia |
| [docs/07-como-empezar.md](docs/07-como-empezar.md) | **Arranque paso a paso** y primeros prompts por rol |
| [docs/adr/](docs/adr/) | Registros de decisión de arquitectura (ADRs) |
| [.claude/skills/](.claude/skills/) | Skills del proyecto para Claude Code: adaptadores de lenguaje, semántica COBOL/PL-SQL/.NET, reglas, tipos, arquitectura por destino, golden master, docs |
| [scripts/](scripts/) | Instalación mínima (Git, Docker, VS Code) y exportación de la imagen para la demo |
| [Dockerfile](Dockerfile) · [.devcontainer/](.devcontainer/) | Entorno completo en un contenedor: el mismo para desarrollar y para la demo |
| [CLAUDE.md](CLAUDE.md) | Instrucciones del proyecto para Claude Code |

## Estructura del repositorio (objetivo)
```
AgenTCS/
├── README.md
├── CLAUDE.md
├── docker-compose.yml          # un solo comando: docker compose up
├── docs/                       # esta documentación
├── samples/                    # artefactos legacy de ejemplo (sintéticos), uno por lenguaje
│   ├── cobol/  plsql/  dotnet/  ...
├── copilot/                    # orquestador + agentes (Python)
│   ├── contracts/              # Spec neutral, tipos neutrales, interfaces de adaptadores
│   ├── languages/              # packs: cobol, plsql, csharp-legacy, java, typescript, csharp, python...
│   ├── engine/                 # motor: extractor, casos, oráculo, generador, bucle, lecciones, CLI
│   ├── analysis/               # parser, AST, grafo, métricas
│   ├── security/               # enmascaramiento de secretos/PII
│   ├── knowledge/              # RAG: estándares, glosario, mapeo de tipos
│   ├── verification/           # sandbox: compilar, ejecutar, comparar
│   └── api/                    # FastAPI (service.py = lógica, app.py = HTTP, demo.py = modo demo)
├── ui/                         # AgenTCS — Migration Studio (React + Vite), ver ui/README.md
└── output/                     # paquete de migración generado por cada ejecución
```

## Motor de migración con autocorrección (ADR-005)
`copilot/engine/` extrae las reglas implícitas del legacy, genera casos de prueba, obtiene los resultados
esperados (oráculo A/B/C), genera el código destino y lo corrige en bucle con la retroalimentación de las
pruebas hasta lograr equivalencia total o dejar de mejorar; devuelve siempre la mejor versión y guarda
lecciones para futuras migraciones (no es fine-tuning).

Destinos: **Java 21, C# (.NET 8), TypeScript (Node) y Python**, con el framework y la arquitectura que
elijas (ADR-006). Origen: cualquier lenguaje, por archivos, comprimidos (.zip, .tar.gz) o repositorio Git.

```bash
python -m copilot.engine migrate --source legacy/INTERES.cbl --target java --auto-approve
AGENTCS_LLM_REPLAY=1 python -m copilot.engine migrate ...   # sin internet, desde output/llm_cache
```
En la API: `AGENTCS_MODE=real` (con `ANTHROPIC_API_KEY`). El modo `demo` sigue disponible y no usa LLM.

## Cómo ejecutar
```bash
# Solo requiere Docker
cp .env.example .env    # poner ANTHROPIC_API_KEY (nunca commitear .env)
docker compose up --build
# Interfaz y API en http://localhost:8000  (AGENTCS_MODE=demo por defecto)
# Con PL/SQL como origen ejecutable:  docker compose --profile oracle up --build

# En otra máquina sin build ni internet:
docker load -i agentcs-demo.tar && docker compose up
```
