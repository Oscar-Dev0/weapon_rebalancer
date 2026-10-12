"""Componentes de salida para la terminal: banner, paneles, tablas, listas de problemas y progreso."""
from __future__ import annotations

import itertools
import threading
import time
from contextlib import contextmanager
from typing import Any, Callable, Iterable, Iterator, Sequence

from .term import Term, pad, truncate, visible_len

SEVERITY = {
    'error': ('err', 'err', 'Bloqueante'),
    'warning': ('warn', 'warn', 'Advertencia'),
    'info': ('info', 'info', 'Recomendación'),
    'ok': ('ok', 'ok', 'Correcto'),
}


def fmt(value: Any, digits: int = 3) -> str:
    """Número legible; `N/D` cuando no hay dato (nunca se inventa)."""
    if value is None or value == '':
        return 'N/D'
    if isinstance(value, bool):
        return 'sí' if value else 'no'
    if isinstance(value, float):
        text = f'{value:.{digits}f}'.rstrip('0').rstrip('.')
        return text if text not in {'', '-0'} else '0'
    if isinstance(value, list):
        return ' '.join(str(v) for v in value) or '—'
    return str(value)


def badge(term: Term, severity: str, text: str | None = None) -> str:
    role, sym, label = SEVERITY.get(severity, SEVERITY['info'])
    return term.style(f'{term.sym[sym]} {text or label}', role)


def banner(term: Term, version: str, author: str = 'OscarDev') -> None:
    width = min(term.width() - 4, 64)
    b = term.box
    lines = [
        '',
        term.style('WEAPON REBALANCER', 'title'),
        term.style('FiveM Weapon Configuration Studio', 'info'),
        '',
        term.style(f'Versión {version}  {term.sym["bullet"]}  {author}', 'muted'),
        '',
    ]
    term.write(term.style(f'  {b["tl"]}{b["h"] * width}{b["tr"]}', 'accent'))
    for line in lines:
        term.write(term.style(f'  {b["v"]}', 'accent') + pad(f'   {line}', width) + term.style(b['v'], 'accent'))
    term.write(term.style(f'  {b["bl"]}{b["h"] * width}{b["br"]}', 'accent'))


def section(term: Term, title: str, subtitle: str = '') -> None:
    term.write('')
    term.write('  ' + term.style(title.upper(), 'title') + (f'  {term.style(subtitle, "muted")}' if subtitle else ''))
    term.write('  ' + term.style(term.box['rule'] * min(term.width() - 4, 64), 'muted'))


def kv(term: Term, rows: Iterable[tuple[str, str]], label_width: int = 18) -> None:
    for label, value in rows:
        term.write('  ' + term.style(pad(label, label_width), 'muted') + ' ' + str(value))


def panel(term: Term, title: str, lines: Sequence[str], width: int | None = None) -> None:
    width = width or min(term.width() - 4, 72)
    b = term.box
    head = f' {title} ' if title else ''
    left = (width - visible_len(head)) // 2
    right = width - left - visible_len(head)
    term.write('  ' + term.style(b['tl'] + b['h'] * left, 'accent') + term.style(head, 'title') + term.style(b['h'] * right + b['tr'], 'accent'))
    for line in ['', *lines, '']:
        term.write('  ' + term.style(b['v'], 'accent') + pad(f'  {line}', width) + term.style(b['v'], 'accent'))
    term.write('  ' + term.style(b['bl'] + b['h'] * width + b['br'], 'accent'))


class Column:
    def __init__(self, title: str, key: str | Callable[[Any], Any], *, align: str = 'left', min_width: int = 4,
                 max_width: int = 40, style: Callable[[Any, Any], str] | None = None, fmt_value: Callable[[Any], str] | None = None) -> None:
        self.title, self.key, self.align = title, key, align
        self.min_width, self.max_width, self.style, self.fmt_value = min_width, max_width, style, fmt_value

    def raw(self, row: Any) -> Any:
        return self.key(row) if callable(self.key) else row.get(self.key)

    def text(self, row: Any) -> str:
        value = self.raw(row)
        return self.fmt_value(value) if self.fmt_value else fmt(value)


def table(term: Term, columns: Sequence[Column], rows: Sequence[Any], *, highlight: int | None = None, indent: int = 2) -> None:
    """Tabla que se adapta al ancho de la terminal (trunca con “…”)."""
    available = term.width() - indent - 2 * (len(columns) - 1)
    widths = []
    for col in columns:
        content = max([visible_len(col.title)] + [visible_len(col.text(r)) for r in rows] or [col.min_width])
        widths.append(max(col.min_width, min(col.max_width, content)))
    while sum(widths) > available and max(widths) > 6:
        index = widths.index(max(widths))
        widths[index] -= 1
    gap = '  '
    head = gap.join(pad(c.title, w, 'right' if c.align == 'right' else 'left') for c, w in zip(columns, widths))
    term.write(' ' * indent + term.style(head, 'muted'))
    term.write(' ' * indent + term.style(term.box['rule'] * min(sum(widths) + len(gap) * (len(columns) - 1), available + 2), 'muted'))
    for index, row in enumerate(rows):
        cells = []
        for col, w in zip(columns, widths):
            text = truncate(col.text(row), w)
            cell = pad(text, w, col.align)
            if col.style:
                cell = col.style(row, cell)
            cells.append(cell)
        line = gap.join(cells)
        if highlight is not None and index == highlight:
            line = term.style(f'{term.sym["pointer"]} ', 'accent') + line
            term.write(' ' * max(0, indent - 2) + line)
        else:
            term.write(' ' * indent + line)


def issues(term: Term, items: Sequence[dict[str, Any]], *, limit: int = 40, empty: str = 'Sin problemas.') -> None:
    if not items:
        term.write('  ' + badge(term, 'ok', empty))
        return
    order = {'error': 0, 'warning': 1, 'info': 2}
    for item in sorted(items, key=lambda i: order.get(i.get('severity'), 9))[:limit]:
        term.write('  ' + badge(term, item.get('severity', 'info')) + '  ' + str(item.get('message', '')))
        if item.get('fix'):
            term.write('     ' + term.style(f'{term.sym["arrow"]} {item["fix"]}', 'muted'))
    if len(items) > limit:
        term.write('  ' + term.style(f'… y {len(items) - limit} más', 'muted'))


def counts_line(term: Term, items: Sequence[dict[str, Any]]) -> str:
    counts = {'error': 0, 'warning': 0, 'info': 0}
    for item in items:
        if item.get('severity') in counts:
            counts[item['severity']] += 1
    parts = [badge(term, 'error', f'{counts["error"]} bloqueantes'), badge(term, 'warning', f'{counts["warning"]} advertencias'),
             badge(term, 'info', f'{counts["info"]} recomendaciones')]
    return '  '.join(parts)


def direction(term: Term, value: str) -> str:
    return {'up': term.style(f'{term.sym["up"]} sube', 'ok'), 'down': term.style(f'{term.sym["down"]} baja', 'err'),
            'same': term.style(f'{term.sym["same"]} igual', 'muted'), 'changed': term.style('≠ cambia', 'warn')}.get(value, value)


STATUS_TAG = {'inherited': ('H', 'info', 'heredado'), 'overridden': ('S', 'accent', 'sobrescrito'), 'own': ('P', 'accent', 'del perfil'),
              'rule': ('R', 'warn', 'regla del motor'), 'original': ('O', 'muted', 'original'), 'ignored': ('X', 'err', 'sin efecto')}


def status_tag(term: Term, status: str | None) -> str:
    if not status:
        return ''
    letter, role, _label = STATUS_TAG.get(status, ('?', 'muted', status))
    return term.style(f'[{letter}]', role)


def status_legend(term: Term) -> str:
    return '  '.join(f'{status_tag(term, key)} {label}' for key, (_l, _r, label) in STATUS_TAG.items())


@contextmanager
def progress(term: Term, message: str) -> Iterator[None]:
    """Indicador de progreso. En terminal anima un spinner; sin terminal imprime una línea."""
    if not term.is_tty:
        yield
        return
    stop = threading.Event()

    def spin() -> None:
        for frame in itertools.cycle(term.sym['spinner']):
            if stop.is_set():
                break
            term.stream.write(f'\r  {term.style(frame, "accent")} {message}')
            term.stream.flush()
            time.sleep(0.08)

    thread = threading.Thread(target=spin, daemon=True)
    started = time.perf_counter()
    thread.start()
    try:
        yield
    finally:
        stop.set()
        thread.join()
        elapsed = time.perf_counter() - started
        term.stream.write('\r' + ' ' * (visible_len(message) + 6) + '\r')
        term.stream.flush()
        if elapsed > 1.5:
            term.write('  ' + term.style(f'{message} ({elapsed:.1f} s)', 'muted'))
