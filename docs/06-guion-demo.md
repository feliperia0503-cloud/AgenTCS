# 06 · Guion de demo (10 minutos)

**Caso principal:** `samples/cobol/INTMORA.cbl`, código sintético sin datos reales.

**Destino preparado:** el destino que haya terminado en verde en la corrida real. No cambiarlo durante la presentación.

**Regla de relato:** decir únicamente métricas visibles en pantalla; no completar de memoria valores pendientes.

| Tiempo | Acción en pantalla | Mensaje del presentador | Evidencia que debe quedar visible |
|---|---|---|---|
| 0:00–0:35 | Abrir AgenTCS y presentar el reto | “Modernizar no es traducir sintaxis: es conservar el comportamiento del negocio y poder demostrarlo.” | Flujo completo de ocho fases y entorno local |
| 0:35–1:10 | **Entrada inválida:** intentar usar `http://127.0.0.1/repo.git` como origen | “El sistema rechaza un repositorio privado antes de clonarlo y explica cómo recuperarse.” | Error seguro, sin traza ni contenido sensible, con su **acción sugerida** |
| 1:10–2:00 | Limpiar el error, cargar `INTMORA.cbl`, mostrar detección de COBOL y seleccionar el destino preparado | “El mismo núcleo admite distintos orígenes y destinos mediante una especificación neutral y adaptadores.” | Archivo sintético identificado; configuración origen → destino |
| 2:00–2:45 | Iniciar la migración; mostrar sanitización, análisis y mapa de riesgo | “La seguridad y el análisis determinista ocurren antes de usar IA.” | Conteo de hallazgos sanitizados, unidades, dependencias y complejidad |
| 2:45–4:00 | Abrir reglas; seleccionar la regla de tasa diaria/redondeo; mostrar archivo y líneas; ajustar o comentar una regla de baja confianza y aprobar la especificación | “La lógica deja de ser una caja negra. Una persona valida la evidencia antes de generar.” | Condición, acción, confianza, líneas legacy y revisión HITL con autor |
| 4:00–5:15 | Mostrar generación y autocorrección | “Cada intento recibe las diferencias del anterior; no se oculta el fallo ni se conserva una versión peor.” | Línea de intentos: aprobados/total, similitud 0–1 y diferencias por campo, esperado, obtenido y regla |
| 5:15–6:10 | Mostrar legacy y código generado lado a lado; cambiar la regla seleccionada | “La trazabilidad conecta la regla, sus líneas legacy resaltadas y el código moderno generado.” | Rango resaltado y selector de archivo generado |
| 6:10–7:10 | **Caso representativo:** saldo `1500000.00`, tasa `0.2400`, `45` días | “Ambos ejecutables reciben la misma entrada. El resultado mostrado es el observado en esta corrida.” | Salida legacy, salida destino y estado de equivalencia del caso |
| 7:10–8:00 | **Caso borde:** saldo `123456.78`, tasa `0.1875`, `400` días; señalar el tope de 360 días | “El borde prueba una regla que una traducción superficial podría omitir.” | Mismo resultado en ambos lados y regla asociada al tope |
| 8:00–8:45 | Mostrar el indicador de oráculo y el resumen de calidad | “Nivel A significa que ejecutamos el legacy; B usa pares E/S provistos; C usa una referencia derivada. La pantalla declara cuál se usó.” | Nivel real, casos aprobados/total, similitud, cobertura y hallazgos |
| 8:45–9:15 | Descargar el paquete | “El resultado incluye código, pruebas y evidencia; no solo una respuesta del modelo.” | Paquete generado e informe de verificación |
| 9:15–10:00 | Cerrar con el informe ejecutivo y el segundo par ya preparado por el equipo | “El diferenciador es agnosticismo con equivalencia demostrable. El ahorro se calcula con la corrida y la línea base del banco.” | Duración real y ahorro solo si ya fueron medidos; de lo contrario, campos marcados como pendientes |

## Ensayo previo

- Cronometrar el recorrido completo y asignar una persona a presentar y otra a operar.
- Confirmar que el destino elegido, el runner legacy, Docker y la descarga del paquete funcionan sin intervención manual.
- Abrir previamente la UI, el informe ejecutivo y este guion; cerrar notificaciones y aplicaciones con datos personales.
- Verificar que `AGENTCS_MODEL` coincide con el modelo usado para grabar la caché de replay.
- Confirmar que `output/llm_cache/` está disponible mediante el volumen del repositorio.
- Grabar el video de contingencia después del último build verde y comprobar audio, resolución y duración.

## Plan de contingencia

1. **Modo en vivo.** Es el recorrido principal. Si una fase no avanza en 15 segundos o aparece un error no previsto, explicar el estado una sola vez y pasar a replay.
2. **Modo replay.** Usarlo solo después de ensayar el mismo archivo, destino y `AGENTCS_MODEL` y confirmar que no existe ningún `REPLAY_MISS`. Mantener la UI y todos los pasos del guion; indicar claramente que la inferencia está reproducida, mientras análisis, gates y presentación de evidencia siguen ejecutándose.
3. **Modo demo precomputado.** Si el replay no cubre el caso, ejecutar `$env:AGENTCS_MODE='demo'; docker compose up -d --force-recreate`. La UI mostrará “Modo demo precomputado” y permitirá recorrer HITL, verificación y descarga sin LLM; declarar este nivel de evidencia como C.
4. **Video.** Si Docker, el runner o la máquina fallan, reproducir el video completo sin cortes y usar la UI abierta únicamente para responder preguntas. El video debe incluir el caso representativo, el caso borde, la entrada inválida, el nivel de oráculo y la descarga.

La contingencia nunca cambia resultados ni oculta fallos: solo cambia el medio con el que se muestra una corrida ya verificada.
