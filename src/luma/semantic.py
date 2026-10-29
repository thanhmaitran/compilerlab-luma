"""Semantic analysis: name resolution, scopes and static type checking.

The analyzer is the single authority on whether a program is valid. It records
the static type of every expression so that later phases (IR generation) can
insert the implicit ``int`` -> ``float`` conversions without re-deriving types.
"""

from luma.ast import (
    AssignStmt,
    Binary,
    BlockStmt,
    Expr,
    ExprStmt,
    IfStmt,
    LetStmt,
    Literal,
    PrintStmt,
    Program,
    Stmt,
    Unary,
    Variable,
    WhileStmt,
)
from luma.errors import Diagnostic

_PHASE = "Semantic error"

# A static type is one of "int", "float", "bool", "string", or ``None`` when the
# type could not be determined because of an earlier error (this suppresses
# cascading diagnostics).
LuType = str | None

NUMERIC = frozenset({"int", "float"})
ARITHMETIC_OPERATORS = frozenset({"+", "-", "*", "/", "%"})
ORDERING_OPERATORS = frozenset({"<", "<=", ">", ">="})
EQUALITY_OPERATORS = frozenset({"==", "!="})
LOGICAL_OPERATORS = frozenset({"and", "or"})


def is_assignable(target: str, source: str) -> bool:
    """Return True if a value of type ``source`` may be stored as ``target``."""
    return target == source or (target == "float" and source == "int")


class SemanticAnalyzer:
    TYPES = frozenset({"int", "float", "bool", "string"})

    def __init__(self) -> None:
        self.scopes: list[dict[str, LuType]] = [{}]
        self.errors: list[Diagnostic] = []
        # Maps id(expression node) -> static type. Valid while the AST is alive.
        self.expression_types: dict[int, LuType] = {}

    def analyze(self, program: Program) -> list[Diagnostic]:
        self._statements(program.statements)
        return self.errors

    # -- statements ---------------------------------------------------

    def _statements(self, statements: tuple[Stmt, ...]) -> None:
        for statement in statements:
            self._statement(statement)

    def _statement(self, statement: Stmt) -> None:
        if isinstance(statement, LetStmt):
            self._let(statement)
        elif isinstance(statement, AssignStmt):
            self._assign(statement)
        elif isinstance(statement, PrintStmt):
            self._expression(statement.expression)
        elif isinstance(statement, ExprStmt):
            self._expression(statement.expression)
        elif isinstance(statement, BlockStmt):
            self._block(statement)
        elif isinstance(statement, IfStmt):
            self._condition(statement.condition, "if")
            self._block(statement.then_branch)
            if statement.else_branch is not None:
                self._block(statement.else_branch)
        elif isinstance(statement, WhileStmt):
            self._condition(statement.condition, "while")
            self._block(statement.body)
        else:  # pragma: no cover - defensive
            raise TypeError(f"Unknown statement node: {statement!r}")

    def _block(self, block: BlockStmt) -> None:
        self.scopes.append({})
        self._statements(block.statements)
        self.scopes.pop()

    def _let(self, statement: LetStmt) -> None:
        initializer_type = self._expression(statement.initializer)
        declared: LuType
        if statement.annotation is None:
            declared = initializer_type
        elif statement.annotation not in self.TYPES:
            self._error(
                f"Unknown type '{statement.annotation}'",
                statement.line,
                statement.column,
            )
            declared = None
        else:
            declared = statement.annotation
            if initializer_type is not None and not is_assignable(
                declared, initializer_type
            ):
                self._error(
                    f"Cannot initialise variable '{statement.name}' of type "
                    f"{declared} with a value of type {initializer_type}",
                    statement.initializer.line,
                    statement.initializer.column,
                )
        scope = self.scopes[-1]
        if statement.name in scope:
            self._error(
                f"Variable '{statement.name}' is already declared in this scope",
                statement.line,
                statement.column,
            )
            return
        scope[statement.name] = declared

    def _assign(self, statement: AssignStmt) -> None:
        value_type = self._expression(statement.value)
        found, target = self._lookup(statement.name)
        if not found:
            self._error(
                f"Undefined variable '{statement.name}'",
                statement.line,
                statement.column,
            )
            return
        if (
            target is not None
            and value_type is not None
            and not is_assignable(target, value_type)
        ):
            self._error(
                f"Cannot assign a value of type {value_type} to variable "
                f"'{statement.name}' of type {target}",
                statement.value.line,
                statement.value.column,
            )

    def _condition(self, condition: Expr, keyword: str) -> None:
        condition_type = self._expression(condition)
        if condition_type is not None and condition_type != "bool":
            self._error(
                f"Condition of '{keyword}' must be of type bool, got {condition_type}",
                condition.line,
                condition.column,
            )

    # -- expressions --------------------------------------------------

    def _expression(self, expression: Expr) -> LuType:
        result = self._infer(expression)
        self.expression_types[id(expression)] = result
        return result

    def _infer(self, expression: Expr) -> LuType:
        if isinstance(expression, Literal):
            return self._literal_type(expression)
        if isinstance(expression, Variable):
            found, variable_type = self._lookup(expression.name)
            if not found:
                self._error(
                    f"Undefined variable '{expression.name}'",
                    expression.line,
                    expression.column,
                )
            return variable_type
        if isinstance(expression, Unary):
            return self._unary(expression)
        if isinstance(expression, Binary):
            return self._binary(expression)
        raise TypeError(f"Unknown expression node: {expression!r}")  # pragma: no cover

    @staticmethod
    def _literal_type(literal: Literal) -> str:
        value = literal.value
        if isinstance(value, bool):  # bool is a subclass of int in Python
            return "bool"
        if isinstance(value, int):
            return "int"
        if isinstance(value, float):
            return "float"
        return "string"

    def _unary(self, expression: Unary) -> LuType:
        operand = self._expression(expression.operand)
        if expression.operator == "-":
            if operand is None:
                return None
            if operand in NUMERIC:
                return operand
            self._error(
                f"Operator '-' cannot be applied to type {operand}",
                expression.line,
                expression.column,
            )
            return None
        if operand is not None and operand != "bool":
            self._error(
                f"Operator 'not' requires a bool operand, got {operand}",
                expression.line,
                expression.column,
            )
        return "bool"

    def _binary(self, expression: Binary) -> LuType:
        operator = expression.operator
        left = self._expression(expression.left)
        right = self._expression(expression.right)
        yields_bool = (
            operator in ORDERING_OPERATORS
            or operator in EQUALITY_OPERATORS
            or operator in LOGICAL_OPERATORS
        )
        if left is None or right is None:
            return "bool" if yields_bool else None

        result: LuType = None
        if operator in LOGICAL_OPERATORS:
            if left == "bool" and right == "bool":
                result = "bool"
        elif operator in ARITHMETIC_OPERATORS:
            if left in NUMERIC and right in NUMERIC:
                result = "int" if left == right == "int" else "float"
            elif operator == "+" and left == right == "string":
                result = "string"
        elif operator in ORDERING_OPERATORS:
            if (left in NUMERIC and right in NUMERIC) or (left == right == "string"):
                result = "bool"
        elif operator in EQUALITY_OPERATORS:
            if (left in NUMERIC and right in NUMERIC) or left == right:
                result = "bool"

        if result is None:
            self._error(
                f"Operator '{operator}' cannot be applied to operands of "
                f"type {left} and {right}",
                expression.line,
                expression.column,
            )
            return "bool" if yields_bool else None
        return result

    # -- helpers ------------------------------------------------------

    def _lookup(self, name: str) -> tuple[bool, LuType]:
        for scope in reversed(self.scopes):
            if name in scope:
                return True, scope[name]
        return False, None

    def _error(self, message: str, line: int, column: int) -> None:
        self.errors.append(Diagnostic(_PHASE, message, line, column))
