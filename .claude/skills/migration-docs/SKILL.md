---
name: migration-docs
description: Plantillas para los entregables del paquete de migración AgenTCS: matriz de trazabilidad, ADR, reporte de verificación, README del paquete e informe ejecutivo de una página. Usar al escribir el agente Documentador o al preparar los entregables de la hackathon.
---

# Documentación del paquete de migración

## Contenido del paquete (`output/<run>/`)
```
README.md                     # cómo compilar, probar y ejecutar (un comando)
docs/business-rules.md        # catálogo aprobado (tabla + Gherkin)
docs/traceability-matrix.md   # regla ↔ líneas legacy ↔ clase/método Java ↔ pruebas
docs/assumptions.md           # supuestos y decisiones del HITL
docs/architecture.md          # diagrama (Mermaid) + modelo de dominio
docs/adr/ADR-00X-*.md
docs/openapi.yaml
reports/equivalence-report.html
reports/coverage/ (JaCoCo)  reports/quality.md (Sonar/PMD/Semgrep/gitleaks)
EXECUTIVE-SUMMARY.md          # 1 página
src/ ... (estructura del destino) Dockerfile
```

## Matriz de trazabilidad
| Regla | Descripción | Legacy (archivo:líneas · unidad) | Código nuevo (archivo#símbolo) | Pruebas | Estado HITL |
|---|---|---|---|---|---|
| BR-003 | Tasa preferencial por monto | AMORTIZA.cbl:142–147 · 2100-AJUSTAR-TASA | `PreferentialRateRule#apply` | `PreferentialRateRuleTest`, escenario "Tasa preferencial" | Aprobada (D.R.) |

## ADR
```
# ADR-00X · <título>
- Estado: Propuesto | Aceptado
- Fecha:
## Contexto
## Decisión
## Alternativas consideradas
## Consecuencias
## Trazabilidad (reglas / líneas legacy relacionadas)
```

## Informe ejecutivo (máximo 1 página)
1. **Qué se migró**: lenguaje origen → destino, programa, dominio, líneas, complejidad original.
2. **Resultado**: nivel de oráculo (A/B/C), reglas descubiertas (n, % aprobadas sin cambios), equivalencia (n casos, 100%), cobertura, hallazgos críticos (0).
3. **Tiempo**: copiloto (minutos medidos) vs. estimado manual (supuesto explícito, p. ej. X horas por cada 100 líneas para análisis + traducción + pruebas).
4. **Riesgos mitigados**: regresión, pérdida de conocimiento, seguridad (datos sintéticos, enmascaramiento).
5. **Próximos pasos**: Strangler Fig, siguientes programas por mapa de riesgo.

Lenguaje para negocio: sin jerga técnica en las secciones 1–4.
