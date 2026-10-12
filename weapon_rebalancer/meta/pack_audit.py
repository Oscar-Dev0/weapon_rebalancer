from __future__ import annotations

import fnmatch
from collections import defaultdict
from pathlib import Path
from typing import Any

from .meta_utils import read_text
from .scanner import DATA_FILE_RE, PackageConfig, ScanConfig, extract_weapon_blocks


def build_weapon_occurrences(
    paths: list[Path],
    scan: ScanConfig,
    package_configs: list[PackageConfig],
    root: Path,
) -> dict[str, list[str]]:
    occurrences: defaultdict[str, list[str]] = defaultdict(list)
    for path in paths:
        try:
            text = read_text(path)
        except Exception:
            continue
        for block in extract_weapon_blocks(path, text, scan, package_configs):
            try:
                source = str(path.relative_to(root))
            except ValueError:
                source = str(path)
            occurrences[block.weapon.upper()].append(source)
    result: dict[str, list[str]] = {}
    for weapon, sources in sorted(occurrences.items()):
        if len(sources) <= 1:
            continue
        counts: defaultdict[str, int] = defaultdict(int)
        labelled: list[str] = []
        for source in sources:
            counts[source] += 1
            suffix = f'#definition-{counts[source]}' if counts[source] > 1 else ''
            labelled.append(f'{source}{suffix}')
        result[weapon] = labelled
    return result


def _find_manifests(root: Path) -> list[Path]:
    manifests = list(root.rglob('fxmanifest.lua')) + list(root.rglob('__resource.lua'))
    # El usuario puede apuntar directamente a una subcarpeta data dentro de un recurso.
    current = root
    for _ in range(4):
        for name in ('fxmanifest.lua', '__resource.lua'):
            candidate = current / name
            if candidate.is_file():
                manifests.append(candidate)
        if current.parent == current:
            break
        current = current.parent
    return sorted(set(manifests))


def _manifest_entries(manifest: Path) -> list[tuple[str, str]]:
    try:
        text = manifest.read_text(encoding='utf-8', errors='ignore')
    except Exception:
        return []
    return [(m.group('kind').upper(), m.group('path').replace('\\', '/')) for m in DATA_FILE_RE.finditer(text)]


def _entry_matches(relative: str, declared: str) -> bool:
    relative = relative.replace('\\', '/')
    declared = declared.lstrip('./').replace('\\', '/')
    if fnmatch.fnmatch(relative.lower(), declared.lower()):
        return True
    if '/' not in declared and Path(relative).name.lower() == declared.lower():
        return True
    return False


def find_unregistered_weapon_meta(paths: list[Path], root: Path) -> list[str]:
    manifests = _find_manifests(root)
    manifest_data: dict[Path, list[tuple[str, str]]] = {m: _manifest_entries(m) for m in manifests}
    unregistered: list[str] = []

    for path in paths:
        candidates: list[Path] = []
        for manifest in manifests:
            try:
                path.relative_to(manifest.parent)
            except ValueError:
                continue
            candidates.append(manifest)
        candidates.sort(key=lambda p: len(p.parent.parts), reverse=True)

        registered = False
        for manifest in candidates:
            relative = path.relative_to(manifest.parent).as_posix()
            for kind, declared in manifest_data.get(manifest, []):
                if 'WEAPONINFO' not in kind:
                    continue
                if _entry_matches(relative, declared):
                    registered = True
                    break
            if registered:
                break

        if not registered:
            try:
                unregistered.append(str(path.relative_to(root)))
            except ValueError:
                unregistered.append(str(path))

    return sorted(unregistered)


def build_pack_audit(
    paths: list[Path],
    scan: ScanConfig,
    package_configs: list[PackageConfig],
    root: Path,
) -> dict[str, Any]:
    return {
        'duplicate_weapons': build_weapon_occurrences(paths, scan, package_configs, root),
        'unregistered_meta_files': find_unregistered_weapon_meta(paths, root),
    }
