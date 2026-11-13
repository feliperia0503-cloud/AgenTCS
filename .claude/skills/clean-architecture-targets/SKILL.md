---
name: clean-architecture-targets
description: Convenciones de arquitectura limpia/hexagonal, DDD y Clean Code para cada lenguaje destino del copiloto (Java 21 + Spring Boot 3, TypeScript + Node, C# .NET 8, Python 3.12), con estructura de carpetas, reglas de dependencias verificables, manejo de errores y pruebas. Usar al escribir plantillas o prompts del agente Desarrollador/Arquitecto, al generar el proyecto destino o al revisar su calidad.
---

# Arquitectura limpia por destino

## Común a todos los destinos
- Capas: **domain** (entidades, value objects, reglas; sin frameworks) → **application** (casos de uso, puertos in/out) → **infrastructure** (web, persistencia, archivos, config).
- Dependencias solo hacia adentro; se **verifican con una prueba** (no con buena voluntad).
- Nombres del dominio en lenguaje de negocio (nunca `WS-MONTO`, `v_mnt`, `txtMonto`).
- Métodos cortos, complejidad ciclomática ≤ 10.
- Decimal exacto con escala y redondeo explícitos (skill `legacy-type-mapping`).
- Errores de negocio = excepciones/resultados de dominio con el **mismo código/mensaje del legacy** cuando forman parte del contrato.
- Cada regla implementada lleva su traza: `Regla BR-003 · <archivo>:142–147`.
- Patrones: Strategy (variantes de cálculo), Specification (condiciones combinables), Factory.
- Harness de equivalencia: comando que lee `cases.json` y escribe `actual.json` (skill `golden-master-testing`).

## Java 21 + Spring Boot 3
```
src/main/java/<base>/{domain/{model,rule,exception}, application/{port/in,port/out,service}, infrastructure/{web,persistence,config}}
```
- Value objects con `record`; `BigDecimal` + `RoundingMode`; `ProblemDetail` en `@RestControllerAdvice`; springdoc-openapi.
- Pruebas: JUnit 5 + AssertJ (`isEqualByComparingTo`), Cucumber, **ArchUnit** (dominio sin Spring ni infraestructura), JaCoCo (80/70 en `pom.xml`), PMD.

## TypeScript + Node 20
```
src/{domain/{model,rules,errors}, application/{ports,use-cases}, infrastructure/{http,persistence,config}}
```
- `strict: true`; `decimal.js` para dinero (nunca `number`); Zod para validar entrada; Express o Fastify en `infrastructure/http`; OpenAPI con `zod-to-openapi` o archivo YAML.
- Pruebas: Jest (o Vitest) con cobertura umbral 80/70 en config; **dependency-cruiser** para reglas de capas; ESLint.

## C# .NET 8
```
src/<Name>.Domain, src/<Name>.Application, src/<Name>.Infrastructure, src/<Name>.Api, tests/<Name>.Tests
```
- Proyectos separados = dependencias forzadas por referencias de proyecto. `decimal` + `MidpointRounding` explícito; `record`; Minimal API o Controllers con `ProblemDetails`; Swashbuckle.
- Pruebas: xUnit + FluentAssertions, coverlet (umbral), **NetArchTest** para capas, analizadores Roslyn con warnings como error.

## Python 3.12
```
src/<pkg>/{domain, application, infrastructure}
```
- `Decimal` con `localcontext` y `quantize(…, rounding=ROUND_HALF_UP)`; `@dataclass(frozen=True)`; Pydantic en el borde; FastAPI para HTTP.
- Pruebas: pytest + pytest-cov (`--cov-fail-under=80`), **import-linter** para capas, ruff + mypy.
