"""Simulador teórico de daño, cadencia, DPS y TTK.

Es un modelo simplificado construido a partir de los campos del META. No reproduce
todo el motor de GTA V (animaciones, latencia, componentes, scripts que alteran el
daño). Sirve para comparar armas y perfiles, no como prueba de daño real.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from ..core.errors import ValidationFailed


@dataclass
class Assumptions:
    target: str = 'player'           # player | npc
    zone: str = 'torso'              # torso | head | limbs
    distance: float = 15.0           # metros
    health: float = 100.0            # vida efectiva (200 de vida - 100 del umbral de muerte)
    armour: float = 0.0              # puntos de blindaje
    armour_absorption: float = 1.0   # fracción del daño que absorbe el blindaje mientras dure
    armour_protects_head: bool = True  # en GTA/FiveM el chaleco absorbe también los tiros a la cabeza
    critical_hits: bool = True       # SetPedSuffersCriticalHits activo en el objetivo
    pellet_hit_ratio: float = 1.0    # fracción de perdigones que impactan (escopetas)
    include_reload: bool = True

    @classmethod
    def parse(cls, data: dict[str, Any] | None) -> 'Assumptions':
        data = data or {}
        a = cls()
        def num(key: str, low: float, high: float) -> None:
            if key in data and data[key] is not None:
                try:
                    value = float(data[key])
                except (TypeError, ValueError) as exc:
                    raise ValidationFailed(f'Supuesto “{key}” debe ser numérico.') from exc
                if not (low <= value <= high):
                    raise ValidationFailed(f'Supuesto “{key}” fuera de rango ({low}–{high}).')
                setattr(a, key, value)
        num('distance', 0, 3000)
        num('health', 1, 10000)
        num('armour', 0, 10000)
        num('armour_absorption', 0, 1)
        num('pellet_hit_ratio', 0, 1)
        for key in ('armour_protects_head', 'critical_hits', 'include_reload'):
            if key in data:
                setattr(a, key, bool(data[key]))
        if data.get('target') in {'player', 'npc'}:
            a.target = data['target']
        if data.get('zone') in {'torso', 'head', 'limbs'}:
            a.zone = data['zone']
        return a


def _f(values: dict[str, Any], key: str, default: float) -> float:
    value = values.get(key)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return default
    return float(value)


def falloff_factor(values: dict[str, Any], distance: float) -> float:
    """1.0 hasta el inicio de caída, interpolación lineal hasta el final y luego el mínimo."""
    weapon_range = _f(values, 'weapon_range', 0.0)
    if weapon_range > 0 and distance > weapon_range:
        return 0.0
    fmin = _f(values, 'falloff_min', 0.0)
    fmax = _f(values, 'falloff_max', 0.0)
    fmod = _f(values, 'falloff_modifier', 1.0)
    if fmax <= 0 or distance <= fmin:
        return 1.0
    if distance >= fmax:
        return fmod
    if fmax <= fmin:
        return fmod
    t = (distance - fmin) / (fmax - fmin)
    return 1.0 + (fmod - 1.0) * t


def zone_multiplier(values: dict[str, Any], a: Assumptions, distance: float) -> tuple[float, str]:
    if a.zone == 'head':
        if not a.critical_hits:
            return 1.0, 'critical hits desactivados: la cabeza cuenta como torso'
        hs_min = _f(values, 'min_headshot_player', 0.0)
        hs_max = _f(values, 'max_headshot_player', 0.0)
        if hs_max > 0 and not (hs_min <= distance <= hs_max):
            return 1.0, f'fuera de la distancia de cabeza ({hs_min:g}–{hs_max:g} m)'
        key = 'network_headshot' if a.target == 'player' else 'headshot_player'
        return _f(values, key, 1.0), ''
    if a.zone == 'limbs':
        key = 'network_hit_limbs' if a.target == 'player' else 'hit_limbs'
        return _f(values, key, 1.0), ''
    return 1.0, ''


def fire_interval(values: dict[str, Any]) -> float | None:
    tbs = _f(values, 'time_between_shots', 0.0)
    if tbs <= 0:
        return None
    anim = _f(values, 'anim_fire_rate_modifier', 1.0)
    return tbs / anim if anim > 1.0 else tbs


def damage_per_shot(values: dict[str, Any], a: Assumptions, distance: float | None = None) -> dict[str, Any]:
    distance = a.distance if distance is None else distance
    base = _f(values, 'damage', 0.0)
    target_mod = _f(values, 'network_player_damage_modifier' if a.target == 'player' else 'network_ped_damage_modifier', 1.0)
    zone_mod, zone_note = zone_multiplier(values, a, distance)
    falloff = falloff_factor(values, distance)
    pellets = max(1.0, _f(values, 'bullets_in_batch', 1.0))
    hit_pellets = pellets * a.pellet_hit_ratio if pellets > 1 else 1.0
    total = base * target_mod * zone_mod * falloff * hit_pellets
    return {
        'base': base, 'target_modifier': target_mod, 'zone_modifier': zone_mod, 'falloff': falloff,
        'pellets': hit_pellets, 'per_shot': total, 'note': zone_note,
        'out_of_range': falloff == 0.0,
    }


def shots_to_kill(per_shot: float, a: Assumptions, max_shots: int = 1000) -> int | None:
    if per_shot <= 0:
        return None
    health = a.health
    armour = a.armour
    armour_applies = a.zone != 'head' or a.armour_protects_head
    for shot in range(1, max_shots + 1):
        damage = per_shot
        if armour_applies and armour > 0:
            absorbed = min(armour, damage * a.armour_absorption)
            armour -= absorbed
            damage -= absorbed
        health -= damage
        if health <= 1e-9:
            return shot
    return None


def simulate_weapon(values: dict[str, Any], a: Assumptions) -> dict[str, Any]:
    dmg = damage_per_shot(values, a)
    interval = fire_interval(values)
    rpm = 60.0 / interval if interval else None
    clip = int(_f(values, 'clip_size', 0.0)) or None
    reload_time = _f(values, 'reload_time_mp', 0.0) or None
    shots = shots_to_kill(dmg['per_shot'], a)
    ttk = None
    reloads = 0
    if shots is not None and interval is not None:
        ttk = (shots - 1) * interval
        if a.include_reload and clip and reload_time and shots > clip:
            reloads = (shots - 1) // clip
            ttk += reloads * reload_time
    dps = dmg['per_shot'] / interval if interval else None
    sustained = None
    if interval and clip and reload_time:
        sustained = (clip * dmg['per_shot']) / (clip * interval + reload_time)
    return {
        'damage': dmg,
        'rpm': rpm,
        'interval': interval,
        'dps': dps,
        'dps_sustained': sustained,
        'shots_to_kill': shots,
        'ttk': ttk,
        'reloads': reloads,
        'clip_size': clip,
        'reload_time': reload_time,
    }


def distance_series(values: dict[str, Any], a: Assumptions, max_distance: float | None = None, points: int = 41) -> dict[str, Any]:
    weapon_range = _f(values, 'weapon_range', 0.0)
    limit = max_distance or max(25.0, min(weapon_range * 1.1 if weapon_range else 150.0, 1000.0))
    step = limit / (points - 1)
    rows = []
    for index in range(points):
        distance = round(index * step, 2)
        row: dict[str, Any] = {'distance': distance}
        for zone in ('torso', 'head', 'limbs'):
            zone_a = Assumptions(**{**asdict(a), 'zone': zone})
            dmg = damage_per_shot(values, zone_a, distance)
            row[zone] = round(dmg['per_shot'], 3)
        current = damage_per_shot(values, a, distance)['per_shot']
        interval = fire_interval(values)
        shots = shots_to_kill(current, a)
        row['shots'] = shots
        row['ttk'] = round((shots - 1) * interval, 3) if shots and interval else None
        rows.append(row)
    return {'max_distance': limit, 'rows': rows}


def percent_change(before: float | None, after: float | None) -> float | None:
    if before in (None, 0) or after is None:
        return None
    return (after - before) / abs(before) * 100.0


def compare(results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Variación porcentual de cada resultado respecto al primero."""
    if not results:
        return []
    base = results[0]['result']
    for item in results:
        r = item['result']
        item['delta'] = {
            key: percent_change(base.get(key) if key != 'per_shot' else base['damage']['per_shot'],
                                r.get(key) if key != 'per_shot' else r['damage']['per_shot'])
            for key in ('per_shot', 'dps', 'ttk', 'rpm', 'shots_to_kill')
        }
    return results
