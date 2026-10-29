# Testing strategy

```
tests/
├── unit/          one file per compiler stage
├── integration/   whole pipeline, CLI, fuzz-style tests
└── regression/    every program in examples/ with its known output
```

Run everything:

```
python -m pytest -q
python -m pytest --cov=src/luma --cov-report=term-missing
```

## Layers

- **Unit tests** exercise each stage in isolation: token positions and longest
  match in the lexer; precedence, associativity and error recovery in the parser;
  every typing rule in the semantic analyzer; label and slot handling in the IR;
  jump resolution and static validation in the bytecode compiler; every opcode
  and every runtime fault in the VM.
- **Integration tests** compile and run real programs end to end, check that each
  error is reported by the *correct phase* with a line and column, that invalid
  programs are never executed, and that the CLI uses the documented exit codes
  and never prints a Python traceback.
- **Differential tests** (`test_fuzz.py`) generate random integer and boolean
  expressions and compare Luma's result with a small reference evaluator written
  in the test. This covers truncating division, sign-of-dividend modulo,
  overflow and short-circuit evaluation.
- **Robustness tests** feed random token sequences, mutated example programs and
  random Unicode text through the whole pipeline. The only acceptable outcomes
  are diagnostics or a `VMError`; any other exception fails the test. All random
  generators use fixed seeds, so failures are reproducible.
- **Regression tests** run every file in `examples/` and compare the output.
  When a bug is fixed, add a focused test that reproduces it.

## Error-path matrix

| Stage | Covered cases |
| --- | --- |
| Lexer | invalid character, unterminated string, invalid escape, lone `&` or pipe character, out-of-range literals, CRLF |
| Parser | missing `;`, unbalanced `)`, missing operand, unclosed block, unknown type, invalid assignment target, multi-error recovery, stray `}` |
| Semantic | undefined variable, duplicate declaration, wrong initializer/assignment type, non-bool condition, every invalid operator use, error cascading |
| IR | duplicate labels, undefined labels, bad slots, unknown opcodes, operand counts |
| Bytecode | missing/extra operands, jump out of range, bad slots, stack underflow, fall-through, inconsistent stack depth |
| VM | underflow, division/modulo by zero, overflow, type mismatches, uninitialised locals, bad jumps, instruction limit |
| CLI | missing file, directory, non-UTF-8 file, BOM, compile errors, runtime errors, usage errors |

## Coverage

Coverage is a tool for finding code that no test reaches, not proof of
correctness. Use `--cov-report=term-missing`, then write tests with meaningful
assertions for the uncovered lines.
