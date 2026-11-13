---
name: legacy-type-mapping
description: Mapeo exacto de tipos y semántica numérica de lenguajes legacy (COBOL, PL/SQL, RPG, C#/VB.NET/VB6, Java antiguo) a tipos neutrales y de ahí a destinos modernos (Java, TypeScript, C#, Python), incluyendo escala y modo de redondeo. Usar al generar o revisar código traducido, al depurar diferencias de redondeo o al construir type_map.yaml de un adaptador.
---

# Mapeo de tipos: origen → neutral → destino

Siempre pasar por el **tipo neutral** (skill `language-adapters`). El modo de redondeo es parte del tipo.

## Origen → neutral
| Origen | Declaración | Neutral | Semántica de asignación |
|---|---|---|---|
| COBOL | `PIC S9(n)V9(m)` (DISPLAY/COMP-3) | `decimal(n+m, m)` | sin `ROUNDED` trunca (DOWN); con `ROUNDED` HALF_UP; desborde sin `ON SIZE ERROR` pierde dígitos altos |
| COBOL | `PIC 9(n)` sin `S` | `decimal(n,0)` ≥ 0 | guarda valor absoluto (pierde signo) |
| COBOL | `COMP`/`BINARY` | `integer` | |
| COBOL | `COMP-1/COMP-2` | `float` | único caso con punto flotante |
| COBOL | `PIC X(n)` | `string(n)` | relleno con espacios |
| PL/SQL | `NUMBER(p,s)` | `decimal(p,s)` | redondea al asignar (HALF_UP) |
| PL/SQL | `NUMBER` | `decimal(38, ?)` | alta precisión, sin escala fija |
| PL/SQL | `PLS_INTEGER` | `integer(32)` | |
| PL/SQL | `VARCHAR2(n)` | `string(n)` | `''` = `NULL` |
| PL/SQL | `DATE` | `datetime` | incluye hora |
| RPG | `nP m` (packed), `nS m` (zoned) | `decimal(n,m)` | `EVAL(H)` = half-adjust (HALF_UP); sin (H) trunca |
| C# | `decimal` | `decimal(28, var)` | `Math.Round` por defecto HALF_EVEN |
| VB.NET | `CInt()` | `integer` | HALF_EVEN |
| VB6 | `Currency` | `decimal(19,4)` | |
| Java legacy | `double` para dinero | `float` ⚠ | decidir en HITL si se replica el error binario o se corrige |
| Java legacy | `BigDecimal.ROUND_HALF_UP` (constante int) | rounding HALF_UP | API obsoleta |

## Neutral → destino
| Neutral | Java | TypeScript | C# | Python |
|---|---|---|---|---|
| `decimal(p,s,R)` | `BigDecimal` + `setScale(s, RoundingMode.R)` | `Decimal` (decimal.js) + `toDecimalPlaces(s, Decimal.ROUND_R)` | `decimal` + `Math.Round(x, s, MidpointRounding.R)` (truncar: `Math.Truncate` escalado) | `Decimal.quantize(Decimal(10)**-s, rounding=ROUND_R)` |
| `integer` | `int`/`long` | `number` (≤ 2^53) / `bigint` | `int`/`long` | `int` |
| `string(n)` | `String` | `string` | `string` | `str` |
| `date` | `LocalDate` | ISO `string` o Temporal | `DateOnly` | `datetime.date` |
| `datetime` | `LocalDateTime` | ISO `string` | `DateTime` | `datetime` |

Equivalencias de redondeo: HALF_UP (mitad lejos de cero) = Java `HALF_UP` = decimal.js `ROUND_HALF_UP` = .NET `MidpointRounding.AwayFromZero` = Python `ROUND_HALF_UP`. Truncar = `DOWN` / `ROUND_DOWN` / `ToZero` / `ROUND_DOWN`.

## Intermedios
- Calcular con precisión amplia (34 dígitos: Java `MathContext.DECIMAL128`, decimal.js `precision: 34`, Python `localcontext(prec=34)`; C# `decimal` tiene 28–29) y redondear/truncar **solo al asignar**, como hace el legacy.
- Potencias `(1+i)^n` con `n` entero: usar la potencia del tipo decimal, no `Math.pow`.
- Ante diferencias en el golden master: revisar primero precisión de intermedios, orden de operaciones y modo de redondeo.
