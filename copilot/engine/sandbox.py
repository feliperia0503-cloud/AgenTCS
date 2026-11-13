"""Ejecución aislada del código generado: carpeta propia por intento, sin shell, con timeout y
salida truncada. Nunca escribe ni ejecuta fuera del workdir."""
from __future__ import annotations

import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

DEFAULT_TIMEOUT = float(os.environ.get("AGENTCS_SANDBOX_TIMEOUT", "120"))
MAX_OUTPUT = 20_000


class SandboxError(Exception):
    pass


@dataclass
class ProcResult:
    returncode: int
    stdout: str
    stderr: str
    timed_out: bool = False

    @property
    def ok(self) -> bool:
        return self.returncode == 0 and not self.timed_out

    def tail(self, chars: int = 3000) -> str:
        text = (self.stderr or "") + ("\n" + self.stdout if self.stdout else "")
        return text[-chars:]


def safe_path(root: Path, relative: str) -> Path:
    """Valida rutas propuestas por el LLM: relativas, sin '..', sin unidad ni raíz."""
    rel = PurePosixPath(relative.replace("\\", "/"))
    if rel.is_absolute() or ".." in rel.parts or (rel.parts and ":" in rel.parts[0]) or not rel.parts:
        raise SandboxError(f"ruta no permitida en el proyecto generado: {relative!r}")
    target = (root / Path(*rel.parts)).resolve()
    if root.resolve() not in target.parents:
        raise SandboxError(f"ruta fuera del workdir: {relative!r}")
    return target


def write_files(root: Path, files: dict[str, str]) -> None:
    root.mkdir(parents=True, exist_ok=True)
    for rel, content in files.items():
        path = safe_path(root, rel)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")


def resolve(executable: str) -> str | None:
    """Ruta completa del ejecutable (en Windows resuelve también .cmd/.exe, p. ej. tsc.cmd)."""
    return shutil.which(executable)


def run_cmd(args: list[str], cwd: Path, timeout: float = DEFAULT_TIMEOUT,
            extra_env: dict[str, str] | None = None, stdin: str | None = None) -> ProcResult:
    env = {k: v for k, v in os.environ.items() if k not in {"ANTHROPIC_API_KEY", "ORACLE_PASSWORD"}}
    env.update({"PYTHONDONTWRITEBYTECODE": "1", "DOTNET_CLI_TELEMETRY_OPTOUT": "1", "DOTNET_NOLOGO": "1"})
    env.update(extra_env or {})
    args = [resolve(args[0]) or args[0], *args[1:]]
    try:
        p = subprocess.run(args, cwd=cwd, capture_output=True, text=True, timeout=timeout,
                           env=env, shell=False, check=False, input=stdin,
                           stdin=None if stdin is not None else subprocess.DEVNULL)
        return ProcResult(p.returncode, p.stdout[-MAX_OUTPUT:], p.stderr[-MAX_OUTPUT:])
    except subprocess.TimeoutExpired as exc:
        out = exc.stdout.decode(errors="replace") if isinstance(exc.stdout, bytes) else (exc.stdout or "")
        return ProcResult(-1, out[-MAX_OUTPUT:], f"Tiempo agotado tras {timeout:.0f} s", timed_out=True)
    except FileNotFoundError as exc:
        return ProcResult(-1, "", f"Ejecutable no encontrado: {exc.filename}")
