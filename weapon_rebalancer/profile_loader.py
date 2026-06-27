from __future__ import annotations

import json
from pathlib import Path
from typing import Any


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
            value = float(multiplier)
            settings.headshot.one_tap_player_modifier = value
            settings.headshot.one_tap_network_modifier = value
            settings.headshot.one_tap_ai_modifier = value

        distance = headshot.get('distance')
        if isinstance(distance, (int, float)):
            settings.headshot.one_tap_default_distance = float(distance)

        no_falloff = headshot.get('no_falloff')
        if isinstance(no_falloff, bool):
            settings.headshot.one_tap_force_no_falloff = no_falloff

        create_missing = headshot.get('create_missing_tags')
        if isinstance(create_missing, bool):
            settings.headshot.create_missing_tags = create_missing

    groups = data.get('groups', {})
    if not isinstance(groups, dict):
        raise ProfileError('groups debe ser un objeto JSON.')
    settings.external_group_profiles = {
        str(group).upper(): {str(k): v for k, v in values.items()}
        for group, values in groups.items()
        if isinstance(values, dict)
    }

    weapons = data.get('weapons', {})
    if isinstance(weapons, dict):
        for weapon, values in weapons.items():
            if isinstance(values, dict):
                settings.explicit_overrides[str(weapon).upper()] = dict(values)

    ignored = data.get('ignore_weapons', [])
    if isinstance(ignored, list):
        settings.ignore_weapons.update(str(w).upper() for w in ignored)
