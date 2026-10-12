"""Migraciones versionadas de perfiles.

Historial de formatos:
- v3–v7: perfiles “legacy”. `schema_version` marcaba la generación del rebalancer
  (3, 4, 5, 7) y no un formato distinto: todos comparten las mismas secciones.
  `name` y `description` estaban en el primer nivel.
- v8: añade el bloque `profile` (id, nombre, descripción, herencia, etiquetas,
  revisión y fechas). El resto de secciones no cambia, así que la migración es
  reversible: `downgrade_to_legacy` devuelve el formato anterior.
"""
from __future__ import annotations

import time
from copy import deepcopy
from typing import Any

from .schema import SCHEMA_VERSION


def now_iso() -> str:
    return time.strftime('%Y-%m-%dT%H:%M:%S%z')


def detect_version(data: dict[str, Any]) -> int:
    if isinstance(data.get('profile'), dict):
        try:
            return int(data.get('schema_version', SCHEMA_VERSION))
        except (TypeError, ValueError):
            return SCHEMA_VERSION
    try:
        legacy = int(data.get('schema_version', 3))
    except (TypeError, ValueError):
        legacy = 3
    return min(legacy, 7)


def is_legacy(data: dict[str, Any]) -> bool:
    return detect_version(data) < SCHEMA_VERSION


def migrate(data: dict[str, Any], profile_id: str) -> tuple[dict[str, Any], list[str]]:
    """Devuelve (perfil v8, notas). Nunca modifica el diccionario recibido."""
    notes: list[str] = []
    source = deepcopy(data)
    version = detect_version(source)
    if version >= SCHEMA_VERSION:
        meta = source.setdefault('profile', {})
        meta.setdefault('id', profile_id)
        return source, notes

    notes.append(f'Migrado de formato legacy (schema_version={source.get("schema_version", "sin indicar")}) a v{SCHEMA_VERSION}.')
    name = source.pop('name', None)
    description = source.pop('description', None)
    documentation = source.get('_documentation')
    purpose = ''
    if isinstance(documentation, dict):
        purpose = str(documentation.get('purpose') or documentation.get('objetivo') or '')
    result: dict[str, Any] = {
        'schema_version': SCHEMA_VERSION,
        'profile': {
            'id': profile_id,
            'name': str(name or profile_id),
            'description': str(description or ''),
            'extends': None,
            'tags': [],
            'purpose': purpose,
            'revision': 0,
            'migrated_from': source.get('schema_version', 3),
            'migrated_at': now_iso(),
        },
    }
    source.pop('schema_version', None)
    # engine_defaults no existía: los perfiles legacy heredaban siempre config.py.
    if 'engine_defaults' not in source:
        result['engine_defaults'] = True
        notes.append('engine_defaults=true para conservar exactamente el comportamiento anterior.')
    result.update(source)
    return result, notes


def downgrade_to_legacy(data: dict[str, Any]) -> dict[str, Any]:
    """Revierte v8 → legacy (para restaurar una migración)."""
    source = deepcopy(data)
    meta = source.pop('profile', {}) or {}
    legacy_version = meta.get('migrated_from', 3)
    result: dict[str, Any] = {
        'name': meta.get('name', ''),
        'description': meta.get('description', ''),
        'schema_version': legacy_version,
    }
    source.pop('schema_version', None)
    if source.get('engine_defaults') is True:
        source.pop('engine_defaults')
    result.update(source)
    return result
