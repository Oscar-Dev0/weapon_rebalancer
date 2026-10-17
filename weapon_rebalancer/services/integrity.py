"""Sello de integridad: detecta cambios en las armas hechos fuera de weapon_rebalancer.

Después de cada aplicación, reversión o paso a otro servidor se guarda el SHA-256 de
cada archivo controlado (los ``.meta`` y ``fxmanifest.lua`` de los packs, y el
``config.lua`` de qbx_recoils). ``check`` compara el disco con ese sello: lo que
cambió sin pasar por la herramienta aparece como cambio manual y queda en el
registro (``data/logs/changes.jsonl``), con fecha de modificación del archivo.

Hay un sello por servidor: ``local`` (el servidor donde corre la herramienta) y uno
por cada destino de ``sync_targets`` (p. ej. ``principal``). Las rutas del sello son
relativas a la raíz de cada servidor para poder comparar entre ellos.
"""
from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Any

from ..core.errors import NotFound, ValidationFailed
from ..core.fsutil import atomic_write_json, read_json, sha256_bytes, sha256_file
from ..core.jsonlog import log
from ..core.paths import data_dir, is_within
from ..core.workspace import Workspace

LOCAL = 'local'
TRACKED_SUFFIXES = ('.meta',)
TRACKED_NAMES = ('fxmanifest.lua',)


def server_root(ws: Workspace, label: str = LOCAL) -> Path:
    if label == LOCAL:
        return ws.server_path
    target = ws.sync_targets.get(label)
    if not target:
        raise NotFound(f'No hay un servidor destino llamado “{label}”.',
                       hint='Configúralo con: wr.py settings set sync_targets.principal=/fivem/principal')
    root = Path(target)
    if not (root / 'resources').is_dir():
        raise ValidationFailed(f'El destino “{label}” no tiene carpeta resources/: {root}')
    return root


def tracked_roots(ws: Workspace, label: str = LOCAL) -> tuple[list[Path], Path | None]:
    """Packs y qbx_recoils de un servidor (los del destino salen de las mismas rutas relativas)."""
    root = server_root(ws, label)
    packs: list[Path] = []
    for pack in ws.pack_paths:
        rel = pack.relative_to(ws.server_path) if is_within(pack, ws.server_path) else None
        if rel is not None:
            packs.append(root / rel)
    qbx = None
    if ws.qbx_recoils_path and is_within(ws.qbx_recoils_path, ws.server_path):
        qbx = root / ws.qbx_recoils_path.relative_to(ws.server_path)
    return packs, qbx


def _is_tracked(name: str) -> bool:
    return name.endswith(TRACKED_SUFFIXES) or name in TRACKED_NAMES


def scan(ws: Workspace, label: str = LOCAL) -> dict[str, dict[str, Any]]:
    """{ruta relativa al servidor: {sha, size, mtime}} de todos los archivos controlados."""
    root = server_root(ws, label)
    packs, qbx = tracked_roots(ws, label)
    files: list[Path] = []
    for pack in packs:
        if not pack.is_dir():
            continue
        for directory, _dirs, names in os.walk(pack):
            files.extend(Path(directory) / name for name in names if _is_tracked(name))
    if qbx is not None and qbx.is_file():
        files.append(qbx)
    result: dict[str, dict[str, Any]] = {}
    for path in files:
        try:
            stat = path.stat()
            result[str(path.relative_to(root))] = {'sha': sha256_file(path), 'size': stat.st_size, 'mtime': stat.st_mtime}
        except OSError:
            continue
    return result


def _seal_file(label: str) -> Path:
    return data_dir('integrity') / f'{label}.json'


def load_seal(label: str = LOCAL) -> dict[str, Any] | None:
    data = read_json(_seal_file(label), default=None)
    return data if isinstance(data, dict) and isinstance(data.get('files'), dict) else None


def _iso(ts: float) -> str:
    return time.strftime('%Y-%m-%dT%H:%M:%S%z', time.localtime(ts))


def seal(ws: Workspace, label: str = LOCAL, *, reason: str, source: str = 'manual',
         paths: list[str] | None = None) -> dict[str, Any]:
    """Guarda el estado actual como bueno.

    Con ``paths`` (rutas absolutas o relativas) solo se actualizan esos archivos y el
    resto del sello se conserva, para que un cambio manual en otro archivo siga
    apareciendo. Sin ``paths`` (o si aún no hay sello) se sella todo.
    """
    if not str(reason or '').strip():
        raise ValidationFailed('Indica el motivo del sello: queda en el registro.')
    root = server_root(ws, label)
    current = scan(ws, label)
    previous = load_seal(label)
    if paths is not None and previous is not None:
        files = dict(previous['files'])
        for raw in paths:
            path = Path(raw)
            rel = str(path.relative_to(root)) if path.is_absolute() and is_within(path, root) else str(raw)
            if rel in current:
                files[rel] = current[rel]
            else:
                files.pop(rel, None)
        scope = 'parcial'
    else:
        files = current
        scope = 'completo'
    data = {'label': label, 'server_root': str(root), 'sealed_at': time.strftime('%Y-%m-%dT%H:%M:%S%z'),
            'reason': reason, 'source': source, 'scope': scope, 'files': files,
            'history': ((previous or {}).get('history') or [])[-49:] + [
                {'at': time.strftime('%Y-%m-%dT%H:%M:%S%z'), 'reason': reason, 'source': source, 'scope': scope,
                 'files': len(paths) if paths is not None and previous is not None else len(files)}],
            'last_drift': None}
    atomic_write_json(_seal_file(label), data)
    log('integrity.seal', stream='changes', server=label, reason=reason, source=source, scope=scope,
        files=data['history'][-1]['files'])
    return {'label': label, 'sealed_at': data['sealed_at'], 'scope': scope, 'files': len(files)}


def check(ws: Workspace, label: str = LOCAL, *, record: bool = True) -> dict[str, Any]:
    """Compara el disco con el sello. ``record`` deja en el registro los cambios manuales nuevos."""
    sealed = load_seal(label)
    if sealed is None:
        return {'label': label, 'sealed': False, 'sealed_at': None, 'modified': [], 'added': [], 'removed': [],
                'total': 0, 'clean': False}
    current = scan(ws, label)
    old = sealed['files']
    modified = [{'path': rel, 'modified_at': _iso(info['mtime'])}
                for rel, info in sorted(current.items()) if rel in old and old[rel]['sha'] != info['sha']]
    added = [{'path': rel, 'modified_at': _iso(info['mtime'])} for rel, info in sorted(current.items()) if rel not in old]
    removed = [{'path': rel} for rel in sorted(old) if rel not in current]
    total = len(modified) + len(added) + len(removed)
    result = {'label': label, 'sealed': True, 'sealed_at': sealed.get('sealed_at'), 'reason': sealed.get('reason'),
              'modified': modified, 'added': added, 'removed': removed, 'total': total, 'clean': total == 0}
    if record and total:
        fingerprint = sha256_bytes(repr([(m['path'], current[m['path']]['sha']) for m in modified]
                                        + [a['path'] for a in added] + [r['path'] for r in removed]).encode())
        if sealed.get('last_drift') != fingerprint:
            log('integrity.manual_change', level='warning', stream='changes', server=label,
                modified=[m['path'] for m in modified][:200], added=[a['path'] for a in added][:200],
                removed=[r['path'] for r in removed][:200],
                newest=max((m['modified_at'] for m in modified + added), default=None))
            sealed['last_drift'] = fingerprint
            atomic_write_json(_seal_file(label), sealed)
    return result


def record_tool_write(ws: Workspace, before: dict[str, dict[str, Any]], *, event: str, reason: str,
                      label: str = LOCAL, **fields: Any) -> list[str]:
    """Para escrituras de la herramienta sin transacción (CLI antigua): registra qué archivos cambiaron y los sella."""
    after = scan(ws, label)
    changed = sorted(rel for rel in set(before) | set(after) if (before.get(rel) or {}).get('sha') != (after.get(rel) or {}).get('sha'))
    log(event, level='warning' if changed else 'info', stream='changes', server=label, reason=reason,
        files=changed[:300], total=len(changed), **fields)
    if changed:
        seal(ws, label, reason=reason, source=event, paths=changed)
    return changed
