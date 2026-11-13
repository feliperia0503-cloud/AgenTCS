---
name: cobol-semantics
description: Cómo leer e interpretar programas COBOL legacy (divisiones, PIC, COMP-3, REDEFINES, OCCURS, PERFORM THRU, GO TO, EXEC SQL, ROUNDED, archivos). Usar al analizar, parsear o explicar código COBOL, o al separar lógica de negocio de infraestructura.
---

# Semántica COBOL para el copiloto AgenTCS

## Estructura
- `IDENTIFICATION DIVISION` → metadatos (PROGRAM-ID = nombre del componente).
- `ENVIRONMENT DIVISION` → `SELECT ... ASSIGN TO` = archivos externos → **infraestructura** (adaptador).
- `DATA DIVISION`
  - `FILE SECTION` (FD) → layout de registros de archivo → DTO de infraestructura.
  - `WORKING-STORAGE SECTION` → variables; niveles 01/05/10 = estructura anidada; `88` = condición con nombre (booleano de dominio, casi siempre **regla de negocio**).
  - `LINKAGE SECTION` → parámetros de entrada/salida del programa (contrato del caso de uso).
  - `COPY nombre` → incluir copybook; resolverlo antes de analizar.
- `PROCEDURE DIVISION` → lógica. Unidades: SECTION y PARAGRAPH (etiqueta terminada en punto, en columna 8).

## Formato de código fijo
Columnas 1–6 secuencia, 7 indicador (`*` o `/` comentario, `-` continuación, `D` debug), 8–11 área A
(divisiones, secciones, párrafos, niveles 01/77/FD), 12–72 área B, 73–80 se ignoran.
Al citar líneas, usar el número de línea físico del archivo.

## Control de flujo
| COBOL | Significado | Traducción moderna |
|---|---|---|
| `PERFORM P` | llamar párrafo y volver | llamada a método |
| `PERFORM A THRU B` | ejecuta todos los párrafos de A hasta B en orden físico | un método que llama en secuencia; cuidado con `GO TO` dentro del rango |
| `PERFORM ... UNTIL c` | while (evalúa antes, salvo `WITH TEST AFTER`) | `while` / `do-while` |
| `PERFORM ... VARYING i FROM a BY b UNTIL c` | for | `for` |
| `GO TO P` | salto incondicional | reestructurar: return temprano, bandera, o extraer método |
| `GO TO A B C DEPENDING ON X` | switch por índice | `switch` |
| `EVALUATE TRUE / WHEN` | switch/if-else | `switch` o Strategy/tabla de decisión |
| `STOP RUN` / `GOBACK` | terminar | return del caso de uso |
| `NEXT SENTENCE` / `CONTINUE` | no-op (NEXT SENTENCE salta al siguiente punto: ¡distinto!) | revisar con cuidado |

## Aritmética (crítico para equivalencia)
- `COMPUTE X = expr` **sin ROUNDED trunca** los decimales que no caben en X (hacia cero).
- `COMPUTE X ROUNDED = expr` redondea mitad alejándose de cero (HALF_UP en Java).
- Si el resultado no cabe en los enteros de X y no hay `ON SIZE ERROR`, **se pierden los dígitos altos** (comportamiento silencioso). Con `ON SIZE ERROR` se ejecuta esa rama y X no cambia.
- Campos sin signo (`PIC 9`, sin `S`) guardan el **valor absoluto**: un negativo pierde el signo.
- `ADD/SUBTRACT/MULTIPLY/DIVIDE ... GIVING` siguen las mismas reglas. `DIVIDE ... REMAINDER` existe.
- La precisión de intermedios depende del compilador: no adivinar; verificar contra GnuCOBOL (golden master).

## Datos
- `REDEFINES` = misma memoria vista con dos layouts (unión). Señalarlo como riesgo.
- `OCCURS n TIMES` = arreglo (índices desde 1). `OCCURS DEPENDING ON` = tamaño variable.
- `VALUE` = valor inicial. Constantes de negocio (tasas, topes) suelen estar aquí → reglas.
- `INITIALIZE`, `MOVE` (MOVE numérico→numérico alinea por el punto decimal y trunca).

## Negocio vs. infraestructura
**Negocio** (va al dominio): cálculos financieros, validaciones de valores, condiciones `88`, `EVALUATE`
sobre conceptos del dominio, constantes de tasas/topes, tablas de decisión.
**Infraestructura** (va a adaptadores): `OPEN/READ/WRITE/CLOSE`, `FILE STATUS`, `EXEC SQL`, `EXEC CICS`,
`ACCEPT/DISPLAY` de terminal, manejo de punteros, formateo de reportes, códigos de retorno técnicos.

## Salida esperada del análisis
Para cada párrafo: nombre, líneas inicio–fin, párrafos que invoca, variables que lee/escribe,
clasificación (negocio / infraestructura / mixto) y complejidad.
