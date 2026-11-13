---
name: language-adapters
description: Cómo agregar o modificar un adaptador de lenguaje (pack de origen legacy o de destino moderno) en el copiloto AgenTCS, con la interfaz común, tipos neutrales de la especificación y checklist. Usar al soportar un lenguaje nuevo (COBOL, PL/SQL, RPG, VB6, .NET, Java, TypeScript, C#, Python, Go…) o al tocar copilot/languages/.
---

# Adaptadores de lenguaje

El núcleo nunca conoce un lenguaje concreto. Todo lo específico vive en `copilot/languages/<id>/`.
Origen → **Spec neutral** → Destino. Ver `docs/02-arquitectura.md` y ADR-003.

## Estructura de un pack
```
copilot/languages/<id>/
├── pack.yaml            # id, nombre, rol: source|target|both, extensiones, versión
├── adapter.py           # implementa SourceAdapter y/o TargetAdapter
├── type_map.yaml        # tipos del lenguaje <-> tipos neutrales
├── knowledge.md         # semántica y trampas (enlaza a la skill <lenguaje>-semantics)
├── templates/           # (destino) proyecto base y plantillas Jinja2
└── tests/               # fixtures mínimos: un programa pequeño + resultado esperado
```

## Interfaces (Python, en `copilot/contracts/adapters.py`)
```python
class SourceAdapter(Protocol):
    id: str
    def detect(self, files: list[SourceFile]) -> float: ...            # 0..1
    def parse(self, files: list[SourceFile]) -> AnalysisResult: ...     # unidades, llamadas, variables, líneas
    def classify(self, analysis: AnalysisResult) -> AnalysisResult: ...  # negocio vs infraestructura
    def to_neutral_type(self, decl: str) -> NeutralType: ...
    runner: LegacyRunner | None                                          # None => oráculo nivel B o C

class LegacyRunner(Protocol):
    def build(self, workdir: Path) -> BuildResult: ...
    def run(self, cases: list[Case]) -> list[CaseOutput]: ...

class TargetAdapter(Protocol):
    id: str
    def scaffold(self, spec: Spec, out: Path) -> None: ...
    def from_neutral_type(self, t: NeutralType) -> str: ...
    def build(self, project: Path) -> BuildResult: ...
    def test(self, project: Path) -> TestResult: ...                      # incluye cobertura
    def run_harness(self, project: Path, cases: Path) -> list[CaseOutput]: ...
    def quality(self, project: Path) -> QualityReport: ...
```

## Tipos neutrales
| Neutral | Ejemplo origen | Java | TypeScript | C# | Python |
|---|---|---|---|---|---|
| `decimal(p,s,rounding)` | `PIC S9(7)V99`, `NUMBER(9,2)`, `decimal` | `BigDecimal` | `Decimal` (decimal.js) | `decimal` | `Decimal` |
| `integer(bits)` | `PIC S9(9) COMP`, `PLS_INTEGER`, `int` | `int`/`long` | `number`/`bigint` | `int`/`long` | `int` |
| `string(max)` | `PIC X(30)`, `VARCHAR2(30)` | `String` | `string` | `string` | `str` |
| `date` / `datetime` | `PIC 9(8)` AAAAMMDD, `DATE` | `LocalDate`/`LocalDateTime` | `Temporal`/ISO string | `DateOnly`/`DateTime` | `date`/`datetime` |
| `boolean` | nivel 88, `BOOLEAN`, `bool` | `boolean` | `boolean` | `bool` | `bool` |
| `enum`, `list<T>`, `record` | `OCCURS`, colecciones, registros | `enum`/`List`/`record` | union/array/interface | `enum`/`List`/`record` | `Enum`/`list`/`dataclass` |

**Nunca** punto flotante para `decimal`. En TypeScript usar `decimal.js` (o `big.js`), jamás `number`.
El modo de redondeo viaja en el tipo: `HALF_UP`, `HALF_EVEN`, `DOWN` (truncar), `UP`, `FLOOR`, `CEILING`.

## Formato de casos (neutral, compartido por runners y harness)
`cases.json`: `[{"id": "C001", "input": {...}, "tags": ["borde","BR-003"]}]`
`expected.json` / `actual.json`: `[{"id": "C001", "output": {...}, "error": null}]`
Decimales como **string** (`"1234.50"`) para no perder precisión entre lenguajes.

## Checklist para un pack nuevo
- [ ] `detect()` reconoce los fixtures y no da falsos positivos con otros packs.
- [ ] `parse()` devuelve líneas exactas por unidad (se verifican contra el archivo).
- [ ] `type_map.yaml` cubre todos los tipos numéricos con escala y redondeo.
- [ ] Origen: runner funcional **o** declaración explícita de nivel de oráculo B/C.
- [ ] Destino: el proyecto generado compila, pasa sus pruebas y el harness produce `actual.json`.
- [ ] Prueba de contrato en `tests/` corre en CI del repo.
- [ ] Runtime agregado al `Dockerfile` (o a un servicio con `profile` en compose si es pesado).
