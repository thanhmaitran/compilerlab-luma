"""Bytecode compiler: IR -> bytecode (labels resolved to addresses)."""

from luma.bytecode import (
    BytecodeError,
    BytecodeInstruction,
    BytecodeProgram,
    OpCode,
    validate_bytecode,
)
from luma.ir import Instruction, IRError, IRProgram, Label, validate_ir

IR_TO_OPCODE = {
    "CONST": OpCode.CONST,
    "LOAD_LOCAL": OpCode.LOAD_LOCAL,
    "STORE_LOCAL": OpCode.STORE_LOCAL,
    "ADD": OpCode.ADD,
    "SUBTRACT": OpCode.SUBTRACT,
    "MULTIPLY": OpCode.MULTIPLY,
    "DIVIDE": OpCode.DIVIDE,
    "MODULO": OpCode.MODULO,
    "NEGATE": OpCode.NEGATE,
    "NOT": OpCode.NOT,
    "EQUAL": OpCode.EQUAL,
    "NOT_EQUAL": OpCode.NOT_EQUAL,
    "LESS": OpCode.LESS,
    "LESS_EQUAL": OpCode.LESS_EQUAL,
    "GREATER": OpCode.GREATER,
    "GREATER_EQUAL": OpCode.GREATER_EQUAL,
    "TO_FLOAT": OpCode.TO_FLOAT,
    "DUP": OpCode.DUP,
    "PRINT": OpCode.PRINT,
    "POP": OpCode.POP,
    "JUMP": OpCode.JUMP,
    "JUMP_IF_FALSE": OpCode.JUMP_IF_FALSE,
}


def compile_ir(program: IRProgram, local_count: int | None = None) -> BytecodeProgram:
    """Compile validated IR to bytecode and append the final ``HALT``.

    ``local_count`` defaults to ``program.local_count``; pass it explicitly to
    override (for example when taking it from ``IRGenerator.local_count``).
    """
    count = program.local_count if local_count is None else local_count
    problems = validate_ir(IRProgram(program.items, count))
    if problems:
        raise IRError("Invalid IR: " + "; ".join(problems))

    # Pass 1: labels do not occupy space; they name the next instruction.
    labels: dict[str, int] = {}
    address = 0
    for item in program.items:
        if isinstance(item, Label):
            labels[item.name] = address
        else:
            address += 1

    # Pass 2: emit instructions, resolving jump targets.
    instructions: list[BytecodeInstruction] = []
    for item in program.items:
        if isinstance(item, Label):
            continue
        instructions.append(_translate(item, labels))
    instructions.append(BytecodeInstruction(OpCode.HALT))

    result = BytecodeProgram(tuple(instructions), count)
    problems = validate_bytecode(result)
    if problems:
        raise BytecodeError("Invalid bytecode: " + "; ".join(problems))
    return result


def _translate(item: Instruction, labels: dict[str, int]) -> BytecodeInstruction:
    opcode = IR_TO_OPCODE[item.opcode]
    if not item.operands:
        return BytecodeInstruction(opcode)
    operand = item.operands[0]
    if isinstance(operand, Label):
        operand = labels[operand.name]
    return BytecodeInstruction(opcode, operand)
