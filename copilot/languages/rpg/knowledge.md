# Semántica RPG relevante para extraer reglas
- Las operaciones TRUNCAN por defecto; `EVAL(H)` o el indicador de half-adjust `(H)` redondean HALF_UP.
- Campos packed/zoned (`P`/`S` con decimales) son decimales exactos; la longitud y decimales definen el tipo neutral.
- Indicadores (`*IN01`–`*IN99`, `*INLR`) controlan flujo: tradúcelos a condiciones con nombre.
- `CHAIN`, `READ`, `SETLL`, `EXFMT` y SQL embebido son infraestructura; `BEGSR`/`EXSR` son subrutinas.
