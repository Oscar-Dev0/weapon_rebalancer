"""Vista previa: ejecuta el motor real en memoria y explica el resultado por arma."""
from __future__ import annotations

import difflib
import hashlib
import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ..adapters.fivem_pack import read_all_fields
from ..engine.config import Settings
from ..core.errors import ValidationFailed
from ..core.fsutil import sha256_bytes
from ..core.workspace import Workspace
from ..meta.meta_utils import read_text
from ..engine.profile_loader import ProfileError, apply_external_profile
from ..profile_store.schema import MODULE_PRESET_KEYS, effective_modules, iter_authored_fields, module_for_field
from ..engine.rebalance import RebalanceEngine
from ..engine.report import RebalanceReport
from ..meta.scanner import ScanConfig, extract_weapon_blocks
from .catalog import effective_rpm

_TOL = 1e-6


def build_settings(engine_profile: dict[str, Any], root: Path, ws: Workspace) -> Settings:
    """Mismo camino que `run_rebalance.py --profile`: config.py + perfil + ruta."""
    settings = Settings.from_config()
    try:
        apply_external_profile(settings, engine_profile)
    except ProfileError as exc:
        raise ValidationFailed(f'El motor rechazó el perfil: {exc}', hint='Corrige el campo indicado y vuelve a validar.') from exc
    settings.root = root
    settings.dry_run = True
    settings.write_json_report = False
    if ws.reference_roots and not settings.baseline_repair.get('reference_roots'):
        settings.baseline_repair['reference_roots'] = list(ws.reference_roots)
    return settings


@dataclass
class EngineRun:
    reports: list[RebalanceReport]
    captured: dict[Path, str]
    originals: dict[Path, str]
    duration_ms: int


def run_engine(engine_profile: dict[str, Any], ws: Workspace, overlay: dict[Path, str] | None = None) -> EngineRun:
    started = time.perf_counter()
    reports: list[RebalanceReport] = []
    captured: dict[Path, str] = {}
    for root in ws.pack_paths:
        if not root.is_dir():
            continue
        settings = build_settings(engine_profile, root, ws)
        engine = RebalanceEngine(settings, capture=captured, overlay=overlay)
        reports.append(engine.run())
    originals = {path: (overlay[path] if overlay and path in overlay else read_text(path)) for path in captured}
    return EngineRun(reports, captured, originals, int((time.perf_counter() - started) * 1000))


def _values_by_weapon(path: Path, text: str) -> dict[str, list[dict[str, Any]]]:
    result: dict[str, list[dict[str, Any]]] = {}
    for block in extract_weapon_blocks(path, text, ScanConfig(), []):
        values, _ = read_all_fields(block.text)
        result.setdefault(block.weapon.upper(), []).append(values)
    return result


def _same(a: Any, b: Any) -> bool:
    if isinstance(a, (int, float)) and isinstance(b, (int, float)) and not isinstance(a, bool) and not isinstance(b, bool):
        return abs(float(a) - float(b)) <= _TOL * max(1.0, abs(float(a)))
    return a == b


def canonical_hash(data: Any) -> str:
    return hashlib.sha256(json.dumps(data, sort_keys=True, ensure_ascii=False, default=str).encode('utf-8')).hexdigest()


@dataclass
class PreviewResult:
    data: dict[str, Any]
    run: EngineRun
    plan_hash: str
    file_hashes: dict[str, tuple[str, str]] = field(default_factory=dict)  # path -> (sha actual, sha nuevo)


def preview(engine_profile: dict[str, Any], ws: Workspace, catalog: Any, *, check_idempotency: bool = True,
            profile_id: str | None = None) -> PreviewResult:
    run = run_engine(engine_profile, ws)

    # Valores propuestos por arma (todas sus definiciones en archivos cambiados).
    proposed_by_weapon: dict[str, list[dict[str, Any]]] = {}
    for path, text in run.captured.items():
        for weapon, values in _values_by_weapon(path, text).items():
            proposed_by_weapon.setdefault(weapon, []).extend(values)

    weapons: dict[str, dict[str, Any]] = {}
    totals = {'files_scanned': 0, 'weapon_blocks': 0, 'weapons_changed': 0, 'weapons_skipped': 0,
              'onetap_total': 0, 'onetap_passed': 0, 'onetap_failed': 0}
    engine_warnings: list[str] = []
    for report in run.reports:
        totals['files_scanned'] += report.files_scanned
        totals['weapon_blocks'] += report.weapon_blocks_found
        totals['onetap_total'] += report.onetap_audit_total
        totals['onetap_passed'] += report.onetap_audit_passed
        totals['onetap_failed'] += report.onetap_audit_failed
        engine_warnings.extend(report.warnings)
        for change in report.changes:
            entry = weapons.setdefault(change.weapon, {
                'weapon': change.weapon, 'group': change.group, 'processed': False, 'skipped_reason': None,
                'changed_fields': [], 'missing_fields': [], 'clamped': {}, 'onetap': None, 'definitions': 0,
            })
            entry['definitions'] += 1
            if change.skipped:
                entry['skipped_reason'] = entry['skipped_reason'] or change.reason
                continue
            entry['processed'] = True
            entry['changed_fields'] = sorted(set(entry['changed_fields']) | set(change.changed_fields))
            entry['missing_fields'] = sorted(set(entry['missing_fields']) | set(change.missing_fields))
            entry['clamped'].update({k: list(v) for k, v in change.clamped_fields.items()})
            if change.onetap_expected:
                entry['onetap'] = {'ready': change.onetap_ready, 'issues': change.onetap_issues,
                                   'metrics': change.onetap_metrics}

    for name, entry in weapons.items():
        current_defs = catalog.definitions.get(name, [])
        current = current_defs[-1].values if current_defs else {}
        proposed_list = proposed_by_weapon.get(name)
        proposed = proposed_list[-1] if proposed_list else current
        diff: dict[str, dict[str, Any]] = {}
        for key in sorted(set(current) | set(proposed)):
            if not _same(current.get(key), proposed.get(key)):
                diff[key] = {'current': current.get(key), 'proposed': proposed.get(key)}
        entry['changes'] = diff
        entry['proposed'] = {k: proposed.get(k) for k in proposed if k != 'weapon_flags'}
        entry['proposed_flags'] = proposed.get('weapon_flags')
        entry['rpm_proposed'] = effective_rpm(proposed)
        if diff:
            totals['weapons_changed'] += 1
        if not entry['processed']:
            totals['weapons_skipped'] += 1

    issues = effect_issues(engine_profile, weapons, catalog)
    idempotency: dict[str, Any] = {'checked': check_idempotency, 'idempotent': True, 'drift': []}
    if check_idempotency and run.captured:
        second = run_engine(engine_profile, ws, overlay=dict(run.captured))
        drift = []
        for path, text in second.captured.items():
            if text != run.captured.get(path):
                before = _values_by_weapon(path, run.captured[path])
                after = _values_by_weapon(path, text)
                for weapon, values_list in after.items():
                    for index, values in enumerate(values_list):
                        prior = before.get(weapon, [{}])[min(index, len(before.get(weapon, [{}])) - 1)]
                        keys = [k for k in values if not _same(values.get(k), prior.get(k))]
                        if keys:
                            drift.append({'weapon': weapon, 'fields': keys})
        idempotency = {'checked': True, 'idempotent': not drift, 'drift': drift[:50]}
        if drift:
            issues.append({
                'code': 'not_idempotent', 'severity': 'warning',
                'message': f'Aplicar el perfil dos veces da otro resultado en {len(drift)} arma(s): los multiplicadores se acumulan.',
                'fix': 'Activa restore.from_backup (Restaurar desde .bak) o define el valor base en el perfil para esas armas.',
                'weapons': sorted({d['weapon'] for d in drift})[:30],
            })

    file_hashes: dict[str, tuple[str, str]] = {}
    files = []
    for path, new_text in sorted(run.captured.items(), key=lambda item: str(item[0])):
        old_text = run.originals[path]
        raw = path.read_bytes()
        file_hashes[str(path)] = (sha256_bytes(raw), sha256_bytes(new_text.encode('utf-8')))
        added = removed = 0
        for line in difflib.unified_diff(old_text.splitlines(), new_text.splitlines(), lineterm='', n=0):
            if line.startswith('+') and not line.startswith('+++'):
                added += 1
            elif line.startswith('-') and not line.startswith('---'):
                removed += 1
        weapons_in_file = sorted(_values_by_weapon(path, new_text))
        files.append({'path': str(path), 'added': added, 'removed': removed, 'weapons': weapons_in_file})

    plan_hash = canonical_hash({'profile': engine_profile, 'files': file_hashes,
                                'roots': [str(p) for p in ws.pack_paths]})
    data = {
        'profile_id': profile_id,
        'generated_at': time.strftime('%Y-%m-%dT%H:%M:%S%z'),
        'duration_ms': run.duration_ms,
        'summary': {**totals, 'files_changed': len(run.captured)},
        'weapons': weapons,
        'files': files,
        'engine_warnings': engine_warnings,
        'issues': issues,
        'idempotency': idempotency,
        'plan_hash': plan_hash,
    }
    return PreviewResult(data=data, run=run, plan_hash=plan_hash, file_hashes=file_hashes)


def effect_issues(engine_profile: dict[str, Any], weapons: dict[str, dict[str, Any]], catalog: Any) -> list[dict[str, Any]]:
    """Compara lo declarado con lo que el motor produjo: detecta cambios sin efecto real."""
    issues: list[dict[str, Any]] = []
    modules = effective_modules(engine_profile)
    known_groups = {d.group for defs in catalog.definitions.values() for d in defs}
    ignored = {str(w).upper() for w in engine_profile.get('ignore_weapons') or []}
    harmless = {str(w).upper() for w in engine_profile.get('harmless_weapons') or []}

    for scope, name, key, value in iter_authored_fields(engine_profile):
        blocked = [m for m in module_for_field(key) if modules.get(m) == 'original']
        if blocked:
            issues.append({
                'code': 'module_original', 'severity': 'warning', 'path': f'{scope}:{name}.{key}',
                'message': f'{key} está configurado en {scope} {name}, pero el módulo “{", ".join(blocked)}” está en original: el motor lo descarta.',
                'fix': f'Cambia modules.{blocked[0]} a “configured” o elimina el valor.',
            })
            continue
        for module, keys in MODULE_PRESET_KEYS.items():
            mode = modules.get(module)
            if key in keys and mode not in (None, 'original', 'configured'):
                issues.append({
                    'code': 'module_preset_overrides', 'severity': 'warning', 'path': f'{scope}:{name}.{key}',
                    'message': f'El preset modules.{module}="{mode}" sobrescribe {key} después de tu valor.',
                    'fix': f'Usa modules.{module}="configured" para que mande el valor del perfil.',
                    'scope': f'{scope} {name}',
                })
        if scope == 'group' and name not in known_groups:
            issues.append({'code': 'unknown_group', 'severity': 'warning', 'path': f'group:{name}',
                           'message': f'Ningún arma del pack usa {name}.', 'fix': 'Revisa el nombre del grupo.'})
        if scope != 'weapon' or not isinstance(value, (int, float)) or isinstance(value, bool):
            continue
        if name not in catalog.definitions:
            issues.append({'code': 'unknown_weapon', 'severity': 'warning', 'path': f'weapon:{name}',
                           'message': f'{name} no tiene weapons.meta en los packs configurados: su configuración no hace nada.',
                           'fix': 'Revisa el nombre o agrega el pack donde está el arma.'})
            continue
        entry = weapons.get(name)
        if entry is None:
            continue
        if not entry['processed']:
            reason = entry.get('skipped_reason') or 'omitida'
            if name in ignored:
                reason = 'está en ignore_weapons'
            issues.append({'code': 'weapon_skipped', 'severity': 'warning', 'path': f'weapon:{name}',
                           'message': f'{name} tiene valores configurados pero el motor la omitió ({reason}).',
                           'fix': 'Quítala de las armas ignoradas o revisa los filtros.'})
            continue
        if name in harmless and key == 'damage':
            continue
        result = (entry.get('proposed') or {}).get(key)
        if result is None or _same(result, float(value)):
            continue
        clamp = entry['clamped'].get(key)
        if clamp:
            issues.append({'code': 'clamped', 'severity': 'warning', 'path': f'weapon:{name}.{key}',
                           'message': f'{name}.{key}={value} está fuera de los límites del motor y queda en {clamp[1]}.',
                           'fix': 'Usa un valor dentro del rango admitido (ver tabla de parámetros).'})
        else:
            reason = _override_reason(engine_profile, name, key)
            issues.append({'code': 'value_overridden', 'severity': 'info', 'path': f'weapon:{name}.{key}',
                           'message': f'{name}.{key}: declaraste {value} y el resultado es {result} ({reason}).',
                           'fix': 'Es correcto si esa regla es intencional; si no, ajusta o quita la regla indicada.'})
    return _dedupe(issues)


def _dedupe(issues: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Un aviso por mensaje; los repetidos acumulan sus ámbitos."""
    merged: dict[tuple[str, str], dict[str, Any]] = {}
    for item in issues:
        key = (item['code'], item['message'])
        if key not in merged:
            merged[key] = {**item, 'scopes': [item['scope']] if item.get('scope') else []}
            continue
        if item.get('scope') and item['scope'] not in merged[key]['scopes']:
            merged[key]['scopes'].append(item['scope'])
    result = []
    for item in merged.values():
        scopes = item.pop('scopes')
        item.pop('scope', None)
        if len(scopes) > 1:
            item['message'] += f' (en {len(scopes)} ámbitos: {", ".join(scopes[:6])}{"…" if len(scopes) > 6 else ""})'
        result.append(item)
    return result


_HEADSHOT_KEYS = {'headshot_player', 'network_headshot', 'headshot_ai', 'min_headshot_player', 'max_headshot_player',
                  'min_headshot_ai', 'max_headshot_ai', 'weapon_range', 'falloff_min', 'falloff_max', 'falloff_modifier',
                  'lightly_armoured', 'penetration', 'network_player_damage_modifier'}


def _override_reason(engine_profile: dict[str, Any], weapon: str, key: str, is_custom: bool | None = None) -> str:
    """Explica qué regla del perfil cambia un valor declarado por arma."""
    multipliers = (engine_profile.get('weapon_field_multipliers') or {}).get(weapon) or {}
    if key in multipliers:
        return f'multiplicador exacto ×{multipliers[key]:g} en weapon_field_multipliers'
    classifier = engine_profile.get('fire_rate_classifier') or {}
    recoil_profiles = classifier.get('onetap_single_shot_recoil_profiles') or {}
    if classifier.get('onetap_single_shot_recoil_enabled') and any(key in v for v in recoil_profiles.values() if isinstance(v, dict)):
        return 'perfil de recoil one-tap tiro a tiro del clasificador de cadencia'
    if key == 'damage' and (engine_profile.get('fire_rate_damage_rules') or classifier.get('non_normal_damage_caps')):
        return 'regla de daño por cadencia'
    harmless = {str(w).upper() for w in engine_profile.get('harmless_weapons') or []}
    if weapon in harmless:
        return 'arma inofensiva: daño y multiplicadores a 0'
    for rule in engine_profile.get('family_rules') or []:
        contains = rule.get('contains') or []
        contains = [contains] if isinstance(contains, str) else contains
        if any(str(c).upper() in weapon for c in contains) and (key in (rule.get('fields') or {}) or key in (rule.get('field_multipliers') or {})):
            return f'regla de familia “{rule.get("name", "?")}”'
    if key in _HEADSHOT_KEYS and str((engine_profile.get('modules') or {}).get('headshot', 'onetap')) != 'original':
        return 'política de cabeza / one-tap'
    from ..engine.baseline import DAMAGE_REPAIR_FIELDS

    classification = engine_profile.get('weapon_classification') or {}
    custom = classification.get('custom') or {}
    if is_custom is not False and classification.get('custom_when_not_official') and key in (custom.get('field_multipliers') or {}):
        return 'normalización de armas personalizadas a la referencia de su categoría'
    repair = engine_profile.get('baseline_repair') or {}
    if repair.get('enabled') and key in DAMAGE_REPAIR_FIELDS:
        if weapon in (repair.get('official_values') or {}):
            return 'tabla de referencia vanilla del perfil'
        if not (engine_profile.get('restore') or {}).get('from_backup'):
            return 'reparación base (valor en 0 o ausente)'
    if (engine_profile.get('restore') or {}).get('from_backup'):
        return 'restaurado desde el .bak'
    modules = engine_profile.get('modules') or {}
    for module, keys in MODULE_PRESET_KEYS.items():
        if key in keys and modules.get(module) not in (None, 'original', 'configured'):
            return f'preset modules.{module}={modules[module]}'
    if key == 'damage' and modules.get('damage') in {'low', 'high', 'lethal', 'none', 'head_only'}:
        return f'preset modules.damage={modules["damage"]}'
    return 'regla interna del motor (config.py)'
