from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .fields import FIELDS


class ProfileError(ValueError):
    pass


HEADSHOT_BOOL_MAP = {
    'no_falloff': 'one_tap_force_no_falloff',
    'sync_weapon_range': 'one_tap_sync_distance_with_weapon_range',
    'sync_lock_on_range': 'one_tap_sync_lock_on_range',
    'create_missing_tags': 'create_missing_tags',
    'bypass_helmets': 'one_tap_through_helmets',
    'force_penetration': 'one_tap_force_penetration',
    'create_missing_armour_tag': 'create_missing_lightly_armoured_tag',
    'create_missing_penetration_tag': 'create_missing_penetration_tag',
    'add_ignore_helmets_flag': 'one_tap_add_ignore_helmets_flag',
    'add_armour_penetrating_flag': 'one_tap_add_armour_penetrating_flag',
    'create_missing_weapon_flags_tag': 'create_missing_weapon_flags_tag',
    'auto_minimum_base_damage': 'one_tap_auto_minimum_base_damage',
    'repair_zero_network_modifier': 'one_tap_repair_zero_network_modifier',
    'create_missing_network_player_modifier_tag': 'create_missing_network_player_modifier_tag',
    'remove_nonlethal_flags': 'one_tap_remove_nonlethal_flags',
}

HEADSHOT_NUMBER_MAP = {
    'multiplier': (
        'one_tap_player_modifier',
        'one_tap_network_modifier',
        'one_tap_ai_modifier',
    ),
    'player_multiplier': ('one_tap_player_modifier',),
    'network_multiplier': ('one_tap_network_modifier',),
    'ai_multiplier': ('one_tap_ai_modifier',),
    'distance': ('one_tap_default_distance',),
    'helmet_multiplier': ('one_tap_helmet_damage_modifier',),
    'penetration': ('one_tap_penetration',),
    'target_effective_health': ('one_tap_target_effective_health',),
    'safety_margin': ('one_tap_safety_margin',),
    'minimum_base_damage': ('one_tap_minimum_base_damage',),
    'network_player_modifier_fallback': ('one_tap_network_player_modifier_fallback',),
}

HEADSHOT_SCOPE_KEYS = {
    'mode', 'enabled', 'one_tap',
    *HEADSHOT_BOOL_MAP.keys(),
    *HEADSHOT_NUMBER_MAP.keys(),
    'blocking_flags',
    'disabled_weapons', 'allowed_weapons', 'one_tap_weapons', 'no_one_tap_weapons',
}


def load_profile(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding='utf-8'))
    except FileNotFoundError as exc:
        raise ProfileError(f'No existe el perfil: {path}') from exc
    except json.JSONDecodeError as exc:
        raise ProfileError(f'JSON inválido en {path}: línea {exc.lineno}, columna {exc.colno}') from exc

    if not isinstance(data, dict):
        raise ProfileError('El perfil debe ser un objeto JSON.')
    return data


def _normalize_flags(value: Any, context: str) -> dict[str, list[str] | bool]:
    if value is None:
        return {'add': [], 'remove': [], 'create_if_missing': False}
    if not isinstance(value, dict):
        raise ProfileError(f'{context}.weapon_flags debe ser un objeto JSON.')
    add = value.get('add', [])
    remove = value.get('remove', [])
    if not isinstance(add, list) or not isinstance(remove, list):
        raise ProfileError(f'{context}.weapon_flags.add/remove deben ser listas.')
    return {
        'add': [str(v) for v in add],
        'remove': [str(v) for v in remove],
        'create_if_missing': bool(value.get('create_if_missing', False)),
    }


def _normalize_headshot_scope(value: Any, context: str) -> dict[str, Any]:
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise ProfileError(f'{context}.headshot debe ser un objeto JSON.')

    result: dict[str, Any] = {}
    for key, item in value.items():
        if key.startswith('_'):
            continue
        if key not in HEADSHOT_SCOPE_KEYS:
            raise ProfileError(f'{context}.headshot.{key} no es una opción válida.')
        if key in {'disabled_weapons', 'allowed_weapons', 'one_tap_weapons', 'no_one_tap_weapons', 'blocking_flags'}:
            if not isinstance(item, list):
                raise ProfileError(f'{context}.headshot.{key} debe ser una lista.')
            result[key] = [str(v) for v in item]
        else:
            result[key] = item
    return result


def _split_scope(
    value: Any,
    context: str,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, list[str] | bool], dict[str, Any]]:
    if value is None:
        return {}, {}, _normalize_flags(None, context), {}
    if not isinstance(value, dict):
        raise ProfileError(f'{context} debe ser un objeto JSON.')

    fields: dict[str, Any] = {}
    nested_fields = value.get('fields')
    if nested_fields is not None:
        if not isinstance(nested_fields, dict):
            raise ProfileError(f'{context}.fields debe ser un objeto JSON.')
        fields.update({str(k): v for k, v in nested_fields.items() if v is not None})

    # Retrocompatibilidad: perfiles antiguos colocan los campos directamente.
    for key, item in value.items():
        if key in {'fields', 'meta', 'weapon_flags', 'headshot', '_comment', '_documentation'}:
            continue
        fields[str(key)] = item

    meta = value.get('meta', {})
    if meta is None:
        meta = {}
    if not isinstance(meta, dict):
        raise ProfileError(f'{context}.meta debe ser un objeto JSON.')

    flags = _normalize_flags(value.get('weapon_flags'), context)
    headshot = _normalize_headshot_scope(value.get('headshot'), context)
    return fields, {str(k): v for k, v in meta.items()}, flags, headshot


def _merge_flag_ops(base: dict[str, list[str] | bool], extra: dict[str, list[str] | bool]) -> dict[str, list[str] | bool]:
    return {
        'add': list(dict.fromkeys([*base.get('add', []), *extra.get('add', [])])),
        'remove': list(dict.fromkeys([*base.get('remove', []), *extra.get('remove', [])])),
        'create_if_missing': bool(base.get('create_if_missing', False) or extra.get('create_if_missing', False)),
    }


def _apply_global_headshot(settings: Any, headshot: dict[str, Any]) -> None:
    mode = headshot.get('mode')
    if mode is not None and mode not in {'off', 'normal', 'onetap'}:
        raise ProfileError('headshot.mode debe ser off, normal u onetap.')
    if mode == 'off':
        settings.headshot.enabled = False
        settings.headshot.one_tap = False
    elif mode == 'normal':
        settings.headshot.enabled = True
        settings.headshot.one_tap = False
    elif mode == 'onetap':
        settings.headshot.enabled = True
        settings.headshot.one_tap = True

    if isinstance(headshot.get('enabled'), bool):
        settings.headshot.enabled = headshot['enabled']
    if isinstance(headshot.get('one_tap'), bool):
        settings.headshot.one_tap = headshot['one_tap']

    for json_key, attr in HEADSHOT_BOOL_MAP.items():
        value = headshot.get(json_key)
        if isinstance(value, bool):
            setattr(settings.headshot, attr, value)

    for json_key, attrs in HEADSHOT_NUMBER_MAP.items():
        value = headshot.get(json_key)
        if isinstance(value, (int, float)):
            for attr in attrs:
                setattr(settings.headshot, attr, float(value))

    blocking = headshot.get('blocking_flags')
    if isinstance(blocking, list):
        settings.headshot.one_tap_blocking_flags = tuple(str(v) for v in blocking)

    set_map = {
        'disabled_weapons': 'disabled_weapons',
        'allowed_weapons': 'allowed_weapons',
        'one_tap_weapons': 'one_tap_weapons',
        'no_one_tap_weapons': 'no_one_tap_weapons',
    }
    for json_key, attr in set_map.items():
        value = headshot.get(json_key)
        if isinstance(value, list):
            setattr(settings.headshot, attr, {str(v).upper() for v in value})


def apply_external_profile(settings: Any, data: dict[str, Any]) -> None:
    modules = data.get('modules', {})
    if not isinstance(modules, dict):
        raise ProfileError('modules debe ser un objeto JSON.')

    mapping = {
        'recoil': 'recoil_profile',
        'accuracy': 'accuracy_profile',
        'damage': 'damage_profile',
        'armour': 'armour_profile',
        'range': 'range_profile',
        'fire_rate': 'fire_rate_profile',
        'reload': 'reload_profile',
        'headshot': 'headshot_profile',
    }
    allowed_modules = {
        'recoil': {'original', 'configured', 'none', 'low', 'normal', 'high'},
        'accuracy': {'original', 'configured', 'laser', 'high', 'normal', 'low'},
        'damage': {'original', 'configured', 'none', 'head_only', 'low', 'normal', 'high', 'lethal'},
        'armour': {'original', 'configured', 'none', 'normal', 'piercing', 'max'},
        'range': {'original', 'configured', 'short', 'normal', 'long', 'very_long'},
        'fire_rate': {'original', 'configured', 'slow', 'normal', 'fast', 'very_fast'},
        'reload': {'original', 'configured', 'slow', 'normal', 'fast', 'very_fast'},
        'headshot': {'original', 'off', 'normal', 'onetap'},
    }
    for key, attr in mapping.items():
        value = modules.get(key)
        if isinstance(value, str):
            if value not in allowed_modules[key]:
                raise ProfileError(f'modules.{key}={value!r} no es válido.')
            setattr(settings, attr, value)

    base_preset = data.get('base_preset')
    if isinstance(base_preset, str):
        settings.active_preset = base_preset

    headshot = data.get('headshot', {})
    if headshot is not None:
        if not isinstance(headshot, dict):
            raise ProfileError('headshot debe ser un objeto JSON.')
        _apply_global_headshot(settings, _normalize_headshot_scope(headshot, 'perfil'))

    default_fields, default_meta, default_flags, default_headshot = _split_scope(data.get('defaults', {}), 'defaults')
    if default_fields:
        settings.external_group_profiles.setdefault('__GLOBAL__', {}).update(default_fields)
    settings.global_meta_overrides.update(default_meta)
    settings.global_flag_ops = _merge_flag_ops(settings.global_flag_ops, default_flags)
    if default_headshot:
        # defaults.headshot funciona como una segunda capa global.
        _apply_global_headshot(settings, default_headshot)

    top_meta = data.get('meta', {})
    if top_meta is not None:
        if not isinstance(top_meta, dict):
            raise ProfileError('meta debe ser un objeto JSON.')
        settings.global_meta_overrides.update({str(k): v for k, v in top_meta.items()})
    settings.global_flag_ops = _merge_flag_ops(settings.global_flag_ops, _normalize_flags(data.get('weapon_flags'), 'perfil'))

    groups = data.get('groups', {})
    if not isinstance(groups, dict):
        raise ProfileError('groups debe ser un objeto JSON.')
    for group, values in groups.items():
        group_name = str(group).upper()
        fields, meta, flags, scoped_headshot = _split_scope(values, f'groups.{group_name}')
        settings.external_group_profiles[group_name] = fields
        if meta:
            settings.group_meta_overrides[group_name] = meta
        if flags.get('add') or flags.get('remove') or flags.get('create_if_missing'):
            settings.group_flag_ops[group_name] = flags
        if scoped_headshot:
            settings.group_headshot_overrides[group_name] = scoped_headshot

    weapons = data.get('weapons', {})
    if not isinstance(weapons, dict):
        raise ProfileError('weapons debe ser un objeto JSON.')
    for weapon, values in weapons.items():
        weapon_name = str(weapon).upper()
        fields, meta, flags, scoped_headshot = _split_scope(values, f'weapons.{weapon_name}')
        settings.explicit_overrides[weapon_name] = {
            **settings.explicit_overrides.get(weapon_name, {}),
            **fields,
        }
        if meta:
            settings.weapon_meta_overrides[weapon_name] = meta
        if flags.get('add') or flags.get('remove') or flags.get('create_if_missing'):
            settings.weapon_flag_ops[weapon_name] = flags
        if scoped_headshot:
            settings.weapon_headshot_overrides[weapon_name] = scoped_headshot

    harmless = data.get('harmless_weapons', [])
    if not isinstance(harmless, list):
        raise ProfileError('harmless_weapons debe ser una lista JSON.')
    settings.harmless_weapons.update(str(w).upper() for w in harmless)

    allow_damage = data.get('allow_damage_weapons', [])
    if not isinstance(allow_damage, list):
        raise ProfileError('allow_damage_weapons debe ser una lista JSON.')
    settings.harmless_weapons.difference_update(str(w).upper() for w in allow_damage)

    ignored = data.get('ignore_weapons', [])
    if not isinstance(ignored, list):
        raise ProfileError('ignore_weapons debe ser una lista JSON.')
    settings.ignore_weapons.update(str(w).upper() for w in ignored)

    validation = data.get('validation', {})
    if validation is None:
        validation = {}
    if not isinstance(validation, dict):
        raise ProfileError('validation debe ser un objeto JSON.')
    settings.validation_options.update(validation)

    strict = bool(settings.validation_options.get('strict_unknown_fields', False))
    if strict:
        unknown: list[str] = []
        scopes = [('defaults', default_fields)]
        scopes.extend((f'groups.{g}', v) for g, v in settings.external_group_profiles.items() if g != '__GLOBAL__')
        scopes.extend((f'weapons.{w}', v) for w, v in settings.explicit_overrides.items())
        for scope, values in scopes:
            for key in values:
                if key not in FIELDS:
                    unknown.append(f'{scope}.{key}')
        if unknown:
            raise ProfileError(
                'Campos estándar desconocidos (usa `meta` para tags XML exactos): '
                + ', '.join(unknown[:20])
            )
