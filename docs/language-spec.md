# Luma language specification (version 1.0)

This document defines the language. The implementation and the tests must agree
with it; if they disagree, that is a bug in one of them.

## 1. Lexical structure

- Source files are UTF-8 text. A leading byte-order mark is ignored.
- Whitespace (space, tab, carriage return, newline) separates tokens.
- `//` starts a comment that runs to the end of the line.
- **Identifiers** match `[A-Za-z_][A-Za-z0-9_]*` (ASCII only).
- **Keywords:** `let print if else while true false and or not`. The type names
  `int`, `float`, `bool`, `string` are ordinary identifiers that are recognised in
  type positions.
- **Integer literals:** decimal digits, at most `9223372036854775807`.
- **Float literals:** digits, a dot, digits (`3.14`). `1.` and `.5` are not valid.
- **String literals:** delimited by `"` and may contain any Unicode character
  except a raw newline. Escapes: `\"`, `\\`, `\n`, `\t`, `\r`. Any other escape
  is a lexical error.
- Operators and punctuation: `+ - * / % ! != = == < <= > >= ( ) { } : ; ,`.

## 2. Grammar (EBNF)

```
program      -> declaration* EOF ;

declaration  -> "let" IDENTIFIER (":" type)? "=" expression ";"
              | statement ;

statement    -> "print" "(" expression ")" ";"
              | "if" "(" expression ")" block
                ("else" (block | ifStatement))?
              | "while" "(" expression ")" block
              | block
              | IDENTIFIER "=" expression ";"
              | expression ";" ;

block        -> "{" declaration* "}" ;
type         -> "int" | "float" | "bool" | "string" ;

expression   -> or ;
or           -> and ("or" and)* ;
and          -> equality ("and" equality)* ;
equality     -> comparison (("==" | "!=") comparison)* ;
comparison   -> term (("<" | "<=" | ">" | ">=") term)* ;
term         -> factor (("+" | "-") factor)* ;
factor       -> unary (("*" | "/" | "%") unary)* ;
unary        -> ("!" | "not" | "-") unary | primary ;
primary      -> INTEGER | FLOAT | STRING | "true" | "false"
              | IDENTIFIER | "(" expression ")" ;
```

`else if` is accepted as sugar for `else { if ... }`.

## 3. Types

| Type | Values |
| --- | --- |
| `int` | signed 64-bit integers |
| `float` | IEEE-754 double precision numbers (never infinite or NaN) |
| `bool` | `true`, `false` |
| `string` | sequences of Unicode characters |

- A variable declared without an annotation (`let x = 1;`) takes the type of its
  initializer. Its type never changes afterwards.
- **Implicit conversion:** an `int` may be used where a `float` is required
  (initialisation, assignment, mixed arithmetic and comparison). A `float` is
  never converted to `int`.
- `bool` is not a number: `true + 1` is a type error.
- There are no other implicit conversions. `"a" + 1` is a type error.

## 4. Operators

Precedence, from lowest to highest binding. All binary operators are
left-associative.

| Level | Operators | Operand types | Result |
| --- | --- | --- | --- |
| 1 | `or` | `bool`, `bool` | `bool` |
| 2 | `and` | `bool`, `bool` | `bool` |
| 3 | `==` `!=` | two numbers, or two values of the same type | `bool` |
| 4 | `<` `<=` `>` `>=` | two numbers, or two strings | `bool` |
| 5 | `+` `-` | two numbers | `int` if both `int`, else `float` |
| 5 | `+` | two strings | `string` (concatenation) |
| 6 | `*` `/` `%` | two numbers | `int` if both `int`, else `float` |
| 7 (prefix) | `-` | number | same type |
| 7 (prefix) | `not` `!` | `bool` | `bool` |

Semantics worth stating precisely:

- **Division:** `int / int` is integer division that **truncates toward zero**
  (`7 / 2 == 3`, `-7 / 2 == -3`). If either operand is a `float`, the result is
  a `float` and the division is exact floating-point division.
- **Modulo:** the result has the **sign of the dividend**, as in C:
  `7 % 3 == 1`, `-7 % 3 == -1`, `7 % -3 == 1`. For floats the same rule applies
  (`fmod`).
- **Equality across numeric types:** `1 == 1.0` is `true` (the `int` is converted
  to `float` first). Comparing other mixed types (`1 == "1"`, `true == 1`) is a
  type error.
- **Short-circuit:** `and` does not evaluate its right operand when the left is
  `false`; `or` does not evaluate its right operand when the left is `true`.
  `false and (1 / 0 > 0)` is therefore `false`, not an error.
- `!` and `not` are the same operator.

## 5. Variables and scope

- `let` declares a variable in the current scope. The initializer is evaluated
  **before** the name is introduced, so `let x = x + 1;` refers to an outer `x`
  (or is an "undefined variable" error).
- Declaring a name twice in the **same** scope is an error. Declaring it in an
  **inner** scope is allowed and shadows the outer variable until the block ends.
- Every `{ ... }` block (including `if`, `else` and `while` bodies) is a scope.
  Variables are not visible after their block ends.
- Assignment `x = e;` requires `x` to be declared and `e` assignable to `x`'s type.

## 6. Statements

- `print(e);` prints the value followed by a newline. Booleans print as `true` /
  `false`; floats print with Python's shortest round-trip form (`14.0`, `3.5`).
- `if (c) { ... } else { ... }`: `c` must be a `bool`. `else` is optional.
- `while (c) { ... }`: `c` must be a `bool` and is re-evaluated on every
  iteration.
- `e;` evaluates `e` and discards the result.

## 7. Errors

Errors are reported with a phase, a 1-based line and column, and a message:

```
examples/invalid_type.luma: [line 1, column 16] Semantic error: Cannot initialise variable 'age' of type int with a value of type string
```

| Phase | Examples |
| --- | --- |
| Lexical error | unexpected character, unterminated string, invalid escape, literal out of range |
| Syntax error | missing `;`, unbalanced parentheses, missing operand, unknown type name |
| Semantic error | undefined variable, duplicate declaration, wrong types, non-bool condition |

A program with any lexical, syntax or semantic error is never executed.

**Runtime errors** (reported by the VM, never as Python tracebacks):

- division or modulo by zero (`int` and `float`)
- integer overflow outside the signed 64-bit range; floating-point overflow
- exceeding the instruction limit (default 1,000,000, `--max-steps` to change)
- malformed bytecode (stack underflow, bad jump target, invalid local slot,
  reading an uninitialised local, operand type mismatch) — impossible for
  bytecode produced by the compiler, but checked anyway

## 8. Command line and exit codes

| Command | Purpose |
| --- | --- |
| `luma check FILE` | lex, parse and type-check only |
| `luma run FILE [--max-steps N]` | compile and run |
| `luma compile FILE [--emit-ir] [--emit-bytecode]` | print IR and/or bytecode (bytecode by default) |
| `luma disassemble FILE` | print the bytecode listing |

| Exit code | Meaning |
| --- | --- |
| 0 | success |
| 1 | the program has lexical, syntax or semantic errors |
| 2 | bad command-line usage, or the file cannot be read |
| 3 | the program failed at run time |

## 9. Not supported in 1.0

Functions, `return`, `break`, `continue`, arrays, classes, inheritance, generics,
modules, input, a garbage collector, `for` loops, and compound assignment
(`+=`). Everything in this list is deliberately out of scope for version 1.0.
