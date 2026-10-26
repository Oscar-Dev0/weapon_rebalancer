"""Componentes aceptados por un arma (AttachPoints de CWeaponInfo).

Un componente nuevo (por ejemplo una skin de flow_weaponpaint hecha como variante de modelo) solo se puede
poner en el arma si figura en sus AttachPoints. Este módulo agrega o quita nombres en el AttachBone indicado,
sin tocar el resto del bloque, y crea el AttachBone si no existe.

Perfil:
    "weapons": {
        "WEAPON_CARBINERIFLE": {
            "attach_components": {
                "add":    { "gun_root": ["COMPONENT_CARBINERIFLE_FWP_FLOW_NEON"] },
                "remove": { "gun_root": [] }
            }
        }
    }
"""
from __future__ import annotations

import re
from typing import Any

NAME_RE = re.compile(r'^[A-Za-z0-9_]{1,64}$')


class AttachComponentsError(ValueError):
    pass


def normalize_component_ops(value: Any, context: str) -> dict[str, dict[str, list[str]]]:
    """{'add': {bone: [nombres]}, 'remove': {bone: [nombres]}} validado; {} si no hay nada."""
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise AttachComponentsError(f'{context}.attach_components debe ser un objeto JSON.')
    out: dict[str, dict[str, list[str]]] = {}
    for op in ('add', 'remove'):
        bones = value.get(op) or {}
        if not isinstance(bones, dict):
            raise AttachComponentsError(f'{context}.attach_components.{op} debe ser {{"bone": ["COMPONENT_X"]}}.')
        for bone, names in bones.items():
            if not NAME_RE.match(str(bone)):
                raise AttachComponentsError(f'{context}.attach_components.{op}: bone inválido «{bone}».')
            if not isinstance(names, list):
                raise AttachComponentsError(f'{context}.attach_components.{op}.{bone} debe ser una lista.')
            clean = []
            for name in names:
                if not NAME_RE.match(str(name)):
                    raise AttachComponentsError(f'{context}.attach_components.{op}.{bone}: componente inválido «{name}».')
                clean.append(str(name).upper())
            if clean:
                out.setdefault(op, {})[str(bone)] = list(dict.fromkeys(clean))
    unknown = set(value) - {'add', 'remove', '_comment'}
    if unknown:
        raise AttachComponentsError(f'{context}.attach_components: claves desconocidas {sorted(unknown)}.')
    return out


def _attach_points_span(content: str) -> tuple[int, int] | None:
    start = content.find('<AttachPoints>')
    if start < 0:
        return None
    end = content.find('</AttachPoints>', start)
    if end < 0:
        return None
    return start, end + len('</AttachPoints>')


def _attach_items(section: str) -> list[tuple[int, int]]:
    """Posiciones de cada <Item> de primer nivel dentro de <AttachPoints>."""
    spans, depth = [], 0
    token = re.compile(r'<Item\b[^>]*?(/?)>|</Item>')
    start = None
    for m in token.finditer(section):
        if m.group(0).startswith('</'):
            depth -= 1
            if depth == 0 and start is not None:
                spans.append((start, m.end()))
                start = None
        elif m.group(1) == '/':
            continue
        else:
            if depth == 0:
                start = m.start()
            depth += 1
    return spans


def read_attach_components(content: str) -> dict[str, list[str]]:
    span = _attach_points_span(content)
    if not span:
        return {}
    section = content[span[0]:span[1]]
    out: dict[str, list[str]] = {}
    for a, b in _attach_items(section):
        item = section[a:b]
        bone = re.search(r'<AttachBone>(.*?)</AttachBone>', item)
        if bone:
            out[bone.group(1)] = re.findall(r'<Name>(.*?)</Name>', item)
    return out


def _indent_before(text: str, index: int) -> str:
    line_start = text.rfind('\n', 0, index) + 1
    return re.match(r'[ \t]*', text[line_start:]).group(0)


def update_attach_components(
    content: str,
    *,
    add: dict[str, list[str]] | None = None,
    remove: dict[str, list[str]] | None = None,
) -> tuple[str, bool, list[str]]:
    """Devuelve (contenido, cambió, problemas). Idempotente: agregar algo que ya está no cambia nada."""
    add, remove = add or {}, remove or {}
    span = _attach_points_span(content)
    if not span:
        return content, False, ['sin <AttachPoints> en el bloque'] if (add or remove) else []
    s0, s1 = span
    section = content[s0:s1]
    original = section
    problems: list[str] = []

    for bone in list(dict.fromkeys([*add.keys(), *remove.keys()])):
        items = _attach_items(section)
        target = None
        for a, b in items:
            m = re.search(r'<AttachBone>(.*?)</AttachBone>', section[a:b])
            if m and m.group(1).lower() == bone.lower():
                target = (a, b)
                break

        wanted = [n for n in add.get(bone, [])]
        drop = {n.lower() for n in remove.get(bone, [])}

        if target is None:
            if not wanted:
                continue
            close = section.rfind('</AttachPoints>')
            item_indent = _indent_before(section, items[-1][0]) if items else _indent_before(section, close) + '  '
            comp_indent = item_indent + '    '
            components = ''.join(
                f'{comp_indent}<Item>\n{comp_indent}  <Name>{n}</Name>\n{comp_indent}  <Default value="false" />\n{comp_indent}</Item>\n'
                for n in wanted if n.lower() not in drop)
            block = (f'{item_indent}<Item>\n{item_indent}  <AttachBone>{bone}</AttachBone>\n{item_indent}  <Components>\n'
                     f'{components}{item_indent}  </Components>\n{item_indent}</Item>\n')
            line_start = section.rfind('\n', 0, close) + 1
            section = section[:line_start] + block + section[line_start:]
            continue

        a, b = target
        item = section[a:b]
        comps_open = item.find('<Components>')
        comps_close = item.rfind('</Components>')
        if comps_open < 0 or comps_close < 0:
            problems.append(f'{bone}: AttachBone sin <Components>')
            continue
        inner = item[comps_open + len('<Components>'):comps_close]

        # Quitar
        kept_inner = inner
        for m in reversed(list(re.finditer(r'[ \t]*<Item>\s*<Name>(.*?)</Name>.*?</Item>[ \t]*\n?', inner, re.S))):
            if m.group(1).lower() in drop:
                kept_inner = kept_inner[:m.start()] + kept_inner[m.end():]
        present = {n.lower() for n in re.findall(r'<Name>(.*?)</Name>', kept_inner)}

        # Agregar (con la sangría del primer componente existente)
        first = re.search(r'\n([ \t]*)<Item>', kept_inner)
        comp_indent = first.group(1) if first else _indent_before(item, comps_open) + '  '
        closing_indent = _indent_before(item, comps_close)
        additions = ''.join(
            f'{comp_indent}<Item>\n{comp_indent}  <Name>{n}</Name>\n{comp_indent}  <Default value="false" />\n{comp_indent}</Item>\n'
            for n in wanted if n.lower() not in present and n.lower() not in drop)
        if additions:
            body = kept_inner.rstrip(' \t')
            if not body.endswith('\n'):
                body += '\n'
            kept_inner = body + additions + closing_indent
        if kept_inner != inner:
            item = item[:comps_open + len('<Components>')] + kept_inner + item[comps_close:]
            section = section[:a] + item + section[b:]

    if section == original:
        return content, False, problems
    return content[:s0] + section + content[s1:], True, problems
