"""Generador: aplica un plan revisado al servidor como una transacción reversible.

Flujo: plan (vista previa con hash) → apply(plan_hash, confirmación) → transacción.

Garantías:
- Solo se escriben archivos dentro de los packs configurados (y qbx_recoils si el
  perfil lo pide). Cualquier otra ruta se rechaza.
- El plan queda atado al contenido exacto de cada archivo: si algo cambió en disco
  después de la vista previa, no se aplica.
- Antes de escribir se copia cada archivo a ``data/backups/<transacción>/``. Se crea
  además el ``.bak`` hermano si no existía (lo usa `restore.from_backup`).
- Escritura atómica por archivo; si falla uno, se revierten los ya escritos.
- XML: si el archivo original era XML válido y el nuevo no, se aborta.
"""
from __future__ import annotations

import json
import shutil
import threading
import time
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ..adapters.qbx_recoils import render_qbx_recoils
from ..core.errors import Conflict, NotFound, ValidationFailed
from ..core.fsutil import atomic_write_bytes, decode_strict, read_json, sha256_bytes, sha256_file
from ..core.jsonlog import log
from ..core.paths import PathGuard, data_dir, is_within
from ..core.workspace import Workspace
from .preview import PreviewResult, canonical_hash, preview

CONFIRM_WORD = 'APLICAR'
_LOCK = threading.Lock()


@dataclass
class Plan:
    plan_hash: str
    profile_id: str | None
    created_at: float
    files: dict[str, bytes]                 # ruta -> contenido nuevo
    expected: dict[str, str]                # ruta -> sha actual esperado
    kinds: dict[str, str]                   # ruta -> meta | qbx_recoils
    preview: dict[str, Any]
    notes: list[str] = field(default_factory=list)


class PlanStore:
    def __init__(self, keep: int = 6) -> None:
        self._plans: dict[str, Plan] = {}
        self._keep = keep
        self._lock = threading.Lock()

    def put(self, plan: Plan) -> None:
        with self._lock:
            self._plans[plan.plan_hash] = plan
            for old in sorted(self._plans.values(), key=lambda p: p.created_at)[:-self._keep]:
                self._plans.pop(old.plan_hash, None)

    def get(self, plan_hash: str) -> Plan:
        with self._lock:
            plan = self._plans.get(plan_hash)
        if plan is None:
            raise NotFound('El plan ya no está disponible.', hint='Genera de nuevo la vista previa.')
        return plan


def _xml_ok(text: str) -> bool:
    try:
        ET.fromstring(text.lstrip('﻿'))
        return True
    except ET.ParseError:
        return False


def build_plan(engine_profile: dict[str, Any], resources: dict[str, Any] | None, ws: Workspace, catalog: Any,
               profile_id: str | None) -> Plan:
    result: PreviewResult = preview(engine_profile, ws, catalog, profile_id=profile_id)
    files: dict[str, bytes] = {}
    expected: dict[str, str] = {}
    kinds: dict[str, str] = {}
    notes: list[str] = []
    blocking: list[dict[str, Any]] = []
    for path, text in result.run.captured.items():
        key = str(path)
        raw = path.read_bytes()
        decoded, error = decode_strict(raw)
        if decoded is None:
            blocking.append({'path': key, 'message': f'No es UTF-8 válido ({error}); escribirlo perdería bytes.'})
            continue
        if _xml_ok(decoded) and not _xml_ok(text):
            blocking.append({'path': key, 'message': 'El resultado dejaría de ser XML válido.'})
            continue
        files[key] = text.encode('utf-8')
        expected[key] = sha256_bytes(raw)
        kinds[key] = 'meta'

    qbx_changes = ((resources or {}).get('qbx_recoils') or {}) if isinstance(resources, dict) else {}
    qbx_preview: list[str] = []
    if qbx_changes:
        qbx_path = ws.qbx_recoils_path
        if not qbx_path or not qbx_path.is_file():
            blocking.append({'path': 'qbx_recoils', 'message': 'El perfil configura qbx_recoils pero no se encontró su config.lua.'})
        else:
            from ..adapters.qbx_recoils import load_qbx_recoils
            loaded = load_qbx_recoils(qbx_path)
            effective: dict[str, float | None] = {}
            for weapon, value in qbx_changes.items():
                name = weapon.upper()
                current = loaded.value_for(name)
                if value is False and current is not None:      # false = desactivar la entrada
                    effective[name] = None
                elif isinstance(value, (int, float)) and not isinstance(value, bool) and current != float(value):
                    effective[name] = float(value)
            if effective:
                new_text, qbx_preview = render_qbx_recoils(qbx_path, effective)
                raw = qbx_path.read_bytes()
                if new_text.encode('utf-8') != raw:
                    files[str(qbx_path)] = new_text.encode('utf-8')
                    expected[str(qbx_path)] = sha256_bytes(raw)
                    kinds[str(qbx_path)] = 'qbx_recoils'
            notes.extend(qbx_preview)

    data = dict(result.data)
    data['blocking'] = blocking
    data['qbx_recoils'] = qbx_preview
    data['summary'] = {**data['summary'], 'files_to_write': len(files)}
    plan_hash = canonical_hash({'base': result.plan_hash, 'files': {k: sha256_bytes(v) for k, v in files.items()},
                                'expected': expected})
    data['plan_hash'] = plan_hash
    return Plan(plan_hash=plan_hash, profile_id=profile_id, created_at=time.time(), files=files,
                expected=expected, kinds=kinds, preview=data, notes=notes)


def file_diff(plan: Plan, path: str, context: int = 3) -> str:
    import difflib
    if path not in plan.files:
        raise NotFound('Ese archivo no forma parte del plan.')
    old = Path(path).read_text(encoding='utf-8', errors='replace').splitlines()
    new = plan.files[path].decode('utf-8').splitlines()
    return '\n'.join(difflib.unified_diff(old, new, fromfile='actual', tofile='propuesto', lineterm='', n=context))


def _write_guard(ws: Workspace) -> PathGuard:
    roots = list(ws.pack_paths)
    if ws.qbx_recoils_path:
        roots.append(ws.qbx_recoils_path.parent)
    return PathGuard(roots, 'packs y qbx_recoils')


def _tx_dir() -> Path:
    return data_dir('backups')


def apply_plan(plan: Plan, ws: Workspace, confirm: str) -> dict[str, Any]:
    if confirm != CONFIRM_WORD:
        raise ValidationFailed(f'Para aplicar escribe {CONFIRM_WORD} en la confirmación.')
    if plan.preview.get('blocking'):
        raise ValidationFailed('El plan tiene bloqueos; corrígelos antes de aplicar.', details=plan.preview['blocking'])
    if not plan.files:
        return {'applied': False, 'message': 'No hay cambios que aplicar: el servidor ya coincide con el perfil.'}
    guard = _write_guard(ws)
    with _LOCK:
        changed_since = []
        for path, sha in plan.expected.items():
            guard.check(Path(path))
            if not Path(path).is_file() or sha256_file(Path(path)) != sha:
                changed_since.append(path)
        if changed_since:
            raise Conflict('Algunos archivos cambiaron después de la vista previa. No se aplicó nada.',
                           hint='Vuelve a generar la vista previa.', details=changed_since[:20])

        tx_id = time.strftime('%Y%m%d-%H%M%S') + f'_{plan.profile_id or "borrador"}'
        tx_root = _tx_dir() / tx_id
        files_dir = tx_root / 'files'
        files_dir.mkdir(parents=True, exist_ok=False)
        manifest: dict[str, Any] = {
            'id': tx_id, 'created_at': time.strftime('%Y-%m-%dT%H:%M:%S%z'), 'profile': plan.profile_id,
            'plan_hash': plan.plan_hash, 'status': 'pending', 'files': [],
            'summary': plan.preview.get('summary'), 'notes': plan.notes,
        }
        for index, (path, content) in enumerate(sorted(plan.files.items())):
            source = Path(path)
            backup_name = f'{index:04d}_{source.name}'
            shutil.copy2(source, files_dir / backup_name)
            sibling = Path(path + '.bak')
            bak_created = False
            if plan.kinds[path] == 'meta' and not sibling.exists():
                shutil.copy2(source, sibling)
                bak_created = True
            manifest['files'].append({
                'path': path, 'kind': plan.kinds[path], 'backup': backup_name,
                'sha_before': plan.expected[path], 'sha_after': sha256_bytes(content), 'bak_created': bak_created,
            })
        (tx_root / 'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')

        written: list[dict[str, Any]] = []
        try:
            for entry in manifest['files']:
                atomic_write_bytes(Path(entry['path']), plan.files[entry['path']])
                written.append(entry)
                if sha256_file(Path(entry['path'])) != entry['sha_after']:
                    raise OSError(f'Verificación fallida tras escribir {entry["path"]}')
        except Exception as exc:  # noqa: BLE001
            for entry in written:
                atomic_write_bytes(Path(entry['path']), (files_dir / entry['backup']).read_bytes())
            manifest['status'] = 'failed_rolled_back'
            manifest['error'] = str(exc)
            (tx_root / 'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')
            log('generator.apply_failed', level='error', tx=tx_id, error=str(exc))
            raise ValidationFailed(f'Error al escribir; se revirtieron los cambios: {exc}') from exc

        manifest['status'] = 'applied'
        (tx_root / 'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')
        weapons_changed = {name: sorted(entry.get('changes', {}).keys())
                           for name, entry in plan.preview.get('weapons', {}).items() if entry.get('changes')}
        log('generator.apply', stream='changes', tx=tx_id, profile=plan.profile_id, files=len(manifest['files']),
            weapons=weapons_changed, qbx=plan.notes)
        return {'applied': True, 'transaction': tx_id, 'files': len(manifest['files']),
                'weapons': len(weapons_changed), 'backup_dir': str(tx_root)}


def list_transactions() -> list[dict[str, Any]]:
    result = []
    for manifest_path in sorted(_tx_dir().glob('*/manifest.json'), reverse=True):
        data = read_json(manifest_path, default={}) or {}
        result.append({
            'id': data.get('id', manifest_path.parent.name), 'created_at': data.get('created_at'),
            'profile': data.get('profile'), 'status': data.get('status'), 'files': len(data.get('files', [])),
            'summary': data.get('summary'), 'rolled_back_at': data.get('rolled_back_at'), 'kind': data.get('kind', 'apply'),
        })
    return result


def rollback(tx_id: str, ws: Workspace, confirm: str) -> dict[str, Any]:
    if confirm != CONFIRM_WORD:
        raise ValidationFailed(f'Para revertir escribe {CONFIRM_WORD} en la confirmación.')
    if '/' in tx_id or '\\' in tx_id or tx_id.startswith('.'):
        raise ValidationFailed('Transacción inválida.')
    tx_root = _tx_dir() / tx_id
    manifest_path = tx_root / 'manifest.json'
    manifest = read_json(manifest_path, default=None)
    if not isinstance(manifest, dict):
        raise NotFound('No existe esa transacción.')
    if manifest.get('status') != 'applied':
        raise Conflict(f'La transacción está en estado “{manifest.get("status")}”: no se puede revertir.')
    guard = _write_guard(ws)
    with _LOCK:
        modified_after = []
        for entry in manifest['files']:
            path = Path(entry['path'])
            guard.check(path)
            if not path.is_file() or sha256_file(path) != entry['sha_after']:
                modified_after.append(entry['path'])
        if modified_after:
            raise Conflict('Estos archivos cambiaron después de aplicar; revertir pisaría esos cambios.',
                           hint='Revisa los archivos o aplica un perfil nuevo en lugar de revertir.',
                           details=modified_after[:20])
        for entry in manifest['files']:
            atomic_write_bytes(Path(entry['path']), (tx_root / 'files' / entry['backup']).read_bytes())
            sibling = Path(entry['path'] + '.bak')
            if entry.get('bak_created') and sibling.is_file() and sha256_file(sibling) == entry['sha_before']:
                sibling.unlink()
        manifest['status'] = 'rolled_back'
        manifest['rolled_back_at'] = time.strftime('%Y-%m-%dT%H:%M:%S%z')
        manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')
        log('generator.rollback', stream='changes', tx=tx_id, files=len(manifest['files']))
        return {'rolled_back': True, 'transaction': tx_id, 'files': len(manifest['files'])}


def guard_status(destination: Path) -> str:
    if not destination.exists():
        return 'new'
    manifest = destination / 'fxmanifest.lua'
    if manifest.is_file() and 'weapon_rebalancer' in manifest.read_text(encoding='utf-8', errors='ignore'):
        return 'generated'
    return 'foreign'


def generate_guard(destination: Path, expected: dict[str, float], ws: Workspace, confirm: str) -> dict[str, Any]:
    """Genera os_weapon_damage_guard. Solo dentro de resources/ y sin pisar carpetas ajenas."""
    from ..runtime.guard import generate_damage_guard

    if confirm != CONFIRM_WORD:
        raise ValidationFailed(f'Para generar el guard escribe {CONFIRM_WORD} en la confirmación.')
    if not is_within(destination, ws.resources_path):
        raise ValidationFailed('El destino del guard debe estar dentro de resources/.')
    status = guard_status(destination)
    if status == 'foreign':
        raise Conflict('La carpeta destino existe y no la generó weapon_rebalancer: no se reemplaza.')
    backup = None
    if status == 'generated':
        backup = _tx_dir() / f'{time.strftime("%Y%m%d-%H%M%S")}_guard'
        shutil.copytree(destination, backup)
    generate_damage_guard(destination, expected, force=status == 'generated')
    log('generator.guard', stream='changes', destination=str(destination), weapons=len(expected), backup=str(backup) if backup else None)
    return {'destination': str(destination), 'weapons': len(expected), 'replaced': status == 'generated',
            'backup': str(backup) if backup else None}
