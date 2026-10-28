"""Paso de las armas a otro servidor (p. ej. de pruebas a principal) con registro.

``plan`` compara los archivos controlados de este servidor con los del destino y
lista lo que se copiaría. ``apply`` lo copia como una transacción reversible
(``wr.py rollback <id>``), igual que el generador:

- Antes de copiar, cada archivo del destino se respalda en ``data/backups/<id>/``.
- Si un archivo del destino cambió a mano desde su último sello, no se pisa sin
  ``force`` (así un arreglo hecho directo en principal no se pierde en silencio).
- Nunca se borran archivos del destino; los que solo existen allí se informan.
- ``skip`` deja fuera rutas concretas (p. ej. un ``fxmanifest.lua`` que se cambió a
  mano en principal y hay que conservar). Con ``skip`` solo se sellan los archivos
  copiados, así los saltados siguen apareciendo como cambio a mano.
- Al terminar se sella el destino y todo queda en ``data/logs/changes.jsonl``.
"""
from __future__ import annotations

import json
import shutil
import threading
import time
from pathlib import Path
from typing import Any

from ..core.errors import Conflict, ValidationFailed
from ..core.fsutil import atomic_write_bytes, sha256_file
from ..core.jsonlog import log
from ..core.paths import PathGuard, data_dir
from ..core.workspace import Workspace
from . import integrity
from .generator import CONFIRM_WORD

_LOCK = threading.Lock()


def target_guard(ws: Workspace, label: str) -> PathGuard:
    packs, qbx = integrity.tracked_roots(ws, label)
    roots = list(packs) + ([qbx.parent] if qbx is not None else [])
    return PathGuard(roots, f'packs de {label}')


def _skip_key(raw: str) -> str:
    """Ruta a comparar: relativa a la raíz del servidor, sin ``resources/`` (como la muestra la terminal)."""
    rel = str(raw).strip().replace('\\', '/').lstrip('./')
    return rel[len('resources/'):] if rel.startswith('resources/') else rel


def plan(ws: Workspace, label: str, skip: list[str] | None = None) -> dict[str, Any]:
    if label == integrity.LOCAL:
        raise ValidationFailed('Indica un servidor destino distinto de este.')
    integrity.server_root(ws, label)            # valida que exista
    source = integrity.scan(ws, integrity.LOCAL)
    target = integrity.scan(ws, label)
    wanted = {_skip_key(raw): str(raw) for raw in skip or [] if str(raw).strip()}
    changes, skipped = [], []
    for rel, info in sorted(source.items()):
        other = target.get(rel)
        status = 'nuevo' if other is None else 'cambia' if other['sha'] != info['sha'] else None
        if status is None:
            continue
        (skipped if _skip_key(rel) in wanted else changes).append({'path': rel, 'status': status})
    matched = {_skip_key(c['path']) for c in skipped}
    skip_unmatched = [raw for key, raw in wanted.items() if key not in matched]
    only_target = sorted(rel for rel in target if rel not in source)
    drift = integrity.check(ws, label, record=True)
    manual = {item['path'] for item in drift['modified'] + drift['added']} if drift['sealed'] else set()
    conflicts = [c['path'] for c in changes if c['path'] in manual]
    local_drift = integrity.check(ws, integrity.LOCAL, record=True)
    return {'target': label, 'target_root': str(integrity.server_root(ws, label)), 'changes': changes,
            'skipped': skipped, 'skip_unmatched': skip_unmatched,
            'only_target': only_target, 'target_sealed': drift['sealed'], 'conflicts': conflicts,
            'source_drift': local_drift['total'] if local_drift['sealed'] else None}


def apply(ws: Workspace, label: str, confirm: str, *, force: bool = False, reason: str = '',
          skip: list[str] | None = None) -> dict[str, Any]:
    if confirm != CONFIRM_WORD:
        raise ValidationFailed(f'Para pasar las armas escribe {CONFIRM_WORD} en la confirmación.')
    with _LOCK:
        current = plan(ws, label, skip)
        if current['skip_unmatched']:
            raise ValidationFailed(f'{len(current["skip_unmatched"])} ruta(s) de --skip no coinciden con ningún archivo '
                                   'que se fuera a copiar.', hint='Copia la ruta tal como sale en la vista previa.',
                                   details=current['skip_unmatched'][:20])
        if current['conflicts'] and not force:
            raise Conflict(f'{len(current["conflicts"])} archivo(s) de {label} se cambiaron a mano desde su último sello; '
                           'pasar los pisaría.', hint='Revísalos (wr.py integrity check --server '
                           f'{label}) y repite con --force si se pueden pisar.', details=current['conflicts'][:20])
        if not current['changes']:
            return {'applied': False, 'target': label, 'message': f'{label} ya coincide con este servidor.'}
        src_root = integrity.server_root(ws, integrity.LOCAL)
        dst_root = integrity.server_root(ws, label)
        guard = target_guard(ws, label)
        tx_id = time.strftime('%Y%m%d-%H%M%S') + f'_sync_{label}'
        tx_root = data_dir('backups') / tx_id
        files_dir = tx_root / 'files'
        files_dir.mkdir(parents=True, exist_ok=False)
        manifest: dict[str, Any] = {
            'id': tx_id, 'kind': 'sync', 'target': label, 'created_at': time.strftime('%Y-%m-%dT%H:%M:%S%z'),
            'profile': ws.active_profile, 'status': 'pending', 'reason': reason, 'forced': bool(force and current['conflicts']),
            'conflicts': current['conflicts'], 'skipped': [c['path'] for c in current['skipped']], 'files': [],
        }
        for index, change in enumerate(current['changes']):
            destination = guard.check(dst_root / change['path'])
            source_file = src_root / change['path']
            entry = {'path': str(destination), 'source': str(source_file), 'status': change['status'],
                     'backup': None, 'sha_before': None, 'sha_after': sha256_file(source_file)}
            if destination.is_file():
                entry['backup'] = f'{index:04d}_{destination.name}'
                entry['sha_before'] = sha256_file(destination)
                shutil.copy2(destination, files_dir / entry['backup'])
            manifest['files'].append(entry)
        (tx_root / 'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')
        written: list[dict[str, Any]] = []
        try:
            for entry in manifest['files']:
                atomic_write_bytes(Path(entry['path']), Path(entry['source']).read_bytes())
                written.append(entry)
                if sha256_file(Path(entry['path'])) != entry['sha_after']:
                    raise OSError(f'Verificación fallida tras copiar {entry["path"]}')
        except Exception as exc:  # noqa: BLE001
            for entry in written:
                if entry['backup']:
                    atomic_write_bytes(Path(entry['path']), (files_dir / entry['backup']).read_bytes())
                else:
                    Path(entry['path']).unlink(missing_ok=True)
            manifest['status'] = 'failed_rolled_back'
            manifest['error'] = str(exc)
            (tx_root / 'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')
            log('sync.apply_failed', level='error', stream='changes', tx=tx_id, target=label, error=str(exc))
            raise ValidationFailed(f'Error al copiar; se revirtieron los cambios: {exc}') from exc
        manifest['status'] = 'applied'
        (tx_root / 'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')
        log('sync.apply', stream='changes', tx=tx_id, target=label, profile=ws.active_profile, reason=reason,
            files=[c['path'] for c in current['changes']][:300], forced=manifest['forced'], skipped=manifest['skipped'])
        copied = [c['path'] for c in current['changes']] if manifest['skipped'] else None
        integrity.seal(ws, label, reason=f'paso a {label} ({tx_id})', source='sync', paths=copied)
        return {'applied': True, 'target': label, 'transaction': tx_id, 'files': len(manifest['files']),
                'skipped': len(manifest['skipped']), 'only_target': len(current['only_target']), 'backup_dir': str(tx_root)}
