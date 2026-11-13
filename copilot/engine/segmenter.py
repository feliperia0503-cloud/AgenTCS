"""Segmentador genérico de respaldo para lenguajes sin pack de origen.

Detecta encabezados de unidades comunes (párrafos COBOL, procedimientos PL/SQL, métodos de lenguajes
tipo C, funciones Python/VB). Es heurístico: el AnalysisResult lleva confidence_penalty > 0 y el
extractor baja la confianza de las reglas en consecuencia.
"""
from __future__ import annotations

import re

from copilot.contracts import (
    AnalysisResult, Classification, Metrics, SourceFile, Unit, UnitKind,
)

GENERIC_PENALTY = 0.15

_HEADERS: list[tuple[UnitKind, re.Pattern[str]]] = [
    (UnitKind.PARAGRAPH, re.compile(r"^ {7}([A-Z0-9][A-Z0-9-]*)\.\s*$")),
    (UnitKind.PROCEDURE, re.compile(
        r"^\s*(?:CREATE\s+(?:OR\s+REPLACE\s+)?)?(?:PROCEDURE|FUNCTION|TRIGGER|PACKAGE(?:\s+BODY)?)\s+([\w.$#\"]+)",
        re.IGNORECASE)),
    (UnitKind.METHOD, re.compile(
        r"^\s*(?:public|private|protected|internal|static|final|override|virtual|async|\s)+"
        r"[\w<>\[\],.? ]+\s+(\w+)\s*\([^;]*$")),
    (UnitKind.FUNCTION, re.compile(r"^\s*(?:Public |Private |Friend )?(?:Function|Sub)\s+(\w+)", re.IGNORECASE)),
    (UnitKind.FUNCTION, re.compile(r"^\s*(?:async\s+)?def\s+(\w+)\s*\(")),
    (UnitKind.PROCEDURE, re.compile(r"^\s*(?:FORM|METHOD|FUNCTION|MODULE)\s+([\w/]+)", re.IGNORECASE)),   # ABAP
    (UnitKind.PROCEDURE, re.compile(r"^\s*(?:BEGSR|DCL-PROC)\s+(\w+)", re.IGNORECASE)),                   # RPG
]
_DECISION = re.compile(r"\b(IF|ELSIF|ELSE IF|WHEN|CASE|WHILE|FOR|UNTIL|PERFORM VARYING|AND|OR|CATCH|EXCEPT|ELSEIF)\b",
                       re.IGNORECASE)


def _headers(lines: list[str]) -> list[tuple[int, str, UnitKind]]:
    found = []
    for i, line in enumerate(lines):
        for kind, pattern in _HEADERS:
            m = pattern.match(line)
            if m and not line.lstrip().startswith(("*", "//", "--", "#")):
                found.append((i + 1, m.group(1).strip('"'), kind))
                break
    return found


def segment(files: list[SourceFile], language: str) -> AnalysisResult:
    units: list[Unit] = []
    loc = 0
    for f in files:
        lines = f.lines
        loc += sum(1 for ln in lines if ln.strip())
        heads = _headers(lines) or [(1, f.path, UnitKind.PROGRAM)]
        if heads[0][0] > 1:
            heads.insert(0, (1, f"{f.path}::preambulo", UnitKind.BLOCK))
        for idx, (start, name, kind) in enumerate(heads):
            end = heads[idx + 1][0] - 1 if idx + 1 < len(heads) else max(len(lines), 1)
            body = "\n".join(lines[start - 1:end])
            units.append(Unit(
                id=f"{f.path}::{name}#{start}", name=name, kind=kind, file=f.path,
                start_line=start, end_line=max(end, start),
                classification=Classification.DESCONOCIDO,
                complexity=1 + len(_DECISION.findall(body))))
    cx = [u.complexity for u in units] or [1]
    return AnalysisResult(
        language=language, parser="generic:segmenter", files=[f.path for f in files], units=units,
        metrics=Metrics(loc=loc, units=len(units), avg_complexity=round(sum(cx) / len(cx), 2),
                        max_complexity=max(cx)),
        confidence_penalty=GENERIC_PENALTY)
