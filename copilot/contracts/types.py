"""Tipos neutrales de la especificación.

Todo tipo del lenguaje origen se mapea a un NeutralType, y de ahí al lenguaje destino.
El modo de redondeo es parte del tipo decimal: así nunca se pierde entre lenguajes.
Ver skill `language-adapters` y `legacy-type-mapping`.
"""
from __future__ import annotations

import re
from decimal import (
    ROUND_CEILING, ROUND_DOWN, ROUND_FLOOR, ROUND_HALF_DOWN, ROUND_HALF_EVEN,
    ROUND_HALF_UP, ROUND_UP, Decimal, InvalidOperation, localcontext,
)
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, model_validator

INTERMEDIATE_PRECISION = 34  # igual que DECIMAL128 / MathContext.DECIMAL128


class Rounding(StrEnum):
    """Modo de redondeo al ASIGNAR un valor (no en intermedios)."""
    HALF_UP = "HALF_UP"        # mitad lejos de cero: COBOL ROUNDED, PL/SQL ROUND, .NET AwayFromZero
    HALF_EVEN = "HALF_EVEN"    # banquero: .NET Math.Round por defecto, VB CInt
    HALF_DOWN = "HALF_DOWN"
    DOWN = "DOWN"              # truncar hacia cero: COBOL sin ROUNDED, PL/SQL TRUNC
    UP = "UP"
    FLOOR = "FLOOR"
    CEILING = "CEILING"


_PY_ROUNDING = {
    Rounding.HALF_UP: ROUND_HALF_UP, Rounding.HALF_EVEN: ROUND_HALF_EVEN,
    Rounding.HALF_DOWN: ROUND_HALF_DOWN, Rounding.DOWN: ROUND_DOWN, Rounding.UP: ROUND_UP,
    Rounding.FLOOR: ROUND_FLOOR, Rounding.CEILING: ROUND_CEILING,
}


class TypeKind(StrEnum):
    DECIMAL = "decimal"
    INTEGER = "integer"
    FLOAT = "float"          # solo cuando el legacy realmente usa punto flotante (COMP-1/2, double)
    STRING = "string"
    DATE = "date"
    DATETIME = "datetime"
    BOOLEAN = "boolean"
    ENUM = "enum"
    LIST = "list"
    RECORD = "record"


class NeutralType(BaseModel):
    model_config = ConfigDict(frozen=True)

    kind: TypeKind
    precision: int | None = None      # decimal: dígitos totales
    scale: int | None = None          # decimal: dígitos decimales
    rounding: Rounding | None = None  # decimal: semántica de asignación
    signed: bool = True               # False: el legacy guarda valor absoluto (COBOL PIC 9 sin S)
    bits: int | None = None           # integer
    max_length: int | None = None     # string
    values: tuple[str, ...] | None = None             # enum
    item: NeutralType | None = None                   # list
    fields: dict[str, NeutralType] | None = None      # record

    @model_validator(mode="after")
    def _check(self) -> NeutralType:
        k = self.kind
        if k == TypeKind.DECIMAL:
            if self.precision is None or self.scale is None or self.rounding is None:
                raise ValueError("decimal requiere precision, scale y rounding explícitos")
            if not 0 <= self.scale <= self.precision:
                raise ValueError("decimal: 0 <= scale <= precision")
        if k == TypeKind.ENUM and not self.values:
            raise ValueError("enum requiere values")
        if k == TypeKind.LIST and self.item is None:
            raise ValueError("list requiere item")
        if k == TypeKind.RECORD and not self.fields:
            raise ValueError("record requiere fields")
        return self

    # ---- representación compacta: "decimal(9,2,HALF_UP)", "string(30)", "integer(32)" ----
    def describe(self) -> str:
        if self.kind == TypeKind.DECIMAL:
            s = f"decimal({self.precision},{self.scale},{self.rounding})"
            return s if self.signed else s + " unsigned"
        if self.kind == TypeKind.STRING and self.max_length:
            return f"string({self.max_length})"
        if self.kind == TypeKind.INTEGER and self.bits:
            return f"integer({self.bits})"
        if self.kind == TypeKind.ENUM:
            return f"enum({'|'.join(self.values or ())})"
        if self.kind == TypeKind.LIST:
            return f"list<{self.item.describe()}>"  # type: ignore[union-attr]
        return self.kind.value

    @classmethod
    def parse(cls, text: str) -> NeutralType:
        """Inversa de describe() para tipos escalares (útil en salidas del LLM)."""
        t = text.strip()
        if m := re.fullmatch(r"decimal\((\d+),\s*(\d+),\s*(\w+)\)(\s+unsigned)?", t):
            return cls(kind=TypeKind.DECIMAL, precision=int(m[1]), scale=int(m[2]),
                       rounding=Rounding(m[3].upper()), signed=m[4] is None)
        if m := re.fullmatch(r"string\((\d+)\)", t):
            return cls(kind=TypeKind.STRING, max_length=int(m[1]))
        if m := re.fullmatch(r"integer\((\d+)\)", t):
            return cls(kind=TypeKind.INTEGER, bits=int(m[1]))
        if m := re.fullmatch(r"enum\((.+)\)", t):
            return cls(kind=TypeKind.ENUM, values=tuple(m[1].split("|")))
        if m := re.fullmatch(r"list<(.+)>", t):
            return cls(kind=TypeKind.LIST, item=cls.parse(m[1]))
        return cls(kind=TypeKind(t))

    # ---- semántica de asignación decimal (referencia para comparador y oráculo nivel C) ----
    def assign(self, value: Decimal | str | int) -> Decimal:
        """Aplica escala y redondeo como lo haría el legacy al guardar en un campo de este tipo.

        Lanza OverflowError si la parte entera no cabe: cada adaptador decide si replica el
        truncamiento de dígitos altos (COBOL sin ON SIZE ERROR) o lo trata como error.
        """
        if self.kind != TypeKind.DECIMAL:
            raise TypeError(f"assign() solo aplica a decimal, no a {self.kind}")
        try:
            d = Decimal(value) if not isinstance(value, Decimal) else value
        except InvalidOperation as exc:
            raise ValueError(f"valor decimal inválido: {value!r}") from exc
        if not self.signed:
            d = abs(d)
        with localcontext() as ctx:
            ctx.prec = INTERMEDIATE_PRECISION
            q = d.quantize(Decimal(1).scaleb(-self.scale), rounding=_PY_ROUNDING[self.rounding])  # type: ignore[index,arg-type]
        int_digits = self.precision - self.scale  # type: ignore[operator]
        if abs(q) >= Decimal(10) ** int_digits:
            raise OverflowError(f"{q} no cabe en {self.describe()}")
        return q


def decimal_str(value: Decimal) -> str:
    """Formato canónico para JSON: string, sin notación científica."""
    return format(value, "f")
