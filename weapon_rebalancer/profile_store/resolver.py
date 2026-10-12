"""Herencia de perfiles (`profile.extends`) y conversión al formato del motor.

La combinación sigue JSON Merge Patch (RFC 7386):
- los objetos se combinan clave a clave,
- las listas y los valores simples se reemplazan,
- `null` elimina lo heredado.

Así un perfil derivado guarda solo lo que cambia y aun así puede reproducir
exactamente cualquier configuración (ver `merge_diff`).
"""
from __future__ import annotations

from copy import deepcopy
from typing import Any, Callable

from ..core.errors import ValidationFailed

MAX_DEPTH = 6
NON_ENGINE_KEYS = {'profile', 'schema_version', 'resources', '$schema'}


def deep_merge(base: Any, override: Any) -> Any:
    if isinstance(base, dict) and isinstance(override, dict):
        result = deepcopy(base)
        for key, value in override.items():
            if value is None:
                result.pop(key, None)
            elif key in result:
                result[key] = deep_merge(result[key], value)
            else:
                result[key] = _strip_nulls(value)
        return result
    return _strip_nulls(override)


def _strip_nulls(value: Any) -> Any:
    if isinstance(value, dict):
        return {k: _strip_nulls(v) for k, v in value.items() if v is not None}
    return deepcopy(value)


def merge_diff(base: Any, target: Any) -> Any:
    """Delta mínimo tal que deep_merge(base, delta) == target (para objetos)."""
    if isinstance(base, dict) and isinstance(target, dict):
        delta: dict[str, Any] = {}
        for key in base:
            if key not in target:
                delta[key] = None
        for key, value in target.items():
            if key not in base:
                delta[key] = deepcopy(value)
            elif isinstance(base[key], dict) and isinstance(value, dict):
                sub = merge_diff(base[key], value)
                if sub:
                    delta[key] = sub
            elif base[key] != value:
                delta[key] = deepcopy(value)
        return delta
    return deepcopy(target)


def chain_of(profile: dict[str, Any], loader: Callable[[str], dict[str, Any]]) -> list[dict[str, Any]]:
    """Lista [base más lejana, …, perfil] validando ciclos, profundidad y referencias."""
    chain = [profile]
    seen = [(profile.get('profile') or {}).get('id', '?')]
    current = profile
    while True:
        parent_id = (current.get('profile') or {}).get('extends')
        if not parent_id:
            break
        if parent_id in seen:
            raise ValidationFailed(f'Herencia circular: {" → ".join([*seen, parent_id])}.',
                                   hint='Un perfil no puede heredar de sí mismo ni de un derivado suyo.')
        if len(seen) >= MAX_DEPTH:
            raise ValidationFailed(f'La cadena de herencia supera {MAX_DEPTH} niveles.')
        current = loader(parent_id)
        seen.append(parent_id)
        chain.append(current)
    return list(reversed(chain))


def resolve(profile: dict[str, Any], loader: Callable[[str], dict[str, Any]]) -> dict[str, Any]:
    chain = chain_of(profile, loader)
    merged: dict[str, Any] = {}
    for item in chain:
        merged = deep_merge(merged, {k: v for k, v in item.items() if k != 'profile'})
    merged['profile'] = deepcopy(profile.get('profile') or {})
    merged['profile']['resolved_chain'] = [(p.get('profile') or {}).get('id', '?') for p in chain]
    return merged


def to_engine(profile: dict[str, Any]) -> dict[str, Any]:
    """Quita los metadatos v8: lo que queda es exactamente lo que lee `apply_external_profile`."""
    engine = {k: deepcopy(v) for k, v in profile.items() if k not in NON_ENGINE_KEYS}
    meta = profile.get('profile') or {}
    engine['name'] = meta.get('name', '')
    return engine
