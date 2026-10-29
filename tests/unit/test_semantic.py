import pytest

from luma.lexer import Lexer
from luma.parser import Parser
from luma.semantic import SemanticAnalyzer


def analyze(source):
    tokens, lex_errors = Lexer(source).scan_tokens()
    assert not lex_errors
    program, parse_errors = Parser(tokens).parse()
    assert not parse_errors
    return SemanticAnalyzer().analyze(program)


def messages(source):
    return [error.message for error in analyze(source)]


def test_valid_integer_program():
    assert analyze("let x: int = 10; print(x + 2);") == []


def test_rejects_wrong_initializer_type():
    errors = analyze('let x: int = "hello";')
    assert len(errors) == 1
    assert "Cannot initialise" in errors[0].message
    assert errors[0].phase == "Semantic error"
    assert (errors[0].line, errors[0].column) == (1, 14)


def test_rejects_undefined_variable():
    errors = analyze("print(missing);")
    assert len(errors) == 1
    assert "Undefined variable 'missing'" in errors[0].message
    assert (errors[0].line, errors[0].column) == (1, 7)


def test_rejects_assignment_to_undefined_variable():
    assert any("Undefined variable" in m for m in messages("y = 1;"))


def test_rejects_non_boolean_condition():
    assert any("must be of type bool" in m for m in messages("if (42) { }"))
    assert any("must be of type bool" in m for m in messages("while (1.5) { }"))


def test_rejects_duplicate_declaration_in_same_scope():
    assert any("already declared" in m for m in messages("let x = 1; let x = 2;"))


def test_shadowing_in_inner_scope_is_allowed():
    assert analyze("let x = 1; { let x = true; print(x); } print(x + 1);") == []


def test_variable_is_not_visible_after_its_block():
    assert any("Undefined" in m for m in messages("{ let x = 1; } print(x);"))


def test_initializer_cannot_see_the_variable_being_declared():
    assert any("Undefined" in m for m in messages("let x = x + 1;"))


def test_int_converts_to_float_but_not_back():
    assert analyze("let f: float = 1; f = 2; print(f);") == []
    assert any("Cannot initialise" in m for m in messages("let i: int = 1.5;"))
    assert any("Cannot assign" in m for m in messages("let i: int = 1; i = 2.5;"))


def test_assignment_must_keep_declared_type():
    assert any("Cannot assign" in m for m in messages('let x = 1; x = "no";'))


def test_inferred_type_is_enforced_on_reassignment():
    assert analyze("let x = 1.5; x = 2.5;") == []
    assert any("Cannot assign" in m for m in messages("let x = true; x = 1;"))


def test_bool_is_not_an_int():
    assert any("Cannot initialise" in m for m in messages("let x: int = true;"))
    assert any("cannot be applied" in m for m in messages("print(true + 1);"))


@pytest.mark.parametrize(
    "source",
    [
        "print(1 + 2.5);",
        "print(1.5 * 2);",
        "print(7 / 2);",
        "print(7 % 2);",
        'print("a" + "b");',
        "print(1 < 2.5);",
        'print("a" < "b");',
        "print(1 == 1.0);",
        'print("a" == "b");',
        "print(true == false);",
        "print(true and false or true);",
        "print(not true);",
        "print(!false);",
        "print(-1);",
        "print(-1.5);",
    ],
)
def test_valid_operator_uses(source):
    assert analyze(source) == []


@pytest.mark.parametrize(
    "source",
    [
        'print("a" + 1);',
        'print("a" - "b");',
        'print("a" * 2);',
        "print(true < false);",
        'print(1 < "a");',
        'print(1 == "a");',
        "print(true == 1);",
        "print(1 and true);",
        "print(true or 1);",
        "print(not 1);",
        'print(-"a");',
        "print(-true);",
    ],
)
def test_invalid_operator_uses(source):
    errors = analyze(source)
    assert len(errors) == 1
    assert errors[0].phase == "Semantic error"


def test_errors_do_not_cascade():
    # One undefined variable must not also produce operator/initializer errors.
    errors = analyze("let x: int = missing + 1; print(x);")
    assert len(errors) == 1


def test_multiple_independent_errors_are_all_reported():
    errors = analyze('let a: int = "s"; print(b); if (1) { }')
    assert len(errors) == 3


def test_expression_types_are_recorded():
    tokens, _ = Lexer("let x = 1; print(x + 1.5);").scan_tokens()
    program, _ = Parser(tokens).parse()
    analyzer = SemanticAnalyzer()
    assert analyzer.analyze(program) == []
    recorded = set(analyzer.expression_types.values())
    assert recorded == {"int", "float"}
