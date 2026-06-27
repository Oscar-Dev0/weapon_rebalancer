from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .fields import EXTRACT_GROUP_RE, EXTRACT_NAME_RE

WEAPON_ITEM_RE = re.compile(
    r'(?P<block><Item\s+type="CWeaponInfo"[^>]*>.*?</Item>)',
    re.IGNORECASE | re.DOTALL,
)
DATA_FILE_RE = re.compile(r"data_file\s+['\"](?P<kind>[^'\"]+)['\"]\s+['\"](?P<path>[^'\"]+)['\"]", re.IGNORECASE)

@dataclass
class ScanConfig:
    recursive: bool = True
    include_bak: bool = False
    scan_all_meta: bool = True
    require_weapon_info: bool = False
    package_config_names: tuple[str, ...] = (
        'weapon_rebalance.json',
        'weapon_balance.json',
        'rebalance.json',
        '.weapon_rebalance.json',
    )
    skip_dir_names: set[str] = field(default_factory=lambda: {
        '.git', '.svn', '__pycache__', 'node_modules', 'cache', 'stream'
    })
    group_hints_by_path: dict[str, str] = field(default_factory=lambda: {
        'melee': 'GROUP_MELEE',
        'knife': 'GROUP_MELEE',
        'dagger': 'GROUP_MELEE',
        'bat': 'GROUP_MELEE',
        'pistol': 'GROUP_PISTOL',
        'handgun': 'GROUP_PISTOL',
        'smg': 'GROUP_SMG',
        'rifle': 'GROUP_RIFLE',
        'shotgun': 'GROUP_SHOTGUN',
        'sniper': 'GROUP_SNIPER',
        'mg': 'GROUP_MG',
    })
    weapon_group_overrides: dict[str, str] = field(default_factory=dict)

@dataclass
class PackageConfig:
    path: Path
    data: dict[str, Any]

@dataclass
class WeaponBlock:
    path: Path
    start: int
    end: int
    text: str
    weapon: str
    group: str
    config_stack: list[PackageConfig]
    source: str = 'CWeaponInfo'


def _safe_json_load(path: Path) -> dict[str, Any] | None:
    try:
        data = json.loads(path.read_text(encoding='utf-8'))
    except Exception:
        return None
    return data if isinstance(data, dict) else None


def find_package_configs(root: Path, cfg: ScanConfig) -> list[PackageConfig]:
    found: list[PackageConfig] = []
    for path in root.rglob('*'):
        if not path.is_file() or path.name not in cfg.package_config_names:
            continue
        data = _safe_json_load(path)
        if data is not None:
            found.append(PackageConfig(path=path, data=data))
    return sorted(found, key=lambda item: len(item.path.parts))


def configs_for_path(path: Path, package_configs: list[PackageConfig]) -> list[PackageConfig]:
    stack: list[PackageConfig] = []
    for pc in package_configs:
        try:
            path.relative_to(pc.path.parent)
        except ValueError:
            continue
        stack.append(pc)
    return stack


def extract_name(text: str) -> str | None:
    m = EXTRACT_NAME_RE.search(text)
    return m.group(2).strip().upper() if m else None


def extract_group(text: str) -> str | None:
    m = EXTRACT_GROUP_RE.search(text)
    return m.group(2).strip().upper() if m else None


def infer_group(path: Path, weapon: str | None, text: str, cfg: ScanConfig) -> str | None:
    if weapon and weapon.upper() in cfg.weapon_group_overrides:
        return cfg.weapon_group_overrides[weapon.upper()]
    direct = extract_group(text)
    if direct:
        return direct
    joined = '/'.join(part.lower() for part in path.parts)
    for needle, group in cfg.group_hints_by_path.items():
        if needle.lower() in joined:
            return group
    if weapon:
        w = weapon.upper()
        if any(k in w for k in ('DAGGER', 'KNIFE', 'BAT', 'MACHETE', 'HATCHET', 'AXE', 'CROWBAR', 'HAMMER', 'WRENCH', 'KNUCKLE', 'NIGHTSTICK', 'POOLCUE', 'BOTTLE')):
            return 'GROUP_MELEE'
        if 'PISTOL' in w or 'GLOCK' in w or 'REVOLVER' in w:
            return 'GROUP_PISTOL'
        if 'SMG' in w or 'MICROSMG' in w:
            return 'GROUP_SMG'
        if 'SHOTGUN' in w or 'PUMPSHOTGUN' in w:
            return 'GROUP_SHOTGUN'
        if 'SNIPER' in w or 'MARKSMAN' in w:
            return 'GROUP_SNIPER'
        if 'MG' in w:
            return 'GROUP_MG'
        if any(k in w for k in ('RIFLE', 'CARBINE', 'AK', 'M4', 'AR15')):
            return 'GROUP_RIFLE'
    return None


def should_skip_path(path: Path, cfg: ScanConfig, skip_basenames: set[str]) -> bool:
    if any(part in cfg.skip_dir_names for part in path.parts):
        return True
    if path.name in skip_basenames:
        return True
    if path.suffix.lower() != '.meta':
        return True
    if not cfg.include_bak and path.name.lower().endswith(('.bak', '.meta.bak')):
        return True
    return False


def discover_meta_paths(root: Path, cfg: ScanConfig, skip_basenames: set[str]) -> list[Path]:
    iterator = root.rglob('*.meta') if cfg.recursive else root.glob('*.meta')
    paths = [p for p in iterator if p.is_file() and not should_skip_path(p, cfg, skip_basenames)]
    return sorted(paths)


def discover_fxmanifest_data_files(root: Path) -> dict[str, list[str]]:
    result: dict[str, list[str]] = {}
    for manifest in list(root.rglob('fxmanifest.lua')) + list(root.rglob('__resource.lua')):
        try:
            text = manifest.read_text(encoding='utf-8', errors='ignore')
        except Exception:
            continue
        hits = [f"{m.group('kind')} -> {m.group('path')}" for m in DATA_FILE_RE.finditer(text)]
        if hits:
            result[str(manifest)] = hits
    return result


def extract_weapon_blocks(path: Path, text: str, cfg: ScanConfig, package_configs: list[PackageConfig]) -> list[WeaponBlock]:
    config_stack = configs_for_path(path, package_configs)
    blocks: list[WeaponBlock] = []
    matches = list(WEAPON_ITEM_RE.finditer(text))

    if matches:
        for match in matches:
            block = match.group('block')
            weapon = extract_name(block)
            if not weapon:
                continue
            group = infer_group(path, weapon, block, cfg) or 'UNKNOWN'
            blocks.append(WeaponBlock(path, match.start('block'), match.end('block'), block, weapon, group, config_stack))
        return blocks

    # Fallback para metas raros que no envuelven con <Item type="CWeaponInfo"> pero sí traen Name/Group.
    weapon = extract_name(text)
    if weapon and (cfg.scan_all_meta or 'CWeaponInfo' in text):
        group = infer_group(path, weapon, text, cfg) or 'UNKNOWN'
        blocks.append(WeaponBlock(path, 0, len(text), text, weapon, group, config_stack, source='whole_file_fallback'))
    return blocks
