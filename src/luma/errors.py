"""Diagnostics shared by the lexer, parser, semantic analyzer and compiler."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Diagnostic:
    """A user-facing problem found in Luma source code.

    A ``line`` of 0 or less means the problem has no source location.
    """

    phase: str
    message: str
    line: int
    column: int

    def __str__(self) -> str:
        if self.line <= 0:
            return f"{self.phase}: {self.message}"
        return f"[line {self.line}, column {self.column}] {self.phase}: {self.message}"
