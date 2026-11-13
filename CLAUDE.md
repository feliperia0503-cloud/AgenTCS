# CLAUDE.md — instrucciones del proyecto AgenTCS

## Contexto
Hackathon TCS: Copiloto de Modernización de Código Legacy. Leer `docs/01-reto-resumen.md` y
`docs/02-arquitectura.md` antes de cambios grandes. El criterio de mayor peso es la **equivalencia
funcional demostrada** (25%); si falla, los criterios 3–7 quedan topados en 3/5.

## Principio de diseño
El copiloto es **agnóstico de lenguaje**: origen → Spec neutral → destino. El núcleo (`copilot/` fuera de
`languages/`) nunca menciona un lenguaje concreto. Todo lo específico va en un adaptador
(`copilot/languages/<id>/`, skill `language-adapters`). No asumir COBOL ni Java.

## Reglas no negociables
- Nunca escribir secretos, llaves ni datos reales en código, prompts, fixtures ni logs. Solo datos sintéticos. `.env` nunca se commitea.
- Todo dinero/tasa: decimal exacto con escala y modo de redondeo explícitos, pasando por el tipo neutral (skill `legacy-type-mapping`). Nunca punto flotante.
- Cada regla de negocio debe citar las líneas de origen del código legacy.
- Lo determinista (parseo, métricas, ejecución, comparación) no se delega al LLM.
- Código generado: arquitectura limpia del destino (skill `clean-architecture-targets`), dominio sin frameworks, complejidad ≤10 por método.
- Las pruebas llevan aserciones explícitas con datos realistas; nada de tests vacíos.

## Stack
Todo corre dentro del contenedor (Dockerfile / Dev Container). Copiloto: Python (uv, LangGraph, Streamlit, tree-sitter).
Runtimes de origen: GnuCOBOL, Mono, JDK, Oracle Free (perfil `oracle`). Destino: JDK 21 + Maven, Node + TypeScript, .NET 8, Python.
No instalar herramientas en el host; si falta algo, agregarlo al Dockerfile o a requirements.txt.

## Comandos
- Pruebas copiloto: `uv run pytest`
- Pruebas del código generado: el comando `test` del adaptador de destino (p. ej. `mvn verify`, `npm test`, `dotnet test`, `pytest`)
- Todo: `docker compose up --build`

## Antes de decir "listo"
Ejecutar las pruebas y mostrar la salida real; no afirmar que algo funciona sin haberlo corrido.
