"""Lectura de packs de armas FiveM: weapons.meta, respaldos y componentes.

Usa el mismo escáner que el motor (`scanner.extract_weapon_blocks`) para que el
catálogo y el generador vean exactamente los mismos bloques CWeaponInfo.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ..engine.config import SKIP_BASENAMES
from ..meta.fields import FIELDS
from ..meta.meta_utils import _coerce_field_raw, _direct_child_spans, read_text, read_weapon_flags
from ..meta.pack_audit import find_unregistered_weapon_meta
from ..meta.scanner import ScanConfig, discover_meta_paths, extract_weapon_blocks, find_package_configs

_TAG_TO_KEY: dict[str, str] = {}
for _key, _field in FIELDS.items():
    for _tag in _field.all_tags:
        _TAG_TO_KEY[_tag.lower()] = _key

_COMPONENT_NAME_RE = re.compile(r'<Name>\s*(COMPONENT_[A-Za-z0-9_]+)\s*</Name>', re.IGNORECASE)
_COMPONENT_ITEM_RE = re.compile(r'<Item\s+type="CWeaponComponent[^"]*"\s*>(.*?)</Item>', re.IGNORECASE | re.DOTALL)
_DAMAGE_MOD_RE = re.compile(r'<(DamageModifier|DamageMultiplier)\s+value="([^"]+)"', re.IGNORECASE)
_CLIP_RE = re.compile(r'<ClipSize\s+value="([^"]+)"', re.IGNORECASE)


def read_all_fields(block_text: str) -> tuple[dict[str, Any], list[str]]:
    """Lee en una pasada todos los campos conocidos que son hijos directos del bloque.

    Devuelve (valores, campos_repetidos). Si un tag directo aparece dos veces se usa
    la primera aparición, igual que `read_field_value` del motor.
    """
    values: dict[str, Any] = {}
    repeated: list[str] = []
    for tag, start, end in _direct_child_spans(block_text):
        key = _TAG_TO_KEY.get(tag.lower())
        if key is None:
            continue
        meta_field = FIELDS[key]
        match = meta_field.pattern.search(block_text[start:end])
        if not match:
            continue
        if key in values:
            repeated.append(key)
            continue
        values[key] = _coerce_field_raw(meta_field, match.group(2))
    if 'weapon_flags' in values:
        values['weapon_flags'] = read_weapon_flags(block_text)
    return values, sorted(set(repeated))


@dataclass
class MetaDefinition:
    weapon: str
    group: str
    path: Path
    relative: str
    resource: str
    source: str
    values: dict[str, Any]
    original: dict[str, Any] | None
    has_backup: bool
    registered: bool
    repeated_fields: list[str] = field(default_factory=list)
    components: list[str] = field(default_factory=list)
    order: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            'weapon': self.weapon,
            'group': self.group,
            'path': str(self.path),
            'relative': self.relative,
            'resource': self.resource,
            'source': self.source,
            'has_backup': self.has_backup,
            'registered': self.registered,
            'repeated_fields': self.repeated_fields,
            'components': self.components,
            'order': self.order,
        }


@dataclass
class ComponentInfo:
    name: str
    path: str
    damage_modifiers: list[float] = field(default_factory=list)
    clip_size: int | None = None


@dataclass
class PackSnapshot:
    roots: list[Path]
    definitions: list[MetaDefinition] = field(default_factory=list)
    components: dict[str, ComponentInfo] = field(default_factory=dict)
    meta_files: int = 0
    signatures: dict[str, tuple[int, int]] = field(default_factory=dict)
    unregistered: list[str] = field(default_factory=list)
    unreadable: list[dict[str, str]] = field(default_factory=list)


def _resource_name(path: Path, root: Path) -> str:
    """Recurso FiveM más cercano (carpeta con fxmanifest.lua) dentro del pack."""
    current = path.parent
    while True:
        if (current / 'fxmanifest.lua').is_file() or (current / '__resource.lua').is_file():
            return current.name
        if current == root or current.parent == current:
            break
        current = current.parent
    try:
        return path.relative_to(root).parts[0]
    except (ValueError, IndexError):
        return root.name


def _backup_values(path: Path, scan: ScanConfig) -> dict[str, list[dict[str, Any]]]:
    backup = Path(str(path) + '.bak')
    if not backup.is_file():
        return {}
    result: dict[str, list[dict[str, Any]]] = {}
    for block in extract_weapon_blocks(backup, read_text(backup), scan, []):
        values, _ = read_all_fields(block.text)
        result.setdefault(block.weapon.upper(), []).append(values)
    return result


def file_signature(path: Path) -> tuple[int, int]:
    stat = path.stat()
    return stat.st_mtime_ns, stat.st_size


def collect_signatures(roots: list[Path]) -> dict[str, tuple[int, int]]:
    """Firma barata (mtime+tamaño) de todos los .meta y .bak para invalidar la caché."""
    signatures: dict[str, tuple[int, int]] = {}
    for root in roots:
        if not root.is_dir():
            continue
        for path in root.rglob('*'):
            name = path.name.lower()
            if name.endswith('.meta') or name.endswith('.meta.bak') or name in {'fxmanifest.lua', '__resource.lua'}:
                try:
                    signatures[str(path)] = file_signature(path)
                except OSError:
                    continue
    return signatures


def scan_components(root: Path) -> dict[str, ComponentInfo]:
    components: dict[str, ComponentInfo] = {}
    for path in sorted(root.rglob('weaponcomponents.meta')):
        if any(part in {'.git', 'stream'} for part in path.parts):
            continue
        text = read_text(path)
        for match in _COMPONENT_ITEM_RE.finditer(text):
            body = match.group(1)
            name_match = re.search(r'<Name>\s*([^<\s]+)\s*</Name>', body)
            if not name_match:
                continue
            info = ComponentInfo(name=name_match.group(1).upper(), path=str(path.relative_to(root)))
            for _tag, raw in _DAMAGE_MOD_RE.findall(body):
                try:
                    info.damage_modifiers.append(float(raw))
                except ValueError:
                    pass
            clip = _CLIP_RE.search(body)
            if clip:
                try:
                    info.clip_size = int(float(clip.group(1)))
                except ValueError:
                    pass
            components.setdefault(info.name, info)
    return components


def scan_pack(roots: list[Path], scan: ScanConfig | None = None) -> PackSnapshot:
    scan = scan or ScanConfig()
    snapshot = PackSnapshot(roots=list(roots))
    order = 0
    for root in roots:
        if not root.is_dir():
            continue
        package_configs = find_package_configs(root, scan)
        paths = discover_meta_paths(root, scan, set(SKIP_BASENAMES))
        snapshot.meta_files += len(paths)
        snapshot.unregistered.extend(str(root / rel) for rel in find_unregistered_weapon_meta(paths, root))
        unregistered_set = set(snapshot.unregistered)
        snapshot.components.update(scan_components(root))
        for path in paths:
            try:
                text = read_text(path)
            except OSError as exc:
                snapshot.unreadable.append({'path': str(path), 'error': str(exc)})
                continue
            blocks = extract_weapon_blocks(path, text, scan, package_configs)
            if not blocks:
                continue
            backups = _backup_values(path, scan)
            registered = str(path) not in unregistered_set
            for block in blocks:
                values, repeated = read_all_fields(block.text)
                original_list = backups.get(block.weapon.upper())
                original = original_list.pop(0) if original_list else None
                order += 1
                snapshot.definitions.append(MetaDefinition(
                    weapon=block.weapon.upper(),
                    group=block.group.upper(),
                    path=path,
                    relative=str(path.relative_to(root)),
                    resource=_resource_name(path, root),
                    source=block.source,
                    values=values,
                    original=original,
                    has_backup=Path(str(path) + '.bak').is_file(),
                    registered=registered,
                    repeated_fields=repeated,
                    components=sorted({m.upper() for m in _COMPONENT_NAME_RE.findall(block.text)}),
                    order=order,
                ))
    # Solo cuentan como “sin registrar” los archivos con bloques CWeaponInfo reales: los
    # archetypes/components/animations se registran con otros data_file.
    weapon_files = {str(d.path) for d in snapshot.definitions if d.source == 'CWeaponInfo'}
    snapshot.unregistered = [path for path in snapshot.unregistered if path in weapon_files]
    snapshot.signatures = collect_signatures(roots)
    return snapshot
