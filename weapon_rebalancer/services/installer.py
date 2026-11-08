"""Instalación de armas nuevas: copia los ``.meta`` de una carpeta de origen a un pack.

Sirve para meter en el servidor un arma hecha con una herramienta de armado (p. ej.
``od_weapon_builder``) sin copiar archivos a mano. ``plan`` es la vista previa (no
escribe nada) y ``apply`` instala como transacción reversible (``wr.py rollback <id>``):

- Solo se copian los ``*.meta`` del origen, con sus subcarpetas. El resto (modelos,
  texturas, textos, enlaces simbólicos) se ignora y se avisa.
- El destino tiene que quedar dentro de un recurso (carpeta con ``fxmanifest.lua``)
  de un pack configurado (``pack_roots``).
- Bloquea: XML inválido o no UTF-8 en el origen, destino fuera de los packs, archivo
  que ya existe sin ``replace`` y, con ``replace``, un archivo cambiado a mano según
  el sello (no se pisa trabajo ajeno).
- Lo que se reemplaza se respalda en ``data/backups/<id>/``; escritura atómica,
  verificación de cada archivo, registro (``install.apply``) y sello parcial de lo
  instalado.
- El rollback borra los archivos creados (si siguen intactos), restaura los
  reemplazados y quita las carpetas vacías que creó la instalación.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import stat
import threading
import time
from pathlib import Path
from typing import Any

from ..core.errors import Conflict, Forbidden, NotFound, ValidationFailed
from ..core.fsutil import atomic_write_bytes, decode_strict, sha256_bytes, sha256_file
from ..core.jsonlog import log
from ..core.paths import PathGuard, data_dir, is_within
from ..core.workspace import Workspace
from ..meta.pack_audit import declared_kinds
from ..meta.scanner import ScanConfig, extract_weapon_blocks
from . import integrity
from .generator import CONFIRM_WORD, _reseal, _xml_ok
from .preview import canonical_hash

SUFFIX = '.meta'
MANIFEST_NAMES = ('fxmanifest.lua', '__resource.lua')
NEW, REPLACE, SAME, BLOCKED = 'nuevo', 'reemplaza', 'idéntico', 'bloqueado'
_LOCK = threading.Lock()
_ID_RE = re.compile(r'[^A-Za-z0-9_-]+')


def write_guard(ws: Workspace) -> PathGuard:
    return PathGuard(ws.pack_paths, 'packs de armas')


def _resource_of(dest: Path, pack: Path) -> tuple[Path, Path] | None:
    """Recurso FiveM (carpeta con fxmanifest.lua) que contiene ``dest``, sin salir del pack."""
    current = dest
    while True:
        for name in MANIFEST_NAMES:
            if (current / name).is_file():
                return current, current / name
        if current == pack or current.parent == current:
            return None
        current = current.parent


def _collect(source: Path) -> tuple[list[tuple[str, Path]], list[dict[str, str]]]:
    """(rel, ruta) de cada ``.meta`` del origen y lista de lo que se ignora."""
    metas: list[tuple[str, Path]] = []
    ignored: list[dict[str, str]] = []
    for directory, dirs, names in os.walk(source):          # no sigue enlaces simbólicos
        base = Path(directory)
        dirs.sort()
        for name in list(dirs):
            hidden = name.startswith('.')
            if hidden or (base / name).is_symlink():
                ignored.append({'path': (base / name).relative_to(source).as_posix() + '/',
                                'why': 'carpeta oculta' if hidden else 'enlace simbólico'})
                dirs.remove(name)
        for name in sorted(names):
            path = base / name
            rel = path.relative_to(source).as_posix()
            if path.is_symlink() or not path.is_file():
                ignored.append({'path': rel, 'why': 'enlace simbólico o archivo especial'})
            elif name.endswith(SUFFIX):
                metas.append((rel, path))
            else:
                ignored.append({'path': rel, 'why': 'no es .meta'})
    return metas, ignored


def _weapons_in(path: Path, text: str) -> list[str]:
    blocks = extract_weapon_blocks(path, text, ScanConfig(), [])
    return sorted({b.weapon.upper() for b in blocks if b.source == 'CWeaponInfo'})


def _build(ws: Workspace, source: str, dest: str, *, replace: bool,
           catalog: Any = None) -> tuple[dict[str, Any], dict[str, bytes]]:
    if not str(source or '').strip():
        raise ValidationFailed('Indica la carpeta de origen (la que tiene los .meta del arma).')
    if not str(dest or '').strip():
        raise ValidationFailed('Indica la carpeta destino con --dest (dentro de un pack de armas).')
    src = Path(source).expanduser().resolve()
    dst = Path(dest).expanduser().resolve()
    if not src.is_dir():
        raise NotFound(f'La carpeta de origen no existe: {src}')
    server = ws.server_path.resolve()
    blocking: list[dict[str, str]] = []
    warnings: list[str] = []

    def block(path: str, message: str) -> None:
        blocking.append({'path': path, 'message': message})

    guard = write_guard(ws)
    pack: Path | None = None
    try:
        guard.check(dst)
        pack = max((root for root in guard.roots if is_within(dst, root)), key=lambda root: len(root.parts))
    except Forbidden:
        block(str(dst), 'El destino está fuera de los packs de armas configurados (pack_roots).')
    if pack is not None and not is_within(dst, server):
        block(str(dst), f'El destino está fuera del servidor ({server}).')
        pack = None
    resource = manifest = None
    if pack is not None:
        found = _resource_of(dst, pack)
        if found is None:
            block(str(dst), 'El destino no está dentro de ningún recurso (carpeta con fxmanifest.lua): '
                            'FiveM no cargaría esos metas.')
        else:
            resource, manifest = found
    if dst.exists() and not dst.is_dir():
        block(str(dst), 'El destino existe y no es una carpeta.')
    if is_within(dst, src) or is_within(src, dst):
        block(str(dst), 'El origen y el destino se solapan (uno está dentro del otro).')

    drift = integrity.check(ws, integrity.LOCAL, record=True)       # deja en el registro los cambios a mano nuevos
    manual = {item['path'] for item in drift['modified'] + drift['added']} if drift['sealed'] else set()
    if not drift['sealed']:
        warnings.append('Este servidor no tiene sello todavía: al instalar se crea uno completo '
                        '(también sella lo que haya hoy en los packs).')

    metas, ignored = _collect(src)
    if not metas:
        block(str(src), 'El origen no tiene archivos .meta.')
    entries: list[dict[str, Any]] = []
    contents: dict[str, bytes] = {}
    for rel, path in metas:
        raw = path.read_bytes()
        target = dst / rel
        server_rel = str(target.relative_to(server)) if is_within(dst, server) else str(target)
        entry: dict[str, Any] = {'rel': rel, 'source': str(path), 'path': str(ws.server_path / server_rel)
                                 if is_within(dst, server) else str(target), 'server_rel': server_rel,
                                 'size': len(raw), 'sha': sha256_bytes(raw), 'status': NEW, 'sha_before': None,
                                 'size_before': None, 'weapons': [], 'note': ''}
        entries.append(entry)
        text, error = decode_strict(raw)
        if text is None:
            entry['status'], entry['note'] = BLOCKED, f'no es UTF-8 válido ({error})'
            block(rel, f'No es UTF-8 válido ({error}).')
            continue
        if not _xml_ok(text):
            entry['status'], entry['note'] = BLOCKED, 'XML inválido'
            block(rel, 'No es XML válido.')
            continue
        entry['weapons'] = _weapons_in(path, text)
        contents[entry['path']] = raw
        if pack is not None:
            try:
                guard.check(target)
            except Forbidden:
                entry['status'], entry['note'] = BLOCKED, 'sale de los packs'
                block(rel, 'La ruta destino sale de los packs (enlace simbólico).')
                continue
        if target.is_symlink() or (target.exists() and not target.is_file()):
            entry['status'], entry['note'] = BLOCKED, 'no es un archivo normal'
            block(rel, 'En el destino ya hay algo con ese nombre que no es un archivo normal.')
            continue
        if not target.is_file():
            continue
        entry['sha_before'] = sha256_file(target)
        entry['size_before'] = target.stat().st_size
        if entry['sha_before'] == entry['sha']:
            entry['status'] = SAME
            if server_rel in manual:
                warnings.append(f'{rel}: idéntico al origen pero sin sellar (cambio a mano según wr.py integrity); '
                                'la instalación no lo toca ni lo sella.')
            continue
        entry['status'] = REPLACE
        old_text, _error = decode_strict(target.read_bytes())
        dropped = sorted(set(_weapons_in(target, old_text)) - set(entry['weapons'])) if old_text is not None else []
        if dropped:
            warnings.append(f'{rel}: al reemplazarlo dejan de existir {", ".join(dropped)} (el archivo nuevo no las define).')
        if not replace:
            entry['note'] = 'ya existe'
            block(rel, 'Ya existe en el destino y es distinto: usa --replace para reemplazarlo.')
        elif not drift['sealed']:
            entry['note'] = 'sin sello'
            block(rel, 'No hay sello: no se puede saber si se cambió a mano, así que no se reemplaza.')
        elif server_rel in manual:
            entry['note'] = 'cambiado a mano'
            block(rel, 'Cambiado a mano según el sello (wr.py integrity): no se pisa.')
        elif Path(str(target) + '.bak').is_file():
            entry['note'] = 'tiene .bak'
            warnings.append(f'{rel}: tiene .bak hermano; el «original» de comparaciones (y de restore.from_backup) '
                            'sigue siendo el de antes.')

    writable = [e for e in entries if e['status'] in (NEW, REPLACE)]
    if manifest is not None and resource is not None:
        for entry in writable:
            relative = (dst / entry['rel']).relative_to(resource).as_posix()
            if not declared_kinds(manifest, relative):
                warnings.append(f'{relative}: ningún data_file de {resource.name}/{manifest.name} lo carga; revisa el fxmanifest.')
    new_weapons = sorted({w for e in writable for w in e['weapons']})
    if catalog is not None:
        targets = {str(Path(e['path']).resolve()) for e in entries}
        ox_weapons = set((catalog.ox.weapons if getattr(catalog, 'ox', None) else {}) or {})
        for weapon in new_weapons:
            others = [d for d in catalog.definitions.get(weapon, [])
                      if d.source == 'CWeaponInfo' and str(Path(d.path).resolve()) not in targets]
            if others:
                where = str(others[0].path).split('resources/')[-1]
                more = f' y {len(others) - 1} más' if len(others) > 1 else ''
                warnings.append(f'{weapon} ya está definida en {where}{more}: quedaría duplicada.')
            if getattr(catalog, 'ox', None) is not None and weapon not in ox_weapons:
                warnings.append(f'{weapon} no está en ox_inventory (data/weapons.lua): no aparecerá en el inventario.')

    counts = {status: sum(1 for e in entries if e['status'] == status) for status in (NEW, REPLACE, SAME, BLOCKED)}
    plan_hash = canonical_hash({'source': str(src), 'dest': str(dst), 'replace': bool(replace),
                                'files': [[e['rel'], e['sha'], e['status'], e['sha_before']] for e in entries]})
    data = {'source': str(src), 'dest': str(dst), 'pack': str(pack) if pack else None,
            'resource': resource.name if resource else None, 'resource_dir': str(resource) if resource else None,
            'replace': bool(replace), 'sealed': drift['sealed'], 'files': entries, 'ignored': ignored,
            'blocking': blocking, 'warnings': warnings, 'weapons': new_weapons, 'plan_hash': plan_hash,
            'summary': {**counts, 'to_write': len(writable), 'bytes': sum(e['size'] for e in writable)}}
    return data, contents


def plan(ws: Workspace, source: str, dest: str, *, replace: bool = False, catalog: Any = None) -> dict[str, Any]:
    """Vista previa: qué se instalaría y qué lo impide. No escribe nada en el servidor."""
    data, _contents = _build(ws, source, dest, replace=replace, catalog=catalog)
    return data


def _tx_id(dest: Path) -> str:
    base = time.strftime('%Y%m%d-%H%M%S') + '_install_' + (_ID_RE.sub('_', dest.name).strip('_') or 'arma')
    root = data_dir('backups')
    tx_id, index = base, 1
    while (root / tx_id).exists():
        index += 1
        tx_id = f'{base}_{index}'
    return tx_id


def _new_dirs(paths: list[str]) -> list[str]:
    """Carpetas que hay que crear para estos archivos, de la más profunda a la menos."""
    found: set[str] = set()
    for raw in paths:
        parent = Path(raw).parent
        while not parent.exists() and parent.parent != parent:
            found.add(str(parent))
            parent = parent.parent
    return sorted(found, key=lambda p: (-len(Path(p).parts), p))


def _inherit_owner(path: Path, gid: int) -> None:
    """Mismo grupo que la carpeta del pack (best effort: solo si el usuario puede)."""
    try:
        if path.stat().st_gid != gid:
            os.chown(path, -1, gid)
    except (OSError, AttributeError):
        pass


def _make_dir(path: Path) -> None:
    parent = path.parent.stat()
    path.mkdir()
    try:
        os.chmod(path, stat.S_IMODE(parent.st_mode))
    except OSError:
        pass
    _inherit_owner(path, parent.st_gid)


def _write_manifest(tx_root: Path, manifest: dict[str, Any]) -> None:
    (tx_root / 'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')


def apply(ws: Workspace, source: str, dest: str, confirm: str, *, replace: bool = False, reason: str = '',
          plan_hash: str | None = None) -> dict[str, Any]:
    if confirm != CONFIRM_WORD:
        raise ValidationFailed(f'Para instalar escribe {CONFIRM_WORD} en la confirmación.')
    reason = str(reason or '').strip()
    if not reason:
        raise ValidationFailed('Indica el motivo con --reason: queda en el registro.')
    with _LOCK:
        data, contents = _build(ws, source, dest, replace=replace)
        if plan_hash and plan_hash != data['plan_hash']:
            raise Conflict('El origen o el destino cambiaron después de la vista previa. No se instaló nada.',
                           hint='Vuelve a ver la vista previa.')
        if data['blocking']:
            raise ValidationFailed('La instalación tiene bloqueos; corrígelos antes de aplicar.', details=data['blocking'])
        todo = [e for e in data['files'] if e['status'] in (NEW, REPLACE)]
        if not todo:
            return {'applied': False, 'dest': data['dest'],
                    'message': 'Nada que instalar: el destino ya tiene esos archivos idénticos.'}
        guard = write_guard(ws)
        created_dirs = _new_dirs([e['path'] for e in todo])
        for raw in created_dirs:
            guard.check(Path(raw))
        tx_id = _tx_id(Path(data['dest']))
        tx_root = data_dir('backups') / tx_id
        files_dir = tx_root / 'files'
        files_dir.mkdir(parents=True, exist_ok=False)
        manifest: dict[str, Any] = {
            'id': tx_id, 'kind': 'install', 'target': integrity.LOCAL, 'created_at': time.strftime('%Y-%m-%dT%H:%M:%S%z'),
            'profile': None, 'status': 'pending', 'reason': reason, 'source': data['source'], 'dest': data['dest'],
            'resource': data['resource'], 'weapons': data['weapons'], 'created_dirs': created_dirs, 'files': [],
            'summary': data['summary'],
        }
        for index, item in enumerate(todo):
            destination = guard.check(Path(item['path']))
            entry = {'path': item['path'], 'source': item['source'], 'status': item['status'], 'backup': None,
                     'sha_before': None, 'sha_after': item['sha'], 'bak_created': False}
            if item['status'] == REPLACE:
                entry['backup'] = f'{index:04d}_{destination.name}'
                entry['sha_before'] = sha256_file(destination)
                shutil.copy2(destination, files_dir / entry['backup'])
            manifest['files'].append(entry)
        _write_manifest(tx_root, manifest)

        made_dirs: list[str] = []
        written: list[dict[str, Any]] = []
        try:
            for raw in reversed(created_dirs):                       # de la menos profunda a la más
                _make_dir(Path(raw))
                made_dirs.append(raw)
            for entry in manifest['files']:
                path = Path(entry['path'])
                gid = path.stat().st_gid if path.is_file() else path.parent.stat().st_gid
                mode = stat.S_IMODE(path.parent.stat().st_mode) & 0o666
                atomic_write_bytes(path, contents[entry['path']], new_mode=mode)
                written.append(entry)
                _inherit_owner(path, gid)
                if sha256_file(path) != entry['sha_after']:
                    raise OSError(f'Verificación fallida tras escribir {entry["path"]}')
        except Exception as exc:  # noqa: BLE001
            for entry in written:
                if entry['backup']:
                    atomic_write_bytes(Path(entry['path']), (files_dir / entry['backup']).read_bytes())
                else:
                    Path(entry['path']).unlink(missing_ok=True)
            for raw in reversed(made_dirs):                          # de la más profunda a la menos
                try:
                    Path(raw).rmdir()
                except OSError:
                    pass
            manifest['status'] = 'failed_rolled_back'
            manifest['error'] = str(exc)
            _write_manifest(tx_root, manifest)
            log('install.apply_failed', level='error', stream='changes', tx=tx_id, dest=data['dest'], error=str(exc))
            raise ValidationFailed(f'Error al instalar; se revirtieron los cambios: {exc}') from exc

        manifest['status'] = 'applied'
        _write_manifest(tx_root, manifest)
        rels = [item['server_rel'] for item in todo]
        created = sum(1 for item in todo if item['status'] == NEW)
        log('install.apply', stream='changes', tx=tx_id, source=data['source'], dest=data['dest'],
            resource=data['resource'], reason=reason, files=rels[:300], created=created, replaced=len(todo) - created,
            weapons=data['weapons'], created_dirs=len(created_dirs))
        _reseal(ws, integrity.LOCAL, rels, f'instalación {tx_id}', 'install')
        return {'applied': True, 'transaction': tx_id, 'dest': data['dest'], 'resource': data['resource'],
                'files': len(todo), 'created': created, 'replaced': len(todo) - created,
                'created_dirs': len(created_dirs), 'weapons': data['weapons'], 'backup_dir': str(tx_root)}
