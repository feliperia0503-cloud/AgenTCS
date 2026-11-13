# ADR-005 · Motor de migración con autocorrección

- **Estado:** Aceptado
- **Fecha:** 2026-11-13
- **Reemplaza parcialmente:** ADR-001 punto 3 (LangGraph como orquestador)

## Contexto
El reto pide migrar código legacy de cualquier lenguaje a uno moderno y **demostrar** equivalencia
funcional (25% de la nota, y topa los criterios 3–7 si falla). Un LLM no acierta siempre a la primera:
los errores típicos son de semántica numérica (truncar vs. redondear), orden de validaciones y códigos de
error. Necesitamos que el sistema detecte y corrija esos errores por sí mismo.

## Decisión
Motor propio en Python (`copilot/engine/`) que convierte la verificación en retroalimentación:

```
legacy (sanitizado) → segmentador/pack de origen → Extractor (LLM) → Spec ─HITL─┐
                                                                                 ▼
           casos (LLM + fronteras deterministas) → Oráculo (A/B/C) → expected.json
                                                                                 ▼
 ┌─► Generador (LLM) → sandbox: compilar → arnés → actual.json → comparador → similitud
 │                                                                    │
 └──────── retroalimentación (casos fallidos, campo, esperado/obtenido, regla, regresiones) ◄┘
```

| Módulo | Responsabilidad |
|---|---|
| `llm.py` | Cliente Anthropic (modelo en `AGENTCS_MODEL`), caché por SHA-256, modo replay (`AGENTCS_LLM_REPLAY=1`), JSON validado con Pydantic y hasta 2 reintentos enviando el error, registro `LLMCall` |
| `segmenter.py` | Unidades por heurística cuando no hay pack de origen (penaliza la confianza en 15%) |
| `extractor.py` | Reglas con líneas exactas; validación determinista: líneas inexistentes descartan la regla, el snippet se toma del archivo real, variables ausentes bajan la confianza |
| `test_generator.py` | Casos del LLM + fronteras de cada condición numérica (umbral y ± la unidad mínima del tipo) + extremos de tipo; deduplicados; decimales como string |
| `oracle.py` | A: legacy ejecutado (runner del pack). B: pares E/S provistos. C: implementación de referencia en Python desde la Spec aprobada |
| `generator.py` | Proyecto completo en el primer intento; en reintentos, solo parche con los archivos que cambian |
| `sandbox.py` / `pyharness.py` | Carpeta por intento, sin shell, timeout, salida truncada, rutas validadas, variables secretas fuera del entorno |
| `loop.py` | El bucle, la métrica y los criterios de parada |
| `lessons.py` | Memoria persistente de lecciones por par de lenguajes |
| `pipeline.py` | Orquesta el motor sobre `RunState` (lo usan la API y la CLI) |

### Por qué no es fine-tuning
El modelo **no se reentrena** (no hay datos, tiempo ni infraestructura para eso en una hackathon, y no
haría falta). El sistema "aprende" de dos formas verificables:
1. **Dentro de una ejecución:** cada fallo de las pruebas vuelve al LLM como retroalimentación precisa.
2. **Entre ejecuciones:** cuando un intento mejora la similitud, el agente de Aprendizaje redacta una
   lección corta y generalizable (sin datos del cliente; pasa por el sanitizador) que se guarda en
   `output/lessons.json` y se inyecta en las siguientes migraciones del mismo par de lenguajes.

### Métrica de similitud (0..1)
`0,7 × casos equivalentes / total + 0,3 × campos iguales / campos comparados`.
El segundo término da crédito parcial y desempata versiones con los mismos casos aprobados. Un intento
que no compila o cuyo arnés falla vale 0. La comparación es la del comparador neutral (tolerancia cero).

### Criterios de parada
| Criterio | Valor por defecto | Variable |
|---|---|---|
| Equivalencia total (todos los casos) | — | — |
| Meseta: intentos seguidos sin mejorar | 2 | `AGENTCS_PATIENCE` |
| Máximo de intentos | 5 | `AGENTCS_MAX_ATTEMPTS` |
| Presupuesto de tokens | 600.000 | `AGENTCS_TOKEN_BUDGET` |

Siempre se devuelve la **mejor** versión (mayor similitud; en empate, la más temprana), no la última. Si
una versión vuelve a fallar un caso que la mejor versión ya pasaba, se marca como **REGRESIÓN** en la
retroalimentación.

## Alternativas consideradas
- **LangGraph:** útil para grafos con estado e interrupciones, pero el flujo es lineal con un bucle y el
  HITL ya lo resuelven la API y `RunState`. Una dependencia menos y control total del bucle.
- **Traducción en un solo paso sin verificación:** rápida, pero sin evidencia de equivalencia.
- **Fine-tuning:** ver arriba.

## Consecuencias
- (+) La equivalencia deja de ser una promesa: el motor la persigue y la mide.
- (+) Agnóstico: el bucle solo usa `TargetAdapter` (build, run_harness) y el oráculo.
- (+) Demo reproducible sin internet gracias a la caché y el modo replay.
- (−) El oráculo nivel C depende de la Spec aprobada: si la Spec está mal, el error se replica. Por eso
  el HITL es obligatorio y el reporte declara el nivel.
- (−) Ejecuta código generado por un LLM: mitigado con un sandbox por intento, sin red de secretos y con
  timeout. En producción, aislar además con contenedor sin red.
- Hoy el único pack de destino es `python`; Java, TypeScript y C# se agregan como packs sin tocar el motor.

## Uso
- API (modo real, `AGENTCS_MODE=real`): crear ejecución → aprobar reglas → aprobar especificación; el
  progreso por intento se ve en `GET /api/runs/{id}` (fase GENERACION) y `GET /api/runs/{id}/verification`.
- CLI: `python -m copilot.engine migrate --source legacy/INTERES.cbl --target python --auto-approve`
