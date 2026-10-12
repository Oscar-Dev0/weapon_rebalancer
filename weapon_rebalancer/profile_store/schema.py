"""Esquema de perfiles v8.

El formato v8 conserva todas las secciones que entiende el motor (las de la v3–v7) y
añade un bloque ``profile`` con los metadatos. Así cualquier perfil v8 sigue siendo
válido para `run_rebalance.py --profile`.

    {
      "schema_version": 8,
      "profile": {"id": "...", "name": "...", "description": "...", "extends": null,
                  "tags": [], "purpose": "", "revision": 1, "created_at": "...", "updated_at": "..."},
      "engine_defaults": false,
      "modules": {...}, "headshot": {...}, "defaults": {...}, "groups": {...}, "weapons": {...}, ...
    }
"""
from __future__ import annotations

from typing import Any

from ..meta.fields import FIELDS
from ..engine.tuning import FIELD_SECTIONS

SCHEMA_VERSION = 8

# Claves de primer nivel que el motor lee. Cualquier otra no produce efecto.
ENGINE_KEYS: dict[str, str] = {
    'base_preset': 'Preset interno base (valores por categoría cuando el perfil no define un grupo).',
    'engine_defaults': 'false = no heredar overrides ni preset de config.py (recomendado para perfiles nuevos).',
    'modules': 'Modo de cada sección: original (no tocar), configured (usar lo del perfil) o un preset.',
    'validation': 'Opciones de validación del motor.',
    'headshot': 'Política global de disparo a la cabeza.',
    'defaults': 'Valores globales para todas las armas procesadas.',
    'groups': 'Valores por categoría (GROUP_*).',
    'weapons': 'Valores por arma (WEAPON_*).',
    'meta': 'Tags XML exactos globales.',
    'weapon_flags': 'Flags globales a agregar o quitar.',
    'ignore_weapons': 'Armas que nunca se tocan.',
    'allow_ignored_weapons': 'Quita armas de la lista de ignoradas por defecto.',
    'harmless_weapons': 'Armas forzadas a daño 0.',
    'allow_damage_weapons': 'Quita armas de la lista de inofensivas por defecto.',
    'restore': 'Restaurar desde .bak antes de aplicar (hace el resultado repetible).',
    'weapon_classification': 'Clasificación oficial/custom y multiplicadores para custom.',
    'baseline_repair': 'Reparación de valores en cero o ausentes.',
    'fire_rate_damage_rules': 'Daño según cadencia (TimeBetweenShots).',
    'fire_rate_classifier': 'Clasificador de cadencia y política one-tap por cadencia.',
    'weapon_field_multipliers': 'Multiplicadores exactos por arma.',
    'family_rules': 'Reglas por familia de nombre (contiene “REVOLVER”, etc.).',
}
# Secciones que no lee el motor de META sino el Generador (recursos externos).
RESOURCE_KEYS: dict[str, str] = {
    'resources': 'Valores para recursos externos: resources.qbx_recoils = {WEAPON_X: valor}.',
}
META_KEYS = {'schema_version', 'profile', 'name', 'description', '$schema'}
SCHEMA_REF = '../schemas/profile.schema.json'
# Metadatos del bloque `profile` (no los lee el motor; los muestran la web y la terminal).
PROFILE_META_FIELDS = (
    'id', 'name', 'short_name', 'description', 'objective', 'audience', 'features', 'warnings', 'extends',
    'tags', 'purpose', 'revision', 'created_at', 'updated_at', 'migrated_from', 'migrated_at', 'migration',
    'resolved_chain',
)
SEVERITY_LABELS = {'error': 'Bloqueante', 'warning': 'Advertencia', 'info': 'Recomendación'}
COMMENT_KEYS = {'_documentation', '_comment', '_field_reference', '_known_weapon_flags'}

MODULE_VALUES: dict[str, list[str]] = {
    'damage': ['original', 'configured', 'none', 'head_only', 'low', 'normal', 'high', 'lethal'],
    'armour': ['original', 'configured', 'none', 'normal', 'piercing', 'max'],
    'recoil': ['original', 'configured', 'none', 'low', 'normal', 'high'],
    'accuracy': ['original', 'configured', 'laser', 'high', 'normal', 'low'],
    'range': ['original', 'configured', 'short', 'normal', 'long', 'very_long'],
    'fire_rate': ['original', 'configured', 'slow', 'normal', 'fast', 'very_fast'],
    'reload': ['original', 'configured', 'slow', 'normal', 'fast', 'very_fast'],
    'headshot': ['original', 'off', 'normal', 'onetap'],
}
# Presets que sobrescriben campos concretos después de los valores del perfil.
MODULE_PRESET_KEYS: dict[str, set[str]] = {
    'recoil': {'recoil_accuracy_max', 'recoil_error_time', 'recoil_recovery_rate', 'recoil_shake_amplitude'},
    'accuracy': {'accuracy_spread', 'run_and_gun_accuracy_modifier', 'accurate_mode_accuracy_modifier'},
    'armour': {'lightly_armoured'},
}

VALIDATION_KEYS = {'strict_unknown_fields', 'fail_on_onetap_audit', 'warn_duplicates', 'warn_unregistered_meta'}
SCOPE_KEYS = {'fields', 'meta', 'weapon_flags', 'headshot', '_comment', '_documentation'}


def effective_modules(data: dict[str, Any]) -> dict[str, str]:
    """Modo real de cada módulo: lo que declare el perfil o el valor por defecto de config.py."""
    from ..engine import config

    defaults = {
        'damage': config.DAMAGE_PROFILE, 'armour': config.ARMOUR_PROFILE, 'recoil': config.RECOIL_PROFILE,
        'accuracy': config.ACCURACY_PROFILE, 'range': config.RANGE_PROFILE, 'fire_rate': config.FIRE_RATE_PROFILE,
        'reload': config.RELOAD_PROFILE, 'headshot': config.HEADSHOT_PROFILE,
    }
    declared = data.get('modules') if isinstance(data.get('modules'), dict) else {}
    return {key: str(declared.get(key, value)) for key, value in defaults.items()}


def module_for_field(key: str) -> list[str]:
    """Módulos que deben estar activos para que el motor aplique este campo."""
    modules = [section for section, keys in FIELD_SECTIONS.items() if key in keys]
    if key == 'lightly_armoured':
        modules.append('armour')
    return modules


def blank_profile(profile_id: str, name: str, description: str = '', extends: str | None = None) -> dict[str, Any]:
    """Perfil neutro: no toca nada hasta que se configure algo."""
    return {
        '$schema': SCHEMA_REF,
        'schema_version': SCHEMA_VERSION,
        'profile': {
            'id': profile_id,
            'name': name,
            'short_name': name[:24],
            'description': description,
            'objective': '',
            'audience': '',
            'features': [],
            'warnings': [],
            'extends': extends,
            'tags': [],
            'revision': 0,
        },
        'engine_defaults': False,
        'modules': {
            'damage': 'configured', 'armour': 'configured', 'recoil': 'configured',
            'accuracy': 'configured', 'range': 'configured', 'fire_rate': 'configured',
            'reload': 'configured', 'headshot': 'original',
        },
        'defaults': {'fields': {}},
        'groups': {},
        'weapons': {},
        'ignore_weapons': [],
        'harmless_weapons': [],
        'allow_damage_weapons': [],
    }


def _scope_fields(scope: Any) -> dict[str, Any]:
    if not isinstance(scope, dict):
        return {}
    fields: dict[str, Any] = {}
    nested = scope.get('fields')
    if isinstance(nested, dict):
        fields.update(nested)
    for key, value in scope.items():
        if key not in SCOPE_KEYS:
            fields[key] = value
    return fields


def iter_authored_fields(data: dict[str, Any]):
    """Recorre (ámbito, nombre, campo, valor) de defaults, groups y weapons."""
    # `None` significa “quitar lo heredado” (RFC 7386): no es un valor que aplicar.
    for key, value in _scope_fields(data.get('defaults')).items():
        if value is not None:
            yield 'defaults', '*', key, value
    for group, scope in (data.get('groups') or {}).items():
        for key, value in _scope_fields(scope).items():
            if value is not None:
                yield 'group', str(group).upper(), key, value
    for weapon, scope in (data.get('weapons') or {}).items():
        for key, value in _scope_fields(scope).items():
            if value is not None:
                yield 'weapon', str(weapon).upper(), key, value


def structural_issues(data: Any) -> list[dict[str, Any]]:
    """Comprobaciones de forma que no dependen del pack. El motor valida el resto."""
    issues: list[dict[str, Any]] = []

    def add(code: str, severity: str, message: str, fix: str = '', path: str = '') -> None:
        issues.append({'code': code, 'severity': severity, 'message': message, 'fix': fix, 'path': path})

    if not isinstance(data, dict):
        add('not_object', 'error', 'El perfil debe ser un objeto JSON.')
        return issues
    for key in data:
        if key in ENGINE_KEYS or key in META_KEYS or key in COMMENT_KEYS or key in RESOURCE_KEYS:
            continue
        add('unknown_top_level', 'warning', f'La clave “{key}” no la lee el motor: no tiene efecto.',
            'Elimínala o muévela a profile.description si es documentación.', key)
    meta = data.get('profile')
    if meta is not None and not isinstance(meta, dict):
        add('profile_block', 'error', '“profile” debe ser un objeto.', path='profile')
    validation = data.get('validation')
    if isinstance(validation, dict):
        for key in validation:
            if key not in VALIDATION_KEYS:
                add('validation_noop', 'warning', f'validation.{key} no lo usa el motor: no tiene efecto.',
                    f'Opciones válidas: {", ".join(sorted(VALIDATION_KEYS))}.', f'validation.{key}')
    modules = data.get('modules')
    if isinstance(modules, dict):
        for key, value in modules.items():
            if key not in MODULE_VALUES:
                add('module_unknown', 'warning', f'modules.{key} no existe.', path=f'modules.{key}')
            elif value not in MODULE_VALUES[key]:
                add('module_value', 'error', f'modules.{key}="{value}" no es válido.',
                    f'Valores: {", ".join(MODULE_VALUES[key])}.', f'modules.{key}')
    declared_modules = data.get('modules') if isinstance(data.get('modules'), dict) else {}
    headshot_block = data.get('headshot') if isinstance(data.get('headshot'), dict) else {}
    head_module = declared_modules.get('headshot')
    if head_module is None and data.get('engine_defaults', True) is not False:
        add('headshot_module_default', 'warning',
            'modules.headshot no está declarado: el motor usa el valor de config.py (onetap) para todas las armas procesadas.',
            'Declara modules.headshot (original si no quieres tocar la cabeza).', 'modules.headshot')
    if head_module not in (None, 'original') and 'mode' not in headshot_block and 'enabled' not in headshot_block and 'one_tap' not in headshot_block:
        add('headshot_mode_inherited', 'warning',
            'La política de cabeza está activa pero headshot.mode no está declarado: se hereda de config.py (one-tap ×1500).',
            f'Declara headshot.mode = "{head_module}" (o el modo que quieras) en la política global.', 'headshot.mode')
    resources = data.get('resources')
    if resources is not None:
        if not isinstance(resources, dict):
            add('resources_type', 'error', '“resources” debe ser un objeto.', path='resources')
        else:
            for key in resources:
                if key != 'qbx_recoils':
                    add('resources_unknown', 'warning', f'resources.{key} no lo usa el Generador: no tiene efecto.',
                        'Única opción disponible: qbx_recoils.', f'resources.{key}')
            recoils = resources.get('qbx_recoils')
            if recoils is not None and not isinstance(recoils, dict):
                add('qbx_type', 'error', 'resources.qbx_recoils debe ser un objeto {WEAPON_X: valor}.', path='resources.qbx_recoils')
            elif isinstance(recoils, dict):
                for weapon, value in recoils.items():
                    if value is None or value is False:
                        continue
                    if isinstance(value, bool) or not isinstance(value, (int, float)) or not (0 <= float(value) <= 10):
                        add('qbx_value', 'error', f'resources.qbx_recoils.{weapon} debe ser un número entre 0 y 10 (o false para desactivar la entrada).',
                            path=f'resources.qbx_recoils.{weapon}')
    issues.extend(contradiction_issues(data))
    for scope, name, key, value in iter_authored_fields(data):
        path = f'{scope}:{name}.{key}'
        if key not in FIELDS:
            add('unknown_field', 'error', f'Campo desconocido “{key}” en {scope} {name}.',
                'Usa un campo del catálogo o la sección meta para tags XML exactos.', path)
            continue
        if FIELDS[key].kind == 'value_attr' and (isinstance(value, bool) or not isinstance(value, (int, float))):
            add('field_type', 'error', f'{key} en {scope} {name} debe ser numérico.', path=path)
    return issues


def _upper_set(values: Any) -> set[str]:
    return {str(v).upper() for v in values} if isinstance(values, list) else set()


def _interval(rule: dict[str, Any]) -> tuple[float, float]:
    low = rule.get('min_time_between_shots')
    high = rule.get('max_time_between_shots')
    return (float(low) if isinstance(low, (int, float)) else 0.0, float(high) if isinstance(high, (int, float)) else float('inf'))


def contradiction_issues(data: dict[str, Any]) -> list[dict[str, Any]]:
    """Reglas que se contradicen o que nunca pueden aplicarse."""
    issues: list[dict[str, Any]] = []

    def add(code: str, severity: str, message: str, fix: str = '', path: str = '') -> None:
        issues.append({'code': code, 'severity': severity, 'message': message, 'fix': fix, 'path': path})

    for listed, allow, label in (('ignore_weapons', 'allow_ignored_weapons', 'ignorada'), ('harmless_weapons', 'allow_damage_weapons', 'inofensiva')):
        both = _upper_set(data.get(listed)) & _upper_set(data.get(allow))
        if both:
            add('list_conflict', 'warning', f'{", ".join(sorted(both))} está a la vez en {listed} y {allow}.',
                f'Decide si debe quedar {label} y quítala de una de las dos listas.', listed)
    configured = {str(w).upper() for w in (data.get('weapons') or {})}
    ignored = _upper_set(data.get('ignore_weapons'))
    for weapon in sorted(configured & ignored):
        add('ignored_but_configured', 'warning', f'{weapon} tiene valores propios pero está en ignore_weapons: el motor no la toca.',
            'Quítala de ignore_weapons o elimina sus valores.', f'weapons.{weapon}')

    def flag_scopes():
        yield 'perfil', data.get('weapon_flags')
        yield 'global', (data.get('defaults') or {}).get('weapon_flags') if isinstance(data.get('defaults'), dict) else None
        for kind in ('groups', 'weapons'):
            for name, scope in (data.get(kind) or {}).items():
                if isinstance(scope, dict):
                    yield name, scope.get('weapon_flags')
    for name, flags in flag_scopes():
        if isinstance(flags, dict):
            both = {str(f).lower() for f in flags.get('add') or []} & {str(f).lower() for f in flags.get('remove') or []}
            if both:
                add('flag_conflict', 'warning', f'{name}: la flag {", ".join(sorted(both))} se agrega y se quita a la vez (gana quitar).',
                    'Deja la flag en una sola lista.', f'{name}.weapon_flags')

    head = data.get('headshot') if isinstance(data.get('headshot'), dict) else {}
    for a, b in (('one_tap_weapons', 'no_one_tap_weapons'), ('allowed_weapons', 'disabled_weapons')):
        both = _upper_set(head.get(a)) & _upper_set(head.get(b))
        if both:
            add('headshot_list_conflict', 'warning', f'headshot.{a} y headshot.{b} comparten {", ".join(sorted(both))}.',
                'Una misma arma no puede estar en ambas listas.', f'headshot.{a}')
    modules = data.get('modules') if isinstance(data.get('modules'), dict) else {}
    if modules.get('headshot') == 'original':
        scoped = [f'groups.{g}' for g, s in (data.get('groups') or {}).items() if isinstance(s, dict) and s.get('headshot')]
        scoped += [f'weapons.{w}' for w, s in (data.get('weapons') or {}).items() if isinstance(s, dict) and s.get('headshot')]
        if scoped:
            add('headshot_scoped_noop', 'warning',
                f'Hay políticas de cabeza por categoría/arma ({len(scoped)}) pero modules.headshot = original: no tienen efecto.',
                'Activa la política global de cabeza (normal u onetap) o elimina esas políticas.', scoped[0])

    rules = data.get('fire_rate_damage_rules')
    if isinstance(rules, list):
        names: set[str] = set()
        for index, rule in enumerate(rules):
            if not isinstance(rule, dict):
                continue
            name = str(rule.get('name') or f'#{index + 1}')
            if name in names:
                add('rule_duplicate_name', 'info', f'Hay dos reglas de cadencia llamadas “{name}”.', 'Usa nombres únicos para identificarlas.')
            names.add(name)
            groups = _upper_set(rule.get('groups'))
            low, high = _interval(rule)
            for previous in rules[:index]:
                if not isinstance(previous, dict):
                    continue
                prev_groups = _upper_set(previous.get('groups'))
                p_low, p_high = _interval(previous)
                covers_groups = not prev_groups or (groups and groups <= prev_groups)
                if covers_groups and p_low <= low and high <= p_high:
                    add('rule_unreachable', 'warning',
                        f'La regla de cadencia “{name}” nunca se aplica: “{previous.get("name", "anterior")}” cubre el mismo rango antes.',
                        'Ordena las reglas de la más específica a la más general o ajusta los rangos.', f'fire_rate_damage_rules[{index}]')
                    break
    if not (data.get('profile') or {}).get('extends'):
        def has_null(value: Any) -> bool:
            if value is None:
                return True
            if isinstance(value, dict):
                return any(has_null(v) for k, v in value.items() if k != 'profile')
            return False
        if has_null({k: v for k, v in data.items() if k not in {'profile', '$schema'}}):
            add('null_without_parent', 'info', 'El perfil usa null (quitar lo heredado) pero no hereda de ningún perfil.',
                'Elimina esas claves: sin perfil base no tienen efecto.')
    return issues
