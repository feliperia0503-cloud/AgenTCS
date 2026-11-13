# 04 · Entorno: portable por diseño

## Principio
**En el computador solo se instala Docker.** Todo el stack vive en una imagen (`Dockerfile`) que se
usa igual para desarrollar (Dev Container), para probar y para la demo. Si la demo es en otra máquina,
se lleva la imagen exportada o se abre en el navegador con GitHub Codespaces. Ver ADR-002.

## Qué se instala en cada máquina
| Máquina | Necesita | Cómo |
|---|---|---|
| Desarrollo | Git, Docker Desktop, VS Code + extensión Dev Containers | `scripts/setup-windows.ps1` |
| Demo (cualquiera) | **Solo Docker Desktop** | `docker load -i agentcs-demo.tar` + `docker compose up` |
| Demo sin nada instalado | Solo un navegador | GitHub Codespaces (usa el mismo `.devcontainer`) |

## Qué hay dentro del contenedor
| Componente | Uso |
|---|---|
| Ubuntu 24.04 | Base |
| GnuCOBOL · Mono · JDK | Ejecutar legacy COBOL, C# .NET Framework y Java antiguo (oráculo nivel A) |
| Oracle Database Free | PL/SQL legacy — servicio aparte, solo con `--profile oracle` |
| JDK 21 + Maven · Node + TypeScript · .NET 8 SDK · Python | Compilar y probar el código destino (las herramientas de prueba/calidad van como dependencias de cada plantilla) |
| Python + uv + `requirements.txt` | Copiloto: anthropic, langgraph, pydantic, streamlit, tree-sitter, oracledb, detect-secrets, networkx, jinja2 |
| Semgrep, gitleaks | SAST y detección de secretos |
| Node + Claude Code | Solo en el Dev Container (desarrollo), no en la demo |

Se eliminó SonarQube (pesado): la calidad se mide con PMD + JaCoCo + ArchUnit desde Maven y Semgrep.

## Skills de Claude Code (en el repo, `.claude/skills/`)
`language-adapters`, `cobol-semantics`, `plsql-semantics`, `dotnet-legacy-semantics`,
`business-rule-extraction`, `legacy-type-mapping`, `clean-architecture-targets`, `golden-master-testing`,
`migration-docs`. Viajan con el repo: no se instalan. Al agregar un lenguaje, crear su skill de semántica.
Skills incluidas en Claude Code que también conviene usar: skill-creator, frontend-design, docx/pdf, pptx.

## Servidores MCP
Opcionales y fuera del camino crítico. Si se quieren (p. ej. Playwright para grabar la demo), agregarlos
dentro del Dev Container con `claude mcp add`.

## Secretos
`ANTHROPIC_API_KEY` en `.env` (excluido por `.gitignore` y `.dockerignore`, nunca entra a la imagen).
En Codespaces: usar *Codespaces secrets*. Sin llave, la app debe arrancar en **modo replay**
(respuestas del LLM cacheadas) — esto también es el plan de contingencia sin internet.
