"""Run every program in examples/ and compare against its known output.

If an example that used to work breaks, that is a regression: fix the compiler,
and add a focused test for the underlying cause.
"""

import contextlib
import io
from pathlib import Path

from luma.cli import main

EXAMPLES = Path(__file__).resolve().parents[2] / "examples"

EXPECTED = {
    "hello.luma": ["Hello from Luma", "30"],
    "control_flow.luma": ["10"],
    "welcome.luma": ["Welcome to CompilerLab", "0", "1", "2"],
    "fizzbuzz.luma": [
        "1",
        "2",
        "Fizz",
        "4",
        "Buzz",
        "Fizz",
        "7",
        "8",
        "Fizz",
        "Buzz",
        "11",
        "Fizz",
        "13",
        "14",
        "FizzBuzz",
    ],  # fmt: skip
    "floats.luma": ["14.0", "3", "3.5", "-1", "true"],
    "scopes.luma": ["2", "12", "1"],
    "short_circuit.luma": ["short-circuit works"],
}


def run_example(name):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = main(["run", str(EXAMPLES / name)])
    return code, out.getvalue().splitlines(), err.getvalue()


def test_every_valid_example_has_an_expectation():
    on_disk = {path.name for path in EXAMPLES.glob("*.luma")}
    assert on_disk == set(EXPECTED) | {"invalid_type.luma"}


def test_valid_examples_produce_expected_output():
    for name, expected in EXPECTED.items():
        code, lines, err = run_example(name)
        assert (code, err) == (0, ""), name
        assert lines == expected, name


def test_invalid_example_is_rejected_before_execution():
    code, lines, err = run_example("invalid_type.luma")
    assert code == 1
    assert lines == []
    assert "Semantic error" in err


def test_examples_all_pass_check():
    for name in EXPECTED:
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            assert main(["check", str(EXAMPLES / name)]) == 0
