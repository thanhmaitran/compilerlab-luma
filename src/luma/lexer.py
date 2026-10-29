"""Lexical analysis: characters -> tokens."""

from luma.errors import Diagnostic
from luma.tokens import Token, TokenType

_PHASE = "Lexical error"


class Lexer:
    KEYWORDS: dict[str, TokenType] = {
        "let": TokenType.LET,
        "print": TokenType.PRINT,
        "if": TokenType.IF,
        "else": TokenType.ELSE,
        "while": TokenType.WHILE,
        "true": TokenType.TRUE,
        "false": TokenType.FALSE,
        "and": TokenType.AND,
        "or": TokenType.OR,
        "not": TokenType.NOT,
    }

    SINGLE_CHAR_TOKENS: dict[str, TokenType] = {
        "(": TokenType.LEFT_PAREN,
        ")": TokenType.RIGHT_PAREN,
        "{": TokenType.LEFT_BRACE,
        "}": TokenType.RIGHT_BRACE,
        ":": TokenType.COLON,
        ";": TokenType.SEMICOLON,
        ",": TokenType.COMMA,
        "+": TokenType.PLUS,
        "-": TokenType.MINUS,
        "*": TokenType.STAR,
        "%": TokenType.PERCENT,
    }

    ESCAPES: dict[str, str] = {
        '"': '"',
        "\\": "\\",
        "n": "\n",
        "t": "\t",
        "r": "\r",
    }

    MAX_INT = 2**63 - 1

    def __init__(self, source: str) -> None:
        self.source = source
        self.tokens: list[Token] = []
        self.errors: list[Diagnostic] = []
        self.start = 0
        self.current = 0
        self.line = 1
        self.line_start = 0
        self._token_line = 1
        self._token_column = 1

    def scan_tokens(self) -> tuple[list[Token], list[Diagnostic]]:
        while not self._at_end():
            self.start = self.current
            self._token_line = self.line
            self._token_column = self.start - self.line_start + 1
            self._scan_token()
        self.tokens.append(
            Token(
                TokenType.EOF,
                "",
                None,
                self.line,
                self.current - self.line_start + 1,
            )
        )
        return self.tokens, self.errors

    # -- scanning -----------------------------------------------------

    def _scan_token(self) -> None:
        char = self._advance()
        if char in " \t\r":
            return
        if char == "\n":
            self._newline()
        elif char in self.SINGLE_CHAR_TOKENS:
            self._add(self.SINGLE_CHAR_TOKENS[char])
        elif char == "/":
            if self._match("/"):
                while not self._at_end() and self._peek() != "\n":
                    self._advance()
            else:
                self._add(TokenType.SLASH)
        elif char == "!":
            self._add(TokenType.BANG_EQUAL if self._match("=") else TokenType.BANG)
        elif char == "=":
            self._add(TokenType.EQUAL_EQUAL if self._match("=") else TokenType.EQUAL)
        elif char == "<":
            self._add(TokenType.LESS_EQUAL if self._match("=") else TokenType.LESS)
        elif char == ">":
            self._add(
                TokenType.GREATER_EQUAL if self._match("=") else TokenType.GREATER
            )
        elif char == '"':
            self._string()
        elif self._is_digit(char):
            self._number()
        elif self._is_alpha(char):
            self._identifier()
        else:
            self._error(
                f"Unexpected character {char!r}",
                self._token_line,
                self._token_column,
            )

    def _string(self) -> None:
        chars: list[str] = []
        while True:
            if self._at_end() or self._peek() == "\n":
                self._error(
                    "Unterminated string literal",
                    self._token_line,
                    self._token_column,
                )
                return
            char = self._advance()
            if char == '"':
                break
            if char != "\\":
                chars.append(char)
                continue
            if self._at_end() or self._peek() == "\n":
                continue  # reported as unterminated on the next iteration
            column = self.current - self.line_start  # 1-based, the backslash
            escape = self._advance()
            if escape in self.ESCAPES:
                chars.append(self.ESCAPES[escape])
            else:
                self._error(
                    f"Invalid escape sequence '\\{escape}'",
                    self.line,
                    column,
                )
        self._add(TokenType.STRING, "".join(chars))

    def _number(self) -> None:
        while self._is_digit(self._peek()):
            self._advance()
        is_float = False
        if self._peek() == "." and self._is_digit(self._peek_next()):
            is_float = True
            self._advance()
            while self._is_digit(self._peek()):
                self._advance()
        text = self.source[self.start : self.current]
        if is_float:
            value = float(text)
            if value == float("inf"):
                self._error(
                    "Float literal out of range",
                    self._token_line,
                    self._token_column,
                )
                return
            self._add(TokenType.FLOAT, value)
            return
        integer = int(text)
        if integer > self.MAX_INT:
            self._error(
                f"Integer literal out of range (maximum is {self.MAX_INT})",
                self._token_line,
                self._token_column,
            )
            return
        self._add(TokenType.INTEGER, integer)

    def _identifier(self) -> None:
        while self._is_alpha(self._peek()) or self._is_digit(self._peek()):
            self._advance()
        text = self.source[self.start : self.current]
        token_type = self.KEYWORDS.get(text, TokenType.IDENTIFIER)
        literal: object | None = None
        if token_type is TokenType.TRUE:
            literal = True
        elif token_type is TokenType.FALSE:
            literal = False
        self._add(token_type, literal)

    # -- helpers ------------------------------------------------------

    def _add(self, token_type: TokenType, literal: object | None = None) -> None:
        lexeme = self.source[self.start : self.current]
        self.tokens.append(
            Token(
                token_type,
                lexeme,
                literal,
                self._token_line,
                self._token_column,
            )
        )

    def _error(self, message: str, line: int, column: int) -> None:
        self.errors.append(Diagnostic(_PHASE, message, line, column))

    def _newline(self) -> None:
        self.line += 1
        self.line_start = self.current

    def _at_end(self) -> bool:
        return self.current >= len(self.source)

    def _advance(self) -> str:
        char = self.source[self.current]
        self.current += 1
        return char

    def _match(self, expected: str) -> bool:
        if self._at_end() or self.source[self.current] != expected:
            return False
        self.current += 1
        return True

    def _peek(self) -> str:
        return "\0" if self._at_end() else self.source[self.current]

    def _peek_next(self) -> str:
        if self.current + 1 >= len(self.source):
            return "\0"
        return self.source[self.current + 1]

    @staticmethod
    def _is_digit(char: str) -> bool:
        return "0" <= char <= "9"

    @staticmethod
    def _is_alpha(char: str) -> bool:
        return "a" <= char <= "z" or "A" <= char <= "Z" or char == "_"
