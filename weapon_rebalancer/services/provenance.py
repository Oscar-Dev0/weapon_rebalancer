"""Procedencia de cada valor efectivo: de qué perfil, ámbito o regla sale.

Orden de resolución que se explica (igual que el motor):
1. Valor original del arma (META actual o .bak con `restore.from_backup`).
2. Reglas generales del perfil (`defaults`).
3. Reglas por categoría (`groups`) o preset interno.
4. Sobrescrituras individuales (`weapons`).
5. Reglas del motor (módulos, cadencia, multiplicadores, familias, política de cabeza, inofensivas, límites).
"""
from __future__ import annotations

from typing import Any

from ..profile_store.schema import MODULE_PRESET_KEYS, effective_modules, module_for_field
from .preview import _override_reason, _same

SCOPE_LABEL = {'weapon': 'arma', 'group': 'categoría', 'defaults': 'global'}


def _declared(profile: dict[str, Any], weapon: str, group: str, key: str) -> tuple[str, Any] | None:
    """Valor declarado por un perfil (sin herencia) para el arma: arma > categoría > global."""
    def scope_value(scope: Any) -> tuple[bool, Any]:
        if not isinstance(scope, dict):
            return False, None
        fields = scope.get('fields')
        if isinstance(fields, dict) and key in fields:
            return True, fields[key]
        if key in scope and key not in {'fields', 'meta', 'weapon_flags', 'headshot'}:
            return True, scope[key]
        return False, None

    for kind, scope in (('weapon', (profile.get('weapons') or {}).get(weapon)),
                        ('group', (profile.get('groups') or {}).get(group)),
                        ('defaults', profile.get('defaults'))):
        found, value = scope_value(scope)
        if found:
            return kind, value
    return None


HEAD_POLICY_KEYS = {'headshot_player', 'network_headshot', 'headshot_ai', 'min_headshot_player', 'max_headshot_player',
                    'min_headshot_ai', 'max_headshot_ai'}


def explain_weapon(weapon: str, group: str, chain: list[dict[str, Any]], resolved: dict[str, Any],
                   original: dict[str, Any], current: dict[str, Any], proposed: dict[str, Any] | None,
                   processed: bool, keys: list[str], is_custom: bool | None = None) -> dict[str, dict[str, Any]]:
    """`chain` = perfiles sin resolver desde la base más lejana hasta el perfil (incluido)."""
    modules = effective_modules(resolved)
    own_id = (chain[-1].get('profile') or {}).get('id') if chain else None
    result: dict[str, dict[str, Any]] = {}
    for key in keys:
        entry: dict[str, Any] = {'original': original.get(key), 'current': current.get(key),
                                 'effective': (proposed or current).get(key)}
        declared_by: list[tuple[str, str, Any]] = []
        for profile in chain:
            hit = _declared(profile, weapon, group, key)
            if hit is not None:
                declared_by.append(((profile.get('profile') or {}).get('id', '?'), hit[0], hit[1]))
        # Un `null` en un derivado borra lo heredado: solo cuenta el último que declara algo.
        live = [d for d in declared_by if d[2] is not None]
        last = declared_by[-1] if declared_by else None
        if last is not None and last[2] is None:
            live = []
        source = live[-1] if live else None
        effective = entry['effective']
        if not processed:
            entry.update({'source': 'meta', 'label': 'META actual (el perfil no procesa esta arma)', 'status': 'original'})
        elif source is not None:
            blocked = [m for m in module_for_field(key) if modules.get(m) == 'original']
            preset = [m for m, k in MODULE_PRESET_KEYS.items() if key in k and modules.get(m) not in ('original', 'configured', None)]
            profile_id, scope, value = source
            entry.update({'profile': profile_id, 'scope': scope, 'declared': value})
            if blocked:
                entry.update({'source': 'module_original', 'status': 'ignored',
                              'label': f'Declarado en {profile_id} ({SCOPE_LABEL[scope]}) pero modules.{blocked[0]} = original'})
            elif preset:
                entry.update({'source': 'preset', 'status': 'rule',
                              'label': f'Preset modules.{preset[0]}={modules[preset[0]]} (pisa {value} de {profile_id})'})
            elif effective is not None and isinstance(value, (int, float)) and not _same(effective, float(value)):
                entry.update({'source': 'rule', 'status': 'rule',
                              'label': f'{_override_reason(resolved, weapon, key, is_custom)} (declarado {value} en {profile_id}, {SCOPE_LABEL[scope]})'})
            else:
                inherited = profile_id != own_id
                overrides = len(live) > 1 and live[-2][2] != value
                entry.update({'source': 'profile', 'status': 'inherited' if inherited else ('overridden' if overrides else 'own'),
                              'label': f'{profile_id} · {SCOPE_LABEL[scope]}' + (' (heredado)' if inherited else ' (sobrescribe la base)' if overrides else '')})
        elif key in HEAD_POLICY_KEYS and modules.get('headshot') not in (None, 'original') and group != 'GROUP_MELEE':
            weapon_head = ((resolved.get('weapons') or {}).get(weapon) or {}).get('headshot') or {}
            group_head = ((resolved.get('groups') or {}).get(group) or {}).get('headshot') or {}
            mode = weapon_head.get('mode') or group_head.get('mode') or (resolved.get('headshot') or {}).get('mode') or modules.get('headshot')
            where = 'del arma' if weapon_head.get('mode') else 'de la categoría' if group_head.get('mode') else 'global'
            entry.update({'source': 'rule', 'status': 'rule', 'label': f'política de cabeza {where} ({mode})'})
        elif effective is not None and not _same(effective, current.get(key)):
            entry.update({'source': 'rule', 'status': 'rule', 'label': _override_reason(resolved, weapon, key, is_custom)})
        else:
            restored = (resolved.get('restore') or {}).get('from_backup') and not _same(current.get(key), original.get(key))
            entry.update({'source': 'meta', 'status': 'original',
                          'label': 'Original (.bak)' if restored else 'META actual (sin cambio)'})
        result[key] = entry
    return result
