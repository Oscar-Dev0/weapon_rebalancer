"""Catálogo de armamento: une ox_inventory (identidad) con los weapons.meta (balance)."""
from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ..adapters.fivem_pack import MetaDefinition, PackSnapshot, collect_signatures, scan_pack
from ..adapters.ox_inventory import OxInventoryData, load_ox_inventory
from ..adapters.qbx_recoils import QbxRecoils, load_qbx_recoils
from ..core.joaat import joaat, signed
from ..core.jsonlog import log
from ..core.workspace import Workspace
from ..meta.vanilla_weapons import OFFICIAL_WEAPONS

CATEGORIES: dict[str, dict[str, Any]] = {
    'GROUP_PISTOL': {'id': 'pistol', 'label': 'Pistolas', 'order': 1},
    'GROUP_SMG': {'id': 'smg', 'label': 'Subfusiles', 'order': 2},
    'GROUP_RIFLE': {'id': 'rifle', 'label': 'Rifles de asalto', 'order': 3},
    'GROUP_SNIPER': {'id': 'sniper', 'label': 'Rifles de precisión', 'order': 4},
    'GROUP_SHOTGUN': {'id': 'shotgun', 'label': 'Escopetas', 'order': 5},
    'GROUP_MG': {'id': 'mg', 'label': 'Ametralladoras', 'order': 6},
    'GROUP_MELEE': {'id': 'melee', 'label': 'Cuerpo a cuerpo', 'order': 7},
    'GROUP_UNARMED': {'id': 'unarmed', 'label': 'Desarmado', 'order': 8},
    'GROUP_HEAVY': {'id': 'heavy', 'label': 'Armas pesadas', 'order': 9},
    'GROUP_THROWN': {'id': 'thrown', 'label': 'Arrojadizas', 'order': 10},
    'GROUP_STUNGUN': {'id': 'stungun', 'label': 'Aturdidoras', 'order': 11},
}
SPECIAL_CATEGORY = {'id': 'special', 'label': 'Armas especiales', 'order': 12}
NO_GROUP_CATEGORY = {'id': 'nogroup', 'label': 'Sin grupo en el META', 'order': 13}
NO_META_CATEGORY = {'id': 'nometa', 'label': 'Sin weapons.meta', 'order': 14}

FIREARM_GROUPS = {'GROUP_PISTOL', 'GROUP_SMG', 'GROUP_RIFLE', 'GROUP_SNIPER', 'GROUP_SHOTGUN', 'GROUP_MG'}
SUMMARY_KEYS = (
    'damage', 'network_player_damage_modifier', 'network_headshot', 'headshot_player', 'hit_limbs',
    'network_hit_limbs', 'time_between_shots', 'anim_fire_rate_modifier', 'clip_size', 'weapon_range',
    'falloff_min', 'falloff_max', 'falloff_modifier', 'max_headshot_player', 'bullets_in_batch',
    'recoil_shake_amplitude', 'accuracy_spread', 'reload_time_mp', 'fire_type',
)
_INTERNAL_PREFIXES = ('VEHICLE_WEAPON_', 'GADGET_', 'OBJECT', 'UNHOLSTER_', 'COMPONENT_')
# Fuentes de daño y ataques de animales que el juego define como CWeaponInfo.
_INTERNAL_NAMES = {f'WEAPON_{n}' for n in (
    'ANIMAL', 'ANIMAL_RETRIEVER', 'BARBED_WIRE', 'BIRD_CRAP', 'BLEEDING', 'BOAR', 'BRIEFCASE',
    'BRIEFCASE_02', 'CAT', 'COUGAR', 'COW', 'COYOTE', 'DEER', 'DROWNING', 'DROWNING_IN_VEHICLE',
    'ELECTRIC_FENCE', 'EXHAUSTION', 'EXPLOSION', 'FALL', 'FIRE', 'HAMMERHEAD_SHARK', 'HELI_CRASH',
    'HEN', 'HIT_BY_WATER_CANNON', 'KILLER_WHALE', 'PIG', 'RABBIT', 'RAMMED_BY_CAR', 'RUN_OVER_BY_CAR',
    'SMALL_DOG', 'TIGER_SHARK', 'AIRSTRIKE_ROCKET', 'PASSENGER_ROCKET', 'VEHICLE_ROCKET', 'REMOTESNIPER',
    'GARBAGEBAG', 'HANDCUFFS', 'DIGISCANNER',
)}


def category_for(group: str | None) -> dict[str, Any]:
    if not group:
        return NO_META_CATEGORY
    if group in CATEGORIES:
        return CATEGORIES[group]
    if group == 'UNKNOWN':
        return NO_GROUP_CATEGORY
    return SPECIAL_CATEGORY


def is_internal(name: str) -> bool:
    """Entradas del juego que no son armas de jugador (vehículos, animales, efectos)."""
    return name.startswith(_INTERNAL_PREFIXES) or not name.startswith('WEAPON_') or name in _INTERNAL_NAMES


def _num(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value)


def effective_rpm(values: dict[str, Any]) -> float | None:
    """RPM teóricas: 60 / (TimeBetweenShots / AnimFireRateModifier si > 1).

    Misma regla que el clasificador de cadencia del motor.
    """
    tbs = _num(values.get('time_between_shots'))
    if not tbs or tbs <= 0:
        return None
    anim = _num(values.get('anim_fire_rate_modifier')) or 1.0
    if anim > 1.0:
        tbs = tbs / anim
    return 60.0 / tbs


def issue(code: str, severity: str, message: str, fix: str = '', **extra: Any) -> dict[str, Any]:
    return {'code': code, 'severity': severity, 'message': message, 'fix': fix, **extra}


def _definition_issues(definition: MetaDefinition, harmless_hint: bool) -> list[dict[str, Any]]:
    values = definition.values
    issues: list[dict[str, Any]] = []
    where = definition.relative
    if not definition.registered:
        issues.append(issue('meta_unregistered', 'warning',
                            f'{where} no aparece en ningún WEAPONINFO_FILE del fxmanifest más cercano.',
                            'Agrega el archivo a data_file \'WEAPONINFO_FILE\' o el arma no cargará esos valores.'))
    if definition.repeated_fields:
        issues.append(issue('repeated_tags', 'info',
                            f'Tags repetidos dentro del bloque: {", ".join(definition.repeated_fields)}.',
                            'El generador iguala todas las copias directas al aplicar.'))
    if not definition.has_backup:
        issues.append(issue('no_backup', 'info', f'{where} no tiene .bak: el “original” es el valor actual.',
                            'Se crea un .bak automáticamente la primera vez que el generador escriba.'))
    if str(values.get('fire_type', '')).upper() == 'PROJECTILE':
        issues.append(issue('projectile', 'info', 'Arma de proyectil: el daño real depende del AmmoInfo/explosión, no solo de Damage.'))
    group = definition.group
    if group in FIREARM_GROUPS and not harmless_hint:
        damage = _num(values.get('damage'))
        net = _num(values.get('network_player_damage_modifier'))
        if damage is not None and damage <= 0:
            issues.append(issue('zero_damage', 'warning', 'Daño base 0: el arma no hace daño.',
                                'Asigna daño en el editor o márcala como inofensiva a propósito.'))
        if net is not None and net <= 0:
            issues.append(issue('zero_network_modifier', 'error', 'NetworkPlayerDamageModifier = 0: no hace daño a jugadores.',
                                'Pon el multiplicador contra jugadores en 1.0.'))
        head = _num(values.get('network_headshot'))
        if damage and head and (net if net is not None else 1.0) > 0:
            head_damage = damage * (net if net is not None else 1.0) * head
            if head_damage >= 100.0:
                issues.append(issue('headshot_onetap', 'info',
                                    f'Un disparo a la cabeza hace ~{head_damage:.0f} pts (≥ 100): mata de un tiro a 0 de blindaje.',
                                    'Si no es intencional, baja el multiplicador de cabeza contra jugadores.',
                                    value=round(head_damage, 2)))
        fmin, fmax = _num(values.get('falloff_min')), _num(values.get('falloff_max'))
        if fmin is not None and fmax is not None and fmin > fmax:
            issues.append(issue('falloff_inverted', 'warning', f'La caída empieza ({fmin:g} m) después de terminar ({fmax:g} m).',
                                'El inicio de caída debe ser menor que el final.'))
    if group == 'UNKNOWN':
        issues.append(issue('no_group', 'warning', 'El META no declara <Group>: las reglas por categoría no le aplican.',
                            'Usa reglas por arma o agrega el grupo en el META.'))
    return issues


@dataclass
class CatalogResult:
    built_at: float
    weapons: dict[str, dict[str, Any]]
    definitions: dict[str, list[MetaDefinition]]
    snapshot: PackSnapshot
    ox: OxInventoryData | None
    qbx_recoils: QbxRecoils | None
    signature: dict[str, Any]
    duration_ms: int
    global_issues: list[dict[str, Any]] = field(default_factory=list)

    def summary(self) -> dict[str, Any]:
        rows = [w for w in self.weapons.values() if not w['internal']]
        severities = {'error': 0, 'warning': 0, 'info': 0}
        for row in rows:
            for item in row['issues']:
                severities[item['severity']] = severities.get(item['severity'], 0) + 1
        categories: dict[str, int] = {}
        for row in rows:
            categories[row['category']['label']] = categories.get(row['category']['label'], 0) + 1
        return {
            'built_at': self.built_at,
            'duration_ms': self.duration_ms,
            'weapons': len(rows),
            'internal_entries': len(self.weapons) - len(rows),
            'meta_files': self.snapshot.meta_files,
            'definitions': len(self.snapshot.definitions),
            'custom': sum(1 for w in rows if w['custom']),
            'official': sum(1 for w in rows if not w['custom']),
            'ox_only': sum(1 for w in rows if w['in_ox'] and not w['in_meta']),
            'meta_only': sum(1 for w in rows if w['in_meta'] and not w['in_ox']),
            'duplicates': sum(1 for w in rows if w['definition_count'] > 1),
            'modified_vs_original': sum(1 for w in rows if w['modified_fields']),
            'issues': severities,
            'categories': categories,
            'ox': self.ox.summary() if self.ox else None,
            'qbx_recoils': self.qbx_recoils.summary() if self.qbx_recoils else None,
            'with_script_recoil': sum(1 for w in rows if w['qbx_recoil'] is not None),
            'components': len(self.snapshot.components),
        }


def _build(ws: Workspace) -> CatalogResult:
    started = time.perf_counter()
    snapshot = scan_pack(ws.pack_paths)
    ox = load_ox_inventory(ws.ox_path) if ws.ox_path else None
    qbx = load_qbx_recoils(ws.qbx_recoils_path) if ws.qbx_recoils_path and ws.qbx_recoils_path.is_file() else None

    definitions: dict[str, list[MetaDefinition]] = {}
    for definition in snapshot.definitions:
        definitions.setdefault(definition.weapon, []).append(definition)

    ox_weapons = ox.weapons if ox else {}
    ox_dupes = {d['name'].upper() for d in (ox.duplicates if ox else []) if d['section'] == 'Weapons'}
    component_hash_to_item: dict[int, str] = {}
    if ox:
        for item in ox.components.values():
            for value in item.hashes:
                component_hash_to_item.setdefault(value, item.name)

    weapons: dict[str, dict[str, Any]] = {}
    for name in sorted(set(definitions) | set(ox_weapons)):
        defs = definitions.get(name, [])
        primary = defs[-1] if defs else None  # la última definición escaneada suele ser la que carga al final
        ox_entry = ox_weapons.get(name)
        group = primary.group if primary else None
        values = primary.values if primary else {}
        original = (primary.original if primary and primary.original is not None else values) if primary else {}
        modified = sorted(
            key for key in set(values) | set(original)
            if key != 'weapon_flags' and values.get(key) != original.get(key)
        )
        if primary and values.get('weapon_flags') != original.get('weapon_flags'):
            modified.append('weapon_flags')
        issues: list[dict[str, Any]] = []
        internal = is_internal(name)
        harmless_hint = name in {'WEAPON_SNOWBALL', 'WEAPON_BALL'}
        if ox_entry and not defs and not internal:
            issues.append(issue('ox_without_meta', 'warning',
                                'Está en ox_inventory pero no se encontró su weapons.meta en los packs configurados.',
                                'Si el arma está instalada en otro recurso, agrégalo en Configuración → Packs; si no, el ítem no tiene modelo ni stats.'))
        if defs and not ox_entry and not internal:
            issues.append(issue('meta_without_ox', 'info', 'Definida en META pero no registrada en ox_inventory.',
                                'No se puede obtener como ítem del inventario.'))
        if len(defs) > 1:
            issues.append(issue('duplicate_definition', 'warning',
                                f'{len(defs)} definiciones CWeaponInfo: ' + ', '.join(d.relative for d in defs),
                                'La última que carga FiveM gana. Deja una sola definición o ajusta todas igual.'))
        if name in ox_dupes:
            issues.append(issue('ox_duplicate_key', 'warning', 'Clave repetida en ox_inventory/data/weapons.lua (en Lua gana la última).',
                                'Deja una sola entrada para esta arma en weapons.lua.'))
        if ox_entry and ox and ox_entry.ammoname and ox_entry.ammoname not in ox.ammo:
            issues.append(issue('ammo_unknown', 'error', f'ammoname “{ox_entry.ammoname}” no existe en la sección Ammo.',
                                'Usa una munición existente en ox_inventory/data/weapons.lua.'))
        for definition in defs:
            for item in _definition_issues(definition, harmless_hint):
                if item not in issues:
                    issues.append(item)

        components = []
        for component in (primary.components if primary else []):
            item_name = component_hash_to_item.get(joaat(component))
            info = snapshot.components.get(component)
            components.append({
                'name': component,
                'ox_item': item_name,
                'damage_modifiers': info.damage_modifiers if info else [],
                'clip_size': info.clip_size if info else None,
            })

        hash_value = ox_entry.hash if ox_entry else joaat(name)
        summary_now = {k: values.get(k) for k in SUMMARY_KEYS if k in values}
        summary_orig = {k: original.get(k) for k in SUMMARY_KEYS if k in original}
        weapons[name] = {
            'name': name,
            'label': ox_entry.label if ox_entry else name.removeprefix('WEAPON_').replace('_', ' ').title(),
            'hash': hash_value,
            'hash_signed': signed(hash_value),
            'group': group,
            'category': category_for(group),
            'custom': name not in OFFICIAL_WEAPONS,
            'internal': internal,
            'in_ox': ox_entry is not None,
            'in_meta': bool(defs),
            'definition_count': len(defs),
            'resources': sorted({d.resource for d in defs}),
            'has_backup': any(d.has_backup for d in defs),
            'ox': ox_entry.to_dict() if ox_entry else None,
            'current': summary_now,
            'original': summary_orig,
            'qbx_recoil': qbx.value_for(name) if qbx else None,
            'rpm': effective_rpm(values) if values else None,
            'rpm_original': effective_rpm(original) if original else None,
            'modified_fields': modified,
            'components': components,
            'issues': issues,
            'severity': (
                'error' if any(i['severity'] == 'error' for i in issues)
                else 'warning' if any(i['severity'] == 'warning' for i in issues)
                else 'info' if issues else 'ok'
            ),
        }

    global_issues: list[dict[str, Any]] = []
    if ox:
        for message in ox.errors:
            global_issues.append(issue('ox_error', 'error', message))
    elif ws.ox_inventory_dir:
        global_issues.append(issue('ox_missing', 'error', 'No se pudo cargar ox_inventory.'))
    for item in snapshot.unreadable:
        global_issues.append(issue('unreadable_meta', 'error', f'No se pudo leer {item["path"]}: {item["error"]}'))

    duration = int((time.perf_counter() - started) * 1000)
    result = CatalogResult(
        built_at=time.time(),
        weapons=weapons,
        definitions=definitions,
        snapshot=snapshot,
        ox=ox,
        qbx_recoils=qbx,
        signature=_signature(ws),
        duration_ms=duration,
        global_issues=global_issues,
    )
    log('catalog.scan', duration_ms=duration, weapons=len(weapons), definitions=len(snapshot.definitions))
    return result


def _signature(ws: Workspace) -> dict[str, Any]:
    ox_file = (ws.ox_path / 'data' / 'weapons.lua') if ws.ox_path else None
    ox_sig = None
    if ox_file and ox_file.is_file():
        stat = ox_file.stat()
        ox_sig = (stat.st_mtime_ns, stat.st_size)
    qbx_sig = None
    if ws.qbx_recoils_path and ws.qbx_recoils_path.is_file():
        stat = ws.qbx_recoils_path.stat()
        qbx_sig = (stat.st_mtime_ns, stat.st_size)
    return {
        'roots': [str(p) for p in ws.pack_paths],
        'ox': [str(ox_file) if ox_file else None, ox_sig],
        'qbx': [str(ws.qbx_recoils_path) if ws.qbx_recoils_path else None, qbx_sig],
        'files': collect_signatures(ws.pack_paths),
    }


class CatalogService:
    """Mantiene el catálogo en memoria y solo reescanea si cambian los archivos."""

    def __init__(self, workspace_loader) -> None:
        self._load_ws = workspace_loader
        self._lock = threading.Lock()
        self._cache: CatalogResult | None = None

    def get(self, *, force: bool = False) -> CatalogResult:
        ws = self._load_ws()
        with self._lock:
            if self._cache is not None and not force:
                if self._cache.signature == _signature(ws):
                    return self._cache
            self._cache = _build(ws)
            return self._cache

    def invalidate(self) -> None:
        with self._lock:
            self._cache = None

    def weapon_detail(self, name: str) -> dict[str, Any] | None:
        catalog = self.get()
        entry = catalog.weapons.get(name.upper())
        if entry is None:
            return None
        defs = catalog.definitions.get(name.upper(), [])
        return {
            **entry,
            'definitions': [
                {**d.to_dict(), 'values': d.values, 'original_values': d.original}
                for d in defs
            ],
        }
