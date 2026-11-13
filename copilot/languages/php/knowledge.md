# Semántica PHP relevante para extraer reglas
- Los números con decimales son `float` binario (IEEE 754): 0.1 + 0.2 != 0.3. El legacy hereda esos errores; documenta cuándo una regla depende de ellos.
- `round($x, n)` redondea la mitad ALEJÁNDOSE de cero (HALF_UP para positivos) y aplica pre-redondeo; `floor`/`ceil` devuelven float; `intval`/`(int)` truncan hacia cero.
- `number_format($x, n)` redondea HALF_UP y agrega separadores de miles (presentación, no cálculo).
- `bcadd`/`bcmul`/`bcdiv` (BCMath) operan en decimal exacto y TRUNCAN a la escala indicada.
- Comparaciones flexibles (`==`) convierten tipos ("10" == "1e1" es true); `===` es estricta. Documenta reglas que dependan de esto.
- Enteros desbordan a float silenciosamente.
- `$_GET`, `$_POST`, `$_SESSION`, `mysqli_*`, `PDO`, `echo` de HTML son infraestructura.
