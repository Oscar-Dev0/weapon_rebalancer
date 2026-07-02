from __future__ import annotations

import re
from pathlib import Path

_COMPONENT_DAMAGE_RE = re.compile(
    r'<(?P<tag>DamageModifier|DamageMultiplier|NetworkPlayerDamageModifier)\b[^>]*\bvalue\s*=\s*["\'](?P<value>-?\d+(?:\.\d+)?)["\']',
    re.IGNORECASE,
)


def scan_component_damage_modifiers(root: Path) -> dict[str, list[str]]:
    findings: dict[str, list[str]] = {}
    if not root.exists():
        return findings
    for path in sorted(root.rglob('*.meta')):
        name = path.name.lower()
        if 'component' not in name and 'weaponcomponent' not in str(path).lower():
            continue
        text = path.read_text(encoding='utf-8', errors='ignore')
        entries: list[str] = []
        for match in _COMPONENT_DAMAGE_RE.finditer(text):
            value = float(match.group('value'))
            if abs(value - 1.0) > 1e-6:
                entries.append(f'{match.group("tag")}={value:g}')
        if entries:
            findings[str(path)] = sorted(set(entries))
    return findings


def scan_projectile_weapons(root: Path, scan: object, skip_basenames: set[str]) -> dict[str, str]:
    from .meta_utils import read_field_value, read_text
    from .scanner import discover_meta_paths, extract_weapon_blocks

    findings: dict[str, str] = {}
    for path in discover_meta_paths(root, scan, skip_basenames):
        for block in extract_weapon_blocks(path, read_text(path), scan, []):
            fire_type = str(read_field_value(block.text, 'fire_type', '')).upper()
            if fire_type != 'PROJECTILE':
                continue
            ammo = str(read_field_value(block.text, 'ammo_info', '') or 'SIN_AMMOINFO')
            findings[block.weapon.upper()] = f'{path} | AmmoInfo={ammo}'
    return findings
