"""Genera docs/js/docs-data.js desde docs/pages/*.md (equivalente al build de os_gym, sin Node).

- Cada página lleva front matter: slug, title, group, description.
- La página `parametros` se genera desde el registro de parámetros del código, así la
  referencia nunca se desincroniza del panel.
- Valida enlaces internos (`pagina.md#ancla`) y las anclas que usa la ayuda contextual
  del panel; si alguna no existe, el build falla.

Uso: python3 wr.py docs
"""
from __future__ import annotations

import json
import re
import sys
import unicodedata
from pathlib import Path

DOCS = Path(__file__).resolve().parents[1]
PROJECT = DOCS.parent
PAGES = DOCS / 'pages'
OUTPUT = DOCS / 'js' / 'docs-data.js'
sys.path.insert(0, str(PROJECT))

FRONT_RE = re.compile(r'^---\r?\n(.*?)\r?\n---\r?\n?', re.DOTALL)
HEADING_RE = re.compile(r'^(#{1,4})\s+(.+?)(?:\s+\{#([a-z0-9_\-]+)\})?\s*$')
LINK_RE = re.compile(r'(?<!!)\[[^\]]+\]\(([^)]+)\)')

# Anclas que el panel enlaza desde sus botones de ayuda (además de parametros/<campo>).
UI_ANCHORS = {
    'parametros/cabeza', 'perfiles/precedencia', 'perfiles/excepciones', 'perfiles/herencia', 'perfiles/engine-defaults',
    'perfiles/repetible', 'perfiles/fire_rate_classifier', 'perfiles/family_rules', 'perfiles/weapon_classification',
    'perfiles/baseline_repair', 'perfiles/meta', 'balanceo/supuestos', 'fivem/qbx-recoils', 'instalacion/rutas',
}
UI_PAGES = {'inicio', 'primeros-pasos', 'editor', 'perfiles-oficiales', 'perfiles', 'balanceo', 'fivem', 'terminal', 'solucion-problemas', 'desarrollo'}


def slugify(value: str) -> str:
    text = unicodedata.normalize('NFD', value)
    text = ''.join(ch for ch in text if unicodedata.category(ch) != 'Mn').lower()
    text = re.sub(r'[^a-z0-9_]+', '-', text).strip('-')
    return text or 'seccion'


def parse_page(path: Path) -> dict:
    source = path.read_text(encoding='utf-8')
    match = FRONT_RE.match(source)
    if not match:
        raise SystemExit(f'{path.name}: falta el front matter')
    meta = {}
    for line in match.group(1).splitlines():
        if ':' in line:
            key, value = line.split(':', 1)
            meta[key.strip()] = value.strip()
    for key in ('slug', 'title', 'group', 'description'):
        if not meta.get(key):
            raise SystemExit(f'{path.name}: falta {key}')
    return {**meta, 'source': f'pages/{path.name}', 'content': source[match.end():].strip() + '\n'}


def anchors_of(content: str) -> set[str]:
    used: dict[str, int] = {}
    result = set()
    first_h1 = True
    in_code = False
    for line in content.splitlines():
        if line.startswith('```'):
            in_code = not in_code
            continue
        if in_code:
            continue
        match = HEADING_RE.match(line)
        if not match:
            continue
        if len(match.group(1)) == 1 and first_h1:
            first_h1 = False
            continue
        base = match.group(3) or slugify(match.group(2))
        count = used.get(base, 0)
        used[base] = count + 1
        result.add(f'{base}-{count + 1}' if count else base)
    return result


def parameters_page() -> dict:
    from weapon_rebalancer.catalog.params import METHODS, NATIVE_PARAMS, PARAMS, RESOURCE_PARAMS, SECTIONS, UNSUPPORTED_PARAMS
    from weapon_rebalancer.profile_store.schema import MODULE_PRESET_KEYS, module_for_field

    lines = [
        '# Referencia de parámetros',
        '',
        'Esta página se genera automáticamente desde el registro de parámetros del código '
        '(`weapon_rebalancer/catalog/params.py`). Es exactamente lo que muestra el panel.',
        '',
        '## Métodos de aplicación {#metodos}',
        '',
        '| Método | Qué significa |',
        '| --- | --- |',
    ]
    for key, info in METHODS.items():
        lines.append(f'| **{info["label"]}** (`{key}`) | {info["description"]} |')
    lines += [
        '',
        '> [!NOTE]',
        '> **Límite del motor**: si un valor queda fuera, el motor lo recorta antes de escribir el META y el panel lo avisa. '
        '**Rango del editor**: solo es el recorrido del deslizador; puedes escribir un valor exacto distinto.',
        '',
        '> [!WARNING]',
        '> **Módulo**: el campo solo se aplica si ese módulo del perfil no está en `original`. Los campos de cabeza los escribe la '
        'política de cabeza (ver [Cabeza](#parametros/cabeza)).',
        '',
    ]
    for section in SECTIONS:
        specs = [spec for spec in PARAMS.values() if spec.section == section['id']]
        if not specs:
            continue
        anchor = 'cabeza' if section['id'] == 'headshot' else f'seccion-{section["id"]}'
        lines += [f'## {section["label"]} {{#{anchor}}}', '', section['summary'], '']
        if section['id'] == 'headshot':
            lines += [
                'Los multiplicadores y distancias de cabeza (`HeadShotDamageModifierPlayer`, `NetworkHeadShotPlayerDamageModifier`, '
                '`HeadShotDamageModifierAI` y las distancias mínima/máxima) los **escribe la política de cabeza** del perfil '
                '(`modules.headshot` + `headshot`), no se editan campo a campo. Con `modules.headshot = original` no se tocan.',
                '',
            ]
        for spec in specs:
            modules = module_for_field(spec.key)
            presets = [m for m, keys in MODULE_PRESET_KEYS.items() if spec.key in keys]
            lines.append(f'### {spec.label} {{#{spec.key}}}')
            lines.append('')
            if spec.description:
                lines.append(spec.description)
                lines.append('')
            rows = [
                ('Tag XML', f'`<{spec.tag}>`'),
                ('Clave en el perfil', f'`{spec.key}`'),
                ('Método', METHODS[spec.method]['label']),
            ]
            if spec.value_type in {'number', 'integer'}:
                rows.append(('Tipo', 'entero' if spec.value_type == 'integer' else 'número' + (f' ({spec.unit})' if spec.unit else '')))
            if spec.slider_min is not None:
                rows.append(('Rango del editor', f'{spec.slider_min:g} – {spec.slider_max:g}'))
            if spec.hard_min is not None:
                rows.append(('Límite del motor', f'{spec.hard_min:g} – {spec.hard_max:g}'))
            if modules:
                rows.append(('Módulo', ', '.join(f'`modules.{m}`' for m in modules)))
            if presets:
                rows.append(('Lo pisa el preset de', ', '.join(f'`modules.{m}`' for m in presets)))
            if spec.insertable:
                rows.append(('Si falta el tag', 'el motor puede crearlo'))
            if spec.advanced:
                rows.append(('Nivel', 'avanzado'))
            lines += ['| | |', '| --- | --- |'] + [f'| {k} | {v} |' for k, v in rows] + ['']
            if spec.notes:
                lines += ['> [!NOTE]', f'> {spec.notes}', '']
    lines += ['## Recursos externos {#recursos}', '', '| Parámetro | Método | Descripción |', '| --- | --- | --- |']
    for item in RESOURCE_PARAMS:
        lines.append(f'| {item["label"]} | {METHODS[item["method"]]["label"]} | {item["description"]} |')
    lines += ['', '## En ejecución (natives) {#natives}', '', '| Parámetro | Descripción |', '| --- | --- |']
    for item in NATIVE_PARAMS:
        lines.append(f'| {item["label"]} | {item["description"]} |')
    lines += ['', '## No compatibles {#no-compatibles}', '',
              'Se piden a menudo pero no existe un mecanismo real en esta instalación. El panel los muestra como no disponibles.', '',
              '| Parámetro | Por qué no |', '| --- | --- |']
    for item in UNSUPPORTED_PARAMS:
        lines.append(f'| {item["label"]} | {item["description"]} |')
    content = '\n'.join(lines) + '\n'
    return {
        'slug': 'parametros', 'title': 'Referencia de parámetros', 'group': 'Editor de armas',
        'description': 'Cada parámetro editable: qué controla, tag XML, método, límites y módulo.',
        'source': 'pages/05-parametros.generated.md', 'content': content, '_order': '05',
    }


def build() -> int:
    pages = []
    for path in sorted(PAGES.glob('*.md')):
        page = parse_page(path)
        page['_order'] = path.name[:2]
        pages.append(page)
    pages.append(parameters_page())
    pages.sort(key=lambda p: (p['_order'], p['slug']))

    slugs = {p['slug']: anchors_of(p['content']) for p in pages}
    errors = []
    by_file = {Path(p['source']).name: p['slug'] for p in pages}
    for page in pages:
        for href in LINK_RE.findall(page['content']):
            if href.startswith(('https://', 'http://')):
                continue
            if href.startswith('#'):
                target = href[1:]
                slug, _, anchor = target.partition('/')
            else:
                file, _, anchor = href.partition('#')
                slug = by_file.get(file) or file.removesuffix('.md')
            if slug not in slugs:
                if not href.startswith(('img/', '../')):
                    errors.append(f'{page["source"]}: enlace a página inexistente {href}')
                continue
            if anchor and anchor not in slugs[slug]:
                errors.append(f'{page["source"]}: ancla inexistente {href}')
    from weapon_rebalancer.catalog.params import PARAMS
    expected = set(UI_ANCHORS) | {f'parametros/{key}' for key in PARAMS}
    for target in sorted(expected):
        slug, _, anchor = target.partition('/')
        if slug not in slugs or anchor not in slugs[slug]:
            errors.append(f'El panel enlaza {target}, que no existe en la documentación.')
    for slug in UI_PAGES:
        if slug not in slugs:
            errors.append(f'El panel enlaza la página {slug}, que no existe.')
    if errors:
        raise SystemExit('Errores en la documentación:\n  ' + '\n  '.join(errors))

    version = (PROJECT / 'VERSION').read_text(encoding='utf-8').strip()
    payload = [{k: v for k, v in page.items() if not k.startswith('_')} for page in pages]
    OUTPUT.write_text(
        '// Generado por docs/tools/build_docs.py. Edita docs/pages/*.md en su lugar.\n'
        f'window.WR_DOCS_VERSION = {json.dumps(version)};\n'
        f'window.WR_DOCS = Object.freeze({json.dumps(payload, ensure_ascii=False, indent=2)});\n',
        encoding='utf-8',
    )
    return len(payload)


if __name__ == '__main__':
    print(f'{build()} páginas generadas en {OUTPUT}')
