# 06 · Guion de demo (≤ 10 minutos)

| Min | Qué se muestra | Mensaje de valor |
|---|---|---|
| 0:00–1:00 | El problema: un banco con COBOL, PL/SQL y .NET legacy sin documentación. Se carga el programa COBOL de amortización; el copiloto detecta el lenguaje y se elige el destino (Java) | "Un senior tardaría ~2 semanas en entender y migrar esto" |
| 1:00–2:00 | **Fase 1**: carga del archivo; el sistema detecta y enmascara una credencial falsa | Seguridad antes de tocar el LLM |
| 2:00–3:00 | **Fase 2**: grafo de dependencias, métricas, mapa de riesgo | Análisis determinista, no solo LLM |
| 3:00–4:30 | **Fases 3–4**: reglas con línea de origen y confianza; el ingeniero **ajusta** una regla de baja confianza y aprueba | Caja negra → conocimiento explícito, con control humano |
| 4:30–6:00 | **Fases 5–6**: arquitectura hexagonal, OpenAPI, código generado lado a lado con el legacy; un error de compilación se autocorrige | Código moderno con guardrails |
| 6:00–8:00 | **Fase 7**: se ejecuta el legacy original y el código nuevo con los mismos casos (oráculo nivel A) → 100% equivalencia, cobertura, 0 críticos. Mostrar una entrada inválida manejada | **Equivalencia demostrada, no prometida** |
| 8:00–8:40 | **Agnosticismo**: mismo flujo ya ejecutado para PL/SQL → TypeScript (resultado guardado), matriz de packs disponibles | "Un lenguaje nuevo = un adaptador, no un proyecto nuevo" |
| 8:40–9:00 | **Fase 8**: descarga del paquete + informe ejecutivo | Listo para el cliente |
| 9:00–10:00 | Tablero: minutos vs. semanas, ahorro estimado, próximos pasos (PL/SQL, RPG, Strangler Fig) | Innovación cuantificada |

## Contingencia
- Video completo pregrabado de la ejecución.
- Modo **replay**: respuestas del LLM cacheadas por hash de prompt para correr sin internet.
- Imágenes Docker ya descargadas en la máquina de la demo.
