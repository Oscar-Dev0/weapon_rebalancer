from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from typing import Any

from .meta_utils import read_field_value
from .scanner import WeaponBlock


DAMAGE_REPAIR_FIELDS = (
    'damage',
    'network_player_damage_modifier',
    'network_ped_damage_modifier',
    'hit_limbs',
    'network_hit_limbs',
    'lightly_armoured',
    'weapon_range',
    'falloff_min',
    'falloff_max',
    'falloff_modifier',
    'headshot_player',
    'network_headshot',
    'headshot_ai',
    'min_headshot_player',
    'max_headshot_player',
    'min_headshot_ai',
    'max_headshot_ai',
)


@dataclass
class BaselineRepairResult:
    profile: dict[str, Any]
    notes: list[str] = field(default_factory=list)


def _number(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value)


def _current_numeric(block: WeaponBlock, profile: dict[str, Any], key: str) -> float | None:
    value = _number(profile.get(key))
    if value is not None:
        return value
    return _number(read_field_value(block.text, key))


def apply_baseline_repair(
    *,
    weapon: str,
    group: str,
    block: WeaponBlock,
    profile: dict[str, Any],
    is_official: bool,
    is_custom: bool,
    config: dict[str, Any],
) -> BaselineRepairResult:
    """Repara valores de daño inválidos antes de aplicar multiplicadores.

    Prioridad:
    1. Valores absolutos por arma (referencia vanilla incluida en el perfil).
    2. Valor válido del propio META.
    3. Fallback conservador del grupo cuando el META viene en 0 o sin tag.

    Los fallback de grupo NO reemplazan un valor válido. Esto evita convertir todas las
    armas custom en clones y permite aplicar +15 % sobre su daño real.
    """
    result = deepcopy(profile)
    notes: list[str] = []
    if not config.get('enabled', False):
        return BaselineRepairResult(result, notes)
    if weapon.upper() in {str(v).upper() for v in config.get('excluded_weapons', [])}:
        return BaselineRepairResult(result, notes)

    official_values = config.get('official_values', {})
    exact = official_values.get(weapon.upper()) if is_official else None
    trusted_fields = set(exact) if isinstance(exact, dict) else set()
    if isinstance(exact, dict):
        exact_changed = False
        for key, value in exact.items():
            numeric = _number(value)
            if key in DAMAGE_REPAIR_FIELDS and numeric is not None:
                current = _current_numeric(block, result, key)
                if current is None or abs(current - numeric) > 1e-9:
                    result[key] = numeric
                    exact_changed = True
        if exact_changed:
            notes.append('baseline:official_reference')

    group_defaults = config.get('group_fallbacks', {})
    fallback = group_defaults.get(group.upper(), {})
    if not isinstance(fallback, dict):
        fallback = {}

    minimum_damage = float(config.get('minimum_valid_damage', 0.01))
    repair_zero = bool(config.get('repair_zero_or_missing', True))
    repair_network = bool(config.get('repair_invalid_network_modifiers', True))
    repair_headshot = bool(config.get('repair_disabled_headshots', True))
    repair_range = bool(config.get('repair_invalid_ranges', True))

    # Para oficiales con referencia exacta, la tabla ya es soberana. Para las demás,
    # solo se repara lo que está roto; no inventamos un balance nuevo encima de un META válido.
    damage = _current_numeric(block, result, 'damage')
    if 'damage' not in trusted_fields and repair_zero and (damage is None or damage < minimum_damage):
        fallback_damage = _number(fallback.get('damage'))
        if fallback_damage is not None:
            result['damage'] = fallback_damage
            notes.append('baseline:damage_group_fallback')

    if repair_network:
        for key in ('network_player_damage_modifier', 'network_ped_damage_modifier'):
            value = _current_numeric(block, result, key)
            if key not in trusted_fields and (value is None or value <= 0.0):
                result[key] = float(fallback.get(key, 1.0))
                notes.append(f'baseline:{key}_repaired')

    if repair_range:
        weapon_range = _current_numeric(block, result, 'weapon_range')
        fallback_range = _number(fallback.get('weapon_range'))
        if 'weapon_range' not in trusted_fields and (weapon_range is None or weapon_range <= 0.0) and fallback_range is not None:
            result['weapon_range'] = fallback_range
            weapon_range = fallback_range
            notes.append('baseline:weapon_range_group_fallback')

        resolved_range = _number(result.get('weapon_range')) or weapon_range or fallback_range
        if resolved_range is not None and resolved_range > 0.0:
            falloff_min = _current_numeric(block, result, 'falloff_min')
            falloff_max = _current_numeric(block, result, 'falloff_max')
            if 'falloff_min' not in trusted_fields and (falloff_min is None or falloff_min <= 0.0):
                result['falloff_min'] = float(fallback.get('falloff_min', resolved_range * 0.45))
                notes.append('baseline:falloff_min_repaired')
            if 'falloff_max' not in trusted_fields and (falloff_max is None or falloff_max <= 0.0):
                result['falloff_max'] = float(fallback.get('falloff_max', resolved_range * 0.85))
                notes.append('baseline:falloff_max_repaired')
            falloff_modifier = _current_numeric(block, result, 'falloff_modifier')
            if 'falloff_modifier' not in trusted_fields and (falloff_modifier is None or falloff_modifier <= 0.0):
                result['falloff_modifier'] = float(fallback.get('falloff_modifier', 0.75))
                notes.append('baseline:falloff_modifier_repaired')

    if repair_headshot:
        head_defaults = {
            'headshot_player': float(fallback.get('headshot_player', 4.0)),
            'network_headshot': float(fallback.get('network_headshot', 1.0)),
            'headshot_ai': float(fallback.get('headshot_ai', 4.0)),
        }
        for key, default in head_defaults.items():
            value = _current_numeric(block, result, key)
            if key not in trusted_fields and (value is None or value <= 0.0):
                result[key] = default
                notes.append(f'baseline:{key}_repaired')

        resolved_range = (
            _number(result.get('weapon_range'))
            or _current_numeric(block, result, 'weapon_range')
            or _number(fallback.get('weapon_range'))
        )
        if resolved_range is not None:
            for key in ('max_headshot_player', 'max_headshot_ai'):
                value = _current_numeric(block, result, key)
                if key not in trusted_fields and (value is None or value <= 0.0):
                    result[key] = resolved_range
                    notes.append(f'baseline:{key}_repaired')
            for key in ('min_headshot_player', 'min_headshot_ai'):
                value = _current_numeric(block, result, key)
                if key not in trusted_fields and (value is None or value < 0.0):
                    result[key] = 0.0
                    notes.append(f'baseline:{key}_repaired')

    return BaselineRepairResult(result, list(dict.fromkeys(notes)))


def build_reference_index(reference_roots: list[Any], scan: Any) -> dict[str, dict[str, float]]:
    """Extrae valores absolutos de uno o más paquetes META de referencia.

    Está desacoplado del target: los archivos de referencia nunca se escriben. La última
    raíz indicada gana, permitiendo usar primero una base general y luego una corrección DLC.
    """
    from pathlib import Path
    from .meta_utils import read_text
    from .scanner import discover_meta_paths, extract_weapon_blocks

    result: dict[str, dict[str, float]] = {}
    for raw_root in reference_roots:
        root = Path(raw_root)
        if not root.exists() or not root.is_dir():
            continue
        paths = discover_meta_paths(root, scan, {
            'weaponanimations.meta', 'weaponarchetypes.meta', 'weaponcomponents.meta', 'pedpersonality.meta'
        })
        for path in paths:
            for block in extract_weapon_blocks(path, read_text(path), scan, []):
                values: dict[str, float] = {}
                for key in DAMAGE_REPAIR_FIELDS:
                    value = _number(read_field_value(block.text, key))
                    if value is not None:
                        values[key] = value
                if values:
                    result[block.weapon.upper()] = values
    return result
