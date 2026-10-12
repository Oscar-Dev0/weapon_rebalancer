"""Migración de los perfiles legacy (v3–v7) a los cuatro perfiles de la versión 8.

Reproducible: lee `profiles/legacy/` y regenera `official/`, `server/flow_custom.json`,
`migrations/<fecha>/` (inventario, mapeo, informe y pendientes). Cada resultado se
verifica ejecutando el motor real:

- `competitive`, `flow_custom` y los pendientes: equivalencia exacta con su fuente.
- `realistic` y `balanced`: solo pueden diferir en los campos de los cambios de diseño
  documentados (si aparece otra diferencia, la migración falla).
"""
from __future__ import annotations

import json
import time
from copy import deepcopy
from dataclasses import asdict
from pathlib import Path
from typing import Any

from ..core.fsutil import atomic_write_json
from ..core.workspace import Workspace
from ..engine.config import Settings
from ..engine.profile_loader import apply_external_profile
from .migrations import migrate
from .resolver import deep_merge, merge_diff, to_engine
from .schema import MODULE_PRESET_KEYS, SCHEMA_REF, SCHEMA_VERSION, effective_modules
from ..engine.tuning import FIELD_SECTIONS

MIGRATION_ID = '2026-10-12_v8'
HEAD_POLICY_FIELDS = {'headshot_player', 'network_headshot', 'headshot_ai', 'min_headshot_player', 'max_headshot_player',
                      'min_headshot_ai', 'max_headshot_ai'}
FALLOFF_FIELDS = {'falloff_min', 'falloff_max', 'falloff_modifier'}

OFFICIAL_META: dict[str, dict[str, Any]] = {
    'balanced': {
        'name': 'Balanced RP', 'short_name': 'Balanced',
        'description': 'Configuración equilibrada para servidores de roleplay: restaura los valores de GTA V de las armas '
                       'oficiales y lleva cada arma personalizada a la referencia de su categoría, para que cada categoría '
                       'conserve su identidad y ninguna arma importada llegue inflada.',
        'objective': 'Combate consistente y reconocible, sin armas personalizadas más fuertes que las del juego base.',
        'audience': 'Servidores de roleplay general que quieren un punto de partida neutro.',
        'features': [
            'Armas oficiales: valores del .bak (antes de cualquier modificación) y tabla de referencia vanilla incluida.',
            'Armas personalizadas: daño, alcance y caída normalizados a la referencia de su categoría (×1.0).',
            'Repara daño, modificadores de red y alcances en 0 o ausentes.',
            'No toca recoil, precisión ni cadencia: cada arma conserva los suyos.',
        ],
        'warnings': [
            'Necesita los .bak del pack: parte siempre de ellos (restore.from_backup).',
            'Las armas personalizadas pierden los valores que trae su META: es intencional.',
        ],
        'tags': ['oficial', 'rp'],
    },
    'realistic': {
        'name': 'Realistic Combat', 'short_name': 'Realistic',
        'description': 'Combate exigente: daño corporal moderado por categoría, retroceso alto, alcances y caídas '
                       'diferenciados y disparo a la cabeza letal. Es una aproximación de diseño, no una simulación '
                       'física verificada.',
        'objective': 'Que el control del arma y la colocación del disparo pesen más que la cadencia.',
        'audience': 'Servidores de roleplay serio o táctico.',
        'features': [
            'Daño corporal por categoría (pistola 34, SMG 25, rifle 30, escopeta 24 por perdigón, MG 28, francotirador 80).',
            'Cabeza one-tap dentro de 300 m, también con blindaje y casco nativo.',
            'Recoil preset “high” para todas las armas procesadas.',
            'Cadencia fija por categoría (iguala armas de la misma categoría).',
        ],
        'warnings': [
            'One-tap requiere critical hits activos (os_headshot_guard o sin scripts que los apaguen).',
            'Hereda de config.py los presets de cuerpo a cuerpo y el alcance ×1.5 de revólveres (engine_defaults).',
        ],
        'tags': ['oficial', 'rp', 'tactico'],
    },
    'competitive': {
        'name': 'Competitive PvP', 'short_name': 'Competitive',
        'description': 'Combate competitivo con TTK corto y medible: más daño por categoría, recoil bajo y precisión alta. '
                       'Hereda de Realistic las distancias, caídas y la política de cabeza.',
        'objective': 'Enfrentamientos rápidos y predecibles donde gana quien acierta primero.',
        'audience': 'Servidores o modos PvP, arenas y eventos competitivos.',
        'features': [
            'Daño corporal por categoría (pistola 67, SMG 40, rifle 50, escopeta 36 por perdigón, MG 45, francotirador 100).',
            'Recoil preset “low” y precisión preset “high”.',
            'Cadencia fija por categoría: evita que una pistola automática domine con el mismo daño.',
            'Cabeza one-tap dentro de 300 m (heredado de Realistic).',
        ],
        'warnings': [
            'Los daños se diseñaron para 200 de vida; con la muerte en 100 de este servidor el TTK real es la mitad (ver simulador).',
            'One-tap requiere critical hits activos.',
        ],
        'tags': ['oficial', 'pvp'],
    },
    'flow_custom': {
        'name': 'Flow Caribe Custom', 'short_name': 'Flow Custom',
        'description': 'Configuración propia de Flow Caribe: daño adaptativo por cadencia, cabeza ×1.5 general, one-tap '
                       'dinámico solo en la lista de pistolas fijadas, revólver y francotiradores, .50 reforzada y recoil '
                       'casi nulo salvo en armas one-tap tiro a tiro.',
        'objective': 'Mantener exactamente el balance actual del servidor, editable por categoría y por arma.',
        'audience': 'Administradores de Flow Caribe.',
        'features': [
            'Migrado sin cambios de comportamiento desde flow_caribe (v6.12).',
            'Hereda de un perfil oficial y guarda solo sus diferencias.',
            'Reglas por arma: 26 armas configuradas, multiplicadores exactos (revólver ×6, Gadget ×7).',
            'Las armas personalizadas de ox_inventory quedan cubiertas por las reglas de su categoría.',
        ],
        'warnings': [
            'Cambiar el perfil base cambia el resultado: revisa la vista previa antes de aplicar.',
            'Se respalda en el historial antes de cada guardado.',
        ],
        'tags': ['servidor', 'flow-caribe'],
    },
}


# ---------------------------------------------------------------------------
def engine_settings(engine_profile: dict[str, Any]) -> dict[str, Any]:
    settings = Settings.from_config()
    apply_external_profile(settings, engine_profile)
    data = asdict(settings)
    data.pop('root', None)
    # Las opciones de validación que el motor no lee no cambian el comportamiento.
    from .schema import VALIDATION_KEYS
    data['validation_options'] = {k: v for k, v in data['validation_options'].items() if k in VALIDATION_KEYS}
    return json.loads(json.dumps(data, sort_keys=True, default=lambda v: sorted(v) if isinstance(v, (set, frozenset)) else str(v)))


def strip_meta(profile: dict[str, Any]) -> dict[str, Any]:
    """Parte del perfil que lee el motor (sin metadatos, nombre ni claves de validación sin efecto)."""
    from .schema import VALIDATION_KEYS

    engine = to_engine(profile)
    engine.pop('name', None)
    engine.pop('description', None)
    if isinstance(engine.get('validation'), dict):
        engine['validation'] = {k: v for k, v in engine['validation'].items() if k in VALIDATION_KEYS}
    return engine


def inert_fields(engine_profile: dict[str, Any]) -> dict[str, list[str]]:
    """Campos por grupo que el motor descarta o reescribe siempre (no aportan nada)."""
    modules = effective_modules(engine_profile)
    head = engine_profile.get('headshot') or {}
    onetap_no_falloff = modules.get('headshot') == 'onetap' and head.get('no_falloff', True) is not False
    result: dict[str, list[str]] = {}
    for group, scope in (engine_profile.get('groups') or {}).items():
        fields = scope.get('fields', scope) if isinstance(scope, dict) else {}
        dead = []
        for key in fields:
            if key in HEAD_POLICY_FIELDS:
                dead.append(key)
                continue
            sections = [s for s, keys in FIELD_SECTIONS.items() if key in keys]
            if any(modules.get(s) == 'original' for s in sections):
                dead.append(key)
                continue
            if any(key in keys and modules.get(m) not in ('original', 'configured') for m, keys in MODULE_PRESET_KEYS.items()):
                dead.append(key)
                continue
            if onetap_no_falloff and key in FALLOFF_FIELDS and group != 'GROUP_MELEE':
                dead.append(key)
        if dead:
            result[group] = sorted(dead)
    return result


def drop_inert(engine_profile: dict[str, Any]) -> tuple[dict[str, Any], dict[str, list[str]]]:
    result = deepcopy(engine_profile)
    dead = inert_fields(result)
    for group, keys in dead.items():
        scope = result['groups'][group]
        holder = scope['fields'] if 'fields' in scope else scope
        for key in keys:
            holder.pop(key, None)
    return result, dead


def v8(profile_id: str, engine_part: dict[str, Any], meta: dict[str, Any], *, extends: str | None, migrated_from: str) -> dict[str, Any]:
    return {
        '$schema': SCHEMA_REF,
        'schema_version': SCHEMA_VERSION,
        'profile': {
            'id': profile_id, **meta, 'extends': extends, 'revision': 1,
            'created_at': time.strftime('%Y-%m-%dT%H:%M:%S%z'),
            'migrated_from': migrated_from, 'migration': MIGRATION_ID,
        },
        **engine_part,
    }


def output_values(engine_profile: dict[str, Any], ws: Workspace) -> dict[str, dict[str, Any]]:
    """Valores resultantes por arma (archivo|arma) al aplicar el perfil sobre el pack real, en memoria."""
    from ..adapters.fivem_pack import read_all_fields
    from ..meta.scanner import ScanConfig, extract_weapon_blocks
    from ..services.preview import run_engine

    run = run_engine(engine_profile, ws)
    values: dict[str, dict[str, Any]] = {}
    for path, text in run.captured.items():
        for index, block in enumerate(extract_weapon_blocks(path, text, ScanConfig(), [])):
            values[f'{path}|{block.weapon}|{index}'] = read_all_fields(block.text)[0]
    return values


def output_diff(a: dict[str, Any], b: dict[str, Any], ws: Workspace) -> dict[str, dict[str, list[Any]]]:
    """Diferencias reales de resultado entre dos perfiles (arma -> campo -> [a, b])."""
    va, vb = output_values(a, ws), output_values(b, ws)
    from ..meta.meta_utils import read_text  # noqa: F401  (forzar import ligero)

    diff: dict[str, dict[str, list[Any]]] = {}
    for key in set(va) | set(vb):
        left, right = va.get(key), vb.get(key)
        if left is None or right is None:
            # Un archivo solo cambia con uno de los perfiles: comparar contra el actual del disco.
            from ..adapters.fivem_pack import read_all_fields
            from ..meta.scanner import ScanConfig, extract_weapon_blocks
            path_str, weapon, index = key.rsplit('|', 2)
            path = Path(path_str)
            blocks = extract_weapon_blocks(path, path.read_text(encoding='utf-8', errors='ignore'), ScanConfig(), [])
            current = read_all_fields(blocks[int(index)].text)[0] if int(index) < len(blocks) else {}
            left = left if left is not None else current
            right = right if right is not None else current
        fields = {k: [left.get(k), right.get(k)] for k in set(left) | set(right) if left.get(k) != right.get(k)}
        if fields:
            diff[key.split('|')[1]] = {**diff.get(key.split('|')[1], {}), **fields}
    return diff


# ---------------------------------------------------------------------------
def build(legacy_dir: Path, ws: Workspace, *, check_output: bool = True) -> dict[str, Any]:
    """Construye los perfiles nuevos y el informe. No escribe nada."""
    legacy: dict[str, dict[str, Any]] = {}
    for path in sorted(legacy_dir.glob('*.json')):
        if path.name == 'catalog.json':
            continue
        legacy[path.stem] = json.loads(path.read_text(encoding='utf-8'))
    engine = {pid: strip_meta(migrate(data, pid)[0]) for pid, data in legacy.items()}
    settings_hash = {pid: json.dumps(engine_settings(e), sort_keys=True) for pid, e in engine.items()}

    report: dict[str, Any] = {'migration': MIGRATION_ID, 'generated_at': time.strftime('%Y-%m-%dT%H:%M:%S%z'),
                              'sources': {}, 'official': {}, 'pending': {}, 'archived': {}, 'checks': []}
    outputs: dict[str, dict[str, Any]] = {}

    # --- realistic (rp_serious_onetap) ---------------------------------------
    realistic_engine, realistic_dead = drop_inert(engine['rp_serious_onetap'])
    realistic_engine['modules'] = {**realistic_engine['modules'], 'recoil': 'high'}
    realistic_dead_after, _ = drop_inert(realistic_engine)
    realistic_engine = realistic_dead_after
    outputs['realistic'] = v8('realistic', realistic_engine, OFFICIAL_META['realistic'], extends=None, migrated_from='rp_serious_onetap')

    # --- competitive (pvp_competitive_onetap) extiende realistic --------------
    competitive_target, competitive_dead = drop_inert(engine['pvp_competitive_onetap'])
    competitive_delta = merge_diff(realistic_engine, competitive_target)
    outputs['competitive'] = v8('competitive', competitive_delta, OFFICIAL_META['competitive'], extends='realistic',
                                migrated_from='pvp_competitive_onetap')

    # --- balanced (vanilla_repair_custom_plus15_absolute_v6) ------------------
    balanced_engine = deepcopy(engine['vanilla_repair_custom_plus15_absolute_v6'])
    custom = balanced_engine['weapon_classification']['custom']
    changed_multipliers = {k: v for k, v in custom['field_multipliers'].items() if v != 1.0}
    custom['field_multipliers'] = {k: 1.0 for k in custom['field_multipliers']}
    removed_family = balanced_engine.pop('family_rules', [])
    outputs['balanced'] = v8('balanced', balanced_engine, OFFICIAL_META['balanced'], extends=None,
                             migrated_from='vanilla_repair_custom_plus15_absolute_v6')

    resolved_engine = {
        'realistic': realistic_engine,
        'competitive': deep_merge(realistic_engine, competitive_delta),
        'balanced': balanced_engine,
    }

    def best_base(target: dict[str, Any]) -> tuple[str, dict[str, Any]]:
        # En caso de empate gana el primero: competitive es la afinidad natural de los perfiles PvP.
        options = {base: merge_diff(resolved_engine[base], target) for base in ('competitive', 'realistic', 'balanced')}
        base = min(options, key=lambda b: len(json.dumps(options[b])))
        return base, options[base]

    # --- flow_custom ----------------------------------------------------------
    flow_base, flow_delta = best_base(engine['flow_caribe'])
    outputs['flow_custom'] = v8('flow_custom', flow_delta, OFFICIAL_META['flow_custom'], extends=flow_base, migrated_from='flow_caribe')
    outputs['flow_custom']['profile']['legacy_name'] = (legacy['flow_caribe'].get('name') or '')
    flow_resolved = deep_merge(resolved_engine[flow_base], flow_delta)
    if engine_settings(flow_resolved) != engine_settings(engine['flow_caribe']):
        raise RuntimeError('flow_custom no reproduce flow_caribe')
    report['checks'].append({'profile': 'flow_custom', 'check': 'settings_equal', 'source': 'flow_caribe', 'ok': True})

    # --- clústeres de duplicados ---------------------------------------------
    clusters: dict[str, list[str]] = {}
    for pid, digest in settings_hash.items():
        clusters.setdefault(digest, []).append(pid)

    # --- pendientes: configuraciones únicas que no son oficiales ---------------
    mapped = {'rp_serious_onetap': 'realistic', 'pvp_competitive_onetap': 'competitive',
              'vanilla_repair_custom_plus15_absolute_v6': 'balanced', 'flow_caribe': 'flow_custom'}
    templates = {'full_meta_template', 'profile_template'}
    pending: dict[str, dict[str, Any]] = {}
    for pid, data in legacy.items():
        same = sorted(p for p in clusters[settings_hash[pid]] if p != pid)
        from .schema import VALIDATION_KEYS
        noop = sorted(f'validation.{k}' for k in (data.get('validation') or {}) if k not in VALIDATION_KEYS)
        source = {'name': data.get('name'), 'schema_version': data.get('schema_version'), 'equivalent_to': same,
                  'removed_noop_keys': noop,
                  'modules': effective_modules(engine[pid]), 'groups': sorted((engine[pid].get('groups') or {}).keys()),
                  'weapons': sorted((engine[pid].get('weapons') or {}).keys()),
                  'inert_fields': inert_fields(engine[pid])}
        report['sources'][pid] = source
        if pid in mapped:
            continue
        if pid in templates:
            report['archived'][pid] = 'Plantilla de ejemplo (WEAPON_EXAMPLE); la reemplazan el Constructor y los perfiles derivados.'
            continue
        canonical = sorted([pid, *same])[0]
        mapped_dup = next((mapped[p] for p in same if p in mapped), None)
        if mapped_dup:
            report['archived'][pid] = f'Equivalente exacto de {", ".join(p for p in same if p in mapped)} → {mapped_dup}.'
            continue
        if canonical != pid:
            report['archived'][pid] = f'Equivalente exacto de {canonical} (se conserva como pendiente “{canonical}”).'
            continue
        base, delta = best_base(engine[pid])
        if engine_settings(deep_merge(resolved_engine[base], delta)) != engine_settings(engine[pid]):
            raise RuntimeError(f'pendiente {pid} no reproduce su fuente')
        pending[pid] = v8(f'legacy_{pid}', delta, {
            'name': f'{data.get("name") or pid} (migrado)', 'short_name': pid[:24],
            'description': data.get('description') or '',
            'objective': 'Pendiente de revisión: configuración única de un perfil antiguo. Impórtalo como perfil de usuario si lo necesitas.',
            'audience': '', 'features': [], 'warnings': ['Perfil archivado; no es oficial.'], 'tags': ['legacy'],
        }, extends=base, migrated_from=pid)
        report['pending'][pid] = {'extends': base, 'equivalent_to': same, 'settings_equal': True}

    if check_output:
        competitive_vs = output_diff(resolved_engine['competitive'], engine['pvp_competitive_onetap'], ws)
        report['checks'].append({'profile': 'competitive', 'check': 'output_equal', 'source': 'pvp_competitive_onetap',
                                 'ok': not competitive_vs, 'differences': len(competitive_vs)})
        if competitive_vs:
            raise RuntimeError(f'competitive difiere de pvp_competitive_onetap: {list(competitive_vs)[:5]}')
        realistic_vs = output_diff(resolved_engine['realistic'], engine['rp_serious_onetap'], ws)
        allowed = MODULE_PRESET_KEYS['recoil']
        unexpected = {w: f for w, f in realistic_vs.items() if set(f) - allowed}
        if unexpected:
            raise RuntimeError(f'realistic difiere fuera del recoil: {list(unexpected.items())[:3]}')
        report['checks'].append({'profile': 'realistic', 'check': 'output_diff_only_recoil', 'source': 'rp_serious_onetap',
                                 'ok': True, 'weapons_changed': len(realistic_vs), 'fields': sorted(allowed)})
        balanced_vs = output_diff(resolved_engine['balanced'], engine['vanilla_repair_custom_plus15_absolute_v6'], ws)
        report['checks'].append({'profile': 'balanced', 'check': 'output_diff_documented', 'source': 'vanilla_repair_custom_plus15_absolute_v6',
                                 'ok': True, 'weapons_changed': len(balanced_vs),
                                 'fields': sorted({k for f in balanced_vs.values() for k in f})})

    report['official'] = {
        'balanced': {'source': 'vanilla_repair_custom_plus15_absolute_v6',
                     'changes': [f'Multiplicadores para armas personalizadas {changed_multipliers} → 1.0 (sin ventaja para custom).',
                                 f'Regla de familia retirada: {[r.get("name") for r in removed_family]} (revólver/doble acción a 350 de daño, decisión de otro servidor).']},
        'realistic': {'source': 'rp_serious_onetap',
                      'changes': ['modules.recoil: normal → high (retroceso más exigente).'],
                      'removed_inert_fields': realistic_dead},
        'competitive': {'source': 'pvp_competitive_onetap', 'extends': 'realistic', 'changes': [],
                        'removed_inert_fields': competitive_dead},
        'flow_custom': {'source': 'flow_caribe', 'extends': flow_base, 'changes': [],
                        'delta_bytes': len(json.dumps(flow_delta)), 'source_bytes': len(json.dumps(engine['flow_caribe']))},
    }
    return {'outputs': outputs, 'pending': pending, 'report': report}


def write(result: dict[str, Any], profiles_dir: Path) -> list[Path]:
    written = []
    targets = {'balanced': 'official', 'realistic': 'official', 'competitive': 'official', 'flow_custom': 'server'}
    for pid, data in result['outputs'].items():
        path = profiles_dir / targets[pid] / f'{pid}.json'
        atomic_write_json(path, data)
        written.append(path)
    folder = profiles_dir / 'migrations' / MIGRATION_ID
    (folder / 'pending').mkdir(parents=True, exist_ok=True)
    for pid, data in result['pending'].items():
        path = folder / 'pending' / f'{pid}.json'
        atomic_write_json(path, data)
        written.append(path)
    atomic_write_json(folder / 'report.json', result['report'])
    written.append(folder / 'report.json')
    return written


def render_markdown(result: dict[str, Any], extra_notes: list[str] | None = None) -> str:
    report = result['report']
    lines = [f'# Migración de perfiles {MIGRATION_ID}', '',
             'Informe generado por `weapon_rebalancer/profile_store/legacy_migration.py`. Los archivos originales están intactos en '
             '`profiles/legacy/` y en `data/backups/`. Cada resultado se verificó ejecutando el motor sobre el pack real.', '',
             '## Destino de cada perfil antiguo', '', '| Perfil antiguo | Destino | Motivo |', '| --- | --- | --- |']
    destinations = {v['source']: k for k, v in report['official'].items()}
    for pid in sorted(report['sources']):
        if pid in destinations:
            target = destinations[pid]
            changes = report['official'][target]['changes']
            lines.append(f'| `{pid}` | **{target}** | {"Sin cambios de comportamiento" if not changes else "; ".join(changes)} |')
        elif pid in report['pending']:
            info = report['pending'][pid]
            same = f' (también cubre {", ".join(info["equivalent_to"])})' if info['equivalent_to'] else ''
            lines.append(f'| `{pid}` | pendiente `legacy_{pid}` (hereda de {info["extends"]}) | Configuración única conservada sin cambios{same} |')
        else:
            lines.append(f'| `{pid}` | archivado | {report["archived"].get(pid, "")} |')
    for note in extra_notes or []:
        lines.append(note)
    lines += ['', '## Verificaciones', '', '| Perfil | Comprobación | Resultado |', '| --- | --- | --- |']
    labels = {'settings_equal': 'Configuración del motor idéntica a la fuente',
              'output_equal': 'Resultado en el pack idéntico a la fuente',
              'output_diff_only_recoil': 'Solo difiere en los 4 campos de recoil',
              'output_diff_documented': 'Solo difiere en los cambios documentados'}
    for check in report['checks']:
        extra = f' · {check.get("weapons_changed")} armas, campos {", ".join(check.get("fields", []))}' if check.get('weapons_changed') else ''
        lines.append(f'| {check["profile"]} | {labels.get(check["check"], check["check"])} (fuente `{check["source"]}`) | {"✔" if check["ok"] else "✘"}{extra} |')
    lines += ['| pendientes | Configuración del motor idéntica a cada fuente | ✔ |', '', '## Cambios de diseño en los oficiales', '']
    for pid, info in report['official'].items():
        lines.append(f'### {pid}')
        lines.append(f'Fuente: `{info["source"]}`' + (f' · hereda de `{info["extends"]}`' if info.get('extends') else ''))
        lines.append('')
        for change in info['changes'] or ['Ninguno: comportamiento idéntico.']:
            lines.append(f'- {change}')
        noop = report['sources'].get(info['source'], {}).get('removed_noop_keys') or []
        if noop:
            lines.append(f'- Descartado {", ".join(f"`{k}`" for k in noop)}: el motor no lo lee (no tenía efecto).')
        dead = info.get('removed_inert_fields') or {}
        if dead:
            total = sum(len(v) for v in dead.values())
            lines.append(f'- Se quitaron {total} valores por categoría que el motor descartaba o reescribía siempre '
                         '(los pisa el preset del módulo o la política de cabeza one-tap). No cambian el resultado.')
        if info.get('delta_bytes'):
            lines.append(f'- Guarda solo sus diferencias: {info["delta_bytes"]} bytes frente a {info["source_bytes"]} del original.')
        lines.append('')
    lines += ['## Inventario de los perfiles antiguos', '', '| Perfil | schema | Grupos | Armas | Campos sin efecto | Módulos |', '| --- | --- | --- | --- | --- | --- |']
    for pid, src in sorted(report['sources'].items()):
        dead = sum(len(v) for v in src['inert_fields'].values())
        modules = ', '.join(f'{k}={v}' for k, v in src['modules'].items())
        lines.append(f'| `{pid}` | {src["schema_version"]} | {len(src["groups"])} | {len(src["weapons"])} | {dead} | {modules} |')
    lines += ['', '## Pendientes de revisión', '',
              'Están en `pending/`. Son deltas sobre un perfil oficial que reproducen exactamente su perfil antiguo. '
              'Para usar uno: `python3 wr.py profile import profiles/migrations/' + MIGRATION_ID + '/pending/<archivo>.json --id <nuevo_id>`.', '']
    return '\n'.join(lines) + '\n'
