"""Reportes del paquete: seguridad del código generado y resumen ejecutivo de una página por corrida.

Todo es determinista (no usa el LLM) y funciona sin internet:
- gitleaks (secretos) y Semgrep con reglas locales (`semgrep-rules.yml`: dinero en punto flotante,
  credenciales, eval). Si una herramienta no está instalada se declara "no disponible", nunca "0 hallazgos".
- Los reportes nunca incluyen el valor de un secreto: solo archivo, línea y regla.
"""
from __future__ import annotations

import json
import tempfile
from datetime import UTC, datetime
from pathlib import Path

from copilot.contracts import OracleLevel, Phase, RuleStatus, RunState
from copilot.engine.sandbox import resolve, run_cmd, write_files

RULES = Path(__file__).with_name("semgrep-rules.yml")
SCAN_TIMEOUT = 180
CACHE_FILE = "security.json"

ORACLE_TEXT = {
    OracleLevel.A: "A · el código legacy se ejecutó de verdad y su salida es la referencia",
    OracleLevel.B: "B · pares entrada/salida aportados por el usuario",
    OracleLevel.C: "C · implementación de referencia generada desde la especificación aprobada",
}


# ---------------------------------------------------------------- seguridad
def _gitleaks(folder: Path) -> dict:
    if resolve("gitleaks") is None:
        return {"available": False, "reason": "gitleaks no está instalado (viene en la imagen Docker)."}
    report = folder.parent / "gitleaks.json"
    result = run_cmd(["gitleaks", "detect", "--no-git", "--redact", "--exit-code", "0", "--no-banner",
                      "--source", str(folder), "--report-format", "json", "--report-path", str(report)],
                     folder.parent, timeout=SCAN_TIMEOUT)
    if not report.is_file():
        return {"available": False, "reason": f"gitleaks no produjo reporte: {result.stderr[-200:].strip()}"}
    raw = json.loads(report.read_text(encoding="utf-8") or "[]") or []
    items = [{"file": _rel(f.get("File", ""), folder), "line": f.get("StartLine"), "rule": f.get("RuleID")}
             for f in raw]
    return {"available": True, "findings": len(items), "items": items[:50]}


def _semgrep(folder: Path) -> dict:
    if resolve("semgrep") is None:
        return {"available": False, "reason": "semgrep no está instalado (viene en la imagen Docker)."}
    result = run_cmd(["semgrep", "scan", "--config", str(RULES), "--json", "--metrics=off",
                      "--disable-version-check", "--quiet", str(folder)], folder.parent, timeout=SCAN_TIMEOUT,
                     extra_env={"SEMGREP_ENABLE_VERSION_CHECK": "0", "SEMGREP_SEND_METRICS": "off"})
    try:
        raw = json.loads(result.stdout or "{}")
    except json.JSONDecodeError:
        return {"available": False, "reason": f"semgrep falló: {result.stderr[-200:].strip()}"}
    items = [{"file": _rel(r.get("path", ""), folder), "line": r.get("start", {}).get("line"),
              "rule": r.get("check_id", "").split(".")[-1], "severity": r.get("extra", {}).get("severity"),
              "message": r.get("extra", {}).get("message")} for r in raw.get("results", [])]
    errors = sum(i["severity"] == "ERROR" for i in items)
    return {"available": True, "findings": len(items), "errors": errors, "items": items[:100]}


def _rel(path: str, folder: Path) -> str:
    try:
        return str(Path(path).resolve().relative_to(folder.resolve()))
    except ValueError:
        return Path(path).name


def security_scan(files: dict[str, str]) -> dict:
    """Escanea el código generado (copia temporal) con gitleaks y Semgrep."""
    with tempfile.TemporaryDirectory(prefix="agentcs-scan-") as tmp:
        folder = Path(tmp) / "src"
        write_files(folder, files)
        leaks, sast = _gitleaks(folder), _semgrep(folder)
    critical = (leaks.get("findings", 0) if leaks["available"] else 0) + (sast.get("errors", 0) if sast["available"] else 0)
    complete = leaks["available"] and sast["available"]
    return {"scanned_at": datetime.now(UTC).isoformat(timespec="seconds"), "files": len(files),
            "gitleaks": leaks, "semgrep": sast, "critical_findings": critical if complete else None,
            "complete": complete}


def cached_security(run_dir: Path, state: RunState) -> dict:
    """Escaneo cacheado por corrida (se repite solo si cambió el intento ganador)."""
    path = run_dir / CACHE_FILE
    if path.is_file():
        cached = json.loads(path.read_text(encoding="utf-8"))
        if cached.get("attempt") == state.generation_attempts and cached.get("files") == len(state.generated_files):
            return cached
    report = security_scan(state.generated_files)
    report["attempt"] = state.generation_attempts
    run_dir.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report


def security_markdown(sec: dict) -> str:
    lines = ["# Seguridad del código generado", ""]
    for name, key in (("gitleaks (secretos)", "gitleaks"), ("Semgrep (reglas AgenTCS locales)", "semgrep")):
        r = sec[key]
        if not r["available"]:
            lines.append(f"- **{name}:** no disponible — {r['reason']}")
            continue
        lines.append(f"- **{name}:** {r['findings']} hallazgo(s)")
        lines += [f"  - `{i['file']}:{i['line']}` · {i['rule']}" + (f" · {i['message']}" if i.get("message") else "")
                  for i in r["items"]]
    verdict = ("Sin hallazgos críticos." if sec["critical_findings"] == 0 else
               f"{sec['critical_findings']} hallazgo(s) crítico(s): revisar antes de liberar." if sec["critical_findings"]
               else "Escaneo incompleto: no se puede afirmar que no haya hallazgos.")
    return "\n".join([*lines, "", f"**Resultado:** {verdict}", ""])


# ---------------------------------------------------------------- resumen ejecutivo
def _duration(state: RunState) -> str:
    starts = [p.started_at for p in state.phases.values() if p.started_at]
    ends = [p.finished_at for p in state.phases.values() if p.finished_at]
    if not starts or not ends:
        return "no disponible"
    seconds = int((max(ends) - min(starts)).total_seconds())
    return f"{seconds // 60} min {seconds % 60} s (incluye la espera de la revisión humana)"


def executive_summary(state: RunState, sec: dict) -> str:
    v, spec = state.verification, state.spec
    rules = spec.rules
    approved = sum(r.status == RuleStatus.APROBADA for r in rules)
    adjusted = sum(r.status == RuleStatus.AJUSTADA for r in rules)
    rejected = sum(r.status == RuleStatus.RECHAZADA for r in rules)
    tokens_in = sum(c.input_tokens for c in state.llm_calls)
    tokens_out = sum(c.output_tokens for c in state.llm_calls)
    replayed = sum(c.replayed for c in state.llm_calls)
    errors = sum(1 for o in state.expected if o.error)
    equivalent = v.total > 0 and v.passed == v.total
    gates = state.phases[Phase.VERIFICACION].gate_message
    crit = sec.get("critical_findings")
    verdict = ("**Apta para revisión técnica final**: equivalencia total contra el oráculo declarado."
               if equivalent and crit == 0 else
               "**No apta todavía**: " + ("hay casos no equivalentes. " if not equivalent else "")
               + ("hay hallazgos de seguridad críticos. " if crit else "")
               + ("el escaneo de seguridad no se completó. " if crit is None else ""))
    rows = [
        ("Programa", f"`{spec.program}`"),
        ("Origen → destino", f"{state.source_language} → {state.target_language}"
                             + (f" ({state.target_framework})" if state.target_framework else "")),
        ("Oráculo", ORACLE_TEXT.get(v.oracle_level, str(v.oracle_level))),
        ("Casos equivalentes", f"{v.passed} de {v.total} ({errors} de ellos validan errores de negocio)"),
        ("Intentos de generación", str(state.generation_attempts)),
        ("Reglas de negocio", f"{len(rules)} extraídas · {approved} aprobadas · {adjusted} ajustadas · {rejected} rechazadas"
                              f" · aprobó: {state.approved_by or '—'}"),
        ("Datos sensibles enmascarados", str(len(state.sanitization))),
        ("Hallazgos de seguridad críticos", "escaneo incompleto" if crit is None else str(crit)),
        ("Cobertura de pruebas", "no medida en esta versión"),
        ("Uso del modelo", f"{len(state.llm_calls)} llamadas · {tokens_in:,} tokens de entrada · {tokens_out:,} de salida"
                           + (f" · {replayed} desde caché" if replayed else "")),
        ("Duración", _duration(state)),
    ]
    table = "\n".join(f"| {k} | {val} |" for k, val in rows)
    return (f"# Resumen ejecutivo · {spec.program}\n\n{verdict}\n\n"
            f"| Indicador | Resultado |\n|---|---|\n{table}\n\n"
            f"**Verificación:** {gates}\n\n"
            "**Cómo leer el oráculo:** el nivel A es la evidencia más fuerte (el legacy real produjo los esperados); "
            "B y C se declaran cuando no se pudo ejecutar el legacy y nunca se presentan como equivalentes a A.\n\n"
            "Datos 100 % sintéticos. Detalle en `reports/equivalence-report.json`, `reports/security.md` y "
            "`docs/traceability-matrix.md`.\n")
