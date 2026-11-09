"""Componentes aceptados por un arma (AttachPoints de CWeaponInfo).

Un componente nuevo (por ejemplo una skin de flow_weaponpaint hecha como variante de modelo) solo se puede
poner en el arma si figura en sus AttachPoints. Este módulo agrega o quita nombres en el AttachBone indicado,
sin tocar el resto del bloque, y crea el AttachBone si no existe. Desde la 7.9.0 respeta un tope de 12 componentes por
punto de montaje (lo que no entra va a otro punto del mismo hueso) y no repite lo que ya está en otro punto del hueso.

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
MAX_PER_POINT = 12          # componentes por punto de montaje (los packs reparten de a 12)


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


def _bone_items(section: str, bone: str) -> list[tuple[int, int]]:
    """Todos los <Item> de primer nivel cuyo AttachBone es `bone` (sin distinguir mayúsculas)."""
    out = []
    for a, b in _attach_items(section):
        m = re.search(r'<AttachBone>(.*?)</AttachBone>', section[a:b])
        if m and m.group(1).strip().lower() == bone.lower():
            out.append((a, b))
    return out


def _component_names(item: str) -> list[str]:
    i, j = item.find('<Components>'), item.rfind('</Components>')
    return re.findall(r'<Name>(.*?)</Name>', item[i:j]) if i >= 0 and j >= 0 else []


def _component_xml(indent: str, name: str) -> str:
    return f'{indent}<Item>\n{indent}  <Name>{name}</Name>\n{indent}  <Default value="false" />\n{indent}</Item>\n'


def update_attach_components(
    content: str,
    *,
    add: dict[str, list[str]] | None = None,
    remove: dict[str, list[str]] | None = None,
    max_per_point: int = MAX_PER_POINT,
) -> tuple[str, bool, list[str]]:
    """Devuelve (contenido, cambió, problemas). Idempotente: agregar algo que ya está no cambia nada.

    Un arma puede tener varios puntos de montaje con el mismo AttachBone (Glizzy y kyros lo hacen). Desde la 7.9.0:
      - lo que ya está en cualquiera de esos puntos no se repite;
      - `remove` quita el componente de todos;
      - cada punto lleva como mucho `max_per_point` componentes (12, como reparten los packs): lo que no entra en los
        puntos que ya existen va a puntos nuevos del mismo hueso, al final de AttachPoints.
    """
    add, remove = add or {}, remove or {}
    span = _attach_points_span(content)
    if not span:
        return content, False, ['sin <AttachPoints> en el bloque'] if (add or remove) else []
    s0, s1 = span
    section = content[s0:s1]
    original = section
    problems: list[str] = []
    cap = max(1, int(max_per_point))

    for bone in list(dict.fromkeys([*add.keys(), *remove.keys()])):
        drop = {n.lower() for n in remove.get(bone, [])}

        # Quitar (en todos los puntos del hueso; de atrás hacia adelante para no mover posiciones)
        for a, b in reversed(_bone_items(section, bone)):
            item = section[a:b]
            ci, cj = item.find('<Components>'), item.rfind('</Components>')
            if ci < 0 or cj < 0:
                continue
            inner = item[ci + len('<Components>'):cj]
            kept = inner
            for m in reversed(list(re.finditer(r'[ \t]*<Item>\s*(?:<Default[^>]*/>\s*)?<Name>(.*?)</Name>.*?</Item>[ \t]*\n?',
                                               inner, re.S))):
                if m.group(1).lower() in drop:
                    kept = kept[:m.start()] + kept[m.end():]
            if kept != inner:
                section = section[:a] + item[:ci + len('<Components>')] + kept + item[cj:] + section[b:]

        # Pendientes: lo pedido que no está en ningún punto del hueso
        present = set()
        for a, b in _bone_items(section, bone):
            present.update(n.lower() for n in _component_names(section[a:b]))
        pending = []
        for n in add.get(bone, []):
            if n.lower() not in present and n.lower() not in drop and n.lower() not in {p.lower() for p in pending}:
                pending.append(n)
        for a, b in _bone_items(section, bone):
            count = len(_component_names(section[a:b]))
            if count > cap:
                problems.append(f'{bone}: un punto de montaje ya trae {count} componentes (tope {cap})')
        if not pending:
            continue

        # Llenar los puntos que ya existen (en orden) hasta el tope
        k = 0
        while pending:
            spans = _bone_items(section, bone)
            if k >= len(spans):
                break
            a, b = spans[k]
            k += 1
            item = section[a:b]
            ci, cj = item.find('<Components>'), item.rfind('</Components>')
            if ci < 0 or cj < 0:
                problems.append(f'{bone}: AttachBone sin <Components>')
                continue
            room = cap - len(_component_names(item))
            if room <= 0:
                continue
            take, pending = pending[:room], pending[room:]
            inner = item[ci + len('<Components>'):cj]
            first = re.search(r'\n([ \t]*)<Item>', inner)
            comp_indent = first.group(1) if first else _indent_before(item, ci) + '  '
            closing_indent = _indent_before(item, cj)
            body = inner.rstrip(' \t')
            if not body.endswith('\n'):
                body += '\n'
            inner = body + ''.join(_component_xml(comp_indent, n) for n in take) + closing_indent
            section = section[:a] + item[:ci + len('<Components>')] + inner + item[cj:] + section[b:]

        # Lo que no entró va a puntos nuevos del mismo hueso
        while pending:
            take, pending = pending[:cap], pending[cap:]
            items = _attach_items(section)
            close = section.rfind('</AttachPoints>')
            item_indent = _indent_before(section, items[-1][0]) if items else _indent_before(section, close) + '  '
            comp_indent = item_indent + '    '
            block = (f'{item_indent}<Item>\n{item_indent}  <AttachBone>{bone}</AttachBone>\n{item_indent}  <Components>\n'
                     + ''.join(_component_xml(comp_indent, n) for n in take)
                     + f'{item_indent}  </Components>\n{item_indent}</Item>\n')
            line_start = section.rfind('\n', 0, close) + 1
            section = section[:line_start] + block + section[line_start:]

    if section == original:
        return content, False, problems
    return content[:s0] + section + content[s1:], True, problems
