from __future__ import annotations

import json
import xml.etree.ElementTree as ET
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from .fields import FIELDS
from .meta_utils import extract_xml_inventory, read_text
from .scanner import ScanConfig, extract_weapon_blocks, find_package_configs


def _coerce(value: str) -> Any:
    text = value.strip()
    lowered = text.lower()
    if lowered in {'true', 'false'}:
        return lowered == 'true'
    try:
        if any(ch in text for ch in ('.', 'e', 'E')):
            return float(text)
        return int(text)
    except ValueError:
        return text


def export_meta_inventory(root: Path, destination: Path) -> dict[str, Any]:
    files: list[dict[str, Any]] = []
    tag_counts: Counter[str] = Counter()
    parse_errors: list[dict[str, str]] = []

    for path in sorted(root.rglob('*.meta')):
        if not path.is_file() or path.name.lower().endswith(('.bak', '.meta.bak')):
            continue
        text = read_text(path)
        inventory = extract_xml_inventory(text)
        entry: dict[str, Any] = {
            'path': str(path),
            'relative_path': str(path.relative_to(root)),
            'size_bytes': path.stat().st_size,
            **inventory,
        }
        if 'parse_error' in inventory:
            parse_errors.append({'path': str(path), 'error': str(inventory['parse_error'])})
        for leaf in inventory.get('leaves', []):
            tag = leaf.get('tag')
            if tag:
                tag_counts[str(tag)] += 1
        files.append(entry)

    result = {
        'format': 'weapon_rebalancer_meta_inventory_v2',
        'root': str(root),
        'summary': {
            'meta_files': len(files),
            'unique_tags': len(tag_counts),
            'parse_errors': len(parse_errors),
        },
        'tag_catalog': dict(sorted(tag_counts.items(), key=lambda item: (-item[1], item[0].lower()))),
        'parse_errors': parse_errors,
        'files': files,
    }
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    return result


def _direct_leaf_data(block_text: str) -> list[tuple[str, str, Any]]:
    try:
        root = ET.fromstring(block_text)
    except ET.ParseError:
        return []
    result: list[tuple[str, str, Any]] = []
    for child in list(root):
        if list(child):
            continue
        if 'value' in child.attrib:
            result.append((child.tag, 'value_attr', _coerce(child.attrib['value'])))
        elif 'ref' in child.attrib:
            result.append((child.tag, 'ref_attr', child.attrib['ref']))
        elif child.attrib:
            result.append((child.tag, 'attributes', dict(child.attrib)))
        else:
            result.append((child.tag, 'text', (child.text or '').strip()))
    return result


def export_full_profile(root: Path, destination: Path, scan: ScanConfig | None = None) -> dict[str, Any]:
    scan = scan or ScanConfig(recursive=True, scan_all_meta=True, require_weapon_info=False)
    package_configs = find_package_configs(root, scan)
    tag_to_key: dict[str, str] = {}
    for key, field in FIELDS.items():
        for tag in field.all_tags:
            tag_to_key[tag.lower()] = key

    weapons: dict[str, dict[str, Any]] = {}
    duplicates: defaultdict[str, list[str]] = defaultdict(list)

    for path in sorted(root.rglob('*.meta')):
        if not path.is_file() or path.name.lower().endswith(('.bak', '.meta.bak')):
            continue
        text = read_text(path)
        for block in extract_weapon_blocks(path, text, scan, package_configs):
            fields: dict[str, Any] = {}
            meta: dict[str, Any] = {}
            flags: list[str] = []
            for tag, kind, value in _direct_leaf_data(block.text):
                key = tag_to_key.get(tag.lower())
                if key == 'weapon_flags':
                    flags = [v for v in str(value).replace(',', ' ').split() if v]
                elif key:
                    fields[key] = value
                elif kind == 'attributes':
                    meta[tag] = {'attributes': value, 'create_if_missing': False}
                else:
                    meta[tag] = {'kind': kind, 'value': value, 'create_if_missing': False}

            source = str(path.relative_to(root))
            entry = {
                '_documentation': {
                    'source': source,
                    'group_detected': block.group,
                    'block_source': block.source,
                },
                'fields': fields,
                'meta': meta,
                'weapon_flags': {
                    'add': flags,
                    'remove': [],
                    'create_if_missing': False,
                },
            }
            if block.weapon in weapons:
                duplicates[block.weapon].append(source)
                # La última definición suele tener prioridad de carga; la conservamos,
                # pero documentamos todas las fuentes duplicadas.
                previous_source = weapons[block.weapon].get('_documentation', {}).get('source')
                if previous_source:
                    duplicates[block.weapon].insert(0, str(previous_source))
            weapons[block.weapon] = entry

    for weapon, sources in duplicates.items():
        unique_sources = list(dict.fromkeys(sources))
        weapons[weapon]['_documentation']['duplicate_sources'] = unique_sources

    result = {
        'name': 'Perfil completo exportado desde los META originales',
        'base_preset': 'rp_balanced',
        'modules': {
            'damage': 'original',
            'armour': 'original',
            'recoil': 'original',
            'accuracy': 'original',
            'range': 'original',
            'fire_rate': 'original',
            'reload': 'original',
            'headshot': 'original',
        },
        'validation': {'strict_unknown_fields': True},
        '_documentation': {
            'root': str(root),
            'weapons_exported': len(weapons),
            'duplicates': len(duplicates),
            'warning': 'Este perfil replica los valores encontrados. Edita solo lo necesario; no actives todo a ciegas.',
        },
        'defaults': {'fields': {}, 'meta': {}, 'weapon_flags': {'add': [], 'remove': [], 'create_if_missing': False}},
        'groups': {},
        'weapons': dict(sorted(weapons.items())),
        'ignore_weapons': [],
        'harmless_weapons': ['WEAPON_SNOWBALL', 'WEAPON_BALL'],
        'allow_damage_weapons': [],
    }
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    return result
