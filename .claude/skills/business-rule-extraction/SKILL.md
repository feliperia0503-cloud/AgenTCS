---
name: business-rule-extraction
description: Cómo extraer y formalizar reglas de negocio de código legacy de cualquier lenguaje (COBOL, PL/SQL, RPG, .NET, Java) en el formato del catálogo AgenTCS (JSON con condición/acción, líneas de origen, confianza, supuestos y Gherkin). Usar al diseñar prompts del agente Extractor, al validar su salida o al escribir el catálogo de reglas.
---

# Extracción de reglas de negocio

## Principios
1. **Toda regla cita sus líneas de origen.** Sin líneas, no es una regla: es una suposición.
2. **Una regla = una decisión de negocio** (una condición o fórmula que un analista de negocio reconocería). No partir una fórmula en pedazos técnicos.
3. **Separar** lo que decide el negocio de lo que hace la plataforma (ver la skill de semántica del lenguaje origen: `cobol-semantics`, `plsql-semantics`, `dotnet-legacy-semantics`).
7. **Neutral al lenguaje**: `condition`/`action` se escriben en pseudocódigo neutral y lenguaje de negocio; la sintaxis original solo va en `source.snippet`. Así la misma regla sirve para cualquier destino.
4. **Confianza honesta.** Bajar la confianza y explicar por qué si hay `REDEFINES`, `GO TO` cruzados, constantes sin nombre, truncamientos implícitos o lógica que depende de datos externos.
5. **Supuestos explícitos.** Todo lo que el modelo infiere y no está en el código va en `assumptions`.
6. El LLM recibe el código **ya sanitizado** y el resultado del análisis estático; nunca el código crudo con secretos.

## Esquema del catálogo (JSON)
```json
{
  "program": "AMORTIZA",
  "source_language": "cobol",
  "rules": [
    {
      "id": "BR-003",
      "name": "Tasa preferencial por monto",
      "category": "CALCULO | VALIDACION | DECISION | CONSTANTE",
      "description": "Si el monto es mayor o igual a 50.000.000 se descuentan 0,5 puntos a la tasa anual.",
      "condition": "monto >= 50000000",
      "action": "tasa_anual = tasa_anual - 0.50",
      "decision_table": null,
      "source": {"file": "AMORTIZA.cbl", "unit": "2100-AJUSTAR-TASA", "lines": [142, 147], "snippet": "IF WS-MONTO >= 50000000 ..."},
      "variables": {"monto": "WS-MONTO", "tasa_anual": "WS-TASA-ANUAL"},
      "result_type": "decimal(5,2,DOWN)",
      "confidence": 0.92,
      "confidence_reason": "Condición y acción explícitas en un único párrafo",
      "assumptions": ["El monto está expresado en pesos sin decimales significativos"],
      "gherkin": "Escenario: Tasa preferencial\n  Dado un crédito de 60.000.000 a tasa anual 18,00\n  Cuando se calcula la tabla de amortización\n  Entonces la tasa aplicada es 17,50",
      "status": "PENDIENTE | APROBADA | AJUSTADA | RECHAZADA",
      "review": {"by": null, "at": null, "comment": null}
    }
  ]
}
```

## Escala de confianza
| Rango | Criterio |
|---|---|
| 0,90–1,00 | Lógica explícita, local, sin efectos colaterales |
| 0,70–0,89 | Requiere seguir PERFORMs o variables entre párrafos |
| 0,50–0,69 | GO TO, REDEFINES, constantes mágicas o semántica numérica dudosa |
| < 0,50 | Depende de datos externos o del entorno; marcar para revisión humana obligatoria |

Reglas con confianza < 0,70 se resaltan en la UI y no pueden aprobarse sin comentario.

## Verificación de la salida del extractor (determinista)
- Las líneas citadas existen y caen dentro de la unidad citada (párrafo, procedimiento, método).
- Las variables citadas aparecen en esas líneas.
- No hay dos reglas con la misma fuente exacta y distinta acción.
- Cobertura: toda unidad clasificada como negocio tiene al menos una regla.
