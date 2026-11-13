---
name: golden-master-testing
description: Cómo demostrar equivalencia funcional entre código legacy (cualquier lenguaje) y código moderno (cualquier destino) con pruebas de caracterización (golden master) y diferenciales, usando casos JSON neutrales, runners de origen, harness de destino y niveles de oráculo A/B/C. Usar al construir la capa de verificación, el comparador o al depurar diferencias.
---

# Golden Master y pruebas diferenciales (agnóstico de lenguaje)

## Flujo
1. **Casos sintéticos** (`cases.json`, formato en skill `language-adapters`) derivados de la spec aprobada:
   - Un caso típico por regla; fronteras de cada condición (umbral exacto y ± unidad mínima).
   - Redondeo en la mitad exacta (,xx5) para cada campo decimal.
   - Extremos de los tipos (máximo del PIC/NUMBER, cero, plazo mínimo).
   - Inválidos: deben producir el mismo código/mensaje de error.
   - Nunca datos reales.
2. **Oráculo (expected.json)** — el copiloto elige el nivel más alto disponible y lo declara:
   | Nivel | Fuente | Ejemplos de runner |
   |---|---|---|
   | A | Ejecutar el legacy | COBOL: `cobc -x` + ejecutable · PL/SQL: Oracle Free + `python-oracledb` · C# Framework: `mcs` (Mono) · Java legacy: `javac`/`java` |
   | B | Pares E/S del cliente (sintéticos/anonimizados) | archivo provisto en la ingesta |
   | C | Implementación de referencia independiente desde la spec (Python, `Decimal`) + valores calculados a mano en bordes | cuando el legacy no puede ejecutarse (RPG, VB6, mainframe CICS) |
   El runner traduce `cases.json` al formato nativo del legacy (CSV/registro fijo/llamada a procedimiento) y su salida de vuelta a JSON neutral.
3. **Ejecutar el destino** con su harness (`run_harness`) → `actual.json`.
4. **Comparar** (Python, neutral):
   - Decimales como string → `Decimal`, normalizados a la escala del tipo neutral. **Tolerancia cero.**
   - Strings sin relleno final si el tipo origen era de ancho fijo.
   - Errores: mismo código y mensaje.
5. **Reporte** `equivalence-report.json/html`: nivel de oráculo, total, aprobados, diferencias (caso, campo, esperado, obtenido, regla ligada).
6. **Diferencias** → al agente Desarrollador solo los casos fallidos + regla ligada → reintento (máx. 3) → si persiste, revisión humana.

## Pruebas nativas del destino (además del diferencial)
JUnit / Jest / xUnit / pytest generadas desde los escenarios Gherkin, con aserciones exactas y datos
realistas; cobertura ≥ 80% líneas / 70% ramas; mutación opcional (PIT, Stryker, Stryker.NET, mutmut).

## En la demo
"Origen X → destino Y · oráculo nivel A · N casos · 100% equivalentes · 0 diferencias de redondeo ·
cobertura a%/b%", y un ejemplo de diferencia detectada y autocorregida en un intento previo.
