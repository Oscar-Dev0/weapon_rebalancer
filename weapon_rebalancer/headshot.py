from __future__ import annotations

from copy import deepcopy
from typing import Any

from .meta_utils import read_field_value, read_weapon_flags


def _as_float(value: Any, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _as_bool(value: Any, default: bool) -> bool:
    return value if isinstance(value, bool) else default


def _apply_overlay(policy: dict[str, Any], overlay: Any) -> None:
    if not isinstance(overlay, dict):
        return

    mode = overlay.get('mode')
    if mode in {'off', 'normal', 'onetap'}:
        policy['mode'] = mode
    if isinstance(overlay.get('enabled'), bool):
        if overlay['enabled'] is False:
            policy['mode'] = 'off'
        elif policy.get('mode') == 'off':
            policy['mode'] = 'normal'
    if isinstance(overlay.get('one_tap'), bool):
        policy['mode'] = 'onetap' if overlay['one_tap'] else ('normal' if policy.get('mode') != 'off' else 'off')

    aliases = {
        'multiplier': ('player_multiplier', 'network_multiplier', 'ai_multiplier'),
        'player_multiplier': ('player_multiplier',),
        'network_multiplier': ('network_multiplier',),
        'ai_multiplier': ('ai_multiplier',),
        'distance': ('distance',),
        'helmet_multiplier': ('helmet_multiplier',),
        'penetration': ('penetration',),
        'target_effective_health': ('target_effective_health',),
        'safety_margin': ('safety_margin',),
        'minimum_base_damage': ('minimum_base_damage',),
        'network_player_modifier_fallback': ('network_player_modifier_fallback',),
    }
    for source, destinations in aliases.items():
        value = overlay.get(source)
        if isinstance(value, (int, float)):
            for destination in destinations:
                policy[destination] = float(value)

    boolean_keys = (
        'no_falloff', 'sync_weapon_range', 'sync_lock_on_range',
        'create_missing_tags', 'bypass_helmets', 'force_penetration',
        'create_missing_armour_tag', 'create_missing_penetration_tag',
        'add_ignore_helmets_flag', 'add_armour_penetrating_flag',
        'create_missing_weapon_flags_tag', 'auto_minimum_base_damage',
        'repair_zero_network_modifier', 'create_missing_network_player_modifier_tag',
        'remove_nonlethal_flags',
    )
    for key in boolean_keys:
        if isinstance(overlay.get(key), bool):
            policy[key] = overlay[key]

    if isinstance(overlay.get('blocking_flags'), list):
        policy['blocking_flags'] = [str(v) for v in overlay['blocking_flags']]


def resolve_headshot_policy(settings: Any, weapon: str, group: str, block: Any | None = None) -> dict[str, Any]:
    h = settings.headshot
    mode = 'off'
    if h.enabled:
        mode = 'onetap' if h.one_tap else 'normal'

    policy: dict[str, Any] = {
        'mode': mode,
        'player_multiplier': float(h.one_tap_player_modifier if h.one_tap else h.enabled_player_modifier),
        'network_multiplier': float(h.one_tap_network_modifier if h.one_tap else h.enabled_network_modifier),
        'ai_multiplier': float(h.one_tap_ai_modifier if h.one_tap else h.enabled_ai_modifier),
        'distance': h.one_tap_default_distance if h.one_tap else h.enabled_default_max_distance,
        'no_falloff': bool(h.one_tap_force_no_falloff),
        'sync_weapon_range': bool(h.one_tap_sync_distance_with_weapon_range),
        'sync_lock_on_range': bool(h.one_tap_sync_lock_on_range),
        'create_missing_tags': bool(h.create_missing_tags),
        'bypass_helmets': bool(h.one_tap_through_helmets),
        'helmet_multiplier': float(h.one_tap_helmet_damage_modifier),
        'force_penetration': bool(h.one_tap_force_penetration),
        'penetration': float(h.one_tap_penetration),
        'create_missing_armour_tag': bool(h.create_missing_lightly_armoured_tag),
        'create_missing_penetration_tag': bool(h.create_missing_penetration_tag),
        'add_ignore_helmets_flag': bool(h.one_tap_add_ignore_helmets_flag),
        'add_armour_penetrating_flag': bool(h.one_tap_add_armour_penetrating_flag),
        'create_missing_weapon_flags_tag': bool(h.create_missing_weapon_flags_tag),
        'auto_minimum_base_damage': bool(h.one_tap_auto_minimum_base_damage),
        'target_effective_health': float(h.one_tap_target_effective_health),
        'safety_margin': float(h.one_tap_safety_margin),
        'minimum_base_damage': float(h.one_tap_minimum_base_damage),
        'repair_zero_network_modifier': bool(h.one_tap_repair_zero_network_modifier),
        'network_player_modifier_fallback': float(h.one_tap_network_player_modifier_fallback),
        'create_missing_network_player_modifier_tag': bool(h.create_missing_network_player_modifier_tag),
        'remove_nonlethal_flags': bool(h.one_tap_remove_nonlethal_flags),
        'blocking_flags': list(h.one_tap_blocking_flags),
    }

    weapon = weapon.upper()
    group = group.upper()

    # Reglas legacy por listas.
    if not h.enabled and weapon not in {str(v).upper() for v in h.allowed_weapons}:
        policy['mode'] = 'off'
    if weapon in {str(v).upper() for v in h.disabled_weapons}:
        policy['mode'] = 'off'
    if weapon in {str(v).upper() for v in h.allowed_weapons} and policy['mode'] == 'off':
        policy['mode'] = 'normal'
    if weapon in {str(v).upper() for v in h.one_tap_weapons}:
        policy['mode'] = 'onetap'
    if weapon in {str(v).upper() for v in h.no_one_tap_weapons} and policy['mode'] == 'onetap':
        policy['mode'] = 'normal'

    _apply_overlay(policy, settings.group_headshot_overrides.get(group))
    _apply_overlay(policy, settings.weapon_headshot_overrides.get(weapon))

    if block is not None:
        for package in block.config_stack:
            data = package.data
            _apply_overlay(policy, data.get('headshot'))
            groups = data.get('groups')
            if isinstance(groups, dict) and isinstance(groups.get(group), dict):
                _apply_overlay(policy, groups[group].get('headshot'))
            weapons = data.get('weapons')
            if isinstance(weapons, dict) and isinstance(weapons.get(weapon), dict):
                _apply_overlay(policy, weapons[weapon].get('headshot'))

            head = data.get('headshot')
            if isinstance(head, dict):
                if weapon in {str(v).upper() for v in head.get('disabled_weapons', [])}:
                    policy['mode'] = 'off'
                if weapon in {str(v).upper() for v in head.get('allowed_weapons', [])} and policy['mode'] == 'off':
                    policy['mode'] = 'normal'
                if weapon in {str(v).upper() for v in head.get('one_tap_weapons', [])}:
                    policy['mode'] = 'onetap'
                if weapon in {str(v).upper() for v in head.get('no_one_tap_weapons', [])} and policy['mode'] == 'onetap':
                    policy['mode'] = 'normal'

    if h.disable_one_tap_for_melee and group == 'GROUP_MELEE' and policy['mode'] == 'onetap':
        policy['mode'] = 'off'

    return policy


def resolve_distance(profile: dict[str, Any], block_text: str, configured: Any) -> float:
    if isinstance(configured, (int, float)) and float(configured) > 0.0:
        return float(configured)
    for key in ('weapon_range', 'falloff_max', 'max_headshot_player'):
        value = profile.get(key)
        if not isinstance(value, (int, float)):
            value = read_field_value(block_text, key, 0.0)
        number = _as_float(value, 0.0)
        if number > 0.0:
            return number
    return 100.0


def apply_policy(
    profile: dict[str, Any],
    block_text: str,
    policy: dict[str, Any],
    *,
    disable_ai_headshot: bool = True,
    disabled_max_distance: float = 0.0,
) -> tuple[dict[str, Any], dict[str, Any]]:
    result = deepcopy(profile)
    mode = policy.get('mode', 'off')
    metrics: dict[str, Any] = {'mode': mode}

    if mode == 'off':
        result.update({
            'headshot_player': 0.0,
            'network_headshot': 0.0,
            'min_headshot_player': 0.0,
            'max_headshot_player': disabled_max_distance,
        })
        if disable_ai_headshot:
            result.update({
                'headshot_ai': 0.0,
                'min_headshot_ai': 0.0,
                'max_headshot_ai': disabled_max_distance,
            })
        return result, metrics

    distance = resolve_distance(result, block_text, policy.get('distance'))
    metrics['distance'] = distance

    if mode == 'onetap':
        if _as_bool(policy.get('sync_weapon_range'), True):
            current = _as_float(result.get('weapon_range', read_field_value(block_text, 'weapon_range', distance)), distance)
            result['weapon_range'] = max(current, distance)
        if _as_bool(policy.get('no_falloff'), True):
            result['falloff_min'] = max(0.0, distance - 0.001)
            result['falloff_max'] = distance
            result['falloff_modifier'] = 1.0
        if _as_bool(policy.get('sync_lock_on_range'), False):
            result['lock_on_range'] = distance

        if _as_bool(policy.get('bypass_helmets'), True):
            current_armour = _as_float(result.get('lightly_armoured', read_field_value(block_text, 'lightly_armoured', 0.0)), 0.0)
            result['lightly_armoured'] = max(current_armour, _as_float(policy.get('helmet_multiplier'), 100.0))
            if _as_bool(policy.get('force_penetration'), True):
                current_pen = _as_float(result.get('penetration', read_field_value(block_text, 'penetration', 0.0)), 0.0)
                result['penetration'] = max(current_pen, _as_float(policy.get('penetration'), 1.0))

        network_damage_modifier = _as_float(
            result.get('network_player_damage_modifier', read_field_value(block_text, 'network_player_damage_modifier', 1.0)),
            1.0,
        )
        if network_damage_modifier <= 0.0 and _as_bool(policy.get('repair_zero_network_modifier'), True):
            network_damage_modifier = max(_as_float(policy.get('network_player_modifier_fallback'), 1.0), 0.001)
            result['network_player_damage_modifier'] = network_damage_modifier

        network_headshot = max(_as_float(policy.get('network_multiplier'), 1500.0), 0.001)
        target = max(_as_float(policy.get('target_effective_health'), 400.0), 1.0)
        margin = max(_as_float(policy.get('safety_margin'), 1.25), 1.0)
        configured_floor = max(_as_float(policy.get('minimum_base_damage'), 0.35), 0.001)
        calculated_floor = (target * margin) / max(network_headshot * max(network_damage_modifier, 0.001), 0.001)
        damage_floor = max(configured_floor, calculated_floor)

        current_damage = _as_float(result.get('damage', read_field_value(block_text, 'damage', 0.0)), 0.0)
        if _as_bool(policy.get('auto_minimum_base_damage'), True) and current_damage < damage_floor:
            result['damage'] = damage_floor
            current_damage = damage_floor

        metrics.update({
            'target_effective_health': target,
            'safety_margin': margin,
            'network_player_damage_modifier': network_damage_modifier,
            'minimum_base_damage_required': damage_floor,
            'base_damage_after_policy': current_damage,
            'estimated_network_headshot_damage': current_damage * network_damage_modifier * network_headshot,
        })

    player_multiplier = _as_float(policy.get('player_multiplier'), 4.0)
    network_multiplier = _as_float(policy.get('network_multiplier'), player_multiplier)
    ai_multiplier = _as_float(policy.get('ai_multiplier'), player_multiplier)
    result.update({
        'headshot_player': player_multiplier,
        'network_headshot': network_multiplier,
        'headshot_ai': ai_multiplier,
        'min_headshot_player': 0.0,
        'max_headshot_player': distance,
        'min_headshot_ai': 0.0,
        'max_headshot_ai': distance,
    })
    return result, metrics


def audit_block(content: str, policy: dict[str, Any], *, expected: bool) -> dict[str, Any]:
    mode = policy.get('mode', 'off')
    result: dict[str, Any] = {
        'expected': expected,
        'mode': mode,
        'ready': True,
        'issues': [],
        'metrics': {},
    }
    if not expected or mode != 'onetap':
        return result

    def number(key: str, default: float = 0.0) -> float:
        return _as_float(read_field_value(content, key, default), default)

    base_damage = number('damage')
    network_damage = number('network_player_damage_modifier', 1.0)
    headshot = number('headshot_player')
    network_headshot = number('network_headshot')
    max_distance = number('max_headshot_player')
    falloff_max = number('falloff_max')
    falloff_modifier = number('falloff_modifier')
    armour_modifier = number('lightly_armoured')
    penetration = number('penetration')
    target_distance = _as_float(policy.get('distance'), max_distance)
    target_health = _as_float(policy.get('target_effective_health'), 400.0)
    margin = _as_float(policy.get('safety_margin'), 1.25)
    estimated = base_damage * max(network_damage, 0.0) * max(network_headshot, 0.0)
    flags = read_weapon_flags(content)
    flags_lower = {flag.lower() for flag in flags}

    metrics = {
        'damage': base_damage,
        'network_player_damage_modifier': network_damage,
        'headshot_player': headshot,
        'network_headshot': network_headshot,
        'estimated_network_headshot_damage': estimated,
        'required_damage_with_margin': target_health * margin,
        'max_headshot_distance': max_distance,
        'falloff_max': falloff_max,
        'falloff_modifier': falloff_modifier,
        'lightly_armoured_modifier': armour_modifier,
        'penetration': penetration,
        'weapon_flags': flags,
    }
    result['metrics'] = metrics

    issues: list[str] = []
    if base_damage <= 0.0:
        issues.append('base_damage_zero')
    if network_damage <= 0.0:
        issues.append('network_player_damage_modifier_zero')
    if headshot <= 0.0:
        issues.append('player_headshot_modifier_zero')
    if network_headshot <= 0.0:
        issues.append('network_headshot_modifier_zero')
    if estimated + 1e-6 < target_health * margin:
        issues.append('estimated_damage_below_target')
    if target_distance > 0.0 and max_distance + 0.001 < target_distance:
        issues.append('headshot_distance_too_short')
    if _as_bool(policy.get('no_falloff'), True):
        if falloff_max + 0.001 < target_distance:
            issues.append('falloff_range_too_short')
        if falloff_modifier + 1e-6 < 1.0:
            issues.append('falloff_modifier_below_one')
    if _as_bool(policy.get('bypass_helmets'), True):
        if armour_modifier + 1e-6 < _as_float(policy.get('helmet_multiplier'), 100.0):
            issues.append('helmet_modifier_too_low')
        if _as_bool(policy.get('force_penetration'), True) and penetration + 1e-6 < _as_float(policy.get('penetration'), 1.0):
            issues.append('penetration_too_low')
        if _as_bool(policy.get('add_ignore_helmets_flag'), True) and 'ignorehelmets' not in flags_lower:
            issues.append('missing_ignore_helmets_flag')
        if _as_bool(policy.get('add_armour_penetrating_flag'), True) and 'armourpenetrating' not in flags_lower:
            issues.append('missing_armour_penetrating_flag')

    if _as_bool(policy.get('remove_nonlethal_flags'), True):
        blocking = {str(v).lower() for v in policy.get('blocking_flags', [])}
        remaining = sorted(flag for flag in flags if flag.lower() in blocking)
        if remaining:
            issues.append('blocking_flags:' + ','.join(remaining))

    result['issues'] = issues
    result['ready'] = not issues
    return result
