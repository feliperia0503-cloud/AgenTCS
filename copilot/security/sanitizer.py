"""Enmascaramiento de secretos y datos personales ANTES de que el código llegue al LLM.

Determinista (regex + validación Luhn). Un mismo valor recibe siempre el mismo marcador dentro de
una ejecución, para que el análisis siga siendo coherente. El valor original nunca se guarda.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from copilot.contracts import SanitizationFinding, SourceFile

# (tipo, patrón, grupo que contiene el valor sensible)
_RULES: list[tuple[str, re.Pattern[str], int]] = [
    ("private_key", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----[\s\S]*?-----END [A-Z ]*PRIVATE KEY-----"), 0),
    ("api_key", re.compile(r"\b(sk-[A-Za-z0-9_-]{20,}|AKIA[0-9A-Z]{16}|ghp_[A-Za-z0-9]{36}|xox[baprs]-[A-Za-z0-9-]{10,})\b"), 1),
    ("connection_string", re.compile(r"(?i)\b(jdbc:[a-z0-9]+:[^\s\"']+|mongodb(?:\+srv)?://[^\s\"']+|postgres(?:ql)?://[^\s\"']+)"), 1),
    ("connection_string", re.compile(r"(?i)((?:server|data source)=[^;\"']+;[^\"'\n]*?(?:password|pwd)=[^;\"'\n]+)"), 1),
    ("oracle_credentials", re.compile(r"\b([A-Za-z]\w*/[^\s/@\"']+@[\w.-]+(?::\d+)?(?:/[\w.]+)?)"), 1),
    ("password", re.compile(r"(?i)\b(?:password|passwd|pwd|secret|token|api[_-]?key|clave|contrase(?:ñ|n)a)\b\s*[:=]\s*[\"']?([^\s\"';,)]+)"), 1),
    ("email", re.compile(r"\b([A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,})\b"), 1),
    ("card_number", re.compile(r"\b(\d(?:[ -]?\d){12,18})\b"), 1),
]

_PREFIX = {
    "private_key": "SECRET", "api_key": "SECRET", "connection_string": "SECRET",
    "oracle_credentials": "SECRET", "password": "SECRET", "email": "EMAIL", "card_number": "CARD",
}


def _luhn_ok(digits: str) -> bool:
    nums = [int(c) for c in digits if c.isdigit()]
    if not 13 <= len(nums) <= 19:
        return False
    total = 0
    for i, n in enumerate(reversed(nums)):
        if i % 2:
            n *= 2
            if n > 9:
                n -= 9
        total += n
    return total % 10 == 0


@dataclass
class Sanitizer:
    """Mantiene la tabla valor -> marcador durante una ejecución."""
    _placeholders: dict[str, str] = field(default_factory=dict)
    _counters: dict[str, int] = field(default_factory=dict)

    def _placeholder(self, kind: str, value: str) -> str:
        if value not in self._placeholders:
            prefix = _PREFIX[kind]
            self._counters[prefix] = self._counters.get(prefix, 0) + 1
            self._placeholders[value] = f"<<{prefix}_{self._counters[prefix]}>>"
        return self._placeholders[value]

    def sanitize_text(self, path: str, text: str) -> tuple[str, list[SanitizationFinding]]:
        findings: list[SanitizationFinding] = []
        for kind, pattern, group in _RULES:
            def repl(m: re.Match[str], kind: str = kind, group: int = group) -> str:
                value = m.group(group)
                if kind == "card_number" and not _luhn_ok(value):
                    return m.group(0)
                if value.startswith("<<") and value.endswith(">>"):
                    return m.group(0)   # ya enmascarado por una regla anterior
                ph = self._placeholder(kind, value)
                line = text.count("\n", 0, m.start(group)) + 1
                findings.append(SanitizationFinding(kind=kind, file=path, line=line,
                                                    placeholder=ph, detector=f"regex:{kind}"))
                start, end = m.start(group) - m.start(0), m.end(group) - m.start(0)
                whole = m.group(0)
                return whole[:start] + ph + whole[end:]
            text = pattern.sub(repl, text)
        return text, findings

    def sanitize_files(self, files: list[tuple[str, str]]) -> tuple[list[SourceFile], list[SanitizationFinding]]:
        out, all_findings = [], []
        for path, content in files:
            clean, findings = self.sanitize_text(path, content)
            out.append(SourceFile(path=path, content=clean))
            all_findings += findings
        return out, all_findings
