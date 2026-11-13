# Semántica VB6 / VB.NET relevante para extraer reglas
- `Currency` (VB6) es punto fijo con 4 decimales; `Decimal` (VB.NET) es exacto. `Double`/`Single` son binarios.
- `Round()` usa redondeo BANCARIO (mitad al par); `CInt`/`CLng` también redondean al par; `Int()` va hacia -infinito y `Fix()` trunca hacia cero.
- `\` es división entera; `Mod` resto. `Variant` y conversiones implícitas pueden cambiar tipos: documenta.
- `On Error GoTo` / `Err.Raise` marcan errores de negocio o técnicos; distínguelos.
- Formularios (.frm), eventos `_Click`, ADO (`Recordset`) y `MsgBox` son infraestructura.
