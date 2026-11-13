"""Ejecución aislada del código generado: carpeta propia por intento, sin shell, con timeout y
salida truncada. Nunca escribe ni ejecuta fuera del workdir."""
from __future__ import annotations

import os
import math
import shutil
import stat
import subprocess
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

DEFAULT_TIMEOUT = float(os.environ.get("AGENTCS_SANDBOX_TIMEOUT", "120"))
MAX_OUTPUT = 20_000
_SAFE_ENV = {
    "PATH", "LANG", "LANGUAGE", "LC_ALL", "TZ", "NODE_PATH", "JAVA_HOME", "DOTNET_ROOT",
    "SSL_CERT_FILE", "REQUESTS_CA_BUNDLE", "GIT_SSL_CAINFO", "SYSTEMROOT", "WINDIR", "PATHEXT",
}
_PROXY_ENV = {"HTTP_PROXY", "HTTPS_PROXY", "NO_PROXY", "ALL_PROXY"}


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


def _environment(cwd: Path, isolated: bool, extra: dict[str, str] | None) -> dict[str, str]:
    allowed = _SAFE_ENV if isolated else _SAFE_ENV | _PROXY_ENV
    env = {k: v for k, v in os.environ.items() if k.upper() in allowed or k.upper().startswith("LC_")}
    env.update({"PYTHONDONTWRITEBYTECODE": "1", "DOTNET_CLI_TELEMETRY_OPTOUT": "1", "DOTNET_NOLOGO": "1",
                "DOTNET_SKIP_FIRST_TIME_EXPERIENCE": "1", "NUGET_XMLDOC_MODE": "skip"})
    if isolated:
        private_tmp = cwd / ".agentcs-tmp"
        private_tmp.mkdir(parents=True, exist_ok=True)
        env.update({"HOME": str(cwd), "TMPDIR": str(private_tmp), "TMP": str(private_tmp),
                    "TEMP": str(private_tmp), "NO_PROXY": "*"})
    env.update(extra or {})
    return env


def _prepare_isolated_tree(cwd: Path) -> tuple[int, int] | None:
    """Entrega solo el workdir al usuario sin privilegios configurado en la imagen."""
    if os.name != "posix" or not hasattr(os, "geteuid") or os.geteuid() != 0:
        return None
    uid = int(os.environ.get("AGENTCS_SANDBOX_UID", "10001"))
    gid = int(os.environ.get("AGENTCS_SANDBOX_GID", "10001"))
    allowed_roots = (Path("/tmp"), Path(os.environ.get("AGENTCS_OUTPUT", "/app/output")).resolve())
    traversal_root = next((root for root in allowed_roots if cwd == root or root in cwd.parents), None)
    if traversal_root:
        parent = cwd.parent
        while parent != traversal_root and traversal_root in parent.parents:
            # Solo permite atravesar la ruta; no concede lectura ni escritura de los directorios padre.
            parent.chmod(parent.stat().st_mode | stat.S_IXOTH)
            parent = parent.parent
    for path in [cwd, *cwd.rglob("*")]:
        try:
            os.chown(path, uid, gid, follow_symlinks=False)
        except FileNotFoundError:
            continue
    return uid, gid


def _preexec(identity: tuple[int, int] | None, timeout: float, *, dotnet: bool = False):
    if os.name != "posix":
        return None

    def configure() -> None:
        try:
            import resource

            cpu = max(1, math.ceil(timeout) + 1)
            resource.setrlimit(resource.RLIMIT_CPU, (cpu, cpu))
            resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
            # CoreCLR aborta incluso en `dotnet --info` si se fijan RLIMIT_FSIZE o RLIMIT_AS.
            if not dotnet:
                resource.setrlimit(resource.RLIMIT_FSIZE, (512 * 1024 * 1024, 512 * 1024 * 1024))
            resource.setrlimit(resource.RLIMIT_NOFILE, (256, 256))
            resource.setrlimit(resource.RLIMIT_NPROC, (64, 64))
            if not dotnet and hasattr(resource, "RLIMIT_AS"):
                resource.setrlimit(resource.RLIMIT_AS, (8 * 1024**3, 8 * 1024**3))
        except (ImportError, OSError, ValueError):
            pass
        if identity and os.geteuid() == 0:
            uid, gid = identity
            os.setgroups([])
            os.setgid(gid)
            os.setuid(uid)

    return configure


def run_cmd(args: list[str], cwd: Path, timeout: float = DEFAULT_TIMEOUT,
            extra_env: dict[str, str] | None = None, stdin: str | None = None,
            isolated: bool = False) -> ProcResult:
    cwd = cwd.resolve()
    env = _environment(cwd, isolated, extra_env)
    identity = _prepare_isolated_tree(cwd) if isolated else None
    args = [resolve(args[0]) or args[0], *args[1:]]
    is_dotnet = Path(args[0]).name.lower() in {"dotnet", "dotnet.exe"}
    try:
        p = subprocess.run(args, cwd=cwd, capture_output=True, text=True, timeout=timeout,
                           env=env, shell=False, check=False, input=stdin,
                           stdin=None if stdin is not None else subprocess.DEVNULL,
                           start_new_session=isolated,
                           preexec_fn=_preexec(identity, timeout, dotnet=is_dotnet) if isolated else None)
        return ProcResult(p.returncode, p.stdout[-MAX_OUTPUT:], p.stderr[-MAX_OUTPUT:])
    except subprocess.TimeoutExpired as exc:
        out = exc.stdout.decode(errors="replace") if isinstance(exc.stdout, bytes) else (exc.stdout or "")
        return ProcResult(-1, out[-MAX_OUTPUT:], f"Tiempo agotado tras {timeout:.0f} s", timed_out=True)
    except FileNotFoundError as exc:
        return ProcResult(-1, "", f"Ejecutable no encontrado: {exc.filename}")
