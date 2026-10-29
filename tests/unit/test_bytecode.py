import pytest

from luma.bytecode import (
    BytecodeError,
    BytecodeInstruction,
    BytecodeProgram,
    OpCode,
    validate_bytecode,
)
from luma.bytecode_compiler import compile_ir
from luma.disassembler import disassemble
from luma.ir import IRError, Instruction, IRProgram, Label


def ins(opcode, operand=None):
    return BytecodeInstruction(opcode, operand)


def program(*instructions, local_count=0):
    return BytecodeProgram(tuple(instructions), local_count)


def test_compile_resolves_labels_to_addresses():
    ir = IRProgram(
        (
            Instruction("CONST", (True,)),
            Instruction("JUMP_IF_FALSE", (Label("end"),)),
            Instruction("CONST", (1,)),
            Instruction("PRINT"),
            Label("end"),
        )
    )
    bytecode = compile_ir(ir)
    assert [i.opcode for i in bytecode.instructions] == [
        OpCode.CONST,
        OpCode.JUMP_IF_FALSE,
        OpCode.CONST,
        OpCode.PRINT,
        OpCode.HALT,
    ]
    assert bytecode.instructions[1].operand == 4  # the label points at HALT


def test_backward_jump_for_loops():
    ir = IRProgram(
        (
            Label("top"),
            Instruction("CONST", (False,)),
            Instruction("JUMP_IF_FALSE", (Label("done"),)),
            Instruction("JUMP", (Label("top"),)),
            Label("done"),
        )
    )
    bytecode = compile_ir(ir)
    assert bytecode.instructions[1].operand == 3
    assert bytecode.instructions[2].operand == 0


def test_compile_takes_local_count_from_argument_or_ir():
    ir = IRProgram((Instruction("CONST", (1,)), Instruction("STORE_LOCAL", (1,))), 2)
    assert compile_ir(ir).local_count == 2
    assert compile_ir(ir, 5).local_count == 5


def test_compile_rejects_invalid_ir():
    with pytest.raises(IRError):
        compile_ir(IRProgram((Instruction("JUMP", (Label("x"),)),)))
    with pytest.raises(IRError):
        compile_ir(IRProgram((Instruction("STORE_LOCAL", (0,)),), 0))


def test_compile_rejects_stack_underflow_in_ir():
    with pytest.raises(BytecodeError):
        compile_ir(IRProgram((Instruction("ADD"),)))


def test_disassembler_formats_addresses_and_operands():
    text = disassemble(
        program(ins(OpCode.CONST, "hi"), ins(OpCode.PRINT), ins(OpCode.HALT))
    )
    assert text == "0000 CONST 'hi'\n0001 PRINT\n0002 HALT"


def test_valid_program_has_no_problems():
    assert validate_bytecode(program(ins(OpCode.HALT))) == []


def test_empty_program_is_invalid():
    assert validate_bytecode(program()) == ["Program is empty"]


def test_missing_and_unexpected_operands():
    problems = validate_bytecode(
        program(ins(OpCode.CONST), ins(OpCode.POP, 3), ins(OpCode.HALT))
    )
    assert any("missing its operand" in p for p in problems)
    assert any("must not have an operand" in p for p in problems)


def test_jump_target_out_of_range():
    problems = validate_bytecode(program(ins(OpCode.JUMP, 9), ins(OpCode.HALT)))
    assert any("invalid jump target" in p for p in problems)


def test_local_slot_out_of_range():
    problems = validate_bytecode(
        program(ins(OpCode.CONST, 1), ins(OpCode.STORE_LOCAL, 0), ins(OpCode.HALT))
    )
    assert any("invalid local slot" in p for p in problems)


def test_unsupported_constant():
    problems = validate_bytecode(program(ins(OpCode.CONST, [1]), ins(OpCode.HALT)))
    assert any("unsupported constant" in p for p in problems)


def test_stack_underflow_detected_statically():
    problems = validate_bytecode(program(ins(OpCode.ADD), ins(OpCode.HALT)))
    assert any("stack underflow" in p for p in problems)


def test_falling_off_the_end_is_detected():
    problems = validate_bytecode(program(ins(OpCode.CONST, 1), ins(OpCode.POP)))
    assert any("falls off the end" in p for p in problems)


def test_value_left_on_stack_at_halt_is_detected():
    problems = validate_bytecode(program(ins(OpCode.CONST, 1), ins(OpCode.HALT)))
    assert any("HALT with 1 value" in p for p in problems)


def test_branches_that_rejoin_with_equal_depth_are_valid():
    problems = validate_bytecode(
        program(
            ins(OpCode.CONST, True),
            ins(OpCode.JUMP_IF_FALSE, 4),
            ins(OpCode.CONST, 1),
            ins(OpCode.POP),
            ins(OpCode.HALT),
        )
    )
    assert problems == []


def test_inconsistent_stack_depth_at_join_is_detected():
    problems = validate_bytecode(
        program(
            ins(OpCode.CONST, True),
            ins(OpCode.JUMP_IF_FALSE, 4),
            ins(OpCode.CONST, 1),
            ins(OpCode.JUMP, 4),
            ins(OpCode.POP),
            ins(OpCode.HALT),
        )
    )
    assert any("inconsistent stack depth" in p for p in problems)
