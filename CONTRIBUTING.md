# Contributing to CompilerLab

Thanks for your interest! CompilerLab is a small educational project, so the
bar for a contribution is simple: it must be correct, tested and documented.

## Development setup

```powershell
git clone <your-fork-url> compilerlab
cd compilerlab
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
```

On Linux or macOS use `python3 -m venv .venv && source .venv/bin/activate`.

## Before opening a pull request

Run the same checks as CI:

```
python -m ruff format src tests benchmarks
python -m ruff check src tests benchmarks
python -m mypy src/luma
python -m pytest --cov=src/luma --cov-report=term-missing
```

## Guidelines

- Add or update tests for every behaviour change. A bug fix starts with a
  failing regression test.
- Do not weaken or delete a test to make it pass; find out whether the code,
  the environment or the test's expectation is wrong.
- Language semantics are defined in `docs/language-spec.md`. If you change the
  language, change the spec, the implementation and the tests together.
- Keep the runtime free of third-party dependencies (`dependencies = []`).
- Only document features that exist and have been verified.

## Commit messages

Use short, imperative subject lines, for example `Fix jump target for empty else`.
