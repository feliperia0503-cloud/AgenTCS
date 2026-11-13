"""CLI del motor de autocorrección.

    python -m copilot.engine migrate --source legacy/PAGOS.cbl --target python --auto-approve
    AGENTCS_LLM_REPLAY=1 python -m copilot.engine migrate ...   # sin internet, desde la caché

Usa la misma lógica que la API (CopilotService en modo real, de forma síncrona).
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from copilot.api.service import CopilotService, ServiceError
from copilot.contracts import Phase, PhaseStatus, RunMode, RunState

from .loop import LoopConfig
from .pipeline import Engine

AUTO_COMMENT = "Auto-aprobada desde la CLI (sin revisión humana)."


def _print_phases(state: RunState) -> None:
    for phase in Phase:
        rec = state.phases[phase]
        print(f"  [{rec.status.value:<16}] {phase.value}. {phase.name:<18} {rec.gate_message}")


def _print_attempts(state: RunState) -> None:
    reports = sorted([*state.verification_history, *([state.verification] if state.verification else [])],
                     key=lambda r: r.attempt)
    print("\n  Intento | Casos OK | Similitud")
    print("  --------+----------+----------")
    for r in reports:
        mark = "  ← mejor" if state.verification and r.attempt == state.verification.attempt else ""
        print(f"  {r.attempt:>7} | {r.passed:>3}/{r.total:<4} | {r.similarity or 0:>8.2f}{mark}")


def migrate(args: argparse.Namespace) -> int:
    config = LoopConfig(max_attempts=args.max_attempts, patience=args.patience)
    service = CopilotService(mode=RunMode.REAL, background=False,
                             engine_factory=lambda: Engine.from_env(config))
    payload = [(Path(p).name, Path(p).read_bytes()) for p in args.source]
    state = service.create_run(payload, args.target, args.source_language, args.domain, demo_mode=False,
                               framework=args.framework or "none", architecture=args.architecture)
    print(f"Ejecución {state.run_id} · {state.source_language} → {state.target_language}")
    if state.phases[Phase.EXTRACCION].status != PhaseStatus.APROBADA:
        _print_phases(state)
        return 1
    for rule in state.spec.rules:
        print(f"  {rule.id} [{rule.confidence:.2f}] {rule.name} · {rule.source.file}:{rule.source.lines[0]}-{rule.source.lines[1]}")
    if not args.auto_approve:
        print(f"\nRevisa y aprueba las reglas en la interfaz o la API (run {state.run_id}), o usa --auto-approve.")
        return 0
    if args.expected:
        info = service.upload_expected(state.run_id, Path(args.expected).name, Path(args.expected).read_bytes())
        print(f"  Pares E/S esperados: {info['pairs']} (oráculo nivel B si el legacy no se puede ejecutar)")
    for rule in state.spec.rules:
        state = service.decide_rule(state.run_id, rule.id, "approve", args.reviewer, AUTO_COMMENT)
    state = service.approve_spec(state.run_id, args.reviewer)
    _print_phases(state)
    _print_attempts(state)
    if state.phases[Phase.EMPAQUETADO].status == PhaseStatus.APROBADA:
        out = service.store.root / state.run_id / "package.zip"
        out.write_bytes(service.package(state.run_id))
        print(f"\nPaquete: {out}")
        return 0 if state.phases[Phase.VERIFICACION].status == PhaseStatus.APROBADA else 2
    return 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m copilot.engine", description="Motor de migración AgenTCS")
    sub = parser.add_subparsers(dest="command", required=True)
    m = sub.add_parser("migrate", help="Migra código legacy con el bucle de autocorrección")
    m.add_argument("--source", nargs="+", required=True, help="Archivos legacy")
    m.add_argument("--target", default="java", help="Destino: java, csharp, typescript o python")
    m.add_argument("--framework", default=None, help="Framework del catálogo (spring, aspnet, nestjs, fastapi, none…)")
    m.add_argument("--architecture", default="hexagonal", help="hexagonal, clean, modular, microservices, event-driven")
    m.add_argument("--source-language", default=None, help="Lenguaje origen (si no, se detecta por extensión)")
    m.add_argument("--domain", default=None)
    m.add_argument("--max-attempts", type=int, default=5)
    m.add_argument("--patience", type=int, default=2)
    m.add_argument("--auto-approve", action="store_true", help="Aprueba todas las reglas (solo para pruebas)")
    m.add_argument("--reviewer", default="cli")
    m.add_argument("--expected", default=None, help="Pares entrada/salida esperados (.json) para el oráculo nivel B")
    args = parser.parse_args(argv)
    try:
        return migrate(args)
    except ServiceError as exc:
        print(f"Error: {exc.message}\nAcción: {exc.action}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
