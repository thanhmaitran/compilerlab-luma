import pytest

from luma.compiler import Compiler
from luma.vm import VirtualMachine, VMError


def execute(source, **options):
    result = Compiler().compile(source)
    assert result.success, [str(error) for error in result.diagnostics]
    return VirtualMachine(result.bytecode, **options).run()


def diagnostics(source):
    result = Compiler().compile(source)
    assert not result.success
    assert result.bytecode is None and result.ir is None
    return list(result.diagnostics)


def test_arithmetic_pipeline():
    assert execute("print(2 + 3 * 4);") == ["14"]


def test_variable_pipeline():
    source = """
    let x: int = 10;
    let y: int = 20;
    print(x + y);
    """
    assert execute(source) == ["30"]


def test_if_else_pipeline():
    source = """
    let x: int = 5;
    if (x > 3) {
        print("big");
    } else {
        print("small");
    }
    if (x > 10) {
        print("huge");
    } else {
        print("not huge");
    }
    """
    assert execute(source) == ["big", "not huge"]


def test_if_without_else():
    assert execute("if (false) { print(1); } print(2);") == ["2"]


def test_while_pipeline():
    source = """
    let i: int = 0;
    let total: int = 0;
    while (i < 5) {
        total = total + i;
        i = i + 1;
    }
    print(total);
    """
    assert execute(source) == ["10"]


def test_nested_loops_and_blocks():
    source = """
    let i = 0;
    let count = 0;
    while (i < 3) {
        let j = 0;
        while (j < 3) {
            if (i != j) { count = count + 1; }
            j = j + 1;
        }
        i = i + 1;
    }
    print(count);
    """
    assert execute(source) == ["6"]


def test_loop_body_declaration_is_reinitialised_each_iteration():
    source = """
    let i = 0;
    while (i < 3) {
        let doubled = i * 2;
        print(doubled);
        i = i + 1;
    }
    """
    assert execute(source) == ["0", "2", "4"]


def test_scoping_and_shadowing():
    source = """
    let x = 1;
    {
        let x = 2;
        x = x + 10;
        print(x);
    }
    print(x);
    """
    assert execute(source) == ["12", "1"]


def test_string_operations():
    assert execute('print("Hello, " + "world");') == ["Hello, world"]
    assert execute('print("a" < "b");') == ["true"]
    assert execute('print("tab\\there");') == ["tab\there"]


def test_bool_printing_and_logic():
    assert execute("print(true and false); print(true or false);") == [
        "false",
        "true",
    ]
    assert execute("print(not true); print(!false);") == ["false", "true"]


def test_int_to_float_conversion_on_declaration_and_assignment():
    source = """
    let f: float = 3;
    print(f);
    f = 4;
    print(f);
    """
    assert execute(source) == ["3.0", "4.0"]


def test_mixed_int_float_arithmetic_and_comparison():
    assert execute("print(1 + 2.5);") == ["3.5"]
    assert execute("print(2.5 * 2);") == ["5.0"]
    assert execute("print(1 == 1.0);") == ["true"]
    assert execute("print(1 < 1.5);") == ["true"]
    assert execute("let x: float = 1; print(x + 1);") == ["2.0"]


def test_division_semantics():
    assert execute("print(7 / 2);") == ["3"]
    assert execute("print(-7 / 2);") == ["-3"]
    assert execute("print(7 / 2.0);") == ["3.5"]
    assert execute("print(7 % 3); print(-7 % 3);") == ["1", "-1"]


def test_unary_minus_and_precedence():
    assert execute("print(-2 * 3);") == ["-6"]
    assert execute("print(2 - -3);") == ["5"]
    assert execute("print(-(1 + 2));") == ["-3"]


def test_and_or_short_circuit_avoids_runtime_error():
    assert execute("print(false and (1 / 0 > 0));") == ["false"]
    assert execute("print(true or (1 / 0 > 0));") == ["true"]
    with pytest.raises(VMError):
        execute("print(true and (1 / 0 > 0));")


def test_short_circuit_skips_side_effect_free_right_operand_only():
    source = """
    let calls = 0;
    let r = false and (calls == calls);
    print(r);
    """
    assert execute(source) == ["false"]


def test_expression_statement_leaves_stack_balanced():
    assert execute("1 + 2; print(3);") == ["3"]


def test_empty_program():
    assert execute("") == []
    assert execute("// only a comment") == []


def test_result_exposes_ir_and_bytecode():
    result = Compiler().compile("print(1);")
    assert result.success
    assert result.ir is not None and result.bytecode is not None
    assert result.bytecode.instructions[-1].opcode.name == "HALT"


def test_lexical_error_stops_compilation():
    found = diagnostics('let x = "oops;')
    assert [d.phase for d in found] == ["Lexical error"]
    assert (found[0].line, found[0].column) == (1, 9)


def test_syntax_error_stops_compilation():
    found = diagnostics("let x = 1\nprint(x);")
    assert [d.phase for d in found] == ["Syntax error"]


def test_semantic_error_stops_compilation():
    found = diagnostics('let x: int = "no";')
    assert [d.phase for d in found] == ["Semantic error"]


def test_semantic_analysis_is_not_run_on_a_broken_parse():
    found = diagnostics("let x = ; print(missing);")
    assert [d.phase for d in found] == ["Syntax error"]


def test_check_reports_front_end_errors_only():
    compiler = Compiler()
    assert compiler.check("print(1);") == ()
    assert len(compiler.check("print(missing);")) == 1


def test_runtime_errors_are_vm_errors_not_python_exceptions():
    with pytest.raises(VMError, match="Division by zero"):
        execute("print(1 / 0);")
    with pytest.raises(VMError, match="Modulo by zero"):
        execute("print(1 % 0);")
    with pytest.raises(VMError, match="overflow"):
        execute("let x = 9223372036854775807; print(x + 1);")


def test_infinite_loop_hits_instruction_limit():
    with pytest.raises(VMError, match="Instruction limit"):
        execute("while (true) { }", max_steps=1000)


def test_deeply_nested_source_reports_diagnostic_instead_of_crashing():
    source = "print(" + "(" * 5000 + "1" + ")" * 5000 + ");"
    result = Compiler().compile(source)
    assert not result.success
    assert "nested too deeply" in str(result.diagnostics[0])
