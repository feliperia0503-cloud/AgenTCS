# samples/ — programas legacy sintéticos para pruebas de punta a punta

Tres programas pequeños con lógica de dinero, escritos desde cero para AgenTCS.
**No contienen datos reales, secretos ni código copiado de terceros.**

| Archivo | Lenguaje | Qué calcula | Trampas de equivalencia |
|---|---|---|---|
| `cobol/INTMORA.cbl` | COBOL (subprograma con LINKAGE) | Interés de mora de un saldo vencido | Tasa diaria **truncada** a 8 decimales antes de multiplicar; interés `ROUNDED`; tope de 360 días; códigos `EX`/`SM` con precedencia |
| `cobol/PAGOMIN.cbl` | COBOL (subprograma con LINKAGE) | Pago mínimo mensual de tarjeta | 5 % y 10 % **truncados**, interés `ROUNDED`; piso 50.00 y techo; estados `A/N/M/J` por días de atraso |
| `plsql/fn_comision_transferencia.sql` | PL/SQL (función) | Comisión de transferencia con IVA | `ROUND` vs `TRUNC`, tramos con límites inclusivos, canal desconocido = WEB, tope antes del IVA |

## Uso

Un programa por ejecución:

```bash
# dentro del contenedor
python -m copilot.engine migrate --source samples/cobol/INTMORA.cbl --target java --auto-approve
python -m copilot.engine migrate --source samples/cobol/PAGOMIN.cbl --target typescript --auto-approve
python -m copilot.engine migrate --source samples/plsql/fn_comision_transferencia.sql --target csharp --auto-approve
```

## Pares esperados (oráculo nivel B)

Cuando el legacy no se puede ejecutar en el contenedor (p. ej. PL/SQL sin Oracle), se pueden aportar pares
entrada/salida esperados. Se usan como casos de prueba y como oráculo; el reporte lo declara como nivel B.

```json
[{"id": "P01", "input": {"monto": "400000", "canal": "WEB", "segmento": "BASICO"}, "output": {"comision": "1904.00"}},
 {"id": "P02", "input": {"monto": "0", "canal": "APP", "segmento": "BASICO"}, "output": {"comision": "0"}}]
```

- Decimales como texto, nunca como número con punto. Cada par lleva `output` o `error` (`{"code", "message"}`).
- Los nombres de los campos deben ser los del contrato de la especificación extraída; si no cuadran, la API
  responde `PAIRS_MISMATCH` con la lista de entradas y salidas esperadas.
- API: `POST /api/runs/{id}/expected` (archivo .json) antes de aprobar la especificación.
  CLI: `--expected pares.json`.

## Casos de referencia

Calculados con `decimal` de Python siguiendo la semántica descrita en cada cabecera. Sirven para revisar
a mano lo que reporte el motor. **No reemplazan al oráculo**: cuando el oráculo de nivel A (GnuCOBOL /
Oracle Free) esté disponible, sus salidas son la verdad.

**INTMORA** (saldo, tasa anual, días → interés, total, código)

| Saldo | Tasa | Días | Interés | Total | Código |
|---|---|---|---|---|---|
| 1500000.00 | 0.2400 | 45 | 44999.55 | 1544999.55 | 00 |
| 999.99 | 0.2400 | 10 | 0.00 | 999.99 | EX |
| 2000.00 | 0.3000 | 0 | 0.00 | 2000.00 | SM |
| 123456.78 | 0.1875 | 400 | 23148.00 | 146604.78 | 00 |
| 5000.00 | 0.2400 | 1 | 3.33 | 5003.33 | 00 |

**PAGOMIN** (saldo, días de atraso → interés del mes, pago mínimo, estado)

| Saldo | Días | Interés | Pago mínimo | Estado |
|---|---|---|---|---|
| 0.00 | 0 | 0.00 | 0.00 | A |
| 800.00 | 0 | 17.20 | 69.70 | N |
| 10000.00 | 10 | 215.00 | 727.50 | N |
| 10000.00 | 45 | 215.00 | 1727.50 | M |
| 10000.00 | 120 | 215.00 | 10227.50 | J |
| 1234.57 | 31 | 26.54 | 224.21 | M |

**fn_comision_transferencia** (monto, canal, segmento → comisión con IVA)

| Monto | Canal | Segmento | Resultado |
|---|---|---|---|
| 400000 | APP | BASICO | 0 |
| 400000 | WEB | BASICO | 1904.00 |
| 1000000 | OFICINA | BASICO | 5950.00 |
| 2500001 | WEB | PREMIUM | 3718.75 |
| 20000000 | OFICINA | BASICO | 29750.00 |
| 1234567 | WEB | PREMIUM | 1836.42 |

## Procedencia y licencias

- El dominio (tarjetas, mora, comisiones) está inspirado en
  [aws-samples/aws-mainframe-modernization-carddemo](https://github.com/aws-samples/aws-mainframe-modernization-carddemo)
  (Apache-2.0) y en NSEvent/cobol-banking-system (no se encontró su licencia, por eso **no se tomó nada de su código**).
- Ningún archivo de esta carpeta reproduce código de esos repositorios; todo es original y sintético.
