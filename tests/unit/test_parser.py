import pytest

from luma.ast import (
    AssignStmt,
    Binary,
    BlockStmt,
    ExprStmt,
    IfStmt,
    LetStmt,
    Literal,
    PrintStmt,
    Unary,
    Variable,
    WhileStmt,
)
from luma.lexer import Lexer
from luma.parser import Parser


def parse(source):
    tokens, lex_errors = Lexer(source).scan_tokens()
    assert not lex_errors
    program, parse_errors = Parser(tokens).parse()
    return program, parse_errors


def only_expression(source):
    program, errors = parse(source)
    assert errors == []
    statement = program.statements[0]
    assert isinstance(statement, ExprStmt | PrintStmt)
    return statement.expression


def test_parses_variable_declaration():
    program, errors = parse("let x: int = 42;")
    assert errors == []
    assert len(program.statements) == 1
    statement = program.statements[0]
    assert isinstance(statement, LetStmt)
    assert statement.name == "x"
    assert statement.annotation == "int"
    assert statement.initializer == Literal(42, 1, 14)


def test_declaration_without_annotation():
    program, errors = parse("let x = 1.5;")
    assert errors == []
    assert program.statements[0].annotation is None


def test_multiplication_has_higher_precedence():
    expression = only_expression("print(2 + 3 * 4);")
    assert isinstance(expression, Binary)
    assert expression.operator == "+"
    assert isinstance(expression.right, Binary)
    assert expression.right.operator == "*"


def test_parentheses_override_precedence():
    expression = only_expression("print((2 + 3) * 4);")
    assert expression.operator == "*"
    assert expression.left.operator == "+"


def test_binary_operators_are_left_associative():
    expression = only_expression("print(10 - 4 - 3);")
    assert expression.operator == "-"
    assert isinstance(expression.left, Binary)
    assert expression.left.operator == "-"
    assert expression.right == Literal(3, 1, 16)


def test_logical_precedence_and_over_or():
    expression = only_expression("print(a or b and c);")
    assert expression.operator == "or"
    assert expression.right.operator == "and"


def test_comparison_binds_tighter_than_equality():
    expression = only_expression("print(a < b == c < d);")
    assert expression.operator == "=="
    assert expression.left.operator == "<"
    assert expression.right.operator == "<"


def test_unary_operators_normalise_bang_to_not():
    bang = only_expression("print(!flag);")
    word = only_expression("print(not flag);")
    assert isinstance(bang, Unary) and bang.operator == "not"
    assert isinstance(word, Unary) and word.operator == "not"
    minus = only_expression("print(--x);")
    assert minus.operator == "-" and minus.operand.operator == "-"


def test_assignment_and_expression_statement():
    program, errors = parse("x = 1; x + 1;")
    assert errors == []
    assert isinstance(program.statements[0], AssignStmt)
    assert isinstance(program.statements[1], ExprStmt)
    assert isinstance(program.statements[1].expression, Binary)
    assert program.statements[0].value == Literal(1, 1, 5)


def test_if_else_and_while_blocks():
    program, errors = parse(
        "if (a) { print(1); } else { print(2); } while (b) { b = false; }"
    )
    assert errors == []
    if_statement, while_statement = program.statements
    assert isinstance(if_statement, IfStmt)
    assert isinstance(if_statement.then_branch, BlockStmt)
    assert if_statement.else_branch is not None
    assert isinstance(while_statement, WhileStmt)
    assert isinstance(while_statement.condition, Variable)


def test_else_if_is_sugar_for_nested_if():
    program, errors = parse("if (a) { } else if (b) { } else { }")
    assert errors == []
    outer = program.statements[0]
    assert isinstance(outer.else_branch.statements[0], IfStmt)


def test_standalone_block_statement():
    program, errors = parse("{ let x = 1; { print(x); } }")
    assert errors == []
    block = program.statements[0]
    assert isinstance(block, BlockStmt)
    assert isinstance(block.statements[1], BlockStmt)


def test_missing_semicolon_reports_position_and_token():
    _, errors = parse("let x = 1\nprint(x);")
    assert len(errors) == 1
    assert errors[0].phase == "Syntax error"
    assert "Expected ';'" in errors[0].message
    assert "'print'" in errors[0].message
    assert (errors[0].line, errors[0].column) == (2, 1)


def test_unbalanced_parenthesis():
    _, errors = parse("print((1 + 2);")
    assert len(errors) == 1
    assert "Expected ')'" in errors[0].message


def test_missing_operand():
    _, errors = parse("let x = 1 + ;")
    assert len(errors) == 1
    assert "Expected expression" in errors[0].message
    assert (errors[0].line, errors[0].column) == (1, 13)


def test_unexpected_end_of_file_mentions_eof():
    _, errors = parse("print(1")
    assert len(errors) == 1
    assert "end of file" in errors[0].message


def test_unclosed_block_at_eof():
    _, errors = parse("while (true) { print(1);")
    assert len(errors) == 1
    assert "Expected '}'" in errors[0].message


def test_unknown_type_annotation():
    _, errors = parse("let x: integer = 1;")
    assert len(errors) == 1
    assert "Unknown type 'integer'" in errors[0].message


def test_invalid_assignment_target():
    _, errors = parse("1 + 2 = 3;")
    assert len(errors) == 1
    assert "Invalid assignment target" in errors[0].message


def test_recovery_reports_multiple_independent_errors():
    _, errors = parse("let = 1;\nprint(2);\nlet y = ;\nprint(3);")
    assert [error.line for error in errors] == [1, 3]


def test_recovery_inside_block_keeps_parsing_after_it():
    program, errors = parse("{ let x = ; print(1); }\nlet ok = 2;")
    assert len(errors) == 1
    assert isinstance(program.statements[-1], LetStmt)
    assert program.statements[-1].name == "ok"


def test_missing_semicolon_before_closing_brace_keeps_block_intact():
    program, errors = parse("{ print(1) }\nprint(2);")
    assert len(errors) == 1
    assert isinstance(program.statements[-1], PrintStmt)


def test_stray_closing_brace_terminates():
    _, errors = parse("}")
    assert len(errors) == 1


@pytest.mark.parametrize(
    "source",
    ["(", ")", "{", "}", "let", "let x", "let x =", "if", "if (", "while", "print"],
)
def test_truncated_input_never_hangs_or_crashes(source):
    _, errors = parse(source)
    assert errors


def test_parser_requires_eof_token():
    with pytest.raises(ValueError):
        Parser([])
