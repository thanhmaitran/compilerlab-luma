"""Stack-based virtual machine that executes Luma bytecode.

The VM never uses ``eval`` or ``exec``. Every runtime fault (stack underflow,
division by zero, type mismatch in hand-written bytecode, integer overflow,
exceeding the instruction limit, ...) is reported as a ``VMError``.
"""

import math
from collections.abc import Callable
from dataclasses import dataclass

from luma.bytecode import BytecodeInstruction, BytecodeProgram, OpCode

INT_MIN = -(2**63)
INT_MAX = 2**63 - 1

_UNSET = object()


class VMError(Exception):
    """Raised when bytecode cannot be executed safely."""

    def __init__(self, message: str, pc: int | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.pc = pc

    def __str__(self) -> str:
        if self.pc is None:
            return self.message
        return f"{self.message} (at instruction {self.pc:04d})"


@dataclass(frozen=True, slots=True)
class ExecutionResult:
    output: tuple[str, ...]
    instructions_executed: int


def type_name(value: object) -> str:
    if isinstance(value, bool):
        return "bool"
    if isinstance(value, int):
        return "int"
    if isinstance(value, float):
        return "float"
    if isinstance(value, str):
        return "string"
    return type(value).__name__


def format_value(value: object) -> str:
    """Format a runtime value the way ``print`` shows it."""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, float):
        return repr(value)
    return str(value)


def _check_int(value: int) -> int:
    if not INT_MIN <= value <= INT_MAX:
        raise VMError("Integer overflow")
    return value


def _check_float(value: float) -> float:
    if not math.isfinite(value):
        raise VMError("Floating-point overflow")
    return value


def _zero_message(opcode: OpCode) -> str:
    return "Division by zero" if opcode is OpCode.DIVIDE else "Modulo by zero"


def _int_arithmetic(opcode: OpCode, a: int, b: int) -> int:
    if opcode is OpCode.ADD:
        return _check_int(a + b)
    if opcode is OpCode.SUBTRACT:
        return _check_int(a - b)
    if opcode is OpCode.MULTIPLY:
        return _check_int(a * b)
    if b == 0:
        raise VMError(_zero_message(opcode))
    if opcode is OpCode.DIVIDE:  # truncates toward zero
        quotient = abs(a) // abs(b)
        return _check_int(-quotient if (a < 0) != (b < 0) else quotient)
    remainder = abs(a) % abs(b)  # MODULO: sign follows the dividend
    return -remainder if a < 0 else remainder


def _float_arithmetic(opcode: OpCode, a: float, b: float) -> float:
    if opcode is OpCode.ADD:
        return _check_float(a + b)
    if opcode is OpCode.SUBTRACT:
        return _check_float(a - b)
    if opcode is OpCode.MULTIPLY:
        return _check_float(a * b)
    if b == 0.0:
        raise VMError(_zero_message(opcode))
    if opcode is OpCode.DIVIDE:
        return _check_float(a / b)
    return math.fmod(a, b)


_ARITHMETIC = frozenset(
    {
        OpCode.ADD,
        OpCode.SUBTRACT,
        OpCode.MULTIPLY,
        OpCode.DIVIDE,
        OpCode.MODULO,
    }
)
_ORDERING = frozenset(
    {OpCode.LESS, OpCode.LESS_EQUAL, OpCode.GREATER, OpCode.GREATER_EQUAL}
)
_EQUALITY = frozenset({OpCode.EQUAL, OpCode.NOT_EQUAL})
_BINARY_OPS = _ARITHMETIC | _ORDERING | _EQUALITY


def _binary(opcode: OpCode, a: object, b: object) -> object:
    ta, tb = type(a), type(b)
    if opcode in _EQUALITY:
        if ta is not tb:
            raise VMError(f"Cannot compare {type_name(a)} with {type_name(b)}")
        return (a == b) if opcode is OpCode.EQUAL else (a != b)
    if opcode in _ORDERING:
        if ta is not tb or ta not in (int, float, str):
            raise VMError(f"Cannot order {type_name(a)} and {type_name(b)}")
        if opcode is OpCode.LESS:
            return a < b  # type: ignore[operator]
        if opcode is OpCode.LESS_EQUAL:
            return a <= b  # type: ignore[operator]
        if opcode is OpCode.GREATER:
            return a > b  # type: ignore[operator]
        return a >= b  # type: ignore[operator]
    if opcode is OpCode.ADD and ta is str and tb is str:
        return a + b  # type: ignore[operator]
    if ta is int and tb is int:
        return _int_arithmetic(opcode, a, b)  # type: ignore[arg-type]
    if ta is float and tb is float:
        return _float_arithmetic(opcode, a, b)  # type: ignore[arg-type]
    raise VMError(
        f"Operator {opcode.name} cannot be applied to {type_name(a)} and {type_name(b)}"
    )


class VirtualMachine:
    def __init__(
        self,
        program: BytecodeProgram,
        *,
        max_steps: int = 1_000_000,
        writer: Callable[[str], None] | None = None,
    ) -> None:
        if max_steps <= 0:
            raise ValueError("max_steps must be positive.")
        if program.local_count < 0:
            raise ValueError("local_count cannot be negative.")
        self.program = program
        self.max_steps = max_steps
        self._writer = writer
        self.stack: list[object] = []
        self.locals: list[object] = []

    def run(self) -> list[str]:
        """Execute the program and return the printed lines."""
        return list(self.execute().output)

    def execute(self) -> ExecutionResult:
        code = self.program.instructions
        size = len(code)
        self.stack = []
        self.locals = [_UNSET] * self.program.local_count
        output: list[str] = []
        pc = 0
        steps = 0
        at = 0
        try:
            while True:
                at = pc
                if not 0 <= pc < size:
                    raise VMError("Execution ran past the end of the program")
                if steps >= self.max_steps:
                    raise VMError(f"Instruction limit of {self.max_steps} exceeded")
                instruction = code[pc]
                pc += 1
                steps += 1
                opcode = instruction.opcode
                if opcode is OpCode.HALT:
                    break
                if opcode is OpCode.CONST:
                    self.stack.append(self._constant(instruction))
                elif opcode is OpCode.LOAD_LOCAL:
                    slot = self._slot(instruction)
                    value = self.locals[slot]
                    if value is _UNSET:
                        raise VMError(f"Read of uninitialised local slot {slot}")
                    self.stack.append(value)
                elif opcode is OpCode.STORE_LOCAL:
                    slot = self._slot(instruction)
                    self.locals[slot] = self._pop()
                elif opcode in _BINARY_OPS:
                    right = self._pop()
                    left = self._pop()
                    self.stack.append(_binary(opcode, left, right))
                elif opcode is OpCode.JUMP:
                    pc = self._target(instruction)
                elif opcode is OpCode.JUMP_IF_FALSE:
                    target = self._target(instruction)
                    condition = self._pop()
                    if type(condition) is not bool:
                        raise VMError(
                            f"Jump condition must be bool, got {type_name(condition)}"
                        )
                    if not condition:
                        pc = target
                elif opcode is OpCode.PRINT:
                    text = format_value(self._pop())
                    output.append(text)
                    if self._writer is not None:
                        self._writer(text)
                elif opcode is OpCode.POP:
                    self._pop()
                elif opcode is OpCode.DUP:
                    value = self._pop()
                    self.stack.append(value)
                    self.stack.append(value)
                elif opcode is OpCode.NEGATE:
                    self.stack.append(self._negate(self._pop()))
                elif opcode is OpCode.NOT:
                    value = self._pop()
                    if type(value) is not bool:
                        raise VMError(
                            f"Operator NOT requires bool, got {type_name(value)}"
                        )
                    self.stack.append(not value)
                elif opcode is OpCode.TO_FLOAT:
                    value = self._pop()
                    if type(value) is not int:
                        raise VMError(f"TO_FLOAT requires int, got {type_name(value)}")
                    self.stack.append(float(value))
                else:
                    raise VMError(f"Unknown opcode {opcode!r}")
        except VMError as error:
            if error.pc is None:
                error.pc = at
            raise
        return ExecutionResult(tuple(output), steps)

    # -- helpers ------------------------------------------------------

    def _pop(self) -> object:
        if not self.stack:
            raise VMError("Stack underflow")
        return self.stack.pop()

    def _constant(self, instruction: BytecodeInstruction) -> object:
        operand = instruction.operand
        if type(operand) not in (bool, int, float, str):
            raise VMError(f"CONST has unsupported operand {operand!r}")
        return operand

    def _slot(self, instruction: BytecodeInstruction) -> int:
        operand = instruction.operand
        if type(operand) is not int or not 0 <= operand < len(self.locals):
            raise VMError(
                f"{instruction.opcode.name} uses invalid local slot {operand!r}"
            )
        return operand

    def _target(self, instruction: BytecodeInstruction) -> int:
        operand = instruction.operand
        size = len(self.program.instructions)
        if type(operand) is not int or not 0 <= operand < size:
            raise VMError(f"Invalid jump target {operand!r}")
        return operand

    @staticmethod
    def _negate(value: object) -> object:
        if type(value) is int:
            return _check_int(-value)
        if type(value) is float:
            return -value
        raise VMError(f"Operator NEGATE requires a number, got {type_name(value)}")
