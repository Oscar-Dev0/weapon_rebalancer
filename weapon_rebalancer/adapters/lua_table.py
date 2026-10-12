"""Parser tolerante de tablas Lua literales (solo lectura).

Pensado para archivos de datos como `ox_inventory/data/weapons.lua`: entiende tablas,
cadenas, números, booleanos y comentarios. Cualquier expresión que no sea un literal
(llamadas a funciones, concatenaciones, variables) se conserva como texto en
``LuaExpr`` en vez de fallar. Registra la línea de cada clave y las claves repetidas,
porque en Lua la última definición sobrescribe a la anterior sin aviso.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any


@dataclass
class LuaExpr:
    raw: str


@dataclass
class LuaTable:
    items: dict[Any, Any] = field(default_factory=dict)
    array: list[Any] = field(default_factory=list)
    lines: dict[Any, int] = field(default_factory=dict)
    duplicates: list[tuple[Any, int, int]] = field(default_factory=list)  # (clave, línea anterior, línea nueva)

    def get(self, key: Any, default: Any = None) -> Any:
        return self.items.get(key, default)

    def to_python(self) -> Any:
        if self.items and not self.array:
            return {k: _plain(v) for k, v in self.items.items()}
        if self.array and not self.items:
            return [_plain(v) for v in self.array]
        data = {k: _plain(v) for k, v in self.items.items()}
        for index, value in enumerate(self.array, start=1):
            data.setdefault(index, _plain(value))
        return data


def _plain(value: Any) -> Any:
    if isinstance(value, LuaTable):
        return value.to_python()
    if isinstance(value, LuaExpr):
        return {'__expr__': value.raw}
    return value


class LuaParseError(ValueError):
    def __init__(self, message: str, line: int) -> None:
        super().__init__(f'{message} (línea {line})')
        self.line = line


_TOKEN_RE = re.compile(
    r"""
    (?P<ws>\s+)
  | (?P<comment>--\[(?P<eq>=*)\[.*?\](?P=eq)\]|--[^\n]*)
  | (?P<lstring>\[(?P<leq>=*)\[.*?\](?P=leq)\])
  | (?P<string>"(?:\\.|[^"\\\n])*"|'(?:\\.|[^'\\\n])*')
  | (?P<number>-?0[xX][0-9a-fA-F]+|-?(?:\d+\.?\d*|\.\d+)(?:[eE][+-]?\d+)?)
  | (?P<name>[A-Za-z_][A-Za-z0-9_]*)
  | (?P<op>[{}\[\]=,;()])
  | (?P<other>.)
    """,
    re.VERBOSE | re.DOTALL,
)

_ESCAPES = {'n': '\n', 't': '\t', 'r': '\r', '\\': '\\', '"': '"', "'": "'", '0': '\0'}


def _unescape(body: str) -> str:
    return re.sub(r'\\(.)', lambda m: _ESCAPES.get(m.group(1), m.group(1)), body)


class _Parser:
    def __init__(self, text: str) -> None:
        self.text = text
        self.tokens: list[tuple[str, str, int, int]] = []  # kind, value, line, offset
        line = 1
        for match in _TOKEN_RE.finditer(text):
            kind = match.lastgroup
            value = match.group(0)
            if kind in {'ws', 'comment'}:
                line += value.count('\n')
                continue
            if kind in {'eq', 'leq'}:
                continue
            self.tokens.append((kind or 'other', value, line, match.start()))
            line += value.count('\n')
        self.pos = 0

    def peek(self, offset: int = 0) -> tuple[str, str, int, int] | None:
        index = self.pos + offset
        return self.tokens[index] if index < len(self.tokens) else None

    def take(self) -> tuple[str, str, int, int]:
        token = self.peek()
        if token is None:
            raise LuaParseError('fin de archivo inesperado', self.tokens[-1][2] if self.tokens else 1)
        self.pos += 1
        return token

    def expect(self, value: str) -> tuple[str, str, int, int]:
        token = self.take()
        if token[1] != value:
            raise LuaParseError(f'se esperaba {value!r} y llegó {token[1]!r}', token[2])
        return token

    def parse_value(self) -> Any:
        token = self.peek()
        if token is None:
            raise LuaParseError('valor ausente', 1)
        kind, value, line, offset = token
        if value == '{':
            return self.parse_table()
        if kind == 'string':
            self.pos += 1
            return _unescape(value[1:-1])
        if kind == 'lstring':
            self.pos += 1
            body = value[value.index('[', 1) + 1:]
            return body[: body.rindex(']', 0, len(body) - 1)]
        if kind == 'number' and not self._is_expression_tail():
            self.pos += 1
            try:
                if value.lower().lstrip('-').startswith('0x'):
                    return int(value, 16)
                number = float(value)
                return int(number) if re.fullmatch(r'-?\d+', value) else number
            except ValueError:
                return LuaExpr(value)
        if kind == 'name' and value in {'true', 'false', 'nil'} and not self._is_expression_tail():
            self.pos += 1
            return {'true': True, 'false': False, 'nil': None}[value]
        return self.parse_expression()

    def _is_expression_tail(self) -> bool:
        following = self.peek(1)
        return following is not None and following[1] not in {',', ';', '}'}

    def parse_expression(self) -> LuaExpr:
        """Captura una expresión no literal hasta la próxima coma/cierre del mismo nivel."""
        start_token = self.peek()
        assert start_token is not None
        depth = 0
        start = start_token[3]
        end = start
        while True:
            token = self.peek()
            if token is None:
                break
            value = token[1]
            if depth == 0 and value in {',', ';', '}'}:
                break
            if value in {'(', '{', '['}:
                depth += 1
            elif value in {')', '}', ']'}:
                depth -= 1
            end = token[3] + len(value)
            self.pos += 1
        return LuaExpr(self.text[start:end].strip())

    def parse_table(self) -> LuaTable:
        self.expect('{')
        table = LuaTable()
        while True:
            token = self.peek()
            if token is None:
                raise LuaParseError('tabla sin cerrar', self.tokens[-1][2])
            if token[1] == '}':
                self.pos += 1
                return table
            key: Any = None
            has_key = False
            if token[1] == '[':
                self.pos += 1
                key = self.parse_value()
                self.expect(']')
                self.expect('=')
                has_key = True
            elif token[0] == 'name' and (nxt := self.peek(1)) is not None and nxt[1] == '=':
                key = token[1]
                self.pos += 2
                has_key = True
            line = token[2]
            value = self.parse_value()
            if has_key:
                if isinstance(key, LuaExpr):
                    key = key.raw
                if key in table.items:
                    table.duplicates.append((key, table.lines.get(key, 0), line))
                table.items[key] = value
                table.lines[key] = line
            else:
                table.array.append(value)
            separator = self.peek()
            if separator is not None and separator[1] in {',', ';'}:
                self.pos += 1


def parse_lua_return_table(text: str) -> LuaTable:
    """Parsea un archivo `return { ... }`."""
    parser = _Parser(text)
    while parser.peek() is not None and parser.peek()[1] != '{':  # type: ignore[index]
        parser.pos += 1
    if parser.peek() is None:
        raise LuaParseError('no se encontró una tabla', 1)
    return parser.parse_table()
