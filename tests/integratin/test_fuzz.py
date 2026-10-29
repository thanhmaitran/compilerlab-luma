"""Seeded, deterministic fuzz-style tests.

1. Differential testing: random integer/boolean expressions are evaluated both
   by Luma (compiler + VM) and by a tiny reference evaluator written here.
2. Robustness: random and mutated programs must only ever produce diagnostics
   or ``VMError``, never an internal Python exception.
"""

import random
from pathlib import Path

import pytest

from luma.compiler import Compiler
from luma.vm import INT_MAX, INT_MIN, VirtualMachine, VMError

EXAMPLES = Path(__file__).resolve().parents[2] / "examples"


# -- reference semantics ------------------------------------------------


def _check(value):
    if not INT_MIN <= value <= INT_MAX:
        raise OverflowError
    return value


def _div(a, b):
    if b == 0:
        raise ZeroDivisionError
    quotient = abs(a) // abs(b)
    return _check(-quotient if (a < 0) != (b < 0) else quotient)


def _mod(a, b):
    if b == 0:
        raise ZeroDivisionError
    remainder = abs(a) % abs(b)
    return -remainder if a < 0 else remainder


INT_OPS = {
    "+": lambda a, b: _check(a + b),
    "-": lambda a, b: _check(a - b),
    "*": lambda a, b: _check(a * b),
    "/": _div,
    "%": _mod,
}
CMP_OPS = {
    "<": lambda a, b: a < b,
    "<=": lambda a, b: a <= b,
    ">": lambda a, b: a > b,
    ">=": lambda a, b: a >= b,
    "==": lambda a, b: a == b,
    "!=": lambda a, b: a != b,
}


def gen_int(rng, depth):
    if depth == 0 or rng.random() < 0.25:
        return ("lit", rng.randint(0, 30))
    if rng.random() < 0.15:
        return ("neg", gen_int(rng, depth - 1))
    op = rng.choice(list(INT_OPS))
    return ("bin", op, gen_int(rng, depth - 1), gen_int(rng, depth - 1))


def gen_bool(rng, depth):
    if depth == 0 or rng.random() < 0.3:
        if rng.random() < 0.5:
            return ("blit", rng.random() < 0.5)
        op = rng.choice(list(CMP_OPS))
        return ("cmp", op, gen_int(rng, 2), gen_int(rng, 2))
    if rng.random() < 0.2:
        return ("not", gen_bool(rng, depth - 1))
    op = rng.choice(["and", "or"])
    return (op, gen_bool(rng, depth - 1), gen_bool(rng, depth - 1))


def source_of(node):
    kind = node[0]
    if kind == "lit":
        return str(node[1])
    if kind == "blit":
        return "true" if node[1] else "false"
    if kind == "neg":
        return f"(-{source_of(node[1])})"
    if kind == "not":
        return f"(not {source_of(node[1])})"
    if kind == "bin" or kind == "cmp":
        return f"({source_of(node[2])} {node[1]} {source_of(node[3])})"
    return f"({source_of(node[1])} {kind} {source_of(node[2])})"


def evaluate(node):
    kind = node[0]
    if kind in ("lit", "blit"):
        return node[1]
    if kind == "neg":
        return _check(-evaluate(node[1]))
    if kind == "not":
        return not evaluate(node[1])
    if kind == "bin":
        left = evaluate(node[2])
        return INT_OPS[node[1]](left, evaluate(node[3]))
    if kind == "cmp":
        left = evaluate(node[2])
        return CMP_OPS[node[1]](left, evaluate(node[3]))
    if kind == "and":
        return evaluate(node[1]) and evaluate(node[2])
    return evaluate(node[1]) or evaluate(node[2])


def luma_result(source):
    result = Compiler().compile(f"print({source});")
    assert result.success, [str(d) for d in result.diagnostics]
    return VirtualMachine(result.bytecode).run()


def check_against_reference(node):
    source = source_of(node)
    try:
        expected = evaluate(node)
    except ZeroDivisionError:
        with pytest.raises(VMError, match="by zero"):
            luma_result(source)
        return
    except OverflowError:
        with pytest.raises(VMError, match="overflow"):
            luma_result(source)
        return
    if isinstance(expected, bool):
        text = "true" if expected else "false"
    else:
        text = str(expected)
    assert luma_result(source) == [text], source


def test_random_integer_expressions_match_reference():
    rng = random.Random(1234)
    for _ in range(400):
        check_against_reference(gen_int(rng, 4))


def test_random_boolean_expressions_match_reference():
    rng = random.Random(5678)
    for _ in range(400):
        check_against_reference(gen_bool(rng, 4))


# -- robustness ---------------------------------------------------------

VOCABULARY = [
    "let", "print", "if", "else", "while", "true", "false", "and", "or", "not",
    "x", "y", "int", "float", "bool", "string", "1", "2.5", '"s"', "(", ")",
    "{", "}", ":", ";", ",", "+", "-", "*", "/", "%", "!", "!=", "=", "==",
    "<", "<=", ">", ">=", "//", "@", '"', "\n",
]  # fmt: skip


def never_crashes(source):
    result = Compiler().compile(source)
    if result.success:
        try:
            VirtualMachine(result.bytecode, max_steps=2000).execute()
        except VMError:
            pass
    else:
        assert result.diagnostics
        for diagnostic in result.diagnostics:
            assert str(diagnostic)


def test_random_token_soup_never_crashes():
    rng = random.Random(42)
    for _ in range(500):
        words = [rng.choice(VOCABULARY) for _ in range(rng.randint(0, 25))]
        never_crashes(" ".join(words))


def test_mutated_example_programs_never_crash():
    rng = random.Random(99)
    sources = [path.read_text(encoding="utf-8") for path in EXAMPLES.glob("*.luma")]
    assert sources
    for _ in range(600):
        chars = list(rng.choice(sources))
        for _ in range(rng.randint(1, 4)):
            position = rng.randrange(len(chars) + 1)
            action = rng.choice(["delete", "insert", "replace"])
            if action == "delete" and chars:
                del chars[min(position, len(chars) - 1)]
            elif action == "insert":
                chars.insert(position, rng.choice(VOCABULARY))
            elif chars:
                chars[min(position, len(chars) - 1)] = rng.choice(VOCABULARY)
        never_crashes("".join(chars))


def test_random_bytes_as_text_never_crash():
    rng = random.Random(7)
    for _ in range(200):
        text = "".join(chr(rng.randint(0, 0x2FF)) for _ in range(rng.randint(0, 40)))
        never_crashes(text)
