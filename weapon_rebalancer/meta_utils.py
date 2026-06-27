from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

from .fields import FIELDS, EXTRACT_GROUP_RE, EXTRACT_NAME_RE
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


def iter_weapon_meta_files(root: Path, skip_basenames: set[str]) -> list[Path]:
    # Compatibilidad con versiones anteriores. La nueva lógica usa scanner.py.
    return discover_meta_paths(root, ScanConfig(), skip_basenames)


def insert_field_if_missing(content: str, key: str, value: str) -> tuple[str, bool]:
    """Inserta un tag soportado si no existe en el bloque.

    Esto es especialmente útil para metas custom que no traen
    NetworkHeadShotPlayerDamageModifier. Se intenta colocar cerca de los tags
    de headshot para mantener el XML legible.
    """
    field = FIELDS[key]
    if field.pattern.search(content):
        return content, False

    snippet = field.xml_snippet(value)
    indent = _guess_indent(content)
    line = f'{indent}{snippet}\n'

    # Puntos de anclaje preferidos dentro de CWeaponInfo.
    anchors_by_key = {
        'network_headshot': ['HeadShotDamageModifierPlayer', 'HeadshotDamageModifierPlayer'],
        'headshot_player': ['DamageFallOffModifier', 'Damage'],
        'headshot_ai': ['NetworkHeadShotPlayerDamageModifier', 'HeadShotDamageModifierPlayer'],
        'min_headshot_player': ['HeadShotDamageModifierAI', 'NetworkHeadShotPlayerDamageModifier'],
        'max_headshot_player': ['MinHeadShotDistancePlayer'],
        'min_headshot_ai': ['MaxHeadShotDistancePlayer'],
        'max_headshot_ai': ['MinHeadShotDistanceAI'],
    }

    for anchor in anchors_by_key.get(key, []):
        pos = _find_end_of_tag_line(content, anchor)
        if pos is not None:
            return content[:pos] + line + content[pos:], True

    # Fallback: antes del cierre del Item.
    close_pos = content.rfind('</Item>')
    if close_pos != -1:
        return content[:close_pos] + line + content[close_pos:], True

    return content, False


def _guess_indent(content: str) -> str:
    for tag in ('HeadShotDamageModifierPlayer', 'Damage', 'WeaponRange'):
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
