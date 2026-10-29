"""Intermediate representation (IR).

The IR is a flat, stack-oriented instruction list with symbolic labels. It is
independent of the bytecode format: IR uses labels, bytecode uses resolved
instruction addresses.
"""

from dataclasses import dataclass


class IRError(Exception):
    """Raised when IR cannot be generated or fails validation."""


@dataclass(frozen=True, slots=True)
class Label:
    name: str


@dataclass(frozen=True, slots=True)
class Instruction:
    opcode: str
    operands: tuple[object, ...] = ()


type IRItem = Label | Instruction


@dataclass(frozen=True, slots=True)
class IRProgram:
    items: tuple[IRItem, ...]
    local_count: int = 0


# Number of operands each IR opcode takes.
OPERAND_COUNTS: dict[str, int] = {
    "CONST": 1,
    "LOAD_LOCAL": 1,
    "STORE_LOCAL": 1,
    "ADD": 0,
    "SUBTRACT": 0,
    "MULTIPLY": 0,
    "DIVIDE": 0,
    "MODULO": 0,
    "NEGATE": 0,
    "NOT": 0,
    "EQUAL": 0,
    "NOT_EQUAL": 0,
    "LESS": 0,
    "LESS_EQUAL": 0,
    "GREATER": 0,
    "GREATER_EQUAL": 0,
    "TO_FLOAT": 0,
    "DUP": 0,
    "PRINT": 0,
    "POP": 0,
    "JUMP": 1,
    "JUMP_IF_FALSE": 1,
}

JUMP_OPCODES = frozenset({"JUMP", "JUMP_IF_FALSE"})
SLOT_OPCODES = frozenset({"LOAD_LOCAL", "STORE_LOCAL"})


def _format_operand(operand: object) -> str:
    if isinstance(operand, Label):
        return operand.name
    return repr(operand)


def format_ir(program: IRProgram) -> str:
    lines = []
    for item in program.items:
        if isinstance(item, Label):
            lines.append(f"{item.name}:")
        else:
            operands = ", ".join(_format_operand(v) for v in item.operands)
            suffix = f" {operands}" if operands else ""
            lines.append(f"    {item.opcode}{suffix}")
    return "\n".join(lines)


def validate_ir(program: IRProgram) -> list[str]:
    """Return a list of problems found in ``program`` (empty when valid)."""
    problems: list[str] = []
    labels: set[str] = set()
    for item in program.items:
        if isinstance(item, Label):
            if item.name in labels:
                problems.append(f"Duplicate label '{item.name}'")
            labels.add(item.name)

    for item in program.items:
        if isinstance(item, Label):
            continue
        opcode = item.opcode
        expected = OPERAND_COUNTS.get(opcode)
        if expected is None:
            problems.append(f"Unknown IR opcode '{opcode}'")
            continue
        if len(item.operands) != expected:
            problems.append(
                f"{opcode} takes {expected} operand(s), got {len(item.operands)}"
            )
            continue
        if opcode in JUMP_OPCODES:
            target = item.operands[0]
            if not isinstance(target, Label) or target.name not in labels:
                problems.append(f"{opcode} targets an undefined label")
        elif opcode in SLOT_OPCODES:
            slot = item.operands[0]
            valid = (
                isinstance(slot, int)
                and not isinstance(slot, bool)
                and 0 <= slot < program.local_count
            )
            if not valid:
                problems.append(
                    f"{opcode} uses invalid slot {slot!r} "
                    f"(local_count={program.local_count})"
                )
        elif opcode == "CONST":
            if type(item.operands[0]) not in (bool, int, float, str):
                problems.append("CONST operand must be a bool, int, float or str")
    return problems
