# ADR-003 · Copiloto agnóstico de lenguaje: especificación neutral + adaptadores

- **Estado:** Propuesto
- **Fecha:** 2026-11-13
- **Reemplaza parcialmente:** ADR-001 (COBOL → Java deja de ser el alcance; pasa a ser el primer par a construir)

## Contexto
El cliente puede tener cualquier lenguaje legacy (COBOL, PL/SQL, RPG, VB6, .NET Framework, Java antiguo)
y querer cualquier destino moderno (Java, TypeScript, C#, Python). Un traductor por par no escala (N × M).

## Decisión
- Pivote: **especificación neutral** (reglas, modelo, contrato I/O en JSON Schema, casos de prueba) con
  tipos neutrales que incluyen escala y modo de redondeo.
- **Adaptadores de origen y destino** como plugins (`copilot/languages/<id>/`) con una interfaz común.
- Lenguaje sin parser dedicado: segmentador genérico + LLM, con confianza reducida y declarada.
- Equivalencia con **niveles de oráculo A/B/C** declarados en el reporte.
- Construcción incremental: COBOL → Java primero; segundo par distinto (PL/SQL → TypeScript) para demostrar agnosticismo.

## Alternativas
- Traducción directa con LLM por par de lenguajes: rápida pero sin spec auditable, N × M y sin HITL útil.
- Un IR de bajo nivel (estilo compilador): demasiado costoso para el tiempo de la hackathon.

## Consecuencias
- (+) Agregar un lenguaje = un adaptador. Argumento fuerte de innovación y escalabilidad.
- (+) La spec aprobada es el entregable de "caja negra → conocimiento" independiente del destino.
- (−) No todo legacy es ejecutable: algunas migraciones tendrán evidencia nivel C. Se declara, no se oculta.
- (−) Imagen más grande por los runtimes; Oracle va en un perfil opcional de Compose.
