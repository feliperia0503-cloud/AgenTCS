"""Pack de DESTINO 'typescript' (TypeScript 5 sobre Node.js). Verificación con `tsc` y `node`; los
decimales usan decimal.js instalado globalmente (en Docker ya viene; local: npm i -g typescript decimal.js)."""
from __future__ import annotations

import functools
import json
from pathlib import Path

from copilot.contracts import BuildResult, Case, CaseOutput, NeutralType, PackInfo, PackRole, TypeKind
from copilot.engine.sandbox import resolve, run_cmd

from ..base import COMMON_RULES, BaseTarget, read_actual, to_build, write_cases

HARNESS = "agentcs_harness.ts"

CONVENTIONS = f"""Destino: TypeScript 5 (strict) sobre Node.js. Única dependencia permitida en el núcleo: decimal.js.
- Punto de entrada OBLIGATORIO: `src/app.ts` con
  `export function run(input: Record<string, unknown>): unknown`.
  En `input` los decimales llegan como string (usa `new Decimal(input.monto as string)`) y los enteros como
  number. Devuelve un objeto con los campos de salida, o un arreglo de objetos si output_is_list. Los decimales
  pueden devolverse como `Decimal` o como string con la escala exacta (`.toFixed(n)`).
- `import Decimal from 'decimal.js';` NUNCA uses `number` para dinero o tasas. Redondeo explícito:
  `.toDecimalPlaces(n, Decimal.ROUND_HALF_UP)` o `Decimal.ROUND_DOWN` para truncar.
- Carpetas: `src/domain`, `src/application`, `src/infrastructure` (adaptadores del framework, NO se compila).
- Sin `any` implícito. No uses APIs de Node en el dominio.
{COMMON_RULES}"""

HARNESS_SOURCE = r'''declare const require: any;
declare const process: any;
const fs = require('fs');
import { run } from './src/app';

function norm(v: any): any {
  if (v === null || v === undefined) return null;
  if (typeof v === 'object' && typeof v.toFixed === 'function' && v.constructor && v.constructor.name === 'Decimal') return v.toFixed();
  if (typeof v === 'number') return Number.isInteger(v) ? v : String(v);
  if (typeof v === 'bigint') return v.toString();
  if (Array.isArray(v)) return v.map(norm);
  if (typeof v === 'object') { const o: any = {}; for (const k of Object.keys(v)) o[k] = norm(v[k]); return o; }
  return v;
}

const cases = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));
const out = cases.map((c: any) => {
  try {
    const r: any = run(c.input);
    if (r && typeof r === 'object' && !Array.isArray(r) && r.error) {
      return { id: c.id, error: { code: String(r.error.code ?? ''), message: String(r.error.message ?? '') } };
    }
    return { id: c.id, output: norm(r) };
  } catch (e: any) {
    return { id: c.id, error: { code: 'EXEC_ERROR', message: String((e && e.message) || e) } };
  }
});
fs.writeFileSync(process.argv[3], JSON.stringify(out));
'''

_TYPES = {TypeKind.DECIMAL: "Decimal", TypeKind.INTEGER: "number", TypeKind.FLOAT: "number", TypeKind.STRING: "string",
          TypeKind.DATE: "string", TypeKind.DATETIME: "string", TypeKind.BOOLEAN: "boolean",
          TypeKind.ENUM: "string", TypeKind.RECORD: "object"}


@functools.lru_cache(maxsize=1)
def global_modules() -> str | None:
    if resolve("npm") is None:
        return None
    result = run_cmd(["npm", "root", "-g"], Path.cwd(), timeout=30)
    path = result.stdout.strip().splitlines()[-1] if result.ok and result.stdout.strip() else ""
    return path or None


def _tsconfig() -> dict:
    root = global_modules() or ""
    return {"compilerOptions": {
        "target": "ES2022", "module": "commonjs", "strict": True, "esModuleInterop": True, "skipLibCheck": True,
        "outDir": "dist", "rootDir": ".", "types": [],
        "paths": {"decimal.js": [str(Path(root) / "decimal.js" / "decimal")]}},
        "include": ["src/**/*.ts", HARNESS], "exclude": ["**/infrastructure/**", "node_modules", "dist"]}


class TypeScriptTarget(BaseTarget):
    info = PackInfo(id="typescript", name="TypeScript 5 (Node.js)", role=PackRole.TARGET, extensions=[".ts"])
    tools = ["node", "tsc"]

    def missing_tools(self) -> list[str]:
        missing = super().missing_tools()
        root = global_modules()
        if not root or not (Path(root) / "decimal.js").is_dir():
            missing.append("decimal.js (npm install -g decimal.js)")
        return missing

    def from_neutral_type(self, t: NeutralType) -> str:
        return f"{self.from_neutral_type(t.item)}[]" if t.kind == TypeKind.LIST and t.item else _TYPES[t.kind]

    def conventions(self) -> str:
        return CONVENTIONS

    def build(self, project: Path) -> BuildResult:
        if not (project / "src/app.ts").is_file():
            return BuildResult(ok=False, log="Falta src/app.ts con export function run(input).")
        (project / HARNESS).write_text(HARNESS_SOURCE, encoding="utf-8")
        (project / "tsconfig.json").write_text(json.dumps(_tsconfig(), indent=2), encoding="utf-8")
        return to_build(run_cmd(["tsc", "-p", "tsconfig.json"], project, isolated=True))

    def run_harness(self, project: Path, cases: list[Case]) -> list[CaseOutput]:
        write_cases(project, cases)
        env = {"NODE_PATH": global_modules() or ""}
        result = run_cmd(["node", "dist/agentcs_harness.js", "cases.json", "actual.json"], project,
                         extra_env=env, isolated=True)
        return read_actual(project, result)
