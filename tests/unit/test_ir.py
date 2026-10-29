import pytest

from luma.ir import (
    IRError,
    IRProgram,
    Instruction,
    Label,
    format_ir,
    validate_ir,
)
from luma.ir_generator import IRGenerator
from luma.lexer import Lexer
from luma.parser import Parser
from luma.semantic import SemanticAnalyzer


def generate(source):
    tokens, _ = Lexer(source).scan_tokens()
    program, errors = Parser(tokens).parse()
    assert errors == []
    analyzer = SemanticAnalyzer()
    assert analyzer.analyze(program) == []
    generator = IRGenerator(analyzer.expression_types)
    return generator.generate(program), generator


def opcodes(ir):
    return [item.opcode for item in ir.items if isinstance(item, Instruction)]


def operands_of(ir, opcode):
    return [
        item.operands[0]
        for item in ir.items
        if isinstance(item, Instruction) and item.opcode == opcode
    ]


def test_simple_program_ir():
    ir, generator = generate("let x: int = 10; print(x + 2);")
    assert format_ir(ir) == "\n".join(
        [
            "    CONST 10",
            "    STORE_LOCAL 0",
            "    LOAD_LOCAL 0",
            "    CONST 2",
            "    ADD",
            "    PRINT",
        ]
    )
    assert generator.local_count == 1
    assert ir.local_count == 1
    assert validate_ir(ir) == []


def test_slots_are_not_reused_after_a_block():
    ir, generator = generate("{ let a = 1; } { let b = 2; } let c = 3;")
    assert generator.local_count == 3
    stores = operands_of(ir, "STORE_LOCAL")
    assert stores == [0, 1, 2]


def test_shadowing_uses_distinct_slots():
    ir, generator = generate("let x = 1; { let x = 2; print(x); } print(x);")
    loads = operands_of(ir, "LOAD_LOCAL")
    assert loads == [1, 0]
    assert generator.local_count == 2


def test_if_else_labels_are_unique_and_defined():
    ir, _ = generate("if (true) { print(1); } else { print(2); } if (false) { }")
    labels = [item.name for item in ir.items if isinstance(item, Label)]
    assert len(labels) == len(set(labels)) == 4
    assert validate_ir(ir) == []


def test_while_loop_structure():
    ir, _ = generate("let i = 0; while (i < 3) { i = i + 1; }")
    text = format_ir(ir)
    assert "while_0:" in text and "endwhile_1:" in text
    assert "JUMP_IF_FALSE endwhile_1" in text
    assert "JUMP while_0" in text


def test_int_is_converted_when_stored_in_float():
    ir, _ = generate("let f: float = 1;")
    assert opcodes(ir) == ["CONST", "TO_FLOAT", "STORE_LOCAL"]


def test_mixed_arithmetic_converts_only_the_int_operand():
    ir, _ = generate("print(1 + 2.5);")
    assert opcodes(ir) == ["CONST", "TO_FLOAT", "CONST", "ADD", "PRINT"]
    ir, _ = generate("print(2.5 + 1);")
    assert opcodes(ir) == ["CONST", "CONST", "TO_FLOAT", "ADD", "PRINT"]


def test_no_conversion_when_types_match():
    ir, _ = generate("print(1 + 2); print(1.5 + 2.5);")
    assert "TO_FLOAT" not in opcodes(ir)


def test_and_or_use_short_circuit_jumps():
    ir, _ = generate("print(true and false);")
    assert opcodes(ir) == ["CONST", "DUP", "JUMP_IF_FALSE", "POP", "CONST", "PRINT"]
    ir, _ = generate("print(true or false);")
    assert opcodes(ir) == [
        "CONST",
        "DUP",
        "NOT",
        "JUMP_IF_FALSE",
        "POP",
        "CONST",
        "PRINT",
    ]


def test_expression_statement_pops_its_value():
    ir, _ = generate("1 + 2;")
    assert opcodes(ir)[-1] == "POP"


def test_generator_rejects_missing_type_information():
    tokens, _ = Lexer("let x = 1;").scan_tokens()
    program, _ = Parser(tokens).parse()
    with pytest.raises(IRError):
        IRGenerator({}).generate(program)


def test_validator_detects_duplicate_labels():
    program = IRProgram((Label("a"), Label("a")))
    assert any("Duplicate label" in p for p in validate_ir(program))


def test_validator_detects_undefined_jump_target():
    program = IRProgram((Instruction("JUMP", (Label("nowhere"),)),))
    assert any("undefined label" in p for p in validate_ir(program))


def test_validator_detects_bad_slot_unknown_opcode_and_operand_count():
    program = IRProgram(
        (
            Instruction("STORE_LOCAL", (5,)),
            Instruction("FROBNICATE"),
            Instruction("ADD", (1,)),
            Instruction("CONST", (None,)),
        ),
        local_count=1,
    )
    problems = validate_ir(program)
    assert any("invalid slot" in p for p in problems)
    assert any("Unknown IR opcode" in p for p in problems)
    assert any("takes 0 operand" in p for p in problems)
    assert any("CONST operand" in p for p in problems)
