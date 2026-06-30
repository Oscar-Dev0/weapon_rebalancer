from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .fields import FIELDS


class ProfileError(ValueError):
    pass


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


def _split_scope(value: Any, context: str) -> tuple[dict[str, Any], dict[str, Any], dict[str, list[str] | bool]]:
    if value is None:
        return {}, {}, _normalize_flags(None, context)
    if not isinstance(value, dict):
        raise ProfileError(f'{context} debe ser un objeto JSON.')

    fields: dict[str, Any] = {}
    nested_fields = value.get('fields')
    if nested_fields is not None:
        if not isinstance(nested_fields, dict):
            raise ProfileError(f'{context}.fields debe ser un objeto JSON.')
        fields.update({str(k): v for k, v in nested_fields.items() if v is not None})

    # Retrocompatibilidad: los perfiles anteriores tienen los campos directamente.
    for key, item in value.items():
        if key in {'fields', 'meta', 'weapon_flags', '_comment', '_documentation'}:
            continue
        fields[str(key)] = item

    meta = value.get('meta', {})
    if meta is None:
        meta = {}
    if not isinstance(meta, dict):
        raise ProfileError(f'{context}.meta debe ser un objeto JSON.')

    flags = _normalize_flags(value.get('weapon_flags'), context)
    return fields, {str(k): v for k, v in meta.items()}, flags


def _merge_flag_ops(base: dict[str, list[str] | bool], extra: dict[str, list[str] | bool]) -> dict[str, list[str] | bool]:
    return {
        'add': list(dict.fromkeys([*base.get('add', []), *extra.get('add', [])])),
        'remove': list(dict.fromkeys([*base.get('remove', []), *extra.get('remove', [])])),
        'create_if_missing': bool(base.get('create_if_missing', False) or extra.get('create_if_missing', False)),
    }


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
    for key, attr in mapping.items():
        value = modules.get(key)
        if isinstance(value, str):
            setattr(settings, attr, value)

    base_preset = data.get('base_preset')
    if isinstance(base_preset, str):
        settings.active_preset = base_preset

    headshot = data.get('headshot', {})
    if isinstance(headshot, dict):
        mode = headshot.get('mode')
        if mode == 'off':
            settings.headshot.enabled = False
            settings.headshot.one_tap = False
        elif mode == 'normal':
            settings.headshot.enabled = True
            settings.headshot.one_tap = False
        elif mode == 'onetap':
            settings.headshot.enabled = True
            settings.headshot.one_tap = True

        multiplier = headshot.get('multiplier')
        if isinstance(multiplier, (int, float)):
            number = float(multiplier)
            settings.headshot.one_tap_player_modifier = number
            settings.headshot.one_tap_network_modifier = number
            settings.headshot.one_tap_ai_modifier = number

        distance = headshot.get('distance')
        if isinstance(distance, (int, float)):
            settings.headshot.one_tap_default_distance = float(distance)

        bool_map = {
            'no_falloff': 'one_tap_force_no_falloff',
            'create_missing_tags': 'create_missing_tags',
            'bypass_helmets': 'one_tap_through_helmets',
            'force_penetration': 'one_tap_force_penetration',
            'create_missing_armour_tag': 'create_missing_lightly_armoured_tag',
            'create_missing_penetration_tag': 'create_missing_penetration_tag',
            'add_ignore_helmets_flag': 'one_tap_add_ignore_helmets_flag',
            'add_armour_penetrating_flag': 'one_tap_add_armour_penetrating_flag',
            'create_missing_weapon_flags_tag': 'create_missing_weapon_flags_tag',
        }
        for json_key, attr in bool_map.items():
            value = headshot.get(json_key)
            if isinstance(value, bool):
                setattr(settings.headshot, attr, value)

        helmet_multiplier = headshot.get('helmet_multiplier')
        if isinstance(helmet_multiplier, (int, float)):
            settings.headshot.one_tap_helmet_damage_modifier = float(helmet_multiplier)

        penetration = headshot.get('penetration')
        if isinstance(penetration, (int, float)):
            settings.headshot.one_tap_penetration = float(penetration)

    default_fields, default_meta, default_flags = _split_scope(data.get('defaults', {}), 'defaults')
    if default_fields:
        # Defaults externos funcionan como perfil base global y se mezclan antes de grupos.
        settings.external_group_profiles.setdefault('__GLOBAL__', {}).update(default_fields)
    settings.global_meta_overrides.update(default_meta)
    settings.global_flag_ops = _merge_flag_ops(settings.global_flag_ops, default_flags)

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
        fields, meta, flags = _split_scope(values, f'groups.{group_name}')
        settings.external_group_profiles[group_name] = fields
        if meta:
            settings.group_meta_overrides[group_name] = meta
        if flags.get('add') or flags.get('remove') or flags.get('create_if_missing'):
            settings.group_flag_ops[group_name] = flags

    weapons = data.get('weapons', {})
    if not isinstance(weapons, dict):
        raise ProfileError('weapons debe ser un objeto JSON.')
    for weapon, values in weapons.items():
        weapon_name = str(weapon).upper()
        fields, meta, flags = _split_scope(values, f'weapons.{weapon_name}')
        settings.explicit_overrides[weapon_name] = {
            **settings.explicit_overrides.get(weapon_name, {}),
            **fields,
        }
        if meta:
            settings.weapon_meta_overrides[weapon_name] = meta
        if flags.get('add') or flags.get('remove') or flags.get('create_if_missing'):
            settings.weapon_flag_ops[weapon_name] = flags

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

    # Validación amable: los campos estándar deben existir en el catálogo. Los tags
    # no catalogados siguen siendo válidos dentro de `meta`.
    strict = bool(data.get('validation', {}).get('strict_unknown_fields', False)) if isinstance(data.get('validation'), dict) else False
    if strict:
        unknown: list[str] = []
        for scope, values in [('defaults', default_fields), *[(f'groups.{g}', v) for g, v in settings.external_group_profiles.items() if g != '__GLOBAL__'], *[(f'weapons.{w}', v) for w, v in settings.explicit_overrides.items()]]:
            for key in values:
                if key not in FIELDS:
                    unknown.append(f'{scope}.{key}')
        if unknown:
            raise ProfileError('Campos estándar desconocidos (usa `meta` para tags XML exactos): ' + ', '.join(unknown[:20]))
