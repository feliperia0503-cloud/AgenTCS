"""Ingesta universal del código legacy: archivos sueltos, comprimidos (.zip, .tar, .tar.gz, .tgz) o un
repositorio Git por HTTPS (GitHub, Bitbucket, GitLab, Azure DevOps...). Cualquier lenguaje.

Seguridad: sin rutas absolutas ni '..' (zip slip), límites de tamaño y cantidad, se descartan binarios y
carpetas de dependencias, clon superficial sin credenciales. El contenido se sanitiza después.
Anti-SSRF: el host del repositorio debe resolver solo a IPs públicas (nada de localhost, redes privadas,
enlace local 169.254.x.x ni metadatos de nube); git se conecta a la IP ya validada y no sigue redirecciones.
"""
from __future__ import annotations

import io
import ipaddress
import re
import socket
import shutil
import tarfile
import tempfile
import zipfile
from collections import Counter
from pathlib import Path, PurePosixPath

from copilot.engine.sandbox import run_cmd

# extensión -> (id de lenguaje, nombre visible, es_logica)  es_logica=False: UI, formularios, config
EXT_LANGUAGE: dict[str, tuple[str, str, bool]] = {
    ".cbl": ("cobol", "COBOL", True), ".cob": ("cobol", "COBOL", True), ".cpy": ("cobol", "COBOL (copybook)", True),
    ".jcl": ("jcl", "JCL", False), ".pli": ("pli", "PL/I", True), ".pl1": ("pli", "PL/I", True),
    ".pks": ("plsql", "PL/SQL", True), ".pkb": ("plsql", "PL/SQL", True), ".prc": ("plsql", "PL/SQL", True),
    ".fnc": ("plsql", "PL/SQL", True), ".trg": ("plsql", "PL/SQL", True), ".plsql": ("plsql", "PL/SQL", True),
    ".sql": ("sql", "SQL / PL/SQL", True), ".pc": ("proc", "Pro*C", True),
    ".pas": ("delphi", "Delphi / Pascal", True), ".dpr": ("delphi", "Delphi / Pascal", True),
    ".dpk": ("delphi", "Delphi / Pascal", False), ".inc": ("delphi", "Delphi / Pascal", True),
    ".dfm": ("delphi", "Delphi (formulario)", False), ".lpr": ("delphi", "Delphi / Pascal", True),
    ".rpg": ("rpg", "RPG", True), ".rpgle": ("rpg", "RPG", True), ".sqlrpgle": ("rpg", "RPG", True),
    ".clp": ("cl", "CL (IBM i)", False), ".cs": ("csharp-legacy", "C#", True), ".vb": ("vbnet", "VB.NET", True),
    ".bas": ("vb6", "VB6", True), ".frm": ("vb6", "VB6 (formulario)", False), ".cls": ("vb6", "VB6", True),
    ".java": ("java-legacy", "Java", True), ".jsp": ("jsp", "JSP", False), ".abap": ("abap", "ABAP", True),
    ".prg": ("xbase", "Clipper / xBase", True), ".4gl": ("informix4gl", "Informix 4GL", True),
    ".f": ("fortran", "Fortran", True), ".for": ("fortran", "Fortran", True), ".f90": ("fortran", "Fortran", True),
    ".c": ("c", "C", True), ".cpp": ("cpp", "C++", True), ".h": ("c", "C/C++ (cabecera)", False),
    ".asm": ("asm", "Assembler", True), ".mac": ("asm", "Assembler", True), ".nsp": ("natural", "Natural", True),
    ".py": ("python", "Python", True), ".js": ("javascript", "JavaScript", True), ".php": ("php", "PHP", True),
    ".rb": ("ruby", "Ruby", True), ".pl": ("perl", "Perl", True), ".ps1": ("powershell", "PowerShell", False),
    ".sh": ("shell", "Shell", False), ".ksh": ("shell", "Shell", False), ".bat": ("batch", "Batch", False),
    ".xml": ("xml", "XML", False), ".config": ("config", "Configuración", False), ".properties": ("config", "Configuración", False),
}
SKIP_DIRS = {".git", ".svn", "node_modules", "target", "bin", "obj", "dist", "build", "out", ".idea", ".vscode",
             "__pycache__", "packages", "vendor", "__history", "__recovery"}
MAX_FILES = 2000
MAX_FILE_BYTES = 2 * 1024 * 1024
MAX_TOTAL_BYTES = 60 * 1024 * 1024
ARCHIVE_SUFFIXES = (".zip", ".tar", ".tar.gz", ".tgz")
CLONE_TIMEOUT = 180
_URL = re.compile(r"^https://[A-Za-z0-9.-]+(?::\d+)?/[\w./~%+-]+?/?$")
_BRANCH = re.compile(r"^[\w./-]{1,100}$")
_BLOCKED_SUFFIXES = (".localhost", ".local", ".internal", ".localdomain", ".home.arpa")


class SourceError(Exception):
    def __init__(self, status: int, code: str, message: str, action: str):
        super().__init__(message)
        self.status, self.code, self.message, self.action = status, code, message, action


def is_archive(name: str) -> bool:
    return name.lower().endswith(ARCHIVE_SUFFIXES)


def _clean_rel(name: str) -> str | None:
    rel = PurePosixPath(name.replace("\\", "/"))
    parts = [p for p in rel.parts if p not in ("", ".")]
    if not parts or rel.is_absolute() or ".." in parts or ":" in parts[0]:
        return None
    if any(p in SKIP_DIRS or p.startswith("__MACOSX") for p in parts[:-1]):
        return None
    return "/".join(parts)


def _decode(data: bytes) -> str | None:
    if b"\x00" in data[:8192]:
        return None   # binario
    for enc in ("utf-8", "cp1252", "latin-1"):
        try:
            return data.decode(enc)
        except UnicodeDecodeError:
            continue
    return None


def _accept(path: str) -> bool:
    return Path(path).suffix.lower() in EXT_LANGUAGE


def expand_archive(name: str, data: bytes) -> list[tuple[str, str]]:
    """Extrae en memoria un .zip/.tar/.tgz y devuelve (ruta, texto) de los archivos de código."""
    entries: list[tuple[str, bytes]] = []
    total = 0
    try:
        if name.lower().endswith(".zip"):
            with zipfile.ZipFile(io.BytesIO(data)) as z:
                for info in z.infolist():
                    if info.is_dir() or info.file_size > MAX_FILE_BYTES:
                        continue
                    total += info.file_size
                    entries.append((info.filename, z.read(info)))
                    if total > MAX_TOTAL_BYTES or len(entries) > MAX_FILES * 2:
                        break
        else:
            with tarfile.open(fileobj=io.BytesIO(data), mode="r:*") as t:
                for member in t:
                    if not member.isfile() or member.size > MAX_FILE_BYTES:
                        continue
                    total += member.size
                    f = t.extractfile(member)
                    if f is not None:
                        entries.append((member.name, f.read()))
                    if total > MAX_TOTAL_BYTES or len(entries) > MAX_FILES * 2:
                        break
    except (zipfile.BadZipFile, tarfile.TarError, EOFError) as exc:
        raise SourceError(422, "ARCHIVE_INVALID", f"No se pudo leer {Path(name).name}.",
                          "Verifica que el archivo no esté dañado y sea .zip, .tar, .tar.gz o .tgz (no .rar ni .7z).") from exc
    if total > MAX_TOTAL_BYTES:
        raise SourceError(413, "ARCHIVE_TOO_LARGE", "El comprimido supera 60 MB descomprimido.",
                          "Comprime solo las carpetas con el código a migrar.")
    out = []
    for raw_name, content in entries:
        rel = _clean_rel(raw_name)
        if rel and _accept(rel):
            text = _decode(content)
            if text is not None:
                out.append((rel, text))
    return out[:MAX_FILES]


def resolve_host(host: str, port: int) -> list[str]:
    """Resuelve el host a sus IPs. Separado para poder simularlo en las pruebas."""
    infos = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
    return sorted({info[4][0] for info in infos})


def _is_public(ip_text: str) -> bool:
    ip = ipaddress.ip_address(ip_text.split("%", 1)[0])
    if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped:
        ip = ip.ipv4_mapped
    return ip.is_global and not ip.is_multicast


def _blocked(message: str) -> SourceError:
    return SourceError(422, "REPO_HOST_BLOCKED", message,
                       "Usa un repositorio público en internet (GitHub, Bitbucket, GitLab, Azure DevOps…) "
                       "o descarga el código como .zip y súbelo.")


def check_public_host(host: str, port: int) -> str:
    """Valida que el host sea público y devuelve la IP con la que se debe conectar git."""
    host = host.lower().rstrip(".")
    if host == "localhost" or host.endswith(_BLOCKED_SUFFIXES):
        raise _blocked("La URL apunta a un equipo local o de red interna.")
    try:
        literal = ipaddress.ip_address(host)
    except ValueError:
        literal = None
    if literal is None and (host.rsplit(".", 1)[-1].isdigit() or "." not in host):
        # 127.1, 2130706433, 0x7f.1 o nombres sin dominio: formas ambiguas que git interpretaría como IP o red local
        raise _blocked("La URL usa una dirección ambigua o sin dominio.")
    if literal is not None:
        ips = [str(literal)]
    else:
        try:
            ips = resolve_host(host, port)
        except (OSError, UnicodeError):
            raise SourceError(422, "REPO_HOST_UNRESOLVED", f"No se pudo resolver {host}.",
                              "Revisa la URL y la conexión a internet, o sube el código como .zip.") from None
    if not ips or not all(_is_public(ip) for ip in ips):
        raise _blocked("La URL apunta a una dirección privada, local o reservada.")
    return ips[0]


def clone_repo(url: str, branch: str | None) -> list[tuple[str, str]]:
    """Clon superficial (solo lectura) de un repositorio HTTPS público y lectura de su código."""
    url, branch = (url or "").strip(), (branch or "").strip()
    authority = url.split("//", 1)[1].split("/", 1)[0] if "//" in url else ""
    if not _URL.match(url) or "@" in authority:
        raise SourceError(422, "REPO_URL_INVALID", "La URL del repositorio no es válida.",
                          "Usa una URL https sin usuario ni token (GitHub, Bitbucket, GitLab, Azure DevOps…) o sube un .zip.")
    if branch and not _BRANCH.match(branch):
        raise SourceError(422, "BRANCH_INVALID", "El nombre de la rama no es válido.", "Revisa la rama (p. ej. main).")
    host, _, port_text = authority.partition(":")
    port = int(port_text) if port_text else 443
    if not 0 < port < 65536:
        raise SourceError(422, "REPO_URL_INVALID", "La URL del repositorio no es válida.", "Revisa el puerto de la URL.")
    ip = check_public_host(host, port)
    pinned = f"[{ip}]" if ":" in ip else ip
    tmp = Path(tempfile.mkdtemp(prefix="agentcs-repo-"))
    try:
        # curloptResolve fija la IP validada (evita DNS rebinding); sin redirecciones hacia otros hosts.
        args = ["git", "-c", "credential.helper=", "-c", "core.askPass=", "-c", "http.followRedirects=false",
                "-c", f"http.curloptResolve={host.lower()}:{port}:{pinned}", "-c", "protocol.allow=never",
                "-c", "protocol.https.allow=always", "clone", "--depth", "1", "--single-branch", "--no-tags",
                *(["--branch", branch] if branch else []), url, str(tmp / "repo")]
        result = run_cmd(args, tmp, timeout=CLONE_TIMEOUT)
        if not result.ok:
            raise SourceError(422, "REPO_CLONE_FAILED", "No se pudo clonar el repositorio.",
                              "Verifica que sea público, que la rama exista y que haya conexión; o descarga el código como .zip y súbelo.")
        return read_dir(tmp / "repo")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def read_dir(root: Path) -> list[tuple[str, str]]:
    out = []
    for path in sorted(root.rglob("*")):
        if len(out) >= MAX_FILES:
            break
        rel = _clean_rel(path.relative_to(root).as_posix())
        if not rel or not path.is_file() or not _accept(rel) or path.stat().st_size > MAX_FILE_BYTES:
            continue
        text = _decode(path.read_bytes())
        if text is not None:
            out.append((rel, text))
    return out


_PLSQL_HINT = re.compile(
    r"\bCREATE\s+(?:OR\s+REPLACE\s+)?(?:EDITIONABLE\s+)?(?:FUNCTION|PROCEDURE|PACKAGE|TRIGGER|TYPE\s+BODY)\b"
    r"|^\s*DECLARE\b|\bEXCEPTION\s+WHEN\b|\bRETURN\s+\w+\s+(?:IS|AS)\b", re.IGNORECASE | re.MULTILINE)


def language_of(path: str, text: str | None = None) -> tuple[str, str, bool]:
    """Lenguaje por extensión; un .sql con bloques procedurales se reconoce como PL/SQL por su contenido."""
    found = EXT_LANGUAGE.get(Path(path).suffix.lower(), ("desconocido", "Otro", True))
    if found[0] == "sql" and text and _PLSQL_HINT.search(text):
        return EXT_LANGUAGE[".plsql"]
    return found


def dominant_language(files: list[tuple[str, str]]) -> str:
    """Lenguaje con más líneas de lógica (ignora formularios, configuración y scripts)."""
    weights: Counter[str] = Counter()
    for path, text in files:
        lang, _, logic = language_of(path, text)
        if logic:
            weights[lang] += text.count("\n") + 1
    return weights.most_common(1)[0][0] if weights else "desconocido"


def inventory(files: list[tuple[str, str]]) -> dict:
    names: Counter[str] = Counter(language_of(p, t)[1] for p, t in files)
    return {"files": len(files), "lines": sum(t.count("\n") + 1 for _, t in files),
            "languages": [{"name": n, "files": c} for n, c in names.most_common()]}


def collect(uploads: list[tuple[str, bytes]], repo_url: str | None, branch: str | None) -> list[tuple[str, str]]:
    """Archivos sueltos y comprimidos subidos; si no hay, el repositorio. Devuelve (ruta, texto)."""
    out: list[tuple[str, str]] = []
    for name, data in uploads:
        if is_archive(name):
            out += expand_archive(name, data)
            continue
        if len(data) > MAX_FILE_BYTES:
            raise SourceError(413, "FILE_TOO_LARGE", f"{Path(name).name} supera 2 MB.",
                              "Sube solo el código a migrar o comprímelo en un .zip.")
        text = _decode(data)
        if text is None:
            raise SourceError(422, "BINARY_FILE", f"{Path(name).name} parece un archivo binario.",
                              "Sube código fuente en texto o un comprimido .zip/.tar.gz con el código.")
        out.append((Path(name.replace("\\", "/")).name, text))
    if not out and (repo_url or "").strip():
        out = clone_repo(repo_url or "", branch)
    if not out:
        raise SourceError(422, "NO_CODE_FOUND", "No se encontró código fuente para analizar.",
                          "Sube archivos o un .zip con código legacy (COBOL, PL/SQL, Delphi, RPG, VB6, C#…) o indica un repositorio.")
    if len(out) > MAX_FILES:
        raise SourceError(422, "TOO_MANY_FILES", f"Se encontraron {len(out)} archivos (máximo {MAX_FILES}).",
                          "Sube solo el módulo o programa a migrar.")
    return out
