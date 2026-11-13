# Semántica PL/SQL relevante para extraer reglas
- Asignar a `NUMBER(p,s)` REDONDEA (mitad alejándose de cero), NO trunca: `v NUMBER(10,2) := 1.005` guarda 1.01. Para truncar el código usa `TRUNC(x, n)` explícito.
- `ROUND(x, n)` redondea la mitad alejándose de cero. `NUMBER` sin escala guarda hasta 38 dígitos.
- `NULL` se propaga en aritmética y en comparaciones (`x = NULL` nunca es verdadero): documenta los `NVL`/`COALESCE`.
- `DATE` incluye hora; `TRUNC(fecha)` la quita. `ADD_MONTHS` ajusta al fin de mes.
- `RAISE_APPLICATION_ERROR(-20xxx, 'msg')` y excepciones con nombre son errores de negocio; `NO_DATA_FOUND`/`TOO_MANY_ROWS` suelen ser reglas implícitas.
- `SELECT ... INTO`, cursores, `DML`, `COMMIT`, `DBMS_OUTPUT`, `UTL_FILE` son acceso a datos/infraestructura; la regla está en la condición o el cálculo, no en el SQL.
