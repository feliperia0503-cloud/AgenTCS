# Semántica Delphi / Object Pascal relevante para extraer reglas
- `Currency` es decimal de punto fijo con 4 decimales (entero de 64 bits escalado): exacto para dinero.
- `Round()` usa redondeo BANCARIO (HALF_EVEN): Round(2.5) = 2. `Trunc()` trunca hacia cero. `SimpleRoundTo`/`RoundTo` tienen otra semántica (alejándose de cero en versiones recientes).
- `Double`/`Extended` son binarios: documenta reglas de dinero calculadas con ellos.
- `div` y `mod` son división entera; `/` siempre devuelve flotante.
- `raise Exception.Create('...')` o `EConvertError` señalan errores de negocio cuando validan datos.
- Formularios (.dfm), eventos `OnClick`, `TQuery`/`TTable`/`TDataSet` y `ShowMessage` son infraestructura; la lógica suele estar mezclada en los eventos: sepárala.
