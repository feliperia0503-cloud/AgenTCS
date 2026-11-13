# Semántica PL/SQL relevante para extraer reglas
- Asignar a `NUMBER(p,s)` REDONDEA (mitad alejándose de cero), NO trunca: `v NUMBER(10,2) := 1.005` guarda 1.01. Para truncar el código usa `TRUNC(x, n)` explícito.
- `ROUND(x, n)` redondea la mitad alejándose de cero. `NUMBER` sin escala guarda hasta 38 dígitos.
- `NULL` se propaga en aritmética y en comparaciones (`x = NULL` nunca es verdadero): documenta los `NVL`/`COALESCE`.
- `DATE` incluye hora; `TRUNC(fecha)` la quita. `ADD_MONTHS` ajusta al fin de mes.
- `RAISE_APPLICATION_ERROR(-20xxx, 'msg')` y excepciones con nombre son errores de negocio; `NO_DATA_FOUND`/`TOO_MANY_ROWS` suelen ser reglas implícitas.
- `SELECT ... INTO`, cursores, `DML`, `COMMIT`, `DBMS_OUTPUT`, `UTL_FILE` son acceso a datos/infraestructura; la regla está en la condición o el cálculo, no en el SQL.
- `PRAGMA AUTONOMOUS_TRANSACTION` (típico en bitácoras) confirma su propio COMMIT aparte: es infraestructura, no regla.
- `SELECT ... FOR UPDATE`, `SAVEPOINT`/`ROLLBACK TO` y `COMMIT` son control transaccional; la regla de negocio es
  el efecto: p. ej. "un error en un registro no detiene el lote" sí es comportamiento a preservar.
- `%TYPE` / `%ROWTYPE` toman el tipo de la columna: el tipo neutral sale del DDL de esa columna.
- Parámetros con `DEFAULT TRUNC(SYSDATE)`: el valor por omisión depende del reloj; en las pruebas se pasa explícito.
- Constantes booleanas en FALSE (`c_modo_debug`) vuelven inalcanzables sus ramas: código muerto.
- Código después de `RETURN`, rutinas privadas que nadie invoca y bloques comentados (`/* ... */` con lógica vieja)
  son código muerto: repórtalos, no los migres.
- Condiciones ya descartadas antes (p. ej. `IF x < 0` después de rechazar `x <= 0`) son ramas inalcanzables.
- El orden de evaluación de las validaciones importa: la primera que falla determina el motivo de rechazo.
