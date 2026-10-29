"""Human-readable listing of bytecode."""

from luma.bytecode import BytecodeProgram


def disassemble(program: BytecodeProgram) -> str:
    lines = []
    for index, instruction in enumerate(program.instructions):
        if instruction.operand is None:
            lines.append(f"{index:04d} {instruction.opcode.name}")
        else:
            lines.append(
                f"{index:04d} {instruction.opcode.name} {instruction.operand!r}"
            )
    return "\n".join(lines)
