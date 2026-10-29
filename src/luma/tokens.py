"""Token definitions for Luma."""

from dataclasses import dataclass
from enum import Enum, auto


class TokenType(Enum):
    # Literals and identifiers
    IDENTIFIER = auto()
    INTEGER = auto()
    FLOAT = auto()
    STRING = auto()

    # Keywords
    LET = auto()
    PRINT = auto()
    IF = auto()
    ELSE = auto()
    WHILE = auto()
    TRUE = auto()
    FALSE = auto()
    AND = auto()
    OR = auto()
    NOT = auto()

    # Punctuation
    LEFT_PAREN = auto()
    RIGHT_PAREN = auto()
    LEFT_BRACE = auto()
    RIGHT_BRACE = auto()
    COLON = auto()
    SEMICOLON = auto()
    COMMA = auto()

    # Operators
    PLUS = auto()
    MINUS = auto()
    STAR = auto()
    SLASH = auto()
    PERCENT = auto()
    BANG = auto()
    BANG_EQUAL = auto()
    EQUAL = auto()
    EQUAL_EQUAL = auto()
    LESS = auto()
    LESS_EQUAL = auto()
    GREATER = auto()
    GREATER_EQUAL = auto()

    EOF = auto()


@dataclass(frozen=True, slots=True)
class Token:
    type: TokenType
    lexeme: str
    literal: object | None
    line: int
    column: int
