"""Recursive-descent parser: tokens -> AST."""

from collections.abc import Callable

from luma.ast import (
    AssignStmt,
    Binary,
    BlockStmt,
    Expr,
    ExprStmt,
    IfStmt,
    LetStmt,
    Literal,
    PrintStmt,
    Program,
    Stmt,
    Unary,
    Variable,
    WhileStmt,
)
from luma.errors import Diagnostic
from luma.tokens import Token, TokenType

_PHASE = "Syntax error"

TYPE_NAMES = ("int", "float", "bool", "string")

# Tokens at which error recovery may resume parsing.
_SYNC_TOKENS = frozenset(
    {
        TokenType.LET,
        TokenType.PRINT,
        TokenType.IF,
        TokenType.WHILE,
        TokenType.LEFT_BRACE,
        TokenType.RIGHT_BRACE,
    }
)


class _ParseError(Exception):
    """Internal signal used to unwind to the nearest recovery point."""


def _describe(token: Token) -> str:
    if token.type is TokenType.EOF:
        return "end of file"
    return f"'{token.lexeme}'"


class Parser:
    def __init__(self, tokens: list[Token]) -> None:
        if not tokens or tokens[-1].type is not TokenType.EOF:
            raise ValueError("Token list must end with an EOF token.")
        self.tokens = tokens
        self.current = 0
        self.errors: list[Diagnostic] = []

    def parse(self) -> tuple[Program, list[Diagnostic]]:
        statements: list[Stmt] = []
        while not self._at_end():
            before = self.current
            try:
                statements.append(self._declaration())
            except _ParseError:
                self._synchronize()
                if self.current == before:
                    self._advance()  # always make progress
        return Program(tuple(statements)), self.errors

    # -- statements ---------------------------------------------------

    def _declaration(self) -> Stmt:
        if self._match(TokenType.LET):
            return self._let_declaration(self._previous())
        return self._statement()

    def _let_declaration(self, keyword: Token) -> LetStmt:
        name = self._consume(TokenType.IDENTIFIER, "Expected variable name")
        annotation: str | None = None
        if self._match(TokenType.COLON):
            type_token = self._consume(
                TokenType.IDENTIFIER, "Expected a type name after ':'"
            )
            annotation = type_token.lexeme
            if annotation not in TYPE_NAMES:
                self._record(
                    type_token,
                    f"Unknown type '{annotation}' "
                    "(expected int, float, bool or string)",
                )
        self._consume(TokenType.EQUAL, "Expected '=' in variable declaration")
        initializer = self._expression()
        self._consume(TokenType.SEMICOLON, "Expected ';' after variable declaration")
        return LetStmt(
            name.lexeme, annotation, initializer, keyword.line, keyword.column
        )

    def _statement(self) -> Stmt:
        token = self._peek()
        if self._match(TokenType.PRINT):
            return self._print_statement(token)
        if self._match(TokenType.IF):
            return self._if_statement(token)
        if self._match(TokenType.WHILE):
            return self._while_statement(token)
        if token.type is TokenType.LEFT_BRACE:
            return self._block("Expected '{'")
        if (
            token.type is TokenType.IDENTIFIER
            and self._peek_next().type is TokenType.EQUAL
        ):
            return self._assignment()
        return self._expression_statement()

    def _print_statement(self, keyword: Token) -> PrintStmt:
        self._consume(TokenType.LEFT_PAREN, "Expected '(' after 'print'")
        expression = self._expression()
        self._consume(TokenType.RIGHT_PAREN, "Expected ')' after expression")
        self._consume(TokenType.SEMICOLON, "Expected ';' after print statement")
        return PrintStmt(expression, keyword.line, keyword.column)

    def _if_statement(self, keyword: Token) -> IfStmt:
        self._consume(TokenType.LEFT_PAREN, "Expected '(' after 'if'")
        condition = self._expression()
        self._consume(TokenType.RIGHT_PAREN, "Expected ')' after condition")
        then_branch = self._block("Expected '{' before 'if' body")
        else_branch: BlockStmt | None = None
        if self._match(TokenType.ELSE):
            if self._check(TokenType.IF):
                nested = self._peek()
                inner = self._statement()  # `else if` is sugar for a nested if
                else_branch = BlockStmt((inner,), nested.line, nested.column)
            else:
                else_branch = self._block("Expected '{' after 'else'")
        return IfStmt(condition, then_branch, else_branch, keyword.line, keyword.column)

    def _while_statement(self, keyword: Token) -> WhileStmt:
        self._consume(TokenType.LEFT_PAREN, "Expected '(' after 'while'")
        condition = self._expression()
        self._consume(TokenType.RIGHT_PAREN, "Expected ')' after condition")
        body = self._block("Expected '{' before 'while' body")
        return WhileStmt(condition, body, keyword.line, keyword.column)

    def _block(self, message: str) -> BlockStmt:
        brace = self._consume(TokenType.LEFT_BRACE, message)
        statements: list[Stmt] = []
        while not self._check(TokenType.RIGHT_BRACE) and not self._at_end():
            before = self.current
            try:
                statements.append(self._declaration())
            except _ParseError:
                self._synchronize()
                if self.current == before:
                    self._advance()
        self._consume(TokenType.RIGHT_BRACE, "Expected '}' after block")
        return BlockStmt(tuple(statements), brace.line, brace.column)

    def _assignment(self) -> AssignStmt:
        name = self._advance()
        self._advance()  # '='
        value = self._expression()
        self._consume(TokenType.SEMICOLON, "Expected ';' after assignment")
        return AssignStmt(name.lexeme, value, name.line, name.column)

    def _expression_statement(self) -> ExprStmt:
        start = self._peek()
        expression = self._expression()
        if self._check(TokenType.EQUAL):
            raise self._error(self._peek(), "Invalid assignment target")
        self._consume(TokenType.SEMICOLON, "Expected ';' after expression")
        return ExprStmt(expression, start.line, start.column)

    # -- expressions --------------------------------------------------

    def _expression(self) -> Expr:
        return self._or()

    def _left_assoc(
        self,
        operand: Callable[[], Expr],
        operators: tuple[TokenType, ...],
    ) -> Expr:
        expression = operand()
        while self._match(*operators):
            operator = self._previous()
            right = operand()
            expression = Binary(
                expression,
                operator.lexeme,
                right,
                operator.line,
                operator.column,
            )
        return expression

    def _or(self) -> Expr:
        return self._left_assoc(self._and, (TokenType.OR,))

    def _and(self) -> Expr:
        return self._left_assoc(self._equality, (TokenType.AND,))

    def _equality(self) -> Expr:
        return self._left_assoc(
            self._comparison, (TokenType.EQUAL_EQUAL, TokenType.BANG_EQUAL)
        )

    def _comparison(self) -> Expr:
        return self._left_assoc(
            self._term,
            (
                TokenType.LESS,
                TokenType.LESS_EQUAL,
                TokenType.GREATER,
                TokenType.GREATER_EQUAL,
            ),
        )

    def _term(self) -> Expr:
        return self._left_assoc(self._factor, (TokenType.PLUS, TokenType.MINUS))

    def _factor(self) -> Expr:
        return self._left_assoc(
            self._unary, (TokenType.STAR, TokenType.SLASH, TokenType.PERCENT)
        )

    def _unary(self) -> Expr:
        if self._match(TokenType.MINUS, TokenType.BANG, TokenType.NOT):
            operator = self._previous()
            operand = self._unary()
            symbol = "-" if operator.type is TokenType.MINUS else "not"
            return Unary(symbol, operand, operator.line, operator.column)
        return self._primary()

    def _primary(self) -> Expr:
        token = self._peek()
        if self._match(TokenType.INTEGER, TokenType.FLOAT, TokenType.STRING):
            value = token.literal
            assert isinstance(value, int | float | str)
            return Literal(value, token.line, token.column)
        if self._match(TokenType.TRUE):
            return Literal(True, token.line, token.column)
        if self._match(TokenType.FALSE):
            return Literal(False, token.line, token.column)
        if self._match(TokenType.IDENTIFIER):
            return Variable(token.lexeme, token.line, token.column)
        if self._match(TokenType.LEFT_PAREN):
            expression = self._expression()
            self._consume(TokenType.RIGHT_PAREN, "Expected ')' after expression")
            return expression
        raise self._error(token, "Expected expression")

    # -- helpers ------------------------------------------------------

    def _record(self, token: Token, message: str) -> None:
        self.errors.append(Diagnostic(_PHASE, message, token.line, token.column))

    def _error(self, token: Token, message: str) -> _ParseError:
        if message.startswith("Expected"):
            message = f"{message}, found {_describe(token)}"
        self._record(token, message)
        return _ParseError()

    def _consume(self, token_type: TokenType, message: str) -> Token:
        if self._check(token_type):
            return self._advance()
        raise self._error(self._peek(), message)

    def _synchronize(self) -> None:
        if not self._at_end() and self._peek().type not in _SYNC_TOKENS:
            self._advance()
        while not self._at_end():
            if self._previous().type is TokenType.SEMICOLON:
                return
            if self._peek().type in _SYNC_TOKENS:
                return
            self._advance()

    def _match(self, *token_types: TokenType) -> bool:
        if self._peek().type in token_types:
            self._advance()
            return True
        return False

    def _check(self, token_type: TokenType) -> bool:
        return self._peek().type is token_type

    def _advance(self) -> Token:
        if not self._at_end():
            self.current += 1
        return self._previous()

    def _at_end(self) -> bool:
        return self._peek().type is TokenType.EOF

    def _peek(self) -> Token:
        return self.tokens[self.current]

    def _peek_next(self) -> Token:
        return self.tokens[min(self.current + 1, len(self.tokens) - 1)]

    def _previous(self) -> Token:
        return self.tokens[self.current - 1]
