from __future__ import annotations

from copy import deepcopy
from typing import Any

from .fields import FIELDS

GROUPS = ('GROUP_PISTOL', 'GROUP_SMG', 'GROUP_RIFLE', 'GROUP_MG', 'GROUP_SHOTGUN', 'GROUP_SNIPER')

FIELD_SECTIONS: dict[str, set[str]] = {
    section: {key for key, field in FIELDS.items() if field.section == section}
    for section in ('damage', 'range', 'recoil', 'accuracy', 'fire_rate', 'reload', 'headshot')
}


RECOIL_PROFILES: dict[str, dict[str, float]] = {
    'none': {'recoil_accuracy_max': 0.01, 'recoil_error_time': 0.01, 'recoil_recovery_rate': 10.0, 'recoil_shake_amplitude': 0.0},
    'low': {'recoil_accuracy_max': 0.28, 'recoil_error_time': 0.05, 'recoil_recovery_rate': 1.65, 'recoil_shake_amplitude': 0.10},
    'normal': {'recoil_accuracy_max': 0.55, 'recoil_error_time': 0.08, 'recoil_recovery_rate': 1.00, 'recoil_shake_amplitude': 0.22},
    'high': {'recoil_accuracy_max': 1.10, 'recoil_error_time': 0.14, 'recoil_recovery_rate': 0.58, 'recoil_shake_amplitude': 0.48},
}

ACCURACY_PROFILES: dict[str, dict[str, float]] = {
    'laser': {'accuracy_spread': 0.05, 'run_and_gun_accuracy_modifier': 0.10, 'accurate_mode_accuracy_modifier': 0.05},
    'high': {'accuracy_spread': 0.42, 'run_and_gun_accuracy_modifier': 0.62, 'accurate_mode_accuracy_modifier': 0.24},
    'normal': {'accuracy_spread': 0.90, 'run_and_gun_accuracy_modifier': 1.22, 'accurate_mode_accuracy_modifier': 0.63},
    'low': {'accuracy_spread': 1.55, 'run_and_gun_accuracy_modifier': 2.20, 'accurate_mode_accuracy_modifier': 1.05},
}

# Multipliers over the damage profile selected with --preset.
DAMAGE_MULTIPLIERS = {'low': 0.72, 'normal': 1.0, 'high': 1.20, 'lethal': 1.45}
ARMOUR_PROFILES = {'none': 0.0, 'normal': 1.0, 'piercing': 1.5, 'max': 2.0}
RANGE_MULTIPLIERS = {'short': 0.65, 'normal': 1.0, 'long': 1.35, 'very_long': 1.75}
FIRE_RATE_MULTIPLIERS = {'slow': 1.25, 'normal': 1.0, 'fast': 0.82, 'very_fast': 0.68}
RELOAD_MULTIPLIERS = {'slow': 1.25, 'normal': 1.0, 'fast': 0.78, 'very_fast': 0.58}


def _scaled(profile: dict[str, Any], keys: tuple[str, ...], multiplier: float) -> None:
    for key in keys:
        value = profile.get(key)
        if isinstance(value, (int, float)):
            profile[key] = float(value) * multiplier


def apply_modular_profiles(profile: dict[str, Any], settings: Any) -> dict[str, Any]:
    """Applies independent overlays and removes sections configured as original.

    `original` means that no XML tag from that section is touched.
    `configured` keeps the values authored in the selected JSON/group profile.
    """
    result = deepcopy(profile)

    section_modes = {
        'damage': settings.damage_profile,
        'range': settings.range_profile,
        'armour': settings.armour_profile,
        'recoil': settings.recoil_profile,
        'accuracy': settings.accuracy_profile,
        'fire_rate': settings.fire_rate_profile,
        'reload': settings.reload_profile,
        'headshot': settings.headshot_profile,
    }

    # Remove fields belonging to sections that must remain exactly as authored.
    for section, mode in section_modes.items():
        if section == 'armour':
            if mode == 'original':
                result.pop('lightly_armoured', None)
            continue
        if mode == 'original':
            for key in FIELD_SECTIONS[section]:
                result.pop(key, None)

    if settings.damage_profile == 'none':
        result['damage'] = 0.0
        result['hit_limbs'] = 0.0
        result['network_hit_limbs'] = 0.0
        result['vehicle_damage_modifier'] = 0.0
    elif settings.damage_profile == 'head_only':
        # META puro no puede tener 0 cuerpo y headshot > 0 porque la cabeza multiplica el daño base.
        # 0.2 deja el cuerpo prácticamente sin daño y, con headshot 1500, produce 300 de daño en cabeza.
        result['damage'] = 0.2
        result['hit_limbs'] = 0.0
        result['network_hit_limbs'] = 0.0
        result['vehicle_damage_modifier'] = 0.0
    elif settings.damage_profile not in ('original', 'normal', 'configured'):
        _scaled(result, ('damage',), DAMAGE_MULTIPLIERS[settings.damage_profile])

    if settings.armour_profile not in ('original', 'configured'):
        result['lightly_armoured'] = ARMOUR_PROFILES[settings.armour_profile]

    if settings.range_profile not in ('original', 'normal', 'configured'):
        multiplier = RANGE_MULTIPLIERS[settings.range_profile]
        _scaled(result, ('weapon_range', 'falloff_min', 'falloff_max', 'max_headshot_player', 'max_headshot_ai', 'lock_on_range'), multiplier)

    if settings.recoil_profile not in ('original', 'configured'):
        result.update(RECOIL_PROFILES[settings.recoil_profile])

    if settings.accuracy_profile not in ('original', 'configured'):
        accuracy = deepcopy(ACCURACY_PROFILES[settings.accuracy_profile])
        # Shotguns must retain pellet spread; never turn them into slug lasers by accident.
        if settings.current_group == 'GROUP_SHOTGUN':
            accuracy['accuracy_spread'] = max(accuracy['accuracy_spread'], 1.10)
        result.update(accuracy)

    if settings.fire_rate_profile not in ('original', 'normal', 'configured'):
        _scaled(result, ('time_between_shots',), FIRE_RATE_MULTIPLIERS[settings.fire_rate_profile])
        inverse = 1.0 / FIRE_RATE_MULTIPLIERS[settings.fire_rate_profile]
        if 'anim_fire_rate_modifier' in result:
            result['anim_fire_rate_modifier'] = float(result['anim_fire_rate_modifier']) * inverse

    if settings.reload_profile not in ('original', 'normal', 'configured'):
        multiplier = RELOAD_MULTIPLIERS[settings.reload_profile]
        _scaled(result, ('reload_time_mp', 'reload_time_sp'), multiplier)
        if 'anim_reload_rate' in result:
            result['anim_reload_rate'] = float(result['anim_reload_rate']) / multiplier

    return result
