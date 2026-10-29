"""IR generation: typed AST -> IR."""

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
from luma.ir import Instruction, IRError, IRItem, IRProgram, Label

_BINARY_OPCODES = {
    "+": "ADD",
    "-": "SUBTRACT",
    "*": "MULTIPLY",
    "/": "DIVIDE",
    "%": "MODULO",
    "==": "EQUAL",
    "!=": "NOT_EQUAL",
    "<": "LESS",
    "<=": "LESS_EQUAL",
    ">": "GREATER",
    ">=": "GREATER_EQUAL",
}

_NUMERIC = ("int", "float")


class IRGenerator:
    """Translate an AST that already passed semantic analysis into IR.

    ``expression_types`` is the map produced by ``SemanticAnalyzer``. The
    generator relies on it to insert ``TO_FLOAT`` where an ``int`` value is used
    as a ``float``. Local slots are never reused, which keeps correctness easy
    to verify (slot allocation optimisations are future work).
    """

    def __init__(self, expression_types: dict[int, str | None]) -> None:
        self.types = expression_types
        self.items: list[IRItem] = []
        self.next_label = 0
        self.next_slot = 0
        self.scopes: list[dict[str, tuple[int, str]]] = [{}]

    @property
    def local_count(self) -> int:
        return self.next_slot

    def generate(self, program: Program) -> IRProgram:
        self.items = []
        self.next_label = 0
        self.next_slot = 0
        self.scopes = [{}]
        self._statements(program.statements)
        return IRProgram(tuple(self.items), self.local_count)

    # -- emit helpers -------------------------------------------------

    def _label(self, prefix: str) -> Label:
        label = Label(f"{prefix}_{self.next_label}")
        self.next_label += 1
        return label

    def _place(self, label: Label) -> None:
        self.items.append(label)

    def _emit(self, opcode: str, *operands: object) -> None:
        self.items.append(Instruction(opcode, tuple(operands)))

    # -- scopes -------------------------------------------------------

    def _begin_scope(self) -> None:
        self.scopes.append({})

    def _end_scope(self) -> None:
        self.scopes.pop()

    def _declare(self, name: str, var_type: str) -> int:
        if name in self.scopes[-1]:
            raise IRError(f"Duplicate declaration in scope: {name}")
        slot = self.next_slot
        self.next_slot += 1
        self.scopes[-1][name] = (slot, var_type)
        return slot

    def _lookup(self, name: str) -> tuple[int, str]:
        for scope in reversed(self.scopes):
            if name in scope:
                return scope[name]
        raise IRError(f"Undefined variable: {name}")

    def _type_of(self, expression: Expr) -> str:
        expression_type = self.types.get(id(expression))
        if expression_type is None:
            raise IRError(
                "Missing type information for expression at "
                f"line {expression.line}, column {expression.column}"
            )
        return expression_type

    # -- statements ---------------------------------------------------

    def _statements(self, statements: tuple[Stmt, ...]) -> None:
        for statement in statements:
            self._statement(statement)

    def _statement(self, statement: Stmt) -> None:
        if isinstance(statement, LetStmt):
            target = statement.annotation or self._type_of(statement.initializer)
            self._expression(statement.initializer, target)
            slot = self._declare(statement.name, target)
            self._emit("STORE_LOCAL", slot)
        elif isinstance(statement, AssignStmt):
            slot, target = self._lookup(statement.name)
            self._expression(statement.value, target)
            self._emit("STORE_LOCAL", slot)
        elif isinstance(statement, PrintStmt):
            self._expression(statement.expression)
            self._emit("PRINT")
        elif isinstance(statement, ExprStmt):
            self._expression(statement.expression)
            self._emit("POP")
        elif isinstance(statement, BlockStmt):
            self._block(statement)
        elif isinstance(statement, IfStmt):
            self._if(statement)
        elif isinstance(statement, WhileStmt):
            self._while(statement)
        else:  # pragma: no cover - defensive
            raise IRError(f"Unknown statement node: {statement!r}")

    def _block(self, block: BlockStmt) -> None:
        self._begin_scope()
        self._statements(block.statements)
        self._end_scope()

    def _if(self, statement: IfStmt) -> None:
        else_label = self._label("else")
        end_label = self._label("endif")
        self._expression(statement.condition)
        self._emit("JUMP_IF_FALSE", else_label)
        self._block(statement.then_branch)
        self._emit("JUMP", end_label)
        self._place(else_label)
        if statement.else_branch is not None:
            self._block(statement.else_branch)
        self._place(end_label)

    def _while(self, statement: WhileStmt) -> None:
        start_label = self._label("while")
        end_label = self._label("endwhile")
        self._place(start_label)
        self._expression(statement.condition)
        self._emit("JUMP_IF_FALSE", end_label)
        self._block(statement.body)
        self._emit("JUMP", start_label)
        self._place(end_label)

    # -- expressions --------------------------------------------------

    def _expression(self, expression: Expr, coerce_to: str | None = None) -> None:
        """Emit code that leaves the expression's value on the stack.

        If ``coerce_to`` is ``"float"`` and the expression is an ``int``, the
        value is converted with ``TO_FLOAT``.
        """
        if isinstance(expression, Literal):
            self._emit("CONST", expression.value)
        elif isinstance(expression, Variable):
            slot, _ = self._lookup(expression.name)
            self._emit("LOAD_LOCAL", slot)
        elif isinstance(expression, Unary):
            self._expression(expression.operand)
            self._emit("NEGATE" if expression.operator == "-" else "NOT")
        elif isinstance(expression, Binary):
            self._binary(expression)
        else:  # pragma: no cover - defensive
            raise IRError(f"Unknown expression node: {expression!r}")
        if coerce_to == "float" and self._type_of(expression) == "int":
            self._emit("TO_FLOAT")

    def _binary(self, expression: Binary) -> None:
        operator = expression.operator
        if operator in ("and", "or"):
            self._logical(expression)
            return
        left_type = self._type_of(expression.left)
        right_type = self._type_of(expression.right)
        common = None
        if left_type in _NUMERIC and right_type in _NUMERIC and left_type != right_type:
            common = "float"
        self._expression(expression.left, common)
        self._expression(expression.right, common)
        self._emit(_BINARY_OPCODES[operator])

    def _logical(self, expression: Binary) -> None:
        """Short-circuit ``and`` / ``or`` using conditional jumps."""
        is_and = expression.operator == "and"
        end_label = self._label("and_end" if is_and else "or_end")
        self._expression(expression.left)
        self._emit("DUP")
        if not is_and:
            self._emit("NOT")
        self._emit("JUMP_IF_FALSE", end_label)
        self._emit("POP")
        self._expression(expression.right)
        self._place(end_label)
