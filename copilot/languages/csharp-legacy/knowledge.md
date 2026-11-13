# Semántica C# (.NET Framework) relevante para extraer reglas
- `decimal` es decimal exacto (28-29 dígitos); `double`/`float` son binarios.
- `Math.Round(x)` y `Math.Round(x, n)` usan redondeo BANCARIO (MidpointRounding.ToEven) por defecto. `Convert.ToInt32(double)` también. El cast `(int)x` trunca hacia cero.
- `decimal.ToString("F2")`/`"N2"` redondea la mitad alejándose de cero: es presentación, no cálculo.
- División entre enteros trunca. `checked`/`unchecked` cambian el desborde.
- Excepciones (`ArgumentException`, `ApplicationException` propias) suelen ser errores de negocio.
- ADO.NET (`SqlCommand`, `DataSet`), WebForms (`Page_Load`, `ViewState`), WCF y `ConfigurationManager` son infraestructura.
