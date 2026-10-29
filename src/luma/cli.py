"""Command-line interface: check, compile, disassemble and run Luma programs."""

import argparse
import sys
from pathlib import Path

from luma import __version__
from luma.compiler import CompilationResult, Compiler
from luma.disassembler import disassemble
from luma.errors import Diagnostic
from luma.ir import format_ir
from luma.vm import VirtualMachine, VMError

EXIT_OK = 0
EXIT_SOURCE_ERROR = 1  # the Luma program is invalid
EXIT_USAGE_ERROR = 2  # bad arguments or unreadable file
EXIT_RUNTIME_ERROR = 3  # the program failed while running


class SourceFileError(Exception):
    """Raised when a source file cannot be read."""


def _read_source(path: str) -> str:
    try:
        # utf-8-sig transparently drops the BOM some Windows editors add.
        return Path(path).read_text(encoding="utf-8-sig")
    except (OSError, UnicodeDecodeError) as exc:
        raise SourceFileError(f"Cannot read '{path}': {exc}") from exc


def _report(path: str, diagnostics: tuple[Diagnostic, ...]) -> None:
    for diagnostic in diagnostics:
        print(f"{path}: {diagnostic}", file=sys.stderr)


def _compile(path: str, source: str) -> CompilationResult | None:
    result = Compiler().compile(source)
    if not result.success:
        _report(path, result.diagnostics)
        return None
    return result


def _configure_streams() -> None:
    """Avoid UnicodeEncodeError on consoles that cannot show some characters."""
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            try:
                reconfigure(errors="replace")
            except (OSError, ValueError):
                pass


def _positive_int(text: str) -> int:
    try:
        value = int(text)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"invalid integer: {text!r}") from exc
    if value <= 0:
        raise argparse.ArgumentTypeError("must be a positive integer")
    return value


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="luma",
        description="Luma compiler and virtual machine",
    )
    parser.add_argument("--version", action="version", version=f"luma {__version__}")
    commands = parser.add_subparsers(dest="command", required=True)

    check = commands.add_parser("check", help="type-check a program without running it")
    check.add_argument("file")

    run = commands.add_parser("run", help="compile and run a program")
    run.add_argument("file")
    run.add_argument(
        "--max-steps",
        type=_positive_int,
        default=1_000_000,
        help="abort after this many VM instructions (default: 1000000)",
    )

    compile_ = commands.add_parser("compile", help="show generated IR or bytecode")
    compile_.add_argument("file")
    compile_.add_argument("--emit-ir", action="store_true", help="print the IR")
    compile_.add_argument(
        "--emit-bytecode",
        action="store_true",
        help="print the bytecode listing (default when no flag is given)",
    )

    disasm = commands.add_parser("disassemble", help="print the bytecode listing")
    disasm.add_argument("file")
    return parser


def main(argv: list[str] | None = None) -> int:
    _configure_streams()
    args = _build_parser().parse_args(argv)

    try:
        source = _read_source(args.file)
    except SourceFileError as exc:
        print(f"luma: error: {exc}", file=sys.stderr)
        return EXIT_USAGE_ERROR

    if args.command == "check":
        diagnostics = Compiler().check(source)
        if diagnostics:
            _report(args.file, diagnostics)
            return EXIT_SOURCE_ERROR
        print(f"{args.file}: no errors found")
        return EXIT_OK

    result = _compile(args.file, source)
    if result is None:
        return EXIT_SOURCE_ERROR
    assert result.bytecode is not None and result.ir is not None

    if args.command == "compile":
        emit_ir = args.emit_ir
        emit_bytecode = args.emit_bytecode or not args.emit_ir
        if emit_ir and emit_bytecode:
            print("== IR ==")
        if emit_ir:
            print(format_ir(result.ir))
        if emit_ir and emit_bytecode:
            print("== Bytecode ==")
        if emit_bytecode:
            print(disassemble(result.bytecode))
        return EXIT_OK

    if args.command == "disassemble":
        print(disassemble(result.bytecode))
        return EXIT_OK

    machine = VirtualMachine(result.bytecode, max_steps=args.max_steps, writer=print)
    try:
        machine.execute()
    except VMError as exc:
        print(f"{args.file}: Runtime error: {exc}", file=sys.stderr)
        return EXIT_RUNTIME_ERROR
    return EXIT_OK
