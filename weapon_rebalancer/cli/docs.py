"""Documentación en la terminal: las mismas páginas que el panel web y docs/index.html."""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from ..core.paths import DOCS_DIR
from .term import Term, read_key, raw_mode

FRONT_RE = re.compile(r'^---\r?\n(.*?)\r?\n---\r?\n?', re.DOTALL)


def list_pages() -> list[dict[str, Any]]:
    pages = []
    for path in sorted((DOCS_DIR / 'pages').glob('*.md')):
        text = path.read_text(encoding='utf-8')
        match = FRONT_RE.match(text)
        meta = dict(line.split(':', 1) for line in match.group(1).splitlines() if ':' in line) if match else {}
        meta = {k.strip(): v.strip() for k, v in meta.items()}
        pages.append({'slug': meta.get('slug', path.stem), 'title': meta.get('title', path.stem), 'group': meta.get('group', ''),
                      'description': meta.get('description', ''), 'content': text[match.end():] if match else text})
    try:
        import sys

        sys.path.insert(0, str(DOCS_DIR.parent))
        from docs.tools.build_docs import parameters_page

        params = parameters_page()
        pages.append({key: params[key] for key in ('slug', 'title', 'group', 'description', 'content')})
    except Exception:  # noqa: BLE001 - la referencia generada es opcional en la terminal
        pass
    order = {p['slug']: i for i, p in enumerate(pages)}
    return sorted(pages, key=lambda p: (0 if p['slug'] == 'inicio' else 1, order[p['slug']]))


def _inline(term: Term, text: str) -> str:
    text = re.sub(r'`([^`]+)`', lambda m: term.style(m.group(1), 'info'), text)
    text = re.sub(r'\*\*([^*]+)\*\*', lambda m: term.style(m.group(1), 'bold'), text)
    text = re.sub(r'!\[[^\]]*\]\([^)]+\)', lambda m: term.style('[imagen: ver en el panel web]', 'muted'), text)
    text = re.sub(r'\[([^\]]+)\]\(([^)]+)\)', lambda m: m.group(1) + term.style(f' ({m.group(2)})', 'muted'), text)
    return text


def render_lines(term: Term, page: dict[str, Any]) -> list[str]:
    import textwrap

    width = min(term.width() - 4, 100)
    lines = [term.style(page['title'].upper(), 'title'), term.style(page['description'], 'muted'), '']
    in_code = False
    for raw in page['content'].splitlines():
        if raw.startswith('```'):
            in_code = not in_code
            lines.append(term.style(term.box['rule'] * 40, 'muted'))
            continue
        if in_code:
            lines.append(term.style('  ' + raw, 'info'))
            continue
        heading = re.match(r'^(#{1,4})\s+(.+?)(?:\s+\{#[^}]+\})?$', raw)
        if heading:
            level = len(heading.group(1))
            if level == 1:
                continue
            lines += ['', term.style(heading.group(2) if level > 2 else heading.group(2).upper(), 'title' if level == 2 else 'accent')]
            continue
        if raw.startswith('> [!'):
            kind = re.match(r'> \[!(\w+)\]', raw).group(1).upper()
            lines.append(term.style({'WARNING': 'Importante', 'DANGER': 'Peligro', 'TIP': 'Consejo', 'SUCCESS': 'Correcto'}.get(kind, 'Nota') + ':',
                                    {'WARNING': 'warn', 'DANGER': 'err', 'SUCCESS': 'ok'}.get(kind, 'info')))
            continue
        if raw.startswith('>'):
            raw = '  ' + raw.lstrip('> ')
        if raw.strip().startswith('|'):
            if re.match(r'^\s*\|?\s*:?-{3,}', raw):
                continue
            cells = [c.strip() for c in raw.strip().strip('|').split('|')]
            lines.append('  ' + term.style(' │ ' if term.unicode else ' | ', 'muted').join(_inline(term, c) for c in cells))
            continue
        if not raw.strip():
            lines.append('')
            continue
        bullet = re.match(r'^(\s*)([-*]|\d+\.)\s+(.*)$', raw)
        if bullet:
            prefix = ('  ' + term.sym['bullet'] + ' ') if bullet.group(2) in '-*' else f'  {bullet.group(2)} '
            wrapped = textwrap.wrap(bullet.group(3), width - len(prefix)) or ['']
            lines.append(prefix + _inline(term, wrapped[0]))
            lines += [' ' * len(prefix) + _inline(term, w) for w in wrapped[1:]]
            continue
        lines += [_inline(term, w) for w in textwrap.wrap(raw.strip(), width)]
    return lines


def render_page(term: Term, page: dict[str, Any]) -> None:
    lines = render_lines(term, page)
    if not term.interactive:
        for line in lines:
            term.write('  ' + line)
        return
    height = term.height() - 3
    top = 0
    with raw_mode():
        while True:
            term.clear()
            for line in lines[top: top + height]:
                term.write('  ' + line)
            term.stream.write(term.style(f'  {min(top + height, len(lines))}/{len(lines)}  ↑↓ desplazar · espacio página · q volver ', 'muted'))
            term.stream.flush()
            key = read_key()
            if key in {'q', 'esc', 'left', 'backspace'}:
                break
            if key in {'down', 'j', 'enter'}:
                top = min(top + 1, max(0, len(lines) - height))
            elif key in {'up', 'k'}:
                top = max(0, top - 1)
            elif key in {'space', 'pgdn'}:
                top = min(top + height, max(0, len(lines) - height))
            elif key in {'pgup', 'b'}:
                top = max(0, top - height)
            elif key == 'home':
                top = 0
            elif key == 'end':
                top = max(0, len(lines) - height)
    term.write('')


_ = Path
