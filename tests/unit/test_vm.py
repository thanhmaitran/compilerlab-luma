import pytest

from luma.bytecode import BytecodeInstruction, BytecodeProgram, OpCode
from luma.vm import VirtualMachine, VMError, format_value


def program(*instructions, local_count=0):
    return BytecodeProgram(tuple(instructions), local_count)


def ins(opcode, operand=None):
    return BytecodeInstruction(opcode, operand)


def run(*instructions, local_count=0, **options):
    bytecode = program(*instructions, ins(OpCode.HALT), local_count=local_count)
    return VirtualMachine(bytecode, **options).run()


def binary(opcode, left, right):
    return run(
        ins(OpCode.CONST, left),
        ins(OpCode.CONST, right),
        ins(opcode),
        ins(OpCode.PRINT),
    )


def test_halt_returns_execution_result():
    bytecode = program(
        ins(OpCode.CONST, 42),
        ins(OpCode.PRINT),
        ins(OpCode.HALT),
    )
    result = VirtualMachine(bytecode).execute()
    assert result.output == ("42",)
    assert result.instructions_executed == 3


def test_vm_rejects_boolean_arithmetic():
    bytecode = program(
        ins(OpCode.CONST, True),
        ins(OpCode.CONST, 1),
        ins(OpCode.ADD),
        ins(OpCode.HALT),
    )
    with pytest.raises(VMError):
        VirtualMachine(bytecode).execute()


def test_arithmetic_on_ints():
    assert binary(OpCode.ADD, 2, 3) == ["5"]
    assert binary(OpCode.SUBTRACT, 2, 3) == ["-1"]
    assert binary(OpCode.MULTIPLY, 4, 5) == ["20"]


def test_integer_division_truncates_toward_zero():
    assert binary(OpCode.DIVIDE, 7, 2) == ["3"]
    assert binary(OpCode.DIVIDE, -7, 2) == ["-3"]
    assert binary(OpCode.DIVIDE, 7, -2) == ["-3"]
    assert binary(OpCode.DIVIDE, -7, -2) == ["3"]


def test_modulo_takes_sign_of_dividend():
    assert binary(OpCode.MODULO, 7, 3) == ["1"]
    assert binary(OpCode.MODULO, -7, 3) == ["-1"]
    assert binary(OpCode.MODULO, 7, -3) == ["1"]
    assert binary(OpCode.MODULO, -7, -3) == ["-1"]


def test_float_arithmetic_and_formatting():
    assert binary(OpCode.ADD, 1.5, 2.25) == ["3.75"]
    assert binary(OpCode.DIVIDE, 1.0, 4.0) == ["0.25"]
    assert binary(OpCode.MODULO, -7.5, 2.0) == ["-1.5"]
    assert binary(OpCode.MULTIPLY, 2.0, 3.0) == ["6.0"]


def test_division_and_modulo_by_zero():
    for opcode in (OpCode.DIVIDE, OpCode.MODULO):
        for zero in (0, 0.0):
            with pytest.raises(VMError, match="by zero"):
                binary(opcode, zero + 1, zero)


def test_string_concatenation_and_comparison():
    assert binary(OpCode.ADD, "ab", "cd") == ["abcd"]
    assert binary(OpCode.LESS, "a", "b") == ["true"]
    assert binary(OpCode.EQUAL, "a", "a") == ["true"]


def test_comparisons():
    assert binary(OpCode.LESS, 1, 2) == ["true"]
    assert binary(OpCode.LESS_EQUAL, 2, 2) == ["true"]
    assert binary(OpCode.GREATER, 1, 2) == ["false"]
    assert binary(OpCode.GREATER_EQUAL, 1, 2) == ["false"]
    assert binary(OpCode.EQUAL, 1, 2) == ["false"]
    assert binary(OpCode.NOT_EQUAL, 1, 2) == ["true"]
    assert binary(OpCode.EQUAL, True, True) == ["true"]


def test_mixed_operand_types_are_rejected():
    with pytest.raises(VMError):
        binary(OpCode.ADD, 1, 1.5)
    with pytest.raises(VMError):
        binary(OpCode.EQUAL, 1, 1.0)
    with pytest.raises(VMError):
        binary(OpCode.LESS, True, False)
    with pytest.raises(VMError):
        binary(OpCode.ADD, "a", 1)


def test_integer_overflow_is_a_runtime_error():
    with pytest.raises(VMError, match="overflow"):
        binary(OpCode.ADD, 2**63 - 1, 1)
    with pytest.raises(VMError, match="overflow"):
        binary(OpCode.MULTIPLY, 2**62, 2)
    with pytest.raises(VMError, match="overflow"):
        binary(OpCode.DIVIDE, -(2**63), -1)


def test_float_overflow_is_a_runtime_error():
    with pytest.raises(VMError, match="overflow"):
        binary(OpCode.MULTIPLY, 1e308, 10.0)


def test_negate_not_and_to_float():
    assert run(ins(OpCode.CONST, 5), ins(OpCode.NEGATE), ins(OpCode.PRINT)) == ["-5"]
    negated = run(ins(OpCode.CONST, 1.5), ins(OpCode.NEGATE), ins(OpCode.PRINT))
    assert negated == ["-1.5"]
    assert run(ins(OpCode.CONST, True), ins(OpCode.NOT), ins(OpCode.PRINT)) == ["false"]
    assert run(ins(OpCode.CONST, 3), ins(OpCode.TO_FLOAT), ins(OpCode.PRINT)) == ["3.0"]
    with pytest.raises(VMError):
        run(ins(OpCode.CONST, 1), ins(OpCode.NOT))
    with pytest.raises(VMError):
        run(ins(OpCode.CONST, "x"), ins(OpCode.NEGATE))
    with pytest.raises(VMError):
        run(ins(OpCode.CONST, 1.5), ins(OpCode.TO_FLOAT))
    with pytest.raises(VMError, match="overflow"):
        run(ins(OpCode.CONST, -(2**63)), ins(OpCode.NEGATE))


def test_locals_store_and_load():
    output = run(
        ins(OpCode.CONST, 7),
        ins(OpCode.STORE_LOCAL, 0),
        ins(OpCode.LOAD_LOCAL, 0),
        ins(OpCode.LOAD_LOCAL, 0),
        ins(OpCode.ADD),
        ins(OpCode.PRINT),
        local_count=1,
    )
    assert output == ["14"]


def test_reading_uninitialised_local_fails():
    with pytest.raises(VMError, match="uninitialised"):
        run(ins(OpCode.LOAD_LOCAL, 0), ins(OpCode.POP), local_count=1)


def test_invalid_local_slot_fails():
    with pytest.raises(VMError, match="invalid local slot"):
        run(ins(OpCode.LOAD_LOCAL, 3), local_count=1)
    with pytest.raises(VMError, match="invalid local slot"):
        run(ins(OpCode.CONST, 1), ins(OpCode.STORE_LOCAL, -1), local_count=1)


def test_dup_and_pop():
    assert run(
        ins(OpCode.CONST, 9),
        ins(OpCode.DUP),
        ins(OpCode.PRINT),
        ins(OpCode.PRINT),
    ) == ["9", "9"]
    assert run(ins(OpCode.CONST, 9), ins(OpCode.POP)) == []


def test_jump_and_conditional_jump():
    output = run(
        ins(OpCode.JUMP, 2),
        ins(OpCode.CONST, "skipped"),
        ins(OpCode.CONST, False),
        ins(OpCode.JUMP_IF_FALSE, 6),
        ins(OpCode.CONST, "not taken"),
        ins(OpCode.PRINT),
        ins(OpCode.CONST, "end"),
        ins(OpCode.PRINT),
    )
    assert output == ["end"]


def test_jump_if_false_requires_bool():
    with pytest.raises(VMError, match="must be bool"):
        run(ins(OpCode.CONST, 0), ins(OpCode.JUMP_IF_FALSE, 0))


def test_invalid_jump_target_fails():
    with pytest.raises(VMError, match="Invalid jump target"):
        run(ins(OpCode.JUMP, 99))
    with pytest.raises(VMError, match="Invalid jump target"):
        run(ins(OpCode.JUMP))


def test_stack_underflow_fails():
    with pytest.raises(VMError, match="underflow"):
        run(ins(OpCode.ADD))
    with pytest.raises(VMError, match="underflow"):
        run(ins(OpCode.POP))
    with pytest.raises(VMError, match="underflow"):
        run(ins(OpCode.CONST, 1), ins(OpCode.ADD))


def test_running_off_the_end_fails():
    bytecode = program(ins(OpCode.CONST, 1), ins(OpCode.POP))
    with pytest.raises(VMError, match="past the end"):
        VirtualMachine(bytecode).execute()


def test_unsupported_constant_fails():
    with pytest.raises(VMError, match="unsupported operand"):
        run(ins(OpCode.CONST, None))


def test_instruction_limit_stops_infinite_loops():
    bytecode = program(ins(OpCode.JUMP, 0), ins(OpCode.HALT))
    with pytest.raises(VMError, match="Instruction limit of 50 exceeded"):
        VirtualMachine(bytecode, max_steps=50).execute()


def test_error_message_includes_instruction_address():
    bytecode = program(ins(OpCode.CONST, 1), ins(OpCode.CONST, 0), ins(OpCode.DIVIDE))
    with pytest.raises(VMError) as info:
        VirtualMachine(bytecode).execute()
    assert info.value.pc == 2
    assert str(info.value) == "Division by zero (at instruction 0002)"


def test_writer_receives_output_as_it_is_printed():
    seen = []
    bytecode = program(
        ins(OpCode.CONST, 1),
        ins(OpCode.PRINT),
        ins(OpCode.CONST, 1),
        ins(OpCode.CONST, 0),
        ins(OpCode.DIVIDE),
    )
    with pytest.raises(VMError):
        VirtualMachine(bytecode, writer=seen.append).execute()
    assert seen == ["1"]


def test_vm_can_be_executed_twice_with_fresh_state():
    bytecode = program(ins(OpCode.CONST, 1), ins(OpCode.PRINT), ins(OpCode.HALT))
    machine = VirtualMachine(bytecode)
    assert machine.run() == ["1"]
    assert machine.run() == ["1"]


def test_constructor_validates_arguments():
    with pytest.raises(ValueError):
        VirtualMachine(program(ins(OpCode.HALT)), max_steps=0)
    with pytest.raises(ValueError):
        VirtualMachine(BytecodeProgram((ins(OpCode.HALT),), -1))


def test_format_value():
    assert format_value(True) == "true"
    assert format_value(False) == "false"
    assert format_value(3) == "3"
    assert format_value(2.0) == "2.0"
    assert format_value("text") == "text"
