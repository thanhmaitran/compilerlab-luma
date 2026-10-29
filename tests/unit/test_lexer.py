from luma.lexer import Lexer
from luma.tokens import TokenType


def lex(source: str):
    return Lexer(source).scan_tokens()


def types(source: str):
    tokens, errors = lex(source)
    assert errors == []
    return [token.type for token in tokens]


def test_variable_declaration():
    tokens, errors = lex("let x: int = 42;")
    assert errors == []
    assert [token.type for token in tokens] == [
        TokenType.LET,
        TokenType.IDENTIFIER,
        TokenType.COLON,
        TokenType.IDENTIFIER,
        TokenType.EQUAL,
        TokenType.INTEGER,
        TokenType.SEMICOLON,
        TokenType.EOF,
    ]
    assert tokens[5].literal == 42


def test_operators_use_longest_match():
    tokens, errors = lex("a == b != c <= d >= e")
    assert errors == []
    assert [token.type for token in tokens[:-1]] == [
        TokenType.IDENTIFIER,
        TokenType.EQUAL_EQUAL,
        TokenType.IDENTIFIER,
        TokenType.BANG_EQUAL,
        TokenType.IDENTIFIER,
        TokenType.LESS_EQUAL,
        TokenType.IDENTIFIER,
        TokenType.GREATER_EQUAL,
        TokenType.IDENTIFIER,
    ]


def test_single_character_operators_and_punctuation():
    assert types("+ - * / % ! < > = ( ) { } : ; ,")[:-1] == [
        TokenType.PLUS,
        TokenType.MINUS,
        TokenType.STAR,
        TokenType.SLASH,
        TokenType.PERCENT,
        TokenType.BANG,
        TokenType.LESS,
        TokenType.GREATER,
        TokenType.EQUAL,
        TokenType.LEFT_PAREN,
        TokenType.RIGHT_PAREN,
        TokenType.LEFT_BRACE,
        TokenType.RIGHT_BRACE,
        TokenType.COLON,
        TokenType.SEMICOLON,
        TokenType.COMMA,
    ]


def test_keywords_versus_identifiers():
    assert types("let print if else while true false and or not letter")[:-1] == [
        TokenType.LET,
        TokenType.PRINT,
        TokenType.IF,
        TokenType.ELSE,
        TokenType.WHILE,
        TokenType.TRUE,
        TokenType.FALSE,
        TokenType.AND,
        TokenType.OR,
        TokenType.NOT,
        TokenType.IDENTIFIER,
    ]


def test_number_literals():
    tokens, errors = lex("12 3.5 7.")
    assert len(errors) == 1  # the trailing '.' of `7.` is not valid
    assert tokens[0].type is TokenType.INTEGER and tokens[0].literal == 12
    assert tokens[1].type is TokenType.FLOAT and tokens[1].literal == 3.5
    assert tokens[2].type is TokenType.INTEGER and tokens[2].literal == 7


def test_float_requires_digit_after_dot():
    _, errors = lex("1.")
    assert len(errors) == 1
    assert "Unexpected character '.'" in errors[0].message


def test_string_literal_with_escapes():
    tokens, errors = lex(r'"a\tb\n\"q\" \\ \r"')
    assert errors == []
    assert tokens[0].type is TokenType.STRING
    assert tokens[0].literal == 'a\tb\n"q" \\ \r'


def test_string_may_contain_unicode():
    tokens, errors = lex('"xin chào ✓"')
    assert errors == []
    assert tokens[0].literal == "xin chào ✓"


def test_comments_are_ignored():
    tokens, errors = lex("let x = 1; // trailing comment\n// whole line\nprint(x);")
    assert errors == []
    assert TokenType.SLASH not in [token.type for token in tokens]
    assert tokens[-2].type is TokenType.SEMICOLON
    assert tokens[-2].line == 3


def test_positions_are_one_based_and_track_lines():
    tokens, _ = lex("let x = 1;\n  print(x);")
    assert (tokens[0].line, tokens[0].column) == (1, 1)
    assert (tokens[1].line, tokens[1].column) == (1, 5)
    print_token = tokens[5]
    assert print_token.type is TokenType.PRINT
    assert (print_token.line, print_token.column) == (2, 3)


def test_invalid_character_reports_line_and_column():
    tokens, errors = lex("let x = 1;\nlet y = @;")
    assert len(errors) == 1
    assert (errors[0].line, errors[0].column) == (2, 9)
    assert errors[0].phase == "Lexical error"
    assert "'@'" in errors[0].message
    assert tokens[-1].type is TokenType.EOF  # scanning continues after errors


def test_unterminated_string():
    _, errors = lex('print("oops);\nprint(1);')
    assert len(errors) == 1
    assert "Unterminated string" in errors[0].message
    assert (errors[0].line, errors[0].column) == (1, 7)


def test_invalid_escape_sequence():
    _, errors = lex(r'"bad \q escape"')
    assert len(errors) == 1
    assert "Invalid escape" in errors[0].message
    assert (errors[0].line, errors[0].column) == (1, 6)


def test_lone_ampersand_and_pipe_are_errors():
    _, errors = lex("a & b | c")
    assert len(errors) == 2


def test_integer_literal_range():
    _, ok = lex("9223372036854775807")
    assert ok == []
    _, too_big = lex("9223372036854775808")
    assert len(too_big) == 1 and "out of range" in too_big[0].message


def test_empty_source_yields_only_eof():
    tokens, errors = lex("")
    assert errors == []
    assert [token.type for token in tokens] == [TokenType.EOF]


def test_crlf_line_endings():
    tokens, errors = lex("let x = 1;\r\nprint(x);\r\n")
    assert errors == []
    assert tokens[5].line == 2
