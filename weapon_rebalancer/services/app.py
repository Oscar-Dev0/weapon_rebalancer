"""Fachada de la aplicación: une catálogo, perfiles, vista previa, simulador y generador.

La API HTTP y las herramientas de línea de comandos usan esta clase; no contiene
lógica de presentación.
"""
from __future__ import annotations

import threading
import time
from collections import OrderedDict
from pathlib import Path
from typing import Any

from ..core.errors import NotFound, ValidationFailed
from ..core.workspace import Workspace, load_workspace
from ..profile_store.migrations import migrate
from ..profile_store.repository import ProfileRepository
from ..profile_store.resolver import resolve, to_engine
from ..profile_store.schema import structural_issues
from . import simulator
from .catalog import CatalogService
from .diagnostics import RuntimeAuditCache, build_diagnostics
from .generator import Plan, PlanStore, apply_plan, build_plan, file_diff, generate_guard, list_transactions, rollback
from .preview import build_settings, canonical_hash, preview

VERSION_FILE = Path(__file__).resolve().parents[2] / 'VERSION'


def version() -> str:
    try:
        return VERSION_FILE.read_text(encoding='utf-8').strip()
    except OSError:
        return 'desconocida'


def flatten(data: Any, prefix: str = '') -> dict[str, Any]:
    if isinstance(data, dict):
        result: dict[str, Any] = {}
        for key, value in data.items():
            result.update(flatten(value, f'{prefix}.{key}' if prefix else str(key)))
        if not data and prefix:
            result[prefix] = {}
        return result
    return {prefix: data}


class App:
    def __init__(self) -> None:
        self.repo = ProfileRepository(server_editable=lambda: load_workspace().server_profiles_editable)
        self.catalog = CatalogService(load_workspace)
        self.plans = PlanStore()
        self.runtime = RuntimeAuditCache()
        self._previews: OrderedDict[str, dict[str, Any]] = OrderedDict()
        self._preview_lock = threading.Lock()
        self.started_at = time.time()

    # ---- workspace ---------------------------------------------------------------
    def workspace(self) -> Workspace:
        return load_workspace()

    # ---- perfiles -----------------------------------------------------------------
    def profile_input(self, body: dict[str, Any]) -> tuple[str | None, dict[str, Any]]:
        """Acepta {profile_id} o {profile: {...}} (borrador sin guardar)."""
        if isinstance(body.get('profile'), dict):
            profile_id = body.get('profile_id') or (body['profile'].get('profile') or {}).get('id') or 'borrador'
            migrated, _ = migrate(body['profile'], str(profile_id))
            return body.get('profile_id'), migrated
        profile_id = body.get('profile_id') or self.workspace().active_profile
        return str(profile_id), self.repo.load(str(profile_id))

    def resolved(self, profile: dict[str, Any]) -> dict[str, Any]:
        return self.repo.resolved(profile)

    def base_resolved(self, profile: dict[str, Any]) -> dict[str, Any] | None:
        """Perfil base ya resuelto (lo que se hereda), o None si no hay base o la cadena es inválida."""
        parent = (profile.get('profile') or {}).get('extends')
        if not parent:
            return None
        try:
            return self.repo.resolved(str(parent))
        except (ValidationFailed, NotFound):
            return None

    def validate_profile(self, profile: dict[str, Any]) -> dict[str, Any]:
        """Validación estructural del perfil resuelto + validación del motor. La usan web y terminal."""
        engine_error = None
        try:
            resolved = self.resolved(profile)
        except ValidationFailed as exc:
            issue = {'code': 'inheritance', 'severity': 'error', 'message': exc.message, 'fix': exc.hint or ''}
            return {'valid': False, 'issues': [issue], 'engine_error': exc.message}
        issues = structural_issues(resolved)
        if not (profile.get('profile') or {}).get('extends'):
            issues.extend(i for i in structural_issues(profile) if i['code'] == 'null_without_parent' and i not in issues)
        try:
            ws = self.workspace()
            build_settings(to_engine(resolved), ws.pack_paths[0] if ws.pack_paths else Path('.'), ws)
        except ValidationFailed as exc:
            engine_error = exc.message
            issues.append({'code': 'engine_rejected', 'severity': 'error', 'message': exc.message, 'fix': exc.hint or ''})
        return {'valid': not any(i['severity'] == 'error' for i in issues), 'issues': issues, 'engine_error': engine_error}

    # ---- vista previa ---------------------------------------------------------------
    def preview_profile(self, profile: dict[str, Any], profile_id: str | None) -> dict[str, Any]:
        resolved = self.resolved(profile)
        engine_profile = to_engine(resolved)
        catalog = self.catalog.get()
        key = canonical_hash({'p': engine_profile, 'sig': catalog.signature, 'r': resolved.get('resources')})
        with self._preview_lock:
            cached = self._previews.get(key)
            if cached is not None:
                self._previews.move_to_end(key)
                return cached
        result = preview(engine_profile, self.workspace(), catalog, profile_id=profile_id).data
        result['structural_issues'] = structural_issues(resolved)
        with self._preview_lock:
            self._previews[key] = result
            while len(self._previews) > 8:
                self._previews.popitem(last=False)
        return result

    # ---- comparador ---------------------------------------------------------------
    def side_values(self, side: dict[str, Any]) -> tuple[str, dict[str, dict[str, Any]], dict[str, Any] | None]:
        """Valores por arma de un lado de la comparación: original (.bak), actual o un perfil."""
        catalog = self.catalog.get()
        source = side.get('source')
        if source in {'original', 'current'}:
            values = {}
            for name, defs in catalog.definitions.items():
                values[name] = (defs[-1].original or defs[-1].values) if source == 'original' else defs[-1].values
            return ('Original (.bak)' if source == 'original' else 'Actual (META)'), values, None
        profile_id, profile = self.profile_input(side)
        preview_data = self.preview_profile(profile, profile_id)
        values = {}
        for name, defs in catalog.definitions.items():
            entry = preview_data['weapons'].get(name) or {}
            values[name] = entry.get('proposed') or defs[-1].values
        return profile_id or 'borrador', values, {'id': profile_id, 'profile': profile, 'preview': preview_data}

    def compare(self, a: dict[str, Any], b: dict[str, Any], *, weapons: list[str] | None = None,
                keys: list[str] | None = None) -> dict[str, Any]:
        """Diferencias de resultado (y de JSON si ambos lados son perfiles) con dirección y procedencia."""
        label_a, values_a, info_a = self.side_values(a)
        label_b, values_b, info_b = self.side_values(b)
        structural = None
        if info_a and info_b:
            flat_a = flatten({k: v for k, v in self.resolved(info_a['profile']).items() if k != 'profile'})
            flat_b = flatten({k: v for k, v in self.resolved(info_b['profile']).items() if k != 'profile'})
            structural = {
                'added': sorted(k for k in flat_b if k not in flat_a),
                'removed': sorted(k for k in flat_a if k not in flat_b),
                'changed': [{'path': k, 'a': flat_a[k], 'b': flat_b[k]} for k in sorted(flat_a) if k in flat_b and flat_a[k] != flat_b[k]],
            }
        wanted = {w.upper() for w in weapons} if weapons else None
        effects = []
        for name in sorted(set(values_a) | set(values_b)):
            if wanted is not None and name not in wanted:
                continue
            va, vb = values_a.get(name, {}), values_b.get(name, {})
            fields = {}
            for key in sorted(set(va) | set(vb)):
                if keys and key not in keys:
                    continue
                left, right = va.get(key), vb.get(key)
                if left == right and not wanted:
                    continue
                direction = 'same'
                if isinstance(left, (int, float)) and isinstance(right, (int, float)) and not isinstance(left, bool):
                    direction = 'up' if right > left + 1e-9 else 'down' if right < left - 1e-9 else 'same'
                elif left != right:
                    direction = 'changed'
                fields[key] = {'a': left, 'b': right, 'direction': direction}
            if fields:
                effects.append({'weapon': name, 'fields': fields})
        if wanted:
            for effect in effects:
                for side_key, info in (('a', info_a), ('b', info_b)):
                    if info:
                        explained = self.explain(effect['weapon'], {'profile_id': info['id'], 'profile': info['profile']},
                                                 keys=list(effect['fields']))
                        for key, item in explained['fields'].items():
                            effect['fields'][key][f'{side_key}_status'] = item['status']
                            effect['fields'][key][f'{side_key}_source'] = item['label']
        summary = {'weapons_affected': len([e for e in effects if any(f['direction'] != 'same' for f in e['fields'].values())])}
        if structural is not None:
            summary['structural_changes'] = sum(len(v) for v in structural.values())
        return {'a': label_a, 'b': label_b, 'structural': structural, 'effects': effects, 'summary': summary}

    # ---- explicación, tabla de armas y edición ---------------------------------------
    def chain(self, profile: dict[str, Any]) -> list[dict[str, Any]]:
        from ..profile_store.resolver import chain_of

        return chain_of(profile, self.repo.load)

    def explain(self, weapon: str, body: dict[str, Any], *, keys: list[str] | None = None) -> dict[str, Any]:
        from ..catalog.params import PARAMS
        from .provenance import explain_weapon

        profile_id, profile = self.profile_input(body)
        catalog = self.catalog.get()
        name = weapon.upper()
        defs = catalog.definitions.get(name)
        if not defs:
            raise NotFound(f'{name} no tiene weapons.meta: no hay valores que explicar.')
        resolved = self.resolved(profile)
        preview_data = self.preview_profile(profile, profile_id)
        entry = preview_data['weapons'].get(name) or {}
        current = defs[-1].values
        original = defs[-1].original or current
        numeric = [k for k, spec in PARAMS.items() if spec.value_type in {'number', 'integer'}]
        keys = keys or [k for k in numeric if k in current or k in (entry.get('proposed') or {})]
        fields = explain_weapon(name, defs[-1].group, self.chain(profile), resolved, original, current,
                                entry.get('proposed'), bool(entry.get('processed')), keys,
                                is_custom=(catalog.weapons.get(name) or {}).get('custom'))
        return {'weapon': name, 'profile': profile_id, 'chain': resolved['profile'].get('resolved_chain'),
                'processed': bool(entry.get('processed')), 'skipped_reason': entry.get('skipped_reason'), 'fields': fields}

    def weapon_rows(self, body: dict[str, Any]) -> dict[str, Any]:
        """Tabla de armas con el perfil aplicado (la usan el Armamento web y `wr.py weapons`)."""
        profile_id, profile = self.profile_input(body)
        catalog = self.catalog.get()
        preview_data = self.preview_profile(profile, profile_id)
        problem_weapons: dict[str, int] = {}
        for issue in preview_data['issues']:
            for name in issue.get('weapons') or []:
                problem_weapons[name] = problem_weapons.get(name, 0) + 1
            path = issue.get('path') or ''
            if path.startswith('weapon:'):
                name = path.split(':', 1)[1].split('.', 1)[0]
                problem_weapons[name] = problem_weapons.get(name, 0) + 1
        rows = []
        from .catalog import effective_rpm

        for weapon in catalog.weapons.values():
            if weapon['internal']:
                continue
            entry = preview_data['weapons'].get(weapon['name']) or {}
            changes = entry.get('changes') or {}
            proposed = entry.get('proposed')
            if not weapon['in_meta']:
                state = 'sin META'
            elif not entry:
                state = 'no la toca'
            elif not entry.get('processed'):
                state = 'omitida'
            else:
                state = f'cambia {len(changes)}' if changes else 'al día'
            issues = weapon['issue_count'] if 'issue_count' in weapon else len(weapon['issues'])
            validation = 'error' if weapon['severity'] == 'error' else ('aviso' if weapon['severity'] == 'warning' or problem_weapons.get(weapon['name']) else 'ok')
            rows.append({
                'name': weapon['name'], 'label': weapon['label'], 'category': weapon['category']['label'],
                'category_id': weapon['category']['id'], 'custom': weapon['custom'], 'in_ox': weapon['in_ox'], 'in_meta': weapon['in_meta'],
                'damage_original': weapon['original'].get('damage'), 'damage_current': weapon['current'].get('damage'),
                'damage_effective': (proposed or {}).get('damage', weapon['current'].get('damage')),
                'rpm': weapon['rpm'], 'rpm_effective': effective_rpm(proposed) if proposed else weapon['rpm'],
                'profile_state': state, 'changes': len(changes), 'validation': validation, 'issues': issues,
            })
        return {'profile': profile_id, 'rows': rows, 'summary': preview_data['summary']}

    def apply_ops(self, body: dict[str, Any]) -> dict[str, Any]:
        """Aplica operaciones de edición a un perfil (o borrador) SIN guardar. Web y terminal."""
        from ..profile_store.edit import apply_ops, summarize_changes

        profile_id, profile = self.profile_input(body)
        result = apply_ops(profile, body.get('ops') or [], resolver=self.resolved,
                           confirm_dormant=bool(body.get('confirm_dormant', False)))
        result['changes'] = summarize_changes(profile, result['profile'])
        result['validation'] = self.validate_profile(result['profile'])
        result['base'] = self.base_resolved(result['profile'])
        result['profile_id'] = profile_id
        return result

    def save_profile(self, profile_id: str, profile: dict[str, Any], *, sha: str | None, note: str = '',
                     allow_invalid: bool = False) -> dict[str, Any]:
        validation = self.validate_profile(profile)
        if not validation['valid'] and not allow_invalid:
            raise ValidationFailed('El perfil tiene errores bloqueantes y no se guardó.', details=validation['issues'])
        result = self.repo.save(profile_id, profile, expected_sha=sha, note=note[:200])
        return {**result, 'validation': validation}

    def affected(self, body: dict[str, Any]) -> list[dict[str, Any]]:
        profile_id, profile = self.profile_input(body)
        data = self.preview_profile(profile, profile_id)
        return [{'weapon': name, 'group': entry.get('group'), 'fields': sorted(entry.get('changes') or {})}
                for name, entry in sorted(data['weapons'].items()) if entry.get('changes')]

    def activate(self, profile_id: str) -> dict[str, Any]:
        from ..core.workspace import update_workspace

        validation = self.validate_profile(self.repo.load(profile_id))
        if not validation['valid']:
            raise ValidationFailed(f'“{profile_id}” tiene errores bloqueantes: no se puede activar.', details=validation['issues'])
        ws = update_workspace({'active_profile': profile_id})
        return {'active_profile': ws.active_profile, 'validation': validation}

    # ---- simulador ---------------------------------------------------------------
    def weapon_values(self, name: str, source: str, proposed_preview: dict[str, Any] | None) -> dict[str, Any]:
        catalog = self.catalog.get()
        defs = catalog.definitions.get(name.upper())
        if not defs:
            raise NotFound(f'{name} no tiene weapons.meta: no hay datos para simular.')
        current = defs[-1].values
        if source == 'original':
            return defs[-1].original or current
        if source == 'proposed':
            entry = (proposed_preview or {}).get('weapons', {}).get(name.upper())
            if entry and entry.get('proposed'):
                return entry['proposed']
            return current
        return current

    def simulate(self, body: dict[str, Any]) -> dict[str, Any]:
        assumptions = simulator.Assumptions.parse(body.get('assumptions'))
        requests = body.get('weapons') or []
        if not isinstance(requests, list) or not requests:
            raise ValidationFailed('Indica al menos un arma para simular.')
        if len(requests) > 8:
            raise ValidationFailed('Máximo 8 series por simulación.')
        needs_preview = any(isinstance(r, dict) and r.get('source') == 'proposed' for r in requests)
        proposed = None
        if needs_preview:
            profile_id, profile = self.profile_input(body)
            proposed = self.preview_profile(profile, profile_id)
        results = []
        for request in requests:
            if not isinstance(request, dict) or not request.get('name'):
                raise ValidationFailed('Cada serie necesita {name, source}.')
            source = request.get('source', 'current')
            if source not in {'current', 'original', 'proposed'}:
                raise ValidationFailed('source debe ser current, original o proposed.')
            values = self.weapon_values(str(request['name']), source, proposed)
            item = {'name': str(request['name']).upper(), 'source': source,
                    'result': simulator.simulate_weapon(values, assumptions)}
            if body.get('series', True):
                item['series'] = simulator.distance_series(values, assumptions, body.get('max_distance'))
            results.append(item)
        return {'assumptions': assumptions.__dict__, 'results': simulator.compare(results),
                'disclaimer': 'Cálculo teórico a partir del META. No sustituye una prueba de daño en el servidor.'}

    # ---- diagnóstico ---------------------------------------------------------------
    def diagnostics(self, *, refresh_runtime: bool = False, include_runtime: bool = True) -> dict[str, Any]:
        ws = self.workspace()
        catalog = self.catalog.get()
        runtime = self.runtime.get(ws, refresh=refresh_runtime) if include_runtime and ws.runtime_path.is_dir() else None
        active_preview = None
        if self.repo.exists(ws.active_profile):
            try:
                active_preview = self.preview_profile(self.repo.load(ws.active_profile), ws.active_profile)
            except ValidationFailed:
                active_preview = None
        return build_diagnostics(ws, catalog, self.repo, runtime, active_preview)

    # ---- generador ---------------------------------------------------------------
    def plan(self, body: dict[str, Any]) -> dict[str, Any]:
        profile_id, profile = self.profile_input(body)
        resolved = self.resolved(profile)
        validation = self.validate_profile(profile)
        if not validation['valid']:
            raise ValidationFailed('El perfil tiene errores; corrígelos antes de generar.', details=validation['issues'])
        plan = build_plan(to_engine(resolved), resolved.get('resources'), self.workspace(), self.catalog.get(), profile_id)
        self.plans.put(plan)
        data = dict(plan.preview)
        data['files_detail'] = [{'path': path, 'kind': plan.kinds[path]} for path in sorted(plan.files)]
        return data

    def plan_diff(self, plan_hash: str, path: str) -> dict[str, Any]:
        plan: Plan = self.plans.get(plan_hash)
        return {'path': path, 'diff': file_diff(plan, path)}

    def apply(self, body: dict[str, Any]) -> dict[str, Any]:
        plan = self.plans.get(str(body.get('plan_hash', '')))
        result = apply_plan(plan, self.workspace(), str(body.get('confirm', '')))
        self.catalog.invalidate()
        with self._preview_lock:
            self._previews.clear()
        return result

    def rollback(self, body: dict[str, Any]) -> dict[str, Any]:
        result = rollback(str(body.get('id', '')), self.workspace(), str(body.get('confirm', '')))
        self.catalog.invalidate()
        with self._preview_lock:
            self._previews.clear()
        return result

    def transactions(self) -> list[dict[str, Any]]:
        return list_transactions()

    def guard(self, body: dict[str, Any]) -> dict[str, Any]:
        ws = self.workspace()
        destination = Path(str(body.get('destination') or ws.guard_destination or ''))
        if not str(destination) or str(destination) == '.':
            raise ValidationFailed('Indica la carpeta destino del guard (dentro de resources/).')
        source = body.get('source', 'current')
        catalog = self.catalog.get()
        expected: dict[str, float] = {}
        proposed = None
        if source == 'proposed':
            profile_id, profile = self.profile_input(body)
            proposed = self.preview_profile(profile, profile_id)
        for name, defs in catalog.definitions.items():
            values = defs[-1].values
            if proposed and proposed['weapons'].get(name, {}).get('proposed'):
                values = proposed['weapons'][name]['proposed']
            damage = values.get('damage')
            if isinstance(damage, (int, float)) and not isinstance(damage, bool) and damage > 0:
                expected[name] = float(damage)
        return generate_guard(destination, expected, ws, str(body.get('confirm', '')))

    # ---- estado ---------------------------------------------------------------
    def status(self) -> dict[str, Any]:
        ws = self.workspace()
        catalog = self.catalog.get()
        transactions = list_transactions()
        return {
            'version': version(),
            'started_at': self.started_at,
            'workspace': ws.to_dict(),
            'catalog': catalog.summary(),
            'profiles': len(self.repo.ids()),
            'active_profile': ws.active_profile,
            'active_exists': self.repo.exists(ws.active_profile),
            'last_transaction': transactions[0] if transactions else None,
        }
