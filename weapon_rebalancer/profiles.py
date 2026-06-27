from __future__ import annotations

from copy import deepcopy

Profile = dict[str, float | str]


def firearm_base(
    *,
    damage: float,
    weapon_range: float,
    falloff_max: float,
    falloff_modifier: float,
    headshot: float,
    limbs: float,
    armour: float,
    tbs: float | None = None,
    spread: float | None = None,
    recoil: float | None = None,
    recovery: float | None = None,
    vehicle_damage: float = 0.35,
) -> Profile:
    p: Profile = {
        'damage': damage,
        'weapon_range': weapon_range,
        'falloff_max': falloff_max,
        'falloff_modifier': falloff_modifier,
        'headshot_player': headshot,
        'network_headshot': headshot,
        'headshot_ai': 1.0,
        'min_headshot_player': 0.0,
        'max_headshot_player': weapon_range,
        'min_headshot_ai': 0.0,
        'max_headshot_ai': weapon_range,
        'hit_limbs': limbs,
        'network_hit_limbs': limbs,
        'lightly_armoured': armour,
        'vehicle_damage_modifier': vehicle_damage,
    }
    if tbs is not None:
        p['time_between_shots'] = tbs
    if spread is not None:
        p['accuracy_spread'] = spread
        p['run_and_gun_accuracy_modifier'] = min(spread * 1.35, 5.0)
        p['accurate_mode_accuracy_modifier'] = max(spread * 0.70, 0.05)
    if recoil is not None:
        p['recoil_accuracy_max'] = recoil
        p['recoil_error_time'] = 0.08
        p['recoil_shake_amplitude'] = min(max(recoil * 0.35, 0.03), 1.6)
    if recovery is not None:
        p['recoil_recovery_rate'] = recovery
    return p


def melee_profile(*, damage: float, weapon_range: float, heavy: bool = False) -> Profile:
    return {
        'damage': damage,
        'weapon_range': weapon_range,
        'falloff_max': max(weapon_range, 1.0),
        'falloff_modifier': 1.0,
        'headshot_player': 0.0,
        'network_headshot': 0.0,
        'headshot_ai': 0.0,
        'min_headshot_player': 0.0,
        'max_headshot_player': 0.0,
        'hit_limbs': 0.75 if heavy else 0.65,
        'network_hit_limbs': 0.75 if heavy else 0.65,
        'lightly_armoured': 0.55 if heavy else 0.45,
        'vehicle_damage_modifier': 0.05 if not heavy else 0.10,
    }


def category_defaults(group: str, preset: str = 'rp_balanced') -> Profile | None:
    scale = {
        'rp_serious': 0.88,
        'rp_balanced': 1.0,
        'pvp_controlled': 1.08,
        'hardcore': 1.20,
        'pvp_lethal': 1.0,
    }.get(preset, 1.0)

    # Perfil PvP letal calculado sobre los 200 HP habituales de GTA/FiveM.
    # Cabeza se resuelve por la política one-tap y, para atravesar armor real,
    # usando únicamente multiplicadores y distancias disponibles en weapons.meta.
    if preset == 'pvp_lethal':
        if group == 'GROUP_PISTOL':
            # 3 impactos al torso: 67 x 3 = 201.
            return firearm_base(damage=67.0, weapon_range=105.0, falloff_max=90.0, falloff_modifier=0.72, headshot=0.0, limbs=0.72, armour=1.0, tbs=0.180, spread=0.82, recoil=0.55, recovery=1.10, vehicle_damage=0.24)
        if group == 'GROUP_SMG':
            return firearm_base(damage=34.0, weapon_range=120.0, falloff_max=100.0, falloff_modifier=0.55, headshot=0.0, limbs=0.68, armour=1.0, tbs=0.105, spread=1.00, recoil=0.58, recovery=1.02, vehicle_damage=0.22)
        if group == 'GROUP_RIFLE':
            # 5 impactos al torso: 40 x 5 = 200.
            return firearm_base(damage=40.0, weapon_range=240.0, falloff_max=210.0, falloff_modifier=0.68, headshot=0.0, limbs=0.66, armour=1.0, tbs=0.125, spread=0.92, recoil=0.62, recovery=0.95, vehicle_damage=0.30)
        if group == 'GROUP_MG':
            return firearm_base(damage=35.0, weapon_range=195.0, falloff_max=170.0, falloff_modifier=0.62, headshot=0.0, limbs=0.64, armour=1.0, tbs=0.115, spread=1.15, recoil=0.66, recovery=0.88, vehicle_damage=0.32)
        if group == 'GROUP_SHOTGUN':
            # Daño por perdigones: letal al pecho solo muy cerca; caída agresiva.
            return firearm_base(damage=30.0, weapon_range=25.0, falloff_max=14.0, falloff_modifier=0.12, headshot=0.0, limbs=0.72, armour=1.0, tbs=0.800, spread=1.45, recoil=0.78, recovery=0.72, vehicle_damage=0.18)
        if group == 'GROUP_SNIPER':
            return firearm_base(damage=85.0, weapon_range=520.0, falloff_max=470.0, falloff_modifier=0.88, headshot=0.0, limbs=0.55, armour=1.0, tbs=1.250, spread=0.16, recoil=0.85, recovery=0.62, vehicle_damage=0.35)
        if group == 'GROUP_MELEE':
            return melee_profile(damage=5.5, weapon_range=1.15, heavy=False)

    if group == 'GROUP_PISTOL':
        return firearm_base(damage=10.0 * scale, weapon_range=110.0, falloff_max=85.0, falloff_modifier=0.55, headshot=0.0, limbs=0.75, armour=0.85, tbs=0.180, spread=0.85, recoil=0.50, recovery=1.15, vehicle_damage=0.25)
    if group == 'GROUP_SMG':
        return firearm_base(damage=9.0 * scale, weapon_range=115.0, falloff_max=95.0, falloff_modifier=0.38, headshot=0.0, limbs=0.62, armour=0.72, tbs=0.105, spread=1.05, recoil=0.50, recovery=1.05, vehicle_damage=0.22)
    if group == 'GROUP_RIFLE':
        return firearm_base(damage=11.5 * scale, weapon_range=240.0, falloff_max=210.0, falloff_modifier=0.45, headshot=0.0, limbs=0.60, armour=0.78, tbs=0.125, spread=0.95, recoil=0.50, recovery=0.95, vehicle_damage=0.30)
    if group == 'GROUP_MG':
        return firearm_base(damage=10.5 * scale, weapon_range=190.0, falloff_max=160.0, falloff_modifier=0.42, headshot=0.0, limbs=0.58, armour=0.76, tbs=0.115, spread=1.20, recoil=0.50, recovery=0.88, vehicle_damage=0.32)
    if group == 'GROUP_SHOTGUN':
        return firearm_base(damage=18.0 * scale, weapon_range=24.0, falloff_max=18.0, falloff_modifier=0.25, headshot=0.0, limbs=0.70, armour=0.82, tbs=0.800, spread=1.60, recoil=0.50, recovery=0.75, vehicle_damage=0.18)
    if group == 'GROUP_SNIPER':
        return firearm_base(damage=38.0 * scale, weapon_range=520.0, falloff_max=450.0, falloff_modifier=0.80, headshot=0.0, limbs=0.45, armour=0.90, tbs=1.250, spread=0.18, recoil=0.50, recovery=0.62, vehicle_damage=0.35)
    if group == 'GROUP_MELEE':
        return melee_profile(damage=5.5 * scale, weapon_range=1.15, heavy=False)
    return None


MELEE_PRESETS: dict[str, Profile] = {
    'light_blade': melee_profile(damage=5.0, weapon_range=1.05),
    'blade': melee_profile(damage=6.0, weapon_range=1.10),
    'blunt': melee_profile(damage=6.0, weapon_range=1.25),
    'tool': melee_profile(damage=5.5, weapon_range=1.10),
    'heavy': melee_profile(damage=7.2, weapon_range=1.30, heavy=True),
    'fist': melee_profile(damage=3.0, weapon_range=0.85),
    'flashlight': melee_profile(damage=2.5, weapon_range=0.90),
}


def with_headshot(profile: Profile, value: float, max_distance: float | None = None) -> Profile:
    p = deepcopy(profile)
    p['headshot_player'] = value
    p['network_headshot'] = value
    if max_distance is not None:
        p['max_headshot_player'] = max_distance
    return p


def no_headshot(profile: Profile) -> Profile:
    p = deepcopy(profile)
    p['headshot_player'] = 0.0
    p['network_headshot'] = 0.0
    p['headshot_ai'] = 0.0
    p['min_headshot_player'] = 0.0
    p['max_headshot_player'] = 0.0
    p['min_headshot_ai'] = 0.0
    p['max_headshot_ai'] = 0.0
    return p
