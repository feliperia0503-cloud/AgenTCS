# 05 · Checklist contra la evaluación

Marcar solo cuando exista **evidencia verificable** (archivo, reporte o paso en la demo).

## 1. Pruebas de funcionalidad y equivalencia — 25%
- [ ] Golden master generado ejecutando el legacy real (oráculo nivel A) y nivel declarado en el reporte
- [ ] 100% de casos de equivalencia aprobados, 0 diferencias en redondeo
- [ ] Casos borde (tasa 0, plazo 1, monto máximo, redondeo .005) y caminos de error
- [ ] JUnit con aserciones explícitas y datos realistas (no esqueletos)
- [ ] Escenarios BDD (Gherkin) derivados del catálogo de reglas
- [ ] Cobertura JaCoCo ≥80% líneas / ≥70% ramas
- [ ] Suite ejecutada **en vivo** desde la UI

## 2. Precisión en extracción de reglas — 15%
- [ ] Catálogo con condición/acción y tablas de decisión
- [ ] 100% de reglas con líneas de origen
- [ ] Nivel de confianza + supuestos explícitos
- [ ] Separación negocio vs. infraestructura visible
- [ ] Aprobación humana registrada (quién, cuándo, comentario)

## 3. Arquitectura — 15%
- [ ] Diagrama de arquitectura del copiloto (capas + agentes)
- [ ] Modelo de dominio del código destino
- [ ] Contrato OpenAPI generado
- [ ] ADRs (copiloto y código destino)
- [ ] ArchUnit verde (dominio sin dependencias de infraestructura)

## 4. Calidad de código — 15%
- [ ] Compila sin errores
- [ ] 0 hallazgos bloqueantes/críticos (Sonar o PMD + Semgrep)
- [ ] Complejidad ≤10 por método
- [ ] `BigDecimal` con escala y `RoundingMode` explícitos
- [ ] Sin `GO TO` equivalentes; nombres de dominio

## 5. Seguridad e IA responsable — 10%
- [ ] Demo del enmascaramiento (secreto falso en el código legacy → oculto antes del LLM)
- [ ] Solo datos sintéticos
- [ ] Semgrep + dependencias + gitleaks: 0 críticos
- [ ] Log de prompts, respuestas y decisiones con trazabilidad

## 6. Entregables y documentación — 10%
- [ ] Repo estructurado + README
- [ ] `docker compose up` de un comando
- [ ] Matriz de trazabilidad
- [ ] Reportes de verificación
- [ ] Informe ejecutivo de 1 página

## 7. UX y demo — 10%
- [ ] Recorrido E2E ≤10 min
- [ ] Tablero de resultados
- [ ] Plan de contingencia (video + modo replay)

## 8. Funcional — 33,33%
- [ ] Flujo completo en vivo sin intervención manual fuera del prototipo
- [ ] 1 caso representativo + 1 caso borde correctos
- [ ] 1 entrada inválida manejada sin exponer datos

## 9. Interactivo y fácil de usar — 33,33%
- [ ] Flujo guiado (wizard) con estado por fase
- [ ] Vista comparativa legacy vs. moderno
- [ ] Errores con acción sugerida
- [ ] Un usuario externo completó la tarea sin ayuda (anotar quién y tiempo)

## 10. Innovador — 33,33%
- [ ] Comparación cuantificada: tiempo manual estimado vs. tiempo medido del copiloto
- [ ] Diferenciador explícito: agnóstico de lenguaje (Spec neutral + adaptadores) y equivalencia demostrada ejecutando el legacy real
- [ ] Al menos 2 pares origen→destino distintos funcionando con el mismo núcleo
- [ ] Caso de negocio del cliente (banco) con ahorro estimado
