from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .fields import FIELDS
from .vanilla_weapons import get_catalog


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


def _field_multipliers(value: Any, context: str) -> dict[str, float]:
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise ProfileError(f'{context} debe ser un objeto JSON.')
    result: dict[str, float] = {}
    for key, raw in value.items():
        field_name = str(key)
        if field_name not in FIELDS:
            raise ProfileError(f'{context}.{field_name} no es un campo estándar válido.')
        if not isinstance(raw, (int, float)) or isinstance(raw, bool):
            raise ProfileError(f'{context}.{field_name} debe ser numérico.')
        multiplier = float(raw)
        if multiplier <= 0.0:
            raise ProfileError(f'{context}.{field_name} debe ser mayor que cero.')
        result[field_name] = multiplier
    return result


def _parse_restore(settings: Any, data: dict[str, Any]) -> None:
    restore = data.get('restore', {})
    if restore is None:
        return
    if not isinstance(restore, dict):
        raise ProfileError('restore debe ser un objeto JSON.')
    if 'from_backup' in restore and not isinstance(restore['from_backup'], bool):
        raise ProfileError('restore.from_backup debe ser booleano.')
    settings.restore_from_backup = bool(restore.get('from_backup', settings.restore_from_backup))
    suffix = restore.get('backup_suffix', settings.restore_backup_suffix)
    if not isinstance(suffix, str) or not suffix.strip():
        raise ProfileError('restore.backup_suffix debe ser texto no vacío.')
    if '/' in suffix or '\\' in suffix:
        raise ProfileError('restore.backup_suffix no puede contener rutas.')
    settings.restore_backup_suffix = suffix


def _parse_weapon_classification(settings: Any, data: dict[str, Any]) -> None:
    classification = data.get('weapon_classification', {})
    if classification is None:
        return
    if not isinstance(classification, dict):
        raise ProfileError('weapon_classification debe ser un objeto JSON.')

    catalog_id = classification.get('official_catalog')
    if catalog_id is not None:
        if not isinstance(catalog_id, str):
            raise ProfileError('weapon_classification.official_catalog debe ser texto.')
        try:
            settings.official_weapons = set(get_catalog(catalog_id))
        except KeyError as exc:
            raise ProfileError(str(exc)) from exc

    additions = classification.get('official_additions', [])
    removals = classification.get('official_removals', [])
    if not isinstance(additions, list) or not isinstance(removals, list):
        raise ProfileError('official_additions/official_removals deben ser listas.')
    settings.official_weapons.update(str(v).upper() for v in additions)
    settings.official_weapons.difference_update(str(v).upper() for v in removals)

    custom_enabled = classification.get('custom_when_not_official', False)
    if not isinstance(custom_enabled, bool):
        raise ProfileError('weapon_classification.custom_when_not_official debe ser booleano.')
    settings.classify_custom_weapons = custom_enabled

    custom = classification.get('custom', {})
    if custom is None:
        custom = {}
    if not isinstance(custom, dict):
        raise ProfileError('weapon_classification.custom debe ser un objeto JSON.')
    groups = custom.get('groups', [])
    if not isinstance(groups, list):
        raise ProfileError('weapon_classification.custom.groups debe ser una lista.')
    settings.custom_weapon_groups = {str(v).upper() for v in groups}
    settings.custom_field_multipliers = _field_multipliers(
        custom.get('field_multipliers', {}),
        'weapon_classification.custom.field_multipliers',
    )

    group_maps = custom.get('group_field_multipliers', {})
    if not isinstance(group_maps, dict):
        raise ProfileError('weapon_classification.custom.group_field_multipliers debe ser un objeto JSON.')
    settings.custom_group_field_multipliers = {
        str(group).upper(): _field_multipliers(
            values,
            f'weapon_classification.custom.group_field_multipliers.{str(group).upper()}',
        )
        for group, values in group_maps.items()
    }

    base_mode = custom.get('multiplier_base', 'weapon')
    if not isinstance(base_mode, str) or base_mode not in {'weapon', 'group_reference'}:
        raise ProfileError(
            'weapon_classification.custom.multiplier_base debe ser "weapon" o "group_reference".'
        )
    settings.custom_multiplier_base = base_mode



def _parse_baseline_repair(settings: Any, data: dict[str, Any]) -> None:
    raw = data.get('baseline_repair')
    if raw is None:
        return
    if not isinstance(raw, dict):
        raise ProfileError('baseline_repair debe ser un objeto JSON.')

    result = dict(settings.baseline_repair)
    bool_keys = (
        'enabled',
        'repair_zero_or_missing',
        'repair_invalid_network_modifiers',
        'repair_disabled_headshots',
        'repair_invalid_ranges',
    )
    for key in bool_keys:
        if key in raw:
            if not isinstance(raw[key], bool):
                raise ProfileError(f'baseline_repair.{key} debe ser booleano.')
            result[key] = raw[key]

    if 'minimum_valid_damage' in raw:
        value = raw['minimum_valid_damage']
        if not isinstance(value, (int, float)) or isinstance(value, bool) or float(value) < 0.0:
            raise ProfileError('baseline_repair.minimum_valid_damage debe ser numérico >= 0.')
        result['minimum_valid_damage'] = float(value)

    excluded = raw.get('excluded_weapons', result.get('excluded_weapons', []))
    if not isinstance(excluded, list):
        raise ProfileError('baseline_repair.excluded_weapons debe ser una lista.')
    result['excluded_weapons'] = [str(v).upper() for v in excluded]

    reference_roots = raw.get('reference_roots', result.get('reference_roots', []))
    if not isinstance(reference_roots, list):
        raise ProfileError('baseline_repair.reference_roots debe ser una lista.')
    result['reference_roots'] = [str(v) for v in reference_roots]

    for section in ('official_values', 'group_fallbacks'):
        value = raw.get(section, result.get(section, {}))
        if not isinstance(value, dict):
            raise ProfileError(f'baseline_repair.{section} debe ser un objeto JSON.')
        normalized: dict[str, dict[str, float]] = {}
        for name, fields in value.items():
            if not isinstance(fields, dict):
                raise ProfileError(f'baseline_repair.{section}.{name} debe ser un objeto JSON.')
            parsed: dict[str, float] = {}
            for field_name, field_value in fields.items():
                if str(field_name) not in FIELDS:
                    raise ProfileError(f'baseline_repair.{section}.{name}.{field_name} no es un campo estándar válido.')
                if not isinstance(field_value, (int, float)) or isinstance(field_value, bool):
                    raise ProfileError(f'baseline_repair.{section}.{name}.{field_name} debe ser numérico.')
                parsed[str(field_name)] = float(field_value)
            normalized[str(name).upper()] = parsed
        result[section] = normalized

    settings.baseline_repair = result

def _parse_family_rules(settings: Any, data: dict[str, Any]) -> None:
    rules = data.get('family_rules', [])
    if not isinstance(rules, list):
        raise ProfileError('family_rules debe ser una lista JSON.')
    parsed: list[dict[str, Any]] = []
    for index, raw in enumerate(rules):
        context = f'family_rules[{index}]'
        if not isinstance(raw, dict):
            raise ProfileError(f'{context} debe ser un objeto JSON.')
        contains = raw.get('contains', [])
        groups = raw.get('groups', [])
        if isinstance(contains, str):
            contains = [contains]
        if isinstance(groups, str):
            groups = [groups]
        if not isinstance(contains, list) or not contains:
            raise ProfileError(f'{context}.contains debe contener al menos un texto.')
        if not isinstance(groups, list):
            raise ProfileError(f'{context}.groups debe ser una lista.')
        fields = raw.get('fields', {})
        if not isinstance(fields, dict):
            raise ProfileError(f'{context}.fields debe ser un objeto JSON.')
        unknown = [str(key) for key in fields if str(key) not in FIELDS]
        if unknown:
            raise ProfileError(f'{context}.fields contiene campos desconocidos: {", ".join(unknown)}')
        for flag_name in ('official_only', 'custom_only'):
            if flag_name in raw and not isinstance(raw[flag_name], bool):
                raise ProfileError(f'{context}.{flag_name} debe ser booleano.')
        if raw.get('official_only') and raw.get('custom_only'):
            raise ProfileError(f'{context} no puede ser official_only y custom_only a la vez.')
        parsed.append({
            'name': str(raw.get('name') or f'rule_{index + 1}'),
            'contains': [str(v).upper() for v in contains if str(v).strip()],
            'groups': {str(v).upper() for v in groups},
            'official_only': bool(raw.get('official_only', False)),
            'custom_only': bool(raw.get('custom_only', False)),
            'field_multipliers': _field_multipliers(raw.get('field_multipliers', {}), f'{context}.field_multipliers'),
            'fields': {str(key): value for key, value in fields.items()},
        })
    settings.family_rules = parsed


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

    _parse_restore(settings, data)
    _parse_weapon_classification(settings, data)
    _parse_baseline_repair(settings, data)
    _parse_family_rules(settings, data)

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

    allowed_ignored = data.get('allow_ignored_weapons', [])
    if not isinstance(allowed_ignored, list):
        raise ProfileError('allow_ignored_weapons debe ser una lista JSON.')
    settings.ignore_weapons.difference_update(str(w).upper() for w in allowed_ignored)

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
