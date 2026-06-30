from __future__ import annotations

import re
import shutil
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any
from xml.sax.saxutils import escape

from .fields import FIELDS
from .scanner import ScanConfig, discover_meta_paths, extract_group as scan_extract_group, extract_name as scan_extract_name


def read_text(path: Path) -> str:
    return path.read_text(encoding='utf-8', errors='ignore')


def write_text(path: Path, content: str, *, dry_run: bool, backup: bool) -> None:
    if dry_run:
        return
    if backup:
        backup_path = path.with_suffix(path.suffix + '.bak')
        if not backup_path.exists():
            shutil.copy2(path, backup_path)
    path.write_text(content, encoding='utf-8')


def extract_weapon_name(content: str) -> str | None:
    return scan_extract_name(content)


def extract_group(content: str) -> str | None:
    return scan_extract_group(content)


def replace_field(content: str, key: str, value: str) -> tuple[str, bool]:
    field = FIELDS[key]
    new_content, count = field.pattern.subn(lambda m: f'{m.group(1)}{value}{m.group(3)}', content, count=1)
    return new_content, count > 0


def read_field_value(content: str, key: str, default: Any = None) -> Any:
    """Lee el primer valor de un campo catalogado sin modificar el XML."""
    field = FIELDS[key]
    match = field.pattern.search(content)
    if not match:
        return default
    raw = match.group(2).strip()
    if field.kind in {'value_attr'}:
        lowered = raw.lower()
        if lowered in {'true', 'false'}:
            return lowered == 'true'
        try:
            if any(ch in raw for ch in ('.', 'e', 'E')):
                return float(raw)
            return int(raw)
        except ValueError:
            return raw
    return raw


def read_weapon_flags(content: str) -> list[str]:
    value = read_field_value(content, 'weapon_flags', '')
    return parse_weapon_flags(str(value)) if value is not None else []


def iter_weapon_meta_files(root: Path, skip_basenames: set[str]) -> list[Path]:
    return discover_meta_paths(root, ScanConfig(), skip_basenames)


def insert_field_if_missing(content: str, key: str, value: str) -> tuple[str, bool]:
    field = FIELDS[key]
    if field.pattern.search(content):
        return content, False
    if not field.safe_insert:
        return content, False

    return insert_xml_snippet(content, field.xml_snippet(value), anchor_tags=_anchors_for_key(key))


def insert_xml_snippet(
    content: str,
    snippet: str,
    *,
    anchor_tags: list[str] | tuple[str, ...] = (),
) -> tuple[str, bool]:
    indent = _guess_indent(content)
    line = f'{indent}{snippet}\n'

    for anchor in anchor_tags:
        pos = _find_end_of_tag_line(content, anchor)
        if pos is not None:
            return content[:pos] + line + content[pos:], True

    close_pos = content.rfind('</Item>')
    if close_pos != -1:
        line_start = content.rfind('\n', 0, close_pos) + 1
        if content[line_start:close_pos].strip() == '':
            return content[:line_start] + line + content[line_start:], True
        return content[:close_pos] + line + content[close_pos:], True

    return content, False


def _anchors_for_key(key: str) -> list[str]:
    anchors_by_key = {
        'network_headshot': ['HeadShotDamageModifierPlayer', 'HeadshotDamageModifierPlayer'],
        'headshot_player': ['DamageFallOffModifier', 'Damage'],
        'headshot_ai': ['NetworkHeadShotPlayerDamageModifier', 'HeadShotDamageModifierPlayer'],
        'min_headshot_player': ['HeadShotDamageModifierAI', 'NetworkHeadShotPlayerDamageModifier'],
        'max_headshot_player': ['MinHeadShotDistancePlayer'],
        'min_headshot_ai': ['MaxHeadShotDistancePlayer'],
        'max_headshot_ai': ['MinHeadShotDistanceAI'],
        'lightly_armoured': ['NetworkHitLimbsDamageModifier', 'HitLimbsDamageModifier', 'Damage'],
        'penetration': ['FragImpulse', 'ProjectileForce', 'ForceFalloffMin'],
        'weapon_flags': ['GunFeedBone', 'TargetSequenceGroup', 'HumanNameHash'],
        'damage': ['HeadShotDamageModifierPlayer', 'ClipSize'],
        'weapon_range': ['LockOnRange', 'NetworkHeadShotPlayerDamageModifier'],
        'falloff_min': ['AiPotentialBlastEventRange', 'WeaponRange'],
        'falloff_max': ['DamageFallOffRangeMin'],
        'falloff_modifier': ['DamageFallOffRangeMax'],
    }
    return anchors_by_key.get(key, [])


def normalize_dynamic_spec(tag: str, spec: Any) -> dict[str, Any]:
    if isinstance(spec, dict):
        result = dict(spec)
        result.setdefault('tag', tag)
        if 'value' not in result and 'text' in result:
            result['value'] = result['text']
        return result
    return {'tag': tag, 'value': spec}


def replace_dynamic_field(content: str, tag: str, spec: Any) -> tuple[str, bool, bool, str | None]:
    """Reemplaza una hoja XML exacta sin conocerla de antemano.

    Retorna: (contenido, cambió, encontrado/insertado, error).
    Formatos aceptados:
      "Tag": 1.0
      "Tag": {"value": 1.0, "kind": "value_attr", "create_if_missing": false}
      "Vector": {"attributes": {"x": 0, "y": 1, "z": 2}}
    """
    cfg = normalize_dynamic_spec(tag, spec)
    actual_tag = str(cfg.get('tag') or tag)
    kind = cfg.get('kind')
    value = cfg.get('value')
    attrs = cfg.get('attributes')
    create = bool(cfg.get('create_if_missing', False))
    anchor = cfg.get('anchor')

    if attrs is not None:
        if not isinstance(attrs, dict):
            return content, False, False, f'{actual_tag}: attributes debe ser objeto'
        pattern = re.compile(rf'(<{re.escape(actual_tag)}\b)([^>]*?)(/?>)', re.IGNORECASE)
        match = pattern.search(content)
        if match:
            rebuilt = match.group(2)
            changed = False
            for attr_name, attr_value in attrs.items():
                attr_re = re.compile(rf'(\b{re.escape(str(attr_name))}\s*=\s*")([^"]*)(")', re.IGNORECASE)
                escaped = escape(str(attr_value), {'"': '&quot;'})
                if attr_re.search(rebuilt):
                    new_rebuilt = attr_re.sub(lambda m: f'{m.group(1)}{escaped}{m.group(3)}', rebuilt, count=1)
                else:
                    new_rebuilt = rebuilt.rstrip() + f' {attr_name}="{escaped}"'
                changed = changed or new_rebuilt != rebuilt
                rebuilt = new_rebuilt
            if not changed:
                return content, False, True, None
            replacement = match.group(1) + rebuilt + match.group(3)
            return content[:match.start()] + replacement + content[match.end():], True, True, None
        if not create:
            return content, False, False, None
        attr_text = ' '.join(f'{k}="{escape(str(v), {chr(34): "&quot;"})}"' for k, v in attrs.items())
        snippet = f'<{actual_tag} {attr_text} />'
        updated, inserted = insert_xml_snippet(content, snippet, anchor_tags=[str(anchor)] if anchor else [])
        return updated, inserted, inserted, None

    if value is None:
        return content, False, False, f'{actual_tag}: falta value'

    escaped_value = escape(str(value), {'"': '&quot;'})

    candidates: list[tuple[str, re.Pattern[str]]] = []
    if kind in (None, 'value_attr'):
        candidates.append(('value_attr', re.compile(rf'(<{re.escape(actual_tag)}\b[^>]*?\bvalue=")([^"]*)("[^>]*/>)', re.IGNORECASE)))
    if kind in (None, 'ref_attr'):
        candidates.append(('ref_attr', re.compile(rf'(<{re.escape(actual_tag)}\b[^>]*?\bref=")([^"]*)("[^>]*/>)', re.IGNORECASE)))
    if kind in (None, 'text'):
        candidates.append(('text', re.compile(rf'(<{re.escape(actual_tag)}>)([^<]*)(</{re.escape(actual_tag)}>)', re.IGNORECASE)))

    for detected_kind, pattern in candidates:
        match = pattern.search(content)
        if not match:
            continue
        if match.group(2) == escaped_value:
            return content, False, True, None
        updated = content[:match.start()] + f'{match.group(1)}{escaped_value}{match.group(3)}' + content[match.end():]
        return updated, True, True, None

    if not create:
        return content, False, False, None

    insert_kind = str(kind or 'value_attr')
    if insert_kind == 'text':
        snippet = f'<{actual_tag}>{escaped_value}</{actual_tag}>'
    elif insert_kind == 'ref_attr':
        snippet = f'<{actual_tag} ref="{escaped_value}" />'
    else:
        snippet = f'<{actual_tag} value="{escaped_value}" />'
    updated, inserted = insert_xml_snippet(content, snippet, anchor_tags=[str(anchor)] if anchor else [])
    return updated, inserted, inserted, None


def parse_weapon_flags(text: str) -> list[str]:
    return [token for token in re.split(r'[\s,]+', text.strip()) if token]


def update_weapon_flags(
    content: str,
    *,
    add: list[str] | set[str] | tuple[str, ...] = (),
    remove: list[str] | set[str] | tuple[str, ...] = (),
    create_if_missing: bool = False,
) -> tuple[str, bool, bool]:
    field = FIELDS['weapon_flags']
    match = field.pattern.search(content)
    add_list = [str(v).strip() for v in add if str(v).strip()]
    remove_set = {str(v).strip().lower() for v in remove if str(v).strip()}

    if match:
        original = match.group(2)
        tokens = parse_weapon_flags(original)
        result: list[str] = []
        seen: set[str] = set()
        for token in tokens:
            lowered = token.lower()
            if lowered in remove_set or lowered in seen:
                continue
            result.append(token)
            seen.add(lowered)
        for token in add_list:
            lowered = token.lower()
            if lowered in remove_set or lowered in seen:
                continue
            result.append(token)
            seen.add(lowered)

        separator = ', ' if ',' in original else ' '
        new_value = separator.join(result)
        if new_value == original.strip():
            return content, False, True
        updated = content[:match.start()] + f'{match.group(1)}{new_value}{match.group(3)}' + content[match.end():]
        return updated, True, True

    if not create_if_missing or not add_list:
        return content, False, False

    snippet = FIELDS['weapon_flags'].xml_snippet(' '.join(dict.fromkeys(add_list)))
    updated, inserted = insert_xml_snippet(content, snippet, anchor_tags=_anchors_for_key('weapon_flags'))
    return updated, inserted, inserted


def extract_xml_inventory(xml_text: str) -> dict[str, Any]:
    """Extrae todas las hojas/atributos de un XML conservando rutas repetidas."""
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError as exc:
        return {'parse_error': str(exc), 'leaves': []}

    leaves: list[dict[str, Any]] = []

    def walk(node: ET.Element, path: str) -> None:
        children = list(node)
        entry: dict[str, Any] = {'path': path, 'tag': node.tag}
        if node.attrib:
            entry['attributes'] = dict(node.attrib)
        text = (node.text or '').strip()
        if text:
            entry['text'] = text
        if not children or node.attrib or text:
            leaves.append(entry)
        counts: dict[str, int] = {}
        for child in children:
            counts[child.tag] = counts.get(child.tag, 0) + 1
            suffix = f'[{counts[child.tag]}]' if sum(1 for c in children if c.tag == child.tag) > 1 else ''
            walk(child, f'{path}/{child.tag}{suffix}')

    walk(root, root.tag)
    return {'root_tag': root.tag, 'leaves': leaves}


def _guess_indent(content: str) -> str:
    for tag in ('HeadShotDamageModifierPlayer', 'Damage', 'WeaponRange', 'ClipSize', 'Name'):
        idx = content.find(f'<{tag}')
        if idx == -1:
            continue
        start = content.rfind('\n', 0, idx) + 1
        prefix = content[start:idx]
        if prefix.strip() == '':
            return prefix
    return '        '


def _find_end_of_tag_line(content: str, tag: str) -> int | None:
    idx = content.lower().find(f'<{tag.lower()}')
    if idx == -1:
        return None
    line_end = content.find('\n', idx)
    if line_end == -1:
        tag_end = content.find('>', idx)
        return tag_end + 1 if tag_end != -1 else None
    return line_end + 1
