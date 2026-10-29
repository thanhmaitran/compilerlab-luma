"""Abstract syntax tree for Luma.

The tree stores program structure, not punctuation. Every node carries the
source position of its most meaningful token for diagnostics.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Literal:
    value: bool | int | float | str
    line: int
    column: int


@dataclass(frozen=True, slots=True)
class Variable:
    name: str
    line: int
    column: int


@dataclass(frozen=True, slots=True)
class Unary:
    operator: str  # "-" or "not"
    operand: Expr
    line: int
    column: int


@dataclass(frozen=True, slots=True)
class Binary:
    left: Expr
    operator: str
    right: Expr
    line: int
    column: int


@dataclass(frozen=True, slots=True)
class LetStmt:
    name: str
    annotation: str | None
    initializer: Expr
    line: int
    column: int


@dataclass(frozen=True, slots=True)
class AssignStmt:
    name: str
    value: Expr
    line: int
    column: int


@dataclass(frozen=True, slots=True)
class PrintStmt:
    expression: Expr
    line: int
    column: int


@dataclass(frozen=True, slots=True)
class ExprStmt:
    expression: Expr
    line: int
    column: int


@dataclass(frozen=True, slots=True)
class BlockStmt:
    statements: tuple[Stmt, ...]
    line: int
    column: int


@dataclass(frozen=True, slots=True)
class IfStmt:
    condition: Expr
    then_branch: BlockStmt
    else_branch: BlockStmt | None
    line: int
    column: int


@dataclass(frozen=True, slots=True)
class WhileStmt:
    condition: Expr
    body: BlockStmt
    line: int
    column: int


@dataclass(frozen=True, slots=True)
class Program:
    statements: tuple[Stmt, ...]


type Expr = Literal | Variable | Unary | Binary
type Stmt = LetStmt | AssignStmt | PrintStmt | ExprStmt | BlockStmt | IfStmt | WhileStmt
