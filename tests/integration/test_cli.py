import contextlib
import io
from pathlib import Path

import pytest

from luma import __version__
from luma.cli import (
    EXIT_OK,
    EXIT_RUNTIME_ERROR,
    EXIT_SOURCE_ERROR,
    EXIT_USAGE_ERROR,
    main,
)

EXAMPLES = Path(__file__).resolve().parents[2] / "examples"


def invoke(*argv):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = main(list(argv))
    return code, out.getvalue(), err.getvalue()


def write(tmp_path, name, text):
    path = tmp_path / name
    path.write_text(text, encoding="utf-8")
    return str(path)


def test_run_hello_example():
    code, out, err = invoke("run", str(EXAMPLES / "hello.luma"))
    assert code == EXIT_OK
    assert out == "Hello from Luma\n30\n"
    assert err == ""


def test_check_valid_program():
    code, out, err = invoke("check", str(EXAMPLES / "hello.luma"))
    assert code == EXIT_OK
    assert "no errors found" in out
    assert err == ""


def test_check_invalid_program_reports_semantic_error_and_does_not_run():
    code, out, err = invoke("check", str(EXAMPLES / "invalid_type.luma"))
    assert code == EXIT_SOURCE_ERROR
    assert out == ""
    assert "Semantic error" in err and "[line 1, column 16]" in err
    assert "Traceback" not in err


def test_run_invalid_program_does_not_execute_it():
    code, out, err = invoke("run", str(EXAMPLES / "invalid_type.luma"))
    assert code == EXIT_SOURCE_ERROR
    assert out == ""
    assert "Semantic error" in err


def test_missing_file_gives_friendly_error():
    code, out, err = invoke("run", str(EXAMPLES / "does-not-exist.luma"))
    assert code == EXIT_USAGE_ERROR
    assert out == ""
    assert err.startswith("luma: error: Cannot read")
    assert "Traceback" not in err


def test_directory_instead_of_file_is_reported():
    code, _, err = invoke("run", str(EXAMPLES))
    assert code == EXIT_USAGE_ERROR
    assert "Cannot read" in err


def test_non_utf8_file_is_reported(tmp_path):
    path = tmp_path / "bad.luma"
    path.write_bytes(b"print(\xff\xfe);")
    code, _, err = invoke("run", str(path))
    assert code == EXIT_USAGE_ERROR
    assert "Cannot read" in err


def test_utf8_bom_is_accepted(tmp_path):
    path = tmp_path / "bom.luma"
    path.write_bytes(b"\xef\xbb\xbfprint(1);")
    code, out, _ = invoke("run", str(path))
    assert code == EXIT_OK and out == "1\n"


def test_compile_emit_ir():
    code, out, _ = invoke("compile", str(EXAMPLES / "hello.luma"), "--emit-ir")
    assert code == EXIT_OK
    assert "STORE_LOCAL 0" in out and "HALT" not in out


def test_compile_emit_bytecode_and_default():
    path = str(EXAMPLES / "hello.luma")
    code, explicit, _ = invoke("compile", path, "--emit-bytecode")
    assert code == EXIT_OK
    assert explicit.splitlines()[0] == "0000 CONST 'Luma'"
    assert explicit.rstrip().endswith("HALT")
    assert invoke("compile", path)[1] == explicit
    assert invoke("disassemble", path)[1] == explicit


def test_compile_both_flags_prints_headed_sections():
    code, out, _ = invoke(
        "compile", str(EXAMPLES / "hello.luma"), "--emit-ir", "--emit-bytecode"
    )
    assert code == EXIT_OK
    assert "== IR ==" in out and "== Bytecode ==" in out


def test_runtime_error_exit_code_and_partial_output(tmp_path):
    path = write(tmp_path, "boom.luma", "print(1);\nprint(1 / 0);\n")
    code, out, err = invoke("run", path)
    assert code == EXIT_RUNTIME_ERROR
    assert out == "1\n"
    assert "Runtime error: Division by zero" in err
    assert "Traceback" not in err


def test_max_steps_option(tmp_path):
    path = write(tmp_path, "loop.luma", "while (true) { }\n")
    code, _, err = invoke("run", path, "--max-steps", "500")
    assert code == EXIT_RUNTIME_ERROR
    assert "Instruction limit of 500 exceeded" in err


def test_invalid_max_steps_is_a_usage_error(tmp_path):
    path = write(tmp_path, "ok.luma", "print(1);")
    with pytest.raises(SystemExit) as info:
        invoke("run", path, "--max-steps", "0")
    assert info.value.code == 2


def test_syntax_error_output(tmp_path):
    path = write(tmp_path, "bad.luma", "let x = 1\nprint(x);\n")
    code, _, err = invoke("check", path)
    assert code == EXIT_SOURCE_ERROR
    assert "Syntax error" in err and "[line 2, column 1]" in err


def test_lexical_error_output(tmp_path):
    path = write(tmp_path, "bad.luma", "let x = 1 @ 2;\n")
    code, _, err = invoke("run", path)
    assert code == EXIT_SOURCE_ERROR
    assert "Lexical error" in err


def test_no_command_is_a_usage_error():
    with pytest.raises(SystemExit) as info:
        invoke()
    assert info.value.code == 2


def test_version_flag():
    out = io.StringIO()
    with contextlib.redirect_stdout(out), pytest.raises(SystemExit) as info:
        main(["--version"])
    assert info.value.code == 0
    assert out.getvalue().strip() == f"luma {__version__}"
