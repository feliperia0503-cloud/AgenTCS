---
name: plsql-semantics
description: Cómo leer e interpretar PL/SQL legacy de Oracle (paquetes, procedimientos, funciones, cursores, excepciones, transacciones, triggers, tipos NUMBER/DATE) y separar reglas de negocio de acceso a datos. Usar al analizar, parsear o migrar código PL/SQL.
---

# Semántica PL/SQL

## Unidades
- `CREATE [OR REPLACE] PACKAGE` (especificación = API pública) y `PACKAGE BODY` (implementación).
- `PROCEDURE` (sin retorno, parámetros `IN`/`OUT`/`IN OUT`) y `FUNCTION ... RETURN tipo`.
- Bloques anónimos `DECLARE ... BEGIN ... EXCEPTION ... END;`.
- `TRIGGER`: lógica escondida que se dispara con INSERT/UPDATE/DELETE → **revisar siempre**, suele contener reglas de negocio.
- Tipos: `%TYPE`, `%ROWTYPE` (heredan el tipo de la columna → resolver contra el DDL si está disponible), `RECORD`, `TABLE OF` / `VARRAY` (colecciones).

## Control y datos
| PL/SQL | Significado | Moderno |
|---|---|---|
| `CURSOR c IS SELECT ...` + `FOR r IN c LOOP` | iterar un resultado | puerto de repositorio que devuelve lista/stream |
| `SELECT ... INTO v` | una fila; lanza `NO_DATA_FOUND` o `TOO_MANY_ROWS` | `Optional` / excepción de dominio |
| `BULK COLLECT`, `FORALL` | operaciones por lotes | repositorio batch |
| `EXCEPTION WHEN x THEN` | manejo de error | excepción de dominio / resultado de error |
| `RAISE_APPLICATION_ERROR(-20001, 'msg')` | error de negocio con código | excepción de dominio con el **mismo código y mensaje** (son parte del contrato) |
| `SQL%ROWCOUNT`, `SQL%FOUND` | filas afectadas | valor de retorno del repositorio |
| `COMMIT` / `ROLLBACK` / `SAVEPOINT` | transacción | límite transaccional en la capa de aplicación (no en el dominio) |
| `PRAGMA AUTONOMOUS_TRANSACTION` | transacción independiente (típico en logs) | infraestructura, documentar como supuesto |
| `EXECUTE IMMEDIATE` | SQL dinámico | riesgo alto: marcar confianza baja |
| `DBMS_OUTPUT`, `UTL_FILE` | salida/archivos | infraestructura |

## Semántica numérica y de fechas (trampas)
- `NUMBER(p,s)` redondea al asignar (mitad lejos de cero). `NUMBER` sin precisión = decimal de alta precisión.
- `ROUND(x, n)` → HALF_UP; `TRUNC(x, n)` → truncar (DOWN). `ROUND/TRUNC` sobre fechas truncan a día/mes.
- `DATE` **incluye hora**. `SYSDATE` depende del servidor → inyectar un reloj en el código moderno.
- `NULL` se propaga en aritmética (`x + NULL = NULL`); `'' IS NULL` es verdadero en Oracle.
- `NVL`, `NVL2`, `DECODE`, `CASE` → condicionales explícitos.
- `MONTHS_BETWEEN`, `ADD_MONTHS` (fin de mes), `LAST_DAY` → replicar exactamente; son fuente común de diferencias.

## Negocio vs. infraestructura
Negocio: cálculos, validaciones, `IF/CASE` sobre conceptos del dominio, `RAISE_APPLICATION_ERROR` de
reglas, lógica de triggers de validación. Infraestructura: SELECT/INSERT/UPDATE (pasan a puertos de
repositorio), commits, logging, archivos, colas (`DBMS_AQ`), jobs (`DBMS_SCHEDULER`).

## Ejecución (oráculo nivel A)
Contenedor Oracle Database Free (perfil `oracle` en docker-compose). El runner crea el esquema
sintético, carga datos de prueba, ejecuta el procedimiento por cada caso y captura salidas/errores.
