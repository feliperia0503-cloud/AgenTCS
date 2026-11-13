# Semántica Java legacy relevante para extraer reglas
- `BigDecimal` es exacto; `setScale(n, BigDecimal.ROUND_HALF_UP)` (constantes int antiguas) equivale a RoundingMode.HALF_UP. `ROUND_DOWN` trunca.
- `new BigDecimal(double)` arrastra el error binario (new BigDecimal(0.1) != 0.1); `BigDecimal.valueOf` no.
- `Math.round` redondea la mitad hacia +infinito; el cast `(int)` trunca hacia cero; división entera trunca.
- `double` para dinero es un riesgo documentable. `equals` de BigDecimal compara también la escala (2.0 != 2.00); `compareTo` no.
- Excepciones checked propias suelen ser errores de negocio. JDBC, EJB (`SessionBean`), Servlets/JSP, JNDI y Struts son infraestructura.
