"""Operaciones de edición de perfiles. Única implementación: la usan la web (POST /api/profiles/ops)
y la terminal (`wr.py set`, editor interactivo).

Cada operación es un dict `{'op': ..., ...}`. `apply_ops` devuelve el perfil nuevo, los avisos
(módulos que se activaron) y, si `confirm_dormant` es False, las confirmaciones necesarias antes
de aplicar (valores ya escritos que pasarían a tener efecto).

Ámbitos (`scope`): `{'type': 'weapon', 'name': 'WEAPON_X'}`, `{'type': 'group', 'name': 'GROUP_X'}`
o `{'type': 'defaults'}`.
"""
from __future__ import annotations

from copy import deepcopy
from typing import Any

from ..core.errors import ValidationFailed
from ..meta.fields import FIELDS
from .schema import MODULE_PRESET_KEYS, MODULE_VALUES, SCOPE_KEYS, effective_modules, module_for_field

LISTS = {'ignore_weapons', 'harmless_weapons', 'allow_ignored_weapons', 'allow_damage_weapons'}
HEADSHOT_NUMBERS = {'multiplier', 'player_multiplier', 'network_multiplier', 'ai_multiplier', 'distance',
                    'target_effective_health', 'safety_margin', 'minimum_base_damage', 'helmet_multiplier', 'penetration'}
HEADSHOT_BOOLS = {'dynamic_multiplier_from_damage', 'dynamic_consider_falloff', 'no_falloff', 'bypass_helmets',
                  'sync_weapon_range', 'force_penetration', 'auto_minimum_base_damage'}
META_TEXT = {'name', 'short_name', 'description', 'objective', 'audience'}
META_LISTS = {'features', 'warnings', 'tags'}


def parse_scope(scope: Any) -> dict[str, str]:
    if isinstance(scope, str):
        text = scope.strip()
        if text.lower() in {'global', 'defaults', '*'}:
            return {'type': 'defaults', 'name': '*'}
        upper = text.upper()
        if upper.startswith('GROUP_'):
            return {'type': 'group', 'name': upper}
        if upper.startswith('WEAPON_') or upper:
            return {'type': 'weapon', 'name': upper}
    if isinstance(scope, dict) and scope.get('type') in {'weapon', 'group', 'defaults'}:
        return {'type': scope['type'], 'name': str(scope.get('name') or '*').upper() if scope['type'] != 'defaults' else '*'}
    raise ValidationFailed('Ámbito inválido.', hint='Usa WEAPON_X, GROUP_X o global.')


def scope_label(scope: dict[str, str]) -> str:
    return {'defaults': 'global', 'group': f'categoría {scope["name"]}', 'weapon': scope['name']}[scope['type']]


def _container(profile: dict[str, Any], scope: dict[str, str], create: bool) -> dict[str, Any] | None:
    if scope['type'] == 'defaults':
        if create:
            profile.setdefault('defaults', {})
        return profile.get('defaults')
    key = 'groups' if scope['type'] == 'group' else 'weapons'
    if create:
        profile.setdefault(key, {}).setdefault(scope['name'], {})
    holder = profile.get(key) or {}
    return holder.get(scope['name'])


def _cleanup(profile: dict[str, Any], scope: dict[str, str]) -> None:
    target = _container(profile, scope, False)
    if target is None:
        return
    for key in ('fields', 'headshot', 'meta'):
        if isinstance(target.get(key), dict) and not target[key]:
            del target[key]
    flags = target.get('weapon_flags')
    if isinstance(flags, dict) and not flags.get('add') and not flags.get('remove'):
        del target['weapon_flags']
    if scope['type'] != 'defaults' and not target:
        del profile['groups' if scope['type'] == 'group' else 'weapons'][scope['name']]


def get_field(profile: dict[str, Any], scope: dict[str, str], key: str) -> Any:
    target = _container(profile, scope, False) or {}
    if isinstance(target.get('fields'), dict) and key in target['fields']:
        return target['fields'][key]
    if key not in SCOPE_KEYS and key in target:
        return target[key]
    return None


def modules_to_enable(resolved: dict[str, Any], key: str) -> list[str]:
    modules = effective_modules(resolved)
    preset = [m for m, keys in MODULE_PRESET_KEYS.items() if key in keys]
    result = []
    for module in module_for_field(key) + preset:
        if module == 'headshot':
            continue
        mode = modules.get(module)
        if mode == 'original' or (module in preset and mode not in ('configured', 'original')):
            result.append(module)
    return sorted(set(result))


def dormant_fields(resolved: dict[str, Any], module: str, exclude: str | None = None) -> list[str]:
    """Valores ya escritos que hoy no tienen efecto y se activarían al encender `module`."""
    from .schema import iter_authored_fields

    result = []
    for scope, name, key, _value in iter_authored_fields(resolved):
        label = f'{"global" if scope == "defaults" else name}.{key}'
        if module in module_for_field(key) and label != exclude:
            result.append(label)
    return result


def _set_module(profile: dict[str, Any], module: str, value: str, notices: list[str], previous: str) -> None:
    profile.setdefault('modules', {})[module] = value
    extra = ''
    if previous not in ('original', 'configured', value) and module != 'headshot':
        extra = f' — deja de aplicarse el preset “{previous}” a todas las armas del perfil; revisa la vista previa'
    elif previous == 'original' and value == 'configured':
        extra = ' — ahora se aplican los valores de esta sección escritos en el perfil'
    notices.append(f'modules.{module}: {previous} → {value}{extra}')


def apply_ops(profile: dict[str, Any], ops: list[dict[str, Any]], *, resolver=None, confirm_dormant: bool = True) -> dict[str, Any]:
    """Aplica operaciones sobre una copia. `resolver(profile)` devuelve el perfil con la herencia aplicada."""
    result = deepcopy(profile)
    notices: list[str] = []
    confirmations: list[dict[str, Any]] = []
    resolve = resolver or (lambda p: p)
    if not isinstance(ops, list) or not ops:
        raise ValidationFailed('No hay operaciones que aplicar.')
    for op in ops:
        kind = op.get('op') if isinstance(op, dict) else None
        if kind in {'set_field', 'unset_field', 'inherit_field'}:
            scope = parse_scope(op.get('scope'))
            key = str(op.get('key', ''))
            if key not in FIELDS:
                raise ValidationFailed(f'Campo desconocido: {key}.', hint='Consulta la referencia de parámetros (wr.py params).')
            if kind == 'set_field':
                value = op.get('value')
                if isinstance(value, bool) or not isinstance(value, (int, float)):
                    raise ValidationFailed(f'{key} debe ser numérico.')
                resolved = resolve(result)
                enable = modules_to_enable(resolved, key)
                if enable:
                    self_label = f'{"global" if scope["type"] == "defaults" else scope["name"]}.{key}'
                    dormant = [f'{f}  (módulo {m})' for m in enable for f in dormant_fields(resolved, m, self_label)]
                    if dormant and not confirm_dormant:
                        # No se toca nada hasta que el usuario confirme.
                        confirmations.append({'key': key, 'modules': enable, 'dormant': dormant})
                        continue
                    modules = effective_modules(resolved)
                    for module in enable:
                        _set_module(result, module, 'configured', notices, modules.get(module, '?'))
            target = _container(result, scope, True)
            if key not in SCOPE_KEYS:
                target.pop(key, None)
            fields = target.setdefault('fields', {})
            if kind == 'set_field':
                fields[key] = float(value) if FIELDS[key].kind == 'value_attr' and not isinstance(value, int) else value
            elif kind == 'unset_field':
                fields.pop(key, None)
            else:  # inherit_field: en un derivado, quitar también lo heredado (null)
                fields[key] = None
            _cleanup(result, scope)
        elif kind == 'set_headshot':
            scope = parse_scope(op.get('scope'))
            patch = op.get('values') or {}
            if scope['type'] == 'defaults':
                target = result.setdefault('headshot', {})
            else:
                target = _container(result, scope, True).setdefault('headshot', {})
            for key, value in patch.items():
                if key == 'mode':
                    if value not in {None, 'off', 'normal', 'onetap', 'inherit', 'original'}:
                        raise ValidationFailed('Modo de cabeza inválido.', hint='off, normal, onetap o inherit.')
                    if scope['type'] == 'defaults':
                        result.setdefault('modules', {})['headshot'] = 'original' if value in {None, 'original', 'inherit'} else value
                        if value in {None, 'original', 'inherit'}:
                            target.pop('mode', None)
                            continue
                    if value in {None, 'inherit', 'original'}:
                        target.pop('mode', None)
                        continue
                elif key == 'distance' and isinstance(value, str):
                    if value.strip().lower() not in {'weapon_range', 'alcance'}:
                        raise ValidationFailed('headshot.distance debe ser numérico o weapon_range.',
                                               hint='weapon_range = la misma distancia que el alcance del arma.')
                    value = 'weapon_range'
                elif key in HEADSHOT_NUMBERS:
                    if value is not None and (isinstance(value, bool) or not isinstance(value, (int, float))):
                        raise ValidationFailed(f'headshot.{key} debe ser numérico.')
                elif key in HEADSHOT_BOOLS:
                    if value is not None and not isinstance(value, bool):
                        raise ValidationFailed(f'headshot.{key} debe ser verdadero o falso.')
                else:
                    raise ValidationFailed(f'Opción de cabeza desconocida: {key}.')
                if value is None:
                    target.pop(key, None)
                else:
                    target[key] = value
            if scope['type'] != 'defaults':
                _cleanup(result, scope)
                resolved = resolve(result)
                if effective_modules(resolved).get('headshot') == 'original' and target:
                    mode = (resolved.get('headshot') or {}).get('mode') or 'normal'
                    _set_module(result, 'headshot', mode, notices, 'original')
                    result.setdefault('headshot', {}).setdefault('mode', mode)
        elif kind in {'add_flag', 'remove_flag', 'clear_flag'}:
            scope = parse_scope(op.get('scope'))
            flag = str(op.get('flag', '')).strip()
            if not flag:
                raise ValidationFailed('Indica la flag.')
            holder = result if scope['type'] == 'defaults' else _container(result, scope, True)
            flags = holder.setdefault('weapon_flags', {'add': [], 'remove': [], 'create_if_missing': True})
            flags.setdefault('add', [])
            flags.setdefault('remove', [])
            flags['add'] = [f for f in flags['add'] if f.lower() != flag.lower()]
            flags['remove'] = [f for f in flags['remove'] if f.lower() != flag.lower()]
            if kind == 'add_flag':
                flags['add'].append(flag)
            elif kind == 'remove_flag':
                flags['remove'].append(flag)
            if not flags['add'] and not flags['remove']:
                holder.pop('weapon_flags', None)
            if scope['type'] != 'defaults':
                _cleanup(result, scope)
        elif kind == 'set_list':
            name = op.get('list')
            weapon = str(op.get('weapon', '')).upper()
            if name not in LISTS or not weapon:
                raise ValidationFailed('Lista o arma inválida.', hint=f'Listas: {", ".join(sorted(LISTS))}.')
            items = [w for w in result.get(name) or [] if str(w).upper() != weapon]
            if op.get('enabled', True):
                items.append(weapon)
            result[name] = items
        elif kind == 'set_multiplier':
            weapon = str(op.get('weapon', '')).upper()
            key = str(op.get('key', ''))
            value = op.get('value')
            if key not in FIELDS:
                raise ValidationFailed(f'Campo desconocido: {key}.')
            table = result.setdefault('weapon_field_multipliers', {})
            entry = table.setdefault(weapon, {})
            if value is None:
                entry.pop(key, None)
            elif isinstance(value, bool) or not isinstance(value, (int, float)) or value <= 0:
                raise ValidationFailed('El multiplicador debe ser mayor que 0.')
            else:
                entry[key] = float(value)
            if not entry:
                table.pop(weapon, None)
            if not table:
                result.pop('weapon_field_multipliers', None)
        elif kind == 'set_qbx_recoil':
            weapon = str(op.get('weapon', '')).upper()
            value = op.get('value', 'unset')
            recoils = result.setdefault('resources', {}).setdefault('qbx_recoils', {})
            if value == 'unset':
                recoils.pop(weapon, None)
            elif value is False:
                recoils[weapon] = False
            elif isinstance(value, bool) or not isinstance(value, (int, float)) or not 0 <= value <= 10:
                raise ValidationFailed('El recoil de qbx_recoils debe estar entre 0 y 10.')
            else:
                recoils[weapon] = float(value)
            if not recoils:
                result['resources'].pop('qbx_recoils', None)
            if not result.get('resources'):
                result.pop('resources', None)
        elif kind == 'set_module':
            module = op.get('module')
            value = op.get('value')
            if module not in MODULE_VALUES or value not in MODULE_VALUES[module]:
                raise ValidationFailed('Módulo o valor inválido.')
            previous = effective_modules(resolve(result)).get(module, '?')
            _set_module(result, module, value, notices, previous)
            if module == 'headshot':
                head = result.setdefault('headshot', {})
                if value == 'original':
                    head.pop('mode', None)
                else:
                    head['mode'] = value
        elif kind == 'set_meta':
            meta = result.setdefault('profile', {})
            key = op.get('key')
            value = op.get('value')
            if key in META_TEXT:
                meta[key] = str(value or '')[:2000]
            elif key in META_LISTS:
                if isinstance(value, str):
                    value = [v.strip() for v in value.split('\n' if key != 'tags' else ',') if v.strip()]
                meta[key] = [str(v)[:300] for v in (value or [])][:30]
            elif key == 'extends':
                meta['extends'] = value or None
            else:
                raise ValidationFailed(f'Metadato desconocido: {key}.')
        elif kind == 'set_section':
            key = op.get('key')
            from .schema import ENGINE_KEYS

            if key not in ENGINE_KEYS:
                raise ValidationFailed(f'Sección desconocida: {key}.')
            if op.get('value') is None:
                result.pop(key, None)
            else:
                result[key] = deepcopy(op['value'])
        else:
            raise ValidationFailed(f'Operación desconocida: {kind}.')
    return {'profile': result, 'notices': notices, 'confirmations': confirmations}


def summarize_changes(before: dict[str, Any], after: dict[str, Any]) -> list[dict[str, Any]]:
    """Diferencias ruta a ruta entre dos versiones del JSON (para confirmar antes de guardar)."""
    changes: list[dict[str, Any]] = []

    def walk(a: Any, b: Any, path: str) -> None:
        # Un objeto nuevo o eliminado se desglosa campo a campo.
        if a is _MISSING and isinstance(b, dict) and b:
            a = {}
        if b is _MISSING and isinstance(a, dict) and a:
            b = {}
        if isinstance(a, dict) and isinstance(b, dict):
            for key in sorted(set(a) | set(b)):
                if key == 'profile' and not path:
                    walk({k: v for k, v in (a.get(key) or {}).items() if k not in {'revision', 'updated_at', 'resolved_chain'}},
                         {k: v for k, v in (b.get(key) or {}).items() if k not in {'revision', 'updated_at', 'resolved_chain'}}, 'profile')
                    continue
                walk(a.get(key, _MISSING), b.get(key, _MISSING), f'{path}.{key}' if path else key)
            return
        if a != b and not (a == {} and b is _MISSING) and not (b == {} and a is _MISSING):
            changes.append({'path': path, 'before': None if a is _MISSING else a, 'after': None if b is _MISSING else b,
                            'kind': 'added' if a is _MISSING else 'removed' if b is _MISSING else 'changed'})

    walk(before, after, '')
    return changes


class _Missing:
    def __repr__(self) -> str:
        return '—'


_MISSING = _Missing()
