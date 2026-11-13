# 01 · Resumen del reto

Fuente: `Reto_Hackathon_original.docx` (en esta misma carpeta).

## El problema
Bancos y aseguradoras corren su core en COBOL, PL/SQL, RPG o Java antiguo. La lógica de negocio vive solo
en el código (caja negra), los expertos se jubilan, el análisis manual de una rutina toma semanas y
traducir a mano genera regresiones (reglas tácitas y casos borde omitidos).

## Nuestra interpretación clave
El copiloto debe servir para **cualquier lenguaje legacy y cualquier destino moderno**, no para un par
fijo. Ver ADR-003: especificación neutral + adaptadores por lenguaje.

## Lo que piden
Un **prototipo funcional con calidad de demo para cliente** que:
1. Ingiera código legacy y lo sanitice (secretos/PII enmascarados antes de ir al LLM).
2. Haga análisis estático (AST, grafo de dependencias, complejidad, mapa de riesgo).
3. Extraiga reglas de negocio (condición/acción, tablas de decisión, Gherkin) **con línea de origen y nivel de confianza**.
4. Permita **validación humana** de cada regla (aprobar / ajustar / rechazar).
5. Diseñe la arquitectura destino (DDD, hexagonal, OpenAPI, ADRs).
6. Genere código moderno compilable, con ciclo de autocorrección.
7. **Verifique equivalencia funcional** (Golden Master + pruebas diferenciales), cobertura y calidad.
8. Empaquete todo: código, pruebas, docs, reportes, Docker de un comando, informe ejecutivo de 1 página.

Sin restricción de stack (Python, LangChain/LangGraph, LlamaIndex, Semantic Kernel, MCP o low-code).

## Reglas duras
- **Fidelidad matemática**: 0 diferencias en cálculos y redondeos.
- **Seguridad**: nada de secretos, credenciales, llaves de API ni datos reales hacia los modelos.
- **Trazabilidad**: cada regla y decisión enlazada a su origen.
- **Pruebas no triviales**: aserciones explícitas con datos realistas del dominio.
- **HITL obligatorio** antes de generar el código final.

## Condiciones habilitantes (¡críticas!)
- El flujo completo (carga → paquete) **debe ejecutarse en la demo**.
- Si las pruebas de funcionalidad/equivalencia no pasan, **los criterios 3 a 7 quedan con máximo 3/5**.
- Datos reales, secretos o credenciales en el flujo = **descalificación**.

## Evaluación
### Criterios técnicos
| # | Criterio | Peso |
|---|---|---|
| 1 | Pruebas de funcionalidad y equivalencia | **25%** |
| 2 | Precisión en extracción de reglas | 15% |
| 3 | Arquitectura | 15% |
| 4 | Calidad de código (Clean Code) | 15% |
| 5 | Seguridad e IA responsable | 10% |
| 6 | Entregables y documentación | 10% |
| 7 | UX y calidad de la demo | 10% |

### Visión de cliente y negocio (33,33% cada uno)
| # | Criterio | Qué hay que mostrar |
|---|---|---|
| 8 | Funcional | Flujo completo en vivo, 1 caso representativo + 1 caso borde, manejo de 1 entrada inválida |
| 9 | Interactivo y fácil de usar | Flujo guiado, vista comparativa, estado por fase, errores con acción sugerida, **un usuario externo completa la tarea sin ayuda** |
| 10 | Innovador | Comparación cuantificada vs. proceso manual y diferenciador explícito |

Escala 1–5 por criterio. Detalle de evidencias en [05-checklist-evaluacion.md](05-checklist-evaluacion.md).

## Umbrales de calidad
| Métrica | Umbral |
|---|---|
| Casos de equivalencia aprobados | 100% |
| Diferencias en cálculos/redondeos | 0 |
| Reglas con referencia a código origen | 100% |
| Cobertura líneas / ramas | ≥ 80% / ≥ 70% |
| Hallazgos bloqueantes/críticos | 0 |
| Complejidad ciclomática por método | ≤ 10 |
| Vulnerabilidades críticas y secretos expuestos | 0 |
| Tiempo E2E por rutina | Minutos vs. semanas |
