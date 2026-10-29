"""Bytecode definitions and validation."""

from dataclasses import dataclass
from enum import Enum, auto


class BytecodeError(Exception):
    """Raised when bytecode cannot be produced or fails validation."""


class OpCode(Enum):
    CONST = auto()
    LOAD_LOCAL = auto()
    STORE_LOCAL = auto()
    ADD = auto()
    SUBTRACT = auto()
    MULTIPLY = auto()
    DIVIDE = auto()
    MODULO = auto()
    NEGATE = auto()
    NOT = auto()
    EQUAL = auto()
    NOT_EQUAL = auto()
    LESS = auto()
    LESS_EQUAL = auto()
    GREATER = auto()
    GREATER_EQUAL = auto()
    TO_FLOAT = auto()
    DUP = auto()
    PRINT = auto()
    POP = auto()
    JUMP = auto()
    JUMP_IF_FALSE = auto()
    HALT = auto()


@dataclass(frozen=True, slots=True)
class BytecodeInstruction:
    opcode: OpCode
    operand: object | None = None


@dataclass(frozen=True, slots=True)
class BytecodeProgram:
    instructions: tuple[BytecodeInstruction, ...]
    local_count: int = 0


JUMP_OPCODES = frozenset({OpCode.JUMP, OpCode.JUMP_IF_FALSE})
SLOT_OPCODES = frozenset({OpCode.LOAD_LOCAL, OpCode.STORE_LOCAL})
OPERAND_OPCODES = JUMP_OPCODES | SLOT_OPCODES | {OpCode.CONST}

_BINARY = (2, 1)
_UNARY = (1, 1)

# (values popped, values pushed) for every opcode.
STACK_EFFECTS: dict[OpCode, tuple[int, int]] = {
    OpCode.CONST: (0, 1),
    OpCode.LOAD_LOCAL: (0, 1),
    OpCode.STORE_LOCAL: (1, 0),
    OpCode.ADD: _BINARY,
    OpCode.SUBTRACT: _BINARY,
    OpCode.MULTIPLY: _BINARY,
    OpCode.DIVIDE: _BINARY,
    OpCode.MODULO: _BINARY,
    OpCode.NEGATE: _UNARY,
    OpCode.NOT: _UNARY,
    OpCode.EQUAL: _BINARY,
    OpCode.NOT_EQUAL: _BINARY,
    OpCode.LESS: _BINARY,
    OpCode.LESS_EQUAL: _BINARY,
    OpCode.GREATER: _BINARY,
    OpCode.GREATER_EQUAL: _BINARY,
    OpCode.TO_FLOAT: _UNARY,
    OpCode.DUP: (1, 2),
    OpCode.PRINT: (1, 0),
    OpCode.POP: (1, 0),
    OpCode.JUMP: (0, 0),
    OpCode.JUMP_IF_FALSE: (1, 0),
    OpCode.HALT: (0, 0),
}


def _in_range(value: object, limit: int) -> bool:
    """True if ``value`` is a real int (not a bool) with 0 <= value < limit."""
    return type(value) is int and 0 <= value < limit


def validate_bytecode(program: BytecodeProgram) -> list[str]:
    """Statically validate bytecode and return a list of problems.

    Checks operands, jump targets, local slots, stack depth (no underflow and
    consistent depth at every join point), and that execution can never run off
    the end of the program. A program is also required to leave the stack empty
    at every ``HALT``.
    """
    problems: list[str] = []
    code = program.instructions
    size = len(code)
    if size == 0:
        return ["Program is empty"]

    for index, instruction in enumerate(code):
        opcode = instruction.opcode
        if not isinstance(opcode, OpCode):
            problems.append(f"{index:04d} invalid opcode {opcode!r}")
            continue
        where = f"{index:04d} {opcode.name}"
        operand = instruction.operand
        if opcode in OPERAND_OPCODES and operand is None:
            problems.append(f"{where} is missing its operand")
        elif opcode not in OPERAND_OPCODES and operand is not None:
            problems.append(f"{where} must not have an operand")
        elif opcode in JUMP_OPCODES:
            if not _in_range(operand, size):
                problems.append(f"{where} has invalid jump target {operand!r}")
        elif opcode in SLOT_OPCODES:
            if not _in_range(operand, program.local_count):
                problems.append(f"{where} uses invalid local slot {operand!r}")
        elif opcode is OpCode.CONST:
            if type(operand) not in (bool, int, float, str):
                problems.append(f"{where} has unsupported constant {operand!r}")
    if problems:
        return problems

    depths: dict[int, int] = {0: 0}
    worklist = [0]
    while worklist:
        index = worklist.pop()
        depth = depths[index]
        instruction = code[index]
        opcode = instruction.opcode
        operand = instruction.operand
        pops, pushes = STACK_EFFECTS[opcode]
        if depth < pops:
            problems.append(f"{index:04d} {opcode.name}: stack underflow")
            continue
        after = depth - pops + pushes
        successors: list[int] = []
        if opcode is OpCode.HALT:
            if depth != 0:
                problems.append(f"{index:04d} HALT with {depth} value(s) on the stack")
        else:
            if opcode is not OpCode.JUMP:
                if index + 1 < size:
                    successors.append(index + 1)
                else:
                    problems.append(
                        f"{index:04d} {opcode.name}: execution falls off the end"
                    )
            if isinstance(operand, int) and opcode in JUMP_OPCODES:
                successors.append(operand)
        for successor in successors:
            known = depths.get(successor)
            if known is None:
                depths[successor] = after
                worklist.append(successor)
            elif known != after:
                problems.append(
                    f"{successor:04d}: inconsistent stack depth ({known} vs {after})"
                )
    return problems
