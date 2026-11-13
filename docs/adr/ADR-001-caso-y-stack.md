# ADR-001 · Caso de negocio y stack tecnológico

- **Estado:** Reemplazado parcialmente por ADR-003 (el alcance es agnóstico de lenguaje; COBOL → Java queda como primer par a construir)
- **Fecha:** 2026-11-13

## Contexto
El reto permite cualquier lenguaje de origen y destino, pero pondera con 25% la equivalencia funcional
demostrada y limita los criterios 3–7 a 3/5 si esta falla. Somos 3 personas con tiempo limitado.

## Decisión
1. **Origen:** COBOL, caso de amortización francesa (ejemplo explícito del reto, dominio bancario).
2. **Destino:** Java 21 + Spring Boot 3 con arquitectura hexagonal.
3. **Orquestación:** ~~LangGraph~~ → motor propio en Python, ver ADR-005.
4. **LLM:** Claude vía API, con salidas estructuradas (JSON schema).
5. **Verificación:** GnuCOBOL ejecuta el original para obtener el golden master; Maven + JUnit 5 para el destino.
6. **UI:** ~~Streamlit~~ → reemplazado por AgenTCS (React + Vite) + FastAPI, ver ADR-004.

## Alternativas consideradas
- PL/SQL como caso principal: requiere Oracle en contenedor (pesado); queda como extensión.
- Node.js/TypeScript como destino: válido, pero Java/BigDecimal es el estándar en banca y facilita la precisión decimal.
- Solo LLM sin ejecutar el legacy: más rápido, pero no demuestra equivalencia (criterio de mayor peso).

## Consecuencias
- (+) Equivalencia verificable contra el comportamiento real del COBOL.
- (+) Narrativa clara para clientes bancarios de TCS.
- (−) Dependencia de Docker/WSL en Windows; mitigar con imágenes preconstruidas.
