# CompilerLab — Luma

A from-scratch programming language implementation featuring a lexer, a
recursive-descent parser, an abstract syntax tree, semantic analysis with static
type checking, an intermediate representation, a bytecode compiler and a
stack-based virtual machine. Zero runtime dependencies, Python 3.12+.

## Project goals

CompilerLab explores the foundations of programming language implementation:
parsing, static type checking, control-flow translation, bytecode generation,
virtual machine execution and automated compiler testing.

**Luma** is the educational language implemented here. It is *not* a native-code
compiler and not a production language: programs are compiled to a custom
bytecode that runs on a virtual machine written in Python.

## Example

```
// examples/welcome.luma
let name: string = "CompilerLab";
let count: int = 3;

print("Welcome to " + name);

let i: int = 0;

while (i < count) {
    print(i);
    i = i + 1;
}
```

```
$ luma run examples/welcome.luma
Welcome to CompilerLab
0
1
2
```

Type errors are caught before anything runs:

```
$ luma check examples/invalid_type.luma
examples/invalid_type.luma: [line 1, column 16] Semantic error: Cannot initialise variable 'age' of type int with a value of type string
```

More programs are in [`examples/`](examples/): `hello`, `control_flow`,
`fizzbuzz`, `floats`, `scopes` and `short_circuit`.

## Features

- Static types: `int` (64-bit), `float`, `bool`, `string`, with implicit
  `int` → `float` conversion only
- Variables with declaration, reassignment, type inference and nested block
  scopes with shadowing
- Arithmetic, comparison and logical expressions; `and`/`or` short-circuit
- `if` / `else` / `else if`, `while`, blocks, `print`
- Diagnostics with phase, line and column; the pipeline stops at the first phase
  that reports errors, and invalid programs are never executed
- IR and bytecode with validators; a VM with controlled runtime errors and an
  instruction limit
- CLI: `check`, `run`, `compile`, `disassemble`

## Compiler architecture

```
Source (.luma) → Lexer → Parser → Semantic analysis → IR generation
              → Bytecode compiler → Virtual machine → Output
```

1. Lexical analysis (`lexer.py`)
2. Syntax analysis and AST construction (`parser.py`, `ast.py`)
3. Semantic analysis and type checking (`semantic.py`)
4. Intermediate representation (`ir.py`, `ir_generator.py`)
5. Bytecode compilation (`bytecode.py`, `bytecode_compiler.py`)
6. Virtual machine execution (`vm.py`)

See [`docs/architecture.md`](docs/architecture.md) for design decisions and the
bytecode reference, and [`docs/language-spec.md`](docs/language-spec.md) for the
formal language definition (grammar, types, operator semantics, errors).

## Requirements

- Python 3.12 or newer
- No runtime dependencies. Development tools (pytest, pytest-cov, ruff, mypy) are
  installed with the `dev` extra.

## Installation

```
python -m pip install -e ".[dev]"
```

This installs the `luma` command. If your shell cannot find it, use
`python -m luma` instead.

## Usage

```
luma check examples/hello.luma                      # type-check only
luma run examples/hello.luma                        # compile and run
luma run program.luma --max-steps 5000000           # change the instruction limit
luma compile examples/hello.luma --emit-ir          # show the IR
luma compile examples/hello.luma --emit-bytecode    # show the bytecode
luma disassemble examples/hello.luma                # same as --emit-bytecode
```

Exit codes: `0` success, `1` the program has compile-time errors, `2` usage error
or unreadable file, `3` runtime error.

## Testing

```
python -m pytest -q
python -m pytest --cov=src/luma --cov-report=term-missing
python -m ruff check src tests
python -m ruff format --check src tests
```

The suite contains unit tests per compiler stage, integration tests for the whole
pipeline and CLI, differential and fuzz-style tests, and regression tests for
every example program. See [`docs/testing.md`](docs/testing.md).

## Benchmark

```
python benchmarks/benchmark.py
```

Measures the compile pipeline and VM execution of one small loop program and
writes `benchmarks/results.json` with the Python version and platform. The numbers
describe only the machine they were measured on, and a single micro-benchmark
says nothing about how Luma compares with other languages.

## Current limitations

- No functions, arrays, classes, modules, input or `for` loops (see the
  specification, section 9)
- The VM is interpreted by Python and is not designed to be fast
- Local variable slots are never reused
- No optimisation passes

## Roadmap

- Functions, call frames and `return`
- Slot reuse and simple optimisations (constant folding) on the IR
- A larger benchmark suite with documented methodology
- More precise error recovery and multi-line diagnostics

## Contributing

See [`CONTRIBUTING.md`](CONTRIBUTING.md).

## License

MIT. See [`LICENSE`](LICENSE).
