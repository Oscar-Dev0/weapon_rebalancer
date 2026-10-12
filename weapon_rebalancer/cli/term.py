"""Terminal: colores, símbolos, ancho y lectura de teclas (solo librería estándar).

- Colores ANSI de 256 con la paleta del proyecto; se desactivan con `NO_COLOR`, `--no-color`,
  `TERM=dumb` o cuando la salida no es una terminal. `FORCE_COLOR` los fuerza.
- En Windows activa el modo VT de la consola; si no se puede, no usa color.
- Si la consola no admite UTF-8, usa bordes y símbolos ASCII.
- Los estados siempre llevan texto o símbolo además del color.
"""
from __future__ import annotations

import os
import re
import shutil
import sys
from contextlib import contextmanager
from typing import Iterator

ANSI_RE = re.compile(r'\x1b\[[0-9;]*m')

PALETTE = {
    'purple': '38;5;141', 'purple_bold': '1;38;5;141', 'blue': '38;5;75', 'green': '38;5;78',
    'yellow': '38;5;221', 'red': '38;5;203', 'gray': '38;5;245', 'white': '38;5;255', 'bold': '1',
    'dim': '2', 'reverse': '7', 'select': '1;38;5;255;48;5;61',
}
ROLES = {
    'title': 'purple_bold', 'accent': 'purple', 'info': 'blue', 'ok': 'green', 'warn': 'yellow', 'err': 'red',
    'muted': 'gray', 'value': 'white', 'bold': 'bold', 'select': 'select', 'dim': 'dim',
}


def _enable_windows_vt() -> bool:
    if os.name != 'nt':
        return True
    try:
        import ctypes

        kernel32 = ctypes.windll.kernel32  # type: ignore[attr-defined]
        handle = kernel32.GetStdHandle(-11)
        mode = ctypes.c_uint32()
        if not kernel32.GetConsoleMode(handle, ctypes.byref(mode)):
            return False
        return bool(kernel32.SetConsoleMode(handle, mode.value | 0x0004))
    except Exception:  # noqa: BLE001
        return False


class Term:
    def __init__(self, *, color: bool | None = None, unicode: bool | None = None, stream=None) -> None:
        self.stream = stream or sys.stdout
        self.is_tty = bool(getattr(self.stream, 'isatty', lambda: False)())
        self.interactive = self.is_tty and bool(getattr(sys.stdin, 'isatty', lambda: False)())
        if color is None:
            if os.environ.get('NO_COLOR'):
                color = False
            elif os.environ.get('FORCE_COLOR'):
                color = True
            else:
                color = self.is_tty and os.environ.get('TERM') != 'dumb'
        if color and self.is_tty and not _enable_windows_vt():
            color = False
        self.color = bool(color)
        if unicode is None:
            encoding = (getattr(self.stream, 'encoding', '') or '').lower()
            unicode = 'utf' in encoding and os.environ.get('WR_ASCII') != '1'
        self.unicode = bool(unicode)
        self.sym = SYMBOLS_UNICODE if self.unicode else SYMBOLS_ASCII
        self.box = BOX_UNICODE if self.unicode else BOX_ASCII

    # ---- texto ----------------------------------------------------------------
    def style(self, text: object, role: str) -> str:
        text = str(text)
        if not self.color or not text:
            return text
        code = PALETTE.get(ROLES.get(role, role))
        return f'\x1b[{code}m{text}\x1b[0m' if code else text

    def width(self) -> int:
        try:
            return max(40, min(shutil.get_terminal_size((100, 30)).columns, 160))
        except OSError:
            return 100

    def height(self) -> int:
        try:
            return max(10, shutil.get_terminal_size((100, 30)).lines)
        except OSError:
            return 30

    def write(self, text: str = '') -> None:
        if not self.color:
            text = ANSI_RE.sub('', text)
        try:
            self.stream.write(text + '\n')
        except UnicodeEncodeError:
            self.stream.write(text.encode('ascii', 'replace').decode('ascii') + '\n')
        self.stream.flush()

    def clear(self) -> None:
        if self.is_tty and self.color:
            self.stream.write('\x1b[2J\x1b[H')
            self.stream.flush()
        elif self.is_tty:
            self.stream.write('\n' * 2)


SYMBOLS_UNICODE = {'ok': '✔', 'warn': '▲', 'err': '✖', 'info': '●', 'arrow': '›', 'up': '↑', 'down': '↓', 'same': '=',
                   'bullet': '•', 'pointer': '❯', 'check_on': '◉', 'check_off': '○', 'ellipsis': '…', 'dash': '—',
                   'spinner': '⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏'}
SYMBOLS_ASCII = {'ok': 'OK', 'warn': '!', 'err': 'X', 'info': '*', 'arrow': '>', 'up': '+', 'down': '-', 'same': '=',
                 'bullet': '*', 'pointer': '>', 'check_on': '[x]', 'check_off': '[ ]', 'ellipsis': '...', 'dash': '-',
                 'spinner': '|/-\\'}
BOX_UNICODE = {'tl': '╭', 'tr': '╮', 'bl': '╰', 'br': '╯', 'h': '─', 'v': '│', 'rule': '─'}
BOX_ASCII = {'tl': '+', 'tr': '+', 'bl': '+', 'br': '+', 'h': '-', 'v': '|', 'rule': '-'}


def visible_len(text: str) -> int:
    return len(ANSI_RE.sub('', text))


def pad(text: str, width: int, align: str = 'left') -> str:
    text = truncate(text, width)
    gap = max(0, width - visible_len(text))
    if align == 'right':
        return ' ' * gap + text
    if align == 'center':
        return ' ' * (gap // 2) + text + ' ' * (gap - gap // 2)
    return text + ' ' * gap


def truncate(text: str, width: int, ellipsis: str = '…') -> str:
    if visible_len(text) <= width:
        return text
    plain = ANSI_RE.sub('', text)
    return plain[: max(0, width - len(ellipsis))] + ellipsis


# ---- teclado ---------------------------------------------------------------
@contextmanager
def raw_mode() -> Iterator[None]:
    if os.name == 'nt':
        yield
        return
    import termios
    import tty

    fd = sys.stdin.fileno()
    previous = termios.tcgetattr(fd)
    try:
        tty.setcbreak(fd)
        yield
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, previous)


_POSIX_KEYS = {
    '\x1b[A': 'up', '\x1b[B': 'down', '\x1b[C': 'right', '\x1b[D': 'left', '\x1bOA': 'up', '\x1bOB': 'down',
    '\x1bOC': 'right', '\x1bOD': 'left', '\x1b[H': 'home', '\x1b[F': 'end', '\x1b[1~': 'home', '\x1b[4~': 'end',
    '\x1b[5~': 'pgup', '\x1b[6~': 'pgdn', '\x1b[3~': 'delete',
}
_WIN_KEYS = {'H': 'up', 'P': 'down', 'K': 'left', 'M': 'right', 'G': 'home', 'O': 'end', 'I': 'pgup', 'Q': 'pgdn', 'S': 'delete'}


def read_key() -> str:
    """Una tecla: 'up', 'down', 'enter', 'esc', 'backspace', 'space', 'tab' o el carácter."""
    if os.name == 'nt':
        import msvcrt

        char = msvcrt.getwch()
        if char in ('\x00', '\xe0'):
            return _WIN_KEYS.get(msvcrt.getwch(), 'unknown')
        return _normalize(char)
    import select

    fd = sys.stdin.fileno()

    def read_char() -> str:
        # Bytes directos del descriptor: con sys.stdin.read() el búfer de Python se tragaría
        # el resto de una secuencia de escape y select() no lo vería.
        first = os.read(fd, 1)
        if not first:
            raise KeyboardInterrupt
        needed = 0
        if first[0] >= 0xF0:
            needed = 3
        elif first[0] >= 0xE0:
            needed = 2
        elif first[0] >= 0xC0:
            needed = 1
        data = first + (os.read(fd, needed) if needed else b'')
        return data.decode('utf-8', 'replace')

    char = read_char()
    if char == '\x1b':
        seq = char
        while select.select([fd], [], [], 0.03)[0]:
            seq += read_char()
            if seq in _POSIX_KEYS or (len(seq) > 2 and seq[-1].isalpha()) or seq.endswith('~'):
                break
        return _POSIX_KEYS.get(seq, 'esc' if seq == '\x1b' else 'unknown')
    return _normalize(char)


def _normalize(char: str) -> str:
    if char in ('\r', '\n'):
        return 'enter'
    if char in ('\x7f', '\b'):
        return 'backspace'
    if char == '\x03':
        raise KeyboardInterrupt
    if char == '\x1b':
        return 'esc'
    if char == ' ':
        return 'space'
    if char == '\t':
        return 'tab'
    return char
