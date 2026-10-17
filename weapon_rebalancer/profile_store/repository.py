"""Almacenamiento de perfiles por niveles, con historial de versiones.

    profiles/
    ├── official/   Balanced RP, Realistic Combat, Competitive PvP (solo lectura)
    ├── server/     perfiles del servidor (flow_caribe); editables si el workspace lo permite
    ├── user/       perfiles creados desde la web o la terminal
    ├── legacy/     perfiles anteriores archivados (solo lectura)
    ├── schemas/    profile.schema.json
    └── migrations/ informes y pendientes de migración

- El identificador es único entre todos los niveles.
- Antes de cada cambio se guarda la versión anterior en ``data/history/<id>/``.
- Borrar mueve el archivo a ``data/trash/``.
- Las escrituras usan un bloqueo entre procesos: el panel web y la terminal pueden
  trabajar a la vez sin pisarse, y `expected_sha` detecta ediciones concurrentes.
"""
from __future__ import annotations

import hashlib
import json
import threading
import time
from copy import deepcopy
from pathlib import Path
from typing import Any, Callable

from ..core.errors import Conflict, Forbidden, NotFound, ValidationFailed
from ..core.filelock import file_lock
from ..core.fsutil import atomic_write_bytes, atomic_write_json, read_json, sha256_bytes
from ..core.jsonlog import log
from ..core.paths import PROFILES_DIR, PathGuard, data_dir, validate_profile_id
from .migrations import detect_version, downgrade_to_legacy, is_legacy, migrate, now_iso
from .resolver import resolve
from .schema import SCHEMA_REF, SCHEMA_VERSION, blank_profile

TIERS = ('official', 'server', 'user', 'legacy')
TIER_LABELS = {'official': 'Oficial', 'server': 'Servidor', 'user': 'Usuario', 'legacy': 'Archivado'}
_LOCK = threading.RLock()


def _dump(data: dict[str, Any]) -> bytes:
    return (json.dumps(data, ensure_ascii=False, indent=2) + '\n').encode('utf-8')


def _stamp() -> str:
    return time.strftime('%Y%m%d-%H%M%S') + f'-{int((time.time() % 1) * 1_000_000):06d}'


def _ordered(payload: dict[str, Any]) -> dict[str, Any]:
    head = {key: payload[key] for key in ('$schema', 'schema_version', 'profile') if key in payload}
    return {**head, **{k: v for k, v in payload.items() if k not in head}}


class ProfileRepository:
    def __init__(self, directory: Path = PROFILES_DIR, *, server_editable: Callable[[], bool] | None = None) -> None:
        self.directory = directory
        self.dirs = {tier: directory / tier for tier in TIERS}
        for tier in ('official', 'server', 'user'):
            self.dirs[tier].mkdir(parents=True, exist_ok=True)
        self.history_root = data_dir('history')
        self.trash = data_dir('trash')
        self.guard = PathGuard([self.directory, self.history_root.parent], 'perfiles')
        self._server_editable = server_editable or (lambda: True)
        self._index: dict[str, tuple[str, Path]] = {}
        self._index_sig: tuple | None = None
        self._index_errors: list[str] = []
        self._load_cache: dict[Path, tuple[tuple[int, int], dict[str, Any], str]] = {}
        self._resolved_cache: dict[str, tuple[dict[str, Any], dict[str, tuple[int, int]]]] = {}

    # ---- índice -----------------------------------------------------------------
    def _dir_signature(self) -> tuple:
        sig = []
        for tier, folder in self.dirs.items():
            try:
                stat = folder.stat()
                sig.append((tier, stat.st_mtime_ns))
            except FileNotFoundError:
                sig.append((tier, None))
        return tuple(sig)

    def index(self) -> dict[str, tuple[str, Path]]:
        """id -> (nivel, ruta). Se recalcula solo si cambia el contenido de las carpetas."""
        signature = self._dir_signature()
        if signature == self._index_sig:
            return self._index
        index: dict[str, tuple[str, Path]] = {}
        errors: list[str] = []
        for tier in TIERS:
            folder = self.dirs[tier]
            if not folder.is_dir():
                continue
            for path in sorted(folder.glob('*.json')):
                if path.name == 'catalog.json':  # catálogo de la CLI antigua, no es un perfil
                    continue
                profile_id = path.stem
                if profile_id in index:
                    errors.append(f'El id “{profile_id}” existe en {index[profile_id][0]} y en {tier}; se usa {index[profile_id][0]}.')
                    continue
                index[profile_id] = (tier, path)
        self._index, self._index_sig, self._index_errors = index, signature, errors
        return index

    def index_errors(self) -> list[str]:
        self.index()
        return list(self._index_errors)

    def ids(self, *, include_legacy: bool = False) -> list[str]:
        return sorted(pid for pid, (tier, _) in self.index().items() if include_legacy or tier != 'legacy')

    def tier(self, profile_id: str) -> str:
        entry = self.index().get(validate_profile_id(profile_id))
        if entry is None:
            raise NotFound(f'No existe el perfil “{profile_id}”.')
        return entry[0]

    def exists(self, profile_id: str) -> bool:
        return validate_profile_id(profile_id) in self.index()

    def path(self, profile_id: str, *, new_tier: str = 'user') -> Path:
        validate_profile_id(profile_id)
        entry = self.index().get(profile_id)
        path = entry[1] if entry else self.dirs[new_tier] / f'{profile_id}.json'
        return self.guard.check(path)

    def history_dir(self, profile_id: str) -> Path:
        path = self.guard.check(self.history_root / validate_profile_id(profile_id))
        path.mkdir(parents=True, exist_ok=True)
        return path

    # ---- permisos ---------------------------------------------------------------
    def editable(self, profile_id: str) -> bool:
        tier = self.tier(profile_id)
        if tier == 'user':
            return True
        if tier == 'server':
            return bool(self._server_editable())
        return False

    def ensure_editable(self, profile_id: str, action: str = 'modificar') -> None:
        tier = self.tier(profile_id)
        if self.editable(profile_id):
            return
        if tier == 'server':
            raise Forbidden(f'La edición de perfiles del servidor está desactivada: no se puede {action} “{profile_id}”.',
                            hint='Actívala en Configuración (server_profiles_editable) o crea un perfil derivado.')
        raise Forbidden(f'“{profile_id}” es un perfil {TIER_LABELS[tier].lower()} protegido: no se puede {action}.',
                        hint=f'Crea un perfil derivado: hereda todo de “{profile_id}” y guarda solo tus cambios.')

    # ---- lectura -----------------------------------------------------------------
    def read_raw(self, profile_id: str) -> tuple[dict[str, Any], str]:
        if not self.exists(profile_id):
            raise NotFound(f'No existe el perfil “{profile_id}”.')
        path = self.path(profile_id)
        stat = path.stat()
        sig = (stat.st_mtime_ns, stat.st_size)
        cached = self._load_cache.get(path)
        if cached and cached[0] == sig:
            return deepcopy(cached[1]), cached[2]
        raw = path.read_bytes()
        try:
            data = json.loads(raw.decode('utf-8'))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ValidationFailed(f'{path.name} no es JSON válido: {exc}') from exc
        if not isinstance(data, dict):
            raise ValidationFailed(f'{path.name} debe contener un objeto JSON.')
        sha = sha256_bytes(raw)
        self._load_cache[path] = (sig, deepcopy(data), sha)
        return data, sha

    def load(self, profile_id: str) -> dict[str, Any]:
        """Perfil en formato v8 (migrado en memoria si es legacy)."""
        data, _ = self.read_raw(profile_id)
        migrated, _notes = migrate(data, profile_id)
        return migrated

    def _file_sig(self, profile_id: str) -> tuple[int, int]:
        stat = self.path(profile_id).stat()
        return stat.st_mtime_ns, stat.st_size

    def resolved(self, profile_or_id: dict[str, Any] | str) -> dict[str, Any]:
        """Perfil con la herencia aplicada. Cacheado mientras no cambie ningún archivo de la cadena."""
        profile = self.load(profile_or_id) if isinstance(profile_or_id, str) else profile_or_id
        key = hashlib.sha256(json.dumps(profile, sort_keys=True, default=str).encode('utf-8')).hexdigest()
        cached = self._resolved_cache.get(key)
        if cached:
            result, deps = cached
            try:
                if all(self._file_sig(pid) == sig for pid, sig in deps.items()):
                    return deepcopy(result)
            except (NotFound, FileNotFoundError, ValidationFailed):
                pass
        deps: dict[str, tuple[int, int]] = {}

        def loader(parent_id: str) -> dict[str, Any]:
            if not self.exists(parent_id):
                raise ValidationFailed(f'El perfil base “{parent_id}” no existe.', hint='Corrige “Hereda de” o restaura ese perfil.')
            deps[parent_id] = self._file_sig(parent_id)
            return self.load(parent_id)

        result = resolve(profile, loader)
        if len(self._resolved_cache) > 64:
            self._resolved_cache.clear()
        self._resolved_cache[key] = (deepcopy(result), deps)
        return result

    def children(self, profile_id: str) -> list[str]:
        result = []
        for other in self.ids(include_legacy=True):
            if other == profile_id:
                continue
            try:
                if (self.load(other).get('profile') or {}).get('extends') == profile_id:
                    result.append(other)
            except Exception:  # noqa: BLE001
                continue
        return result

    def summary(self, profile_id: str) -> dict[str, Any]:
        tier, path = self.index()[validate_profile_id(profile_id)]
        base = {'id': profile_id, 'tier': tier, 'tier_label': TIER_LABELS[tier], 'path': str(path.relative_to(self.directory))}
        try:
            raw, sha = self.read_raw(profile_id)
        except ValidationFailed as exc:
            return {**base, 'name': profile_id, 'error': exc.message, 'editable': False}
        data, _ = migrate(raw, profile_id)
        meta = data.get('profile') or {}
        return {
            **base,
            'editable': self.editable(profile_id),
            'name': meta.get('name') or profile_id,
            'short_name': meta.get('short_name') or meta.get('name') or profile_id,
            'description': meta.get('description', ''),
            'objective': meta.get('objective') or meta.get('purpose', ''),
            'audience': meta.get('audience', ''),
            'features': meta.get('features', []),
            'warnings': meta.get('warnings', []),
            'extends': meta.get('extends'),
            'tags': meta.get('tags', []),
            'revision': meta.get('revision', 0),
            'updated_at': meta.get('updated_at') or time.strftime('%Y-%m-%dT%H:%M:%S', time.localtime(path.stat().st_mtime)),
            'format_version': detect_version(raw),
            'legacy': is_legacy(raw),
            'engine_defaults': data.get('engine_defaults', True),
            'weapons': len(data.get('weapons') or {}),
            'groups': len(data.get('groups') or {}),
            'size': path.stat().st_size,
            'sha': sha,
        }

    def list(self, *, include_legacy: bool = False) -> list[dict[str, Any]]:
        order = {tier: i for i, tier in enumerate(TIERS)}
        rows = [self.summary(pid) for pid in self.ids(include_legacy=include_legacy)]
        return sorted(rows, key=lambda r: (order[r['tier']], r['id']))

    # ---- escritura ---------------------------------------------------------------
    def _snapshot(self, profile_id: str, action: str, note: str, sha_after: str | None, revision: int | None) -> str | None:
        path = self.path(profile_id)
        name: str | None = None
        sha_before = None
        if path.is_file():
            content = path.read_bytes()
            name = f'{_stamp()}_{action}.json'
            (self.history_dir(profile_id) / name).write_bytes(content)
            sha_before = sha256_bytes(content)
        entry = {
            'file': name, 'ts': now_iso(), 'action': action, 'note': note,
            'sha_before': sha_before, 'sha_after': sha_after, 'revision': revision,
        }
        with open(self.history_dir(profile_id) / 'index.jsonl', 'a', encoding='utf-8') as handle:
            handle.write(json.dumps(entry, ensure_ascii=False) + '\n')
        return name

    def save(self, profile_id: str, data: dict[str, Any], *, expected_sha: str | None = None, action: str = 'edit',
             note: str = '', tier: str = 'user', check_permissions: bool = True) -> dict[str, Any]:
        """Guarda con control de conflictos, bloqueo entre procesos y versión anterior en el historial."""
        if not isinstance(data, dict):
            raise ValidationFailed('El perfil debe ser un objeto JSON.')
        with _LOCK, file_lock('profiles'):
            exists = self.exists(profile_id)
            if exists and check_permissions:
                self.ensure_editable(profile_id, 'guardar')
            path = self.path(profile_id, new_tier=tier)
            current_sha = sha256_bytes(path.read_bytes()) if path.is_file() else None
            if expected_sha is not None and current_sha is not None and expected_sha != current_sha:
                raise Conflict('El perfil cambió en disco desde que lo abriste (quizá desde la otra interfaz).',
                               hint='Recarga el perfil para ver la versión actual antes de guardar.')
            payload, _notes = migrate(data, profile_id)
            meta = payload.setdefault('profile', {})
            meta['id'] = profile_id
            meta.pop('resolved_chain', None)
            meta['revision'] = int(meta.get('revision') or 0) + 1
            meta.setdefault('created_at', now_iso())
            meta['updated_at'] = now_iso()
            payload['schema_version'] = SCHEMA_VERSION
            payload.setdefault('$schema', SCHEMA_REF)
            payload = _ordered(payload)
            if current_sha is not None:
                previous, _ = self.read_raw(profile_id)
                comparable = {k: v for k, v in previous.items() if k != 'profile'}
                if comparable == {k: v for k, v in payload.items() if k != 'profile'} and \
                        {k: v for k, v in (previous.get('profile') or {}).items() if k not in {'revision', 'updated_at'}} == \
                        {k: v for k, v in meta.items() if k not in {'revision', 'updated_at'}}:
                    return {'id': profile_id, 'sha': current_sha, 'changed': False}
            self._snapshot(profile_id, action, note, sha256_bytes(_dump(payload)), meta.get('revision'))
            atomic_write_json(path, payload)
            log('profile.save', profile=profile_id, action=action, revision=meta.get('revision'))
            return {'id': profile_id, 'sha': sha256_bytes(path.read_bytes()), 'changed': True}

    def create(self, profile_id: str, name: str, description: str = '', *, extends: str | None = None,
               source: str | None = None) -> dict[str, Any]:
        """Crea un perfil de usuario: vacío, copia de otro (`source`) o derivado (`extends`)."""
        with _LOCK, file_lock('profiles'):
            if self.exists(profile_id):
                raise Conflict(f'Ya existe un perfil con id “{profile_id}”.')
            if extends:
                self.load(extends)
            if source:
                data = self.load(source)
                meta = data.setdefault('profile', {})
                meta.update({'id': profile_id, 'name': name, 'short_name': name[:24],
                             'description': description or meta.get('description', ''), 'revision': 0, 'created_at': now_iso()})
                for key in ('migrated_from', 'migrated_at', 'migration'):
                    meta.pop(key, None)
                if extends is not None:
                    meta['extends'] = extends
            elif extends:
                data = {'$schema': SCHEMA_REF, 'schema_version': SCHEMA_VERSION,
                        'profile': {**blank_profile(profile_id, name, description)['profile'], 'extends': extends}}
            else:
                data = blank_profile(profile_id, name, description, None)
            return self.save(profile_id, data, action='create', note=f'origen: {source or (f"deriva de {extends}" if extends else "vacío")}',
                             tier='user', check_permissions=False)

    def duplicate(self, profile_id: str, new_id: str, name: str | None = None) -> dict[str, Any]:
        source = self.load(profile_id)
        return self.create(new_id, name or f'{(source.get("profile") or {}).get("name", profile_id)} (copia)', source=profile_id)

    def derive(self, profile_id: str, new_id: str, name: str | None = None) -> dict[str, Any]:
        source = self.load(profile_id)
        label = (source.get('profile') or {}).get('name', profile_id)
        return self.create(new_id, name or f'{label} (derivado)', f'Hereda de {label}; solo guarda sus diferencias.', extends=profile_id)

    def rename(self, profile_id: str, new_id: str, name: str | None = None) -> dict[str, Any]:
        with _LOCK, file_lock('profiles'):
            if self.tier(profile_id) != 'user':
                if name and new_id == profile_id:
                    self.ensure_editable(profile_id, 'renombrar')
                else:
                    raise Forbidden('Solo los perfiles de usuario cambian de identificador (los oficiales y del servidor son estables).',
                                    hint='Puedes cambiar su nombre visible o crear un perfil derivado.')
            if self.exists(new_id) and new_id != profile_id:
                raise Conflict(f'Ya existe un perfil con id “{new_id}”.')
            data = self.load(profile_id)
            meta = data.setdefault('profile', {})
            if name:
                meta['name'] = name
            if new_id == profile_id:
                return self.save(profile_id, data, action='rename', note=f'nombre: {name}')
            children = self.children(profile_id)
            result = self.save(new_id, data, action='rename', note=f'renombrado desde {profile_id}', tier='user', check_permissions=False)
            self._snapshot(profile_id, 'renamed', f'renombrado a {new_id}', None, None)
            old_history = self.history_dir(profile_id)
            new_history = self.history_dir(new_id)
            for item in old_history.iterdir():
                if item.name != 'index.jsonl':
                    item.replace(new_history / item.name)
            self.path(profile_id).unlink()
            self._index_sig = None
            for child in children:
                if not self.editable(child):
                    continue
                child_data = self.load(child)
                child_data['profile']['extends'] = new_id
                self.save(child, child_data, action='parent_renamed', note=f'{profile_id} → {new_id}')
            return {**result, 'updated_children': children}

    def delete(self, profile_id: str) -> dict[str, Any]:
        with _LOCK, file_lock('profiles'):
            if self.tier(profile_id) != 'user':
                raise Forbidden('Solo se pueden borrar perfiles de usuario.', hint='Los oficiales, del servidor y archivados están protegidos.')
            path = self.path(profile_id)
            children = self.children(profile_id)
            if children:
                raise Conflict(f'No se puede borrar: {", ".join(children)} heredan de este perfil.',
                               hint='Cambia o elimina primero la herencia de esos perfiles.')
            self._snapshot(profile_id, 'delete', 'movido a la papelera', None, None)
            target = self.trash / f'{profile_id}_{_stamp()}.json'
            path.replace(target)
            self._index_sig = None
            log('profile.delete', profile=profile_id, trash=str(target))
            return {'id': profile_id, 'trash': str(target)}

    # ---- historial ---------------------------------------------------------------
    def history(self, profile_id: str) -> list[dict[str, Any]]:
        # Solo lectura: no crea la carpeta de historial de un perfil que nunca se guardó.
        index = self.guard.check(self.history_root / validate_profile_id(profile_id)) / 'index.jsonl'
        if not index.is_file():
            return []
        entries = []
        for line in index.read_text(encoding='utf-8').splitlines():
            try:
                entries.append(json.loads(line))
            except json.JSONDecodeError:
                continue
        return list(reversed(entries))

    def revision_content(self, profile_id: str, file_name: str) -> dict[str, Any]:
        if '/' in file_name or '\\' in file_name or not file_name.endswith('.json'):
            raise ValidationFailed('Nombre de versión inválido.')
        path = self.guard.check(self.history_dir(profile_id) / file_name)
        if not path.is_file():
            raise NotFound('Esa versión no existe.')
        data = read_json(path)
        if not isinstance(data, dict):
            raise ValidationFailed('La versión guardada no es un objeto JSON.')
        return data

    def restore(self, profile_id: str, file_name: str) -> dict[str, Any]:
        """Devuelve el archivo exactamente como estaba (mismos bytes), guardando antes el actual."""
        self.revision_content(profile_id, file_name)
        content = (self.history_dir(profile_id) / file_name).read_bytes()
        with _LOCK, file_lock('profiles'):
            self.ensure_editable(profile_id, 'restaurar')
            path = self.path(profile_id)
            if path.is_file() and path.read_bytes() == content:
                return {'id': profile_id, 'sha': sha256_bytes(content), 'changed': False}
            self._snapshot(profile_id, 'restore', f'restaurado desde {file_name}', sha256_bytes(content), None)
            atomic_write_bytes(path, content)
            log('profile.restore', profile=profile_id, source=file_name)
            return {'id': profile_id, 'sha': sha256_bytes(content), 'changed': True}

    # ---- import / export / migración ---------------------------------------------
    def import_profile(self, profile_id: str, content: str, *, overwrite: bool = False) -> dict[str, Any]:
        try:
            data = json.loads(content)
        except json.JSONDecodeError as exc:
            raise ValidationFailed(f'JSON inválido: línea {exc.lineno}, columna {exc.colno}.') from exc
        if not isinstance(data, dict):
            raise ValidationFailed('El archivo debe contener un objeto JSON.')
        if self.exists(profile_id):
            if not overwrite:
                raise Conflict(f'Ya existe “{profile_id}”.', hint='Elige otro id o marca “sobrescribir”.')
            self.ensure_editable(profile_id, 'sobrescribir')
        migrated, notes = migrate(data, profile_id)
        result = self.save(profile_id, migrated, action='import', note='; '.join(notes), tier='user')
        return {**result, 'notes': notes}

    def export(self, profile_id: str, *, resolved: bool = False, legacy: bool = False) -> dict[str, Any]:
        data = self.resolved(profile_id) if resolved else self.load(profile_id)
        if resolved:
            data.get('profile', {}).pop('extends', None)
        return downgrade_to_legacy(data) if legacy else data

    def migrate_file(self, profile_id: str, *, dry_run: bool = False) -> dict[str, Any]:
        raw, _ = self.read_raw(profile_id)
        if not is_legacy(raw):
            return {'id': profile_id, 'migrated': False, 'notes': ['Ya está en v8.']}
        migrated, notes = migrate(raw, profile_id)
        if dry_run or not self.editable(profile_id):
            return {'id': profile_id, 'migrated': False, 'would_migrate': self.editable(profile_id), 'notes': notes}
        self.save(profile_id, migrated, action='migrate', note='; '.join(notes))
        return {'id': profile_id, 'migrated': True, 'notes': notes}

    def revert_migration(self, profile_id: str) -> dict[str, Any]:
        for entry in self.history(profile_id):
            if entry.get('action') == 'migrate' and entry.get('file'):
                return self.restore(profile_id, entry['file'])
        raise NotFound('Este perfil no tiene una migración registrada.')
