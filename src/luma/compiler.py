"""Compiler facade: source text -> bytecode, running every front-end phase."""

from dataclasses import dataclass

from luma.ast import Program
from luma.bytecode import BytecodeError, BytecodeProgram
from luma.bytecode_compiler import compile_ir
from luma.errors import Diagnostic
from luma.ir import IRError, IRProgram
from luma.ir_generator import IRGenerator
from luma.lexer import Lexer
from luma.parser import Parser
from luma.semantic import LuType, SemanticAnalyzer

_INTERNAL = "Internal compiler error"
_TOO_DEEP = Diagnostic(
    "Compile error", "Program is nested too deeply to be compiled", 0, 0
)


@dataclass(frozen=True, slots=True)
class CompilationResult:
    bytecode: BytecodeProgram | None
    ir: IRProgram | None
    diagnostics: tuple[Diagnostic, ...]

    @property
    def success(self) -> bool:
        return self.bytecode is not None and not self.diagnostics


class Compiler:
    def check(self, source: str) -> tuple[Diagnostic, ...]:
        """Run the front end (lexer, parser, semantic analysis) only."""
        try:
            _, _, diagnostics = self._front_end(source)
        except RecursionError:
            return (_TOO_DEEP,)
        return tuple(diagnostics)

    def compile(self, source: str) -> CompilationResult:
        """Compile ``source``. Any diagnostic stops the pipeline early."""
        try:
            program, types, diagnostics = self._front_end(source)
            if diagnostics:
                return CompilationResult(None, None, tuple(diagnostics))
            assert program is not None
            generator = IRGenerator(types)
            ir = generator.generate(program)
            bytecode = compile_ir(ir, generator.local_count)
        except RecursionError:
            return CompilationResult(None, None, (_TOO_DEEP,))
        except (IRError, BytecodeError) as error:
            diagnostic = Diagnostic(_INTERNAL, str(error), 0, 0)
            return CompilationResult(None, None, (diagnostic,))
        return CompilationResult(bytecode, ir, ())

    @staticmethod
    def _front_end(
        source: str,
    ) -> tuple[Program | None, dict[int, LuType], list[Diagnostic]]:
        tokens, lexer_errors = Lexer(source).scan_tokens()
        if lexer_errors:
            return None, {}, lexer_errors
        program, parser_errors = Parser(tokens).parse()
        if parser_errors:
            return None, {}, parser_errors
        analyzer = SemanticAnalyzer()
        semantic_errors = analyzer.analyze(program)
        return program, analyzer.expression_types, semantic_errors
