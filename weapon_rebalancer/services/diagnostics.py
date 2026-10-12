"""Diagnóstico: reúne problemas de rutas, inventario, packs, perfiles y scripts runtime."""
from __future__ import annotations

import re
import threading
import time
from pathlib import Path
from typing import Any

from ..engine.config import Settings
from ..core.workspace import Workspace, validate_workspace
from ..engine.profile_loader import ProfileError, apply_external_profile
from ..profile_store.migrations import is_legacy
from ..profile_store.resolver import to_engine
from ..profile_store.schema import structural_issues
from ..runtime.audit import scan_runtime_conflicts

_IF_RE = re.compile(r'^\s*(?:if|elseif)\s+(.+?)\s+then\b')
_FIXES = {
    'critical_hits_disabled': 'Quita o condiciona la llamada con false, o instala os_headshot_guard después de ese recurso.',
    'critical_hits_disabled_native_hash': 'Igual que la anterior: el hash es SetPedSuffersCriticalHits.',
    'critical_hits_disabled_csharp_hash': 'Igual que la anterior, en C#.',
    'weapon_damage_forced_zero': 'Un modificador 0 anula cualquier META. Revisa ese recurso.',
    'weapon_damage_event_cancelled': 'Si el recurso es un minijuego o arena, es esperado; si no, cancela el daño de todas las armas.',
    'damage_event_health_or_armour_restore': 'Normal en arenas o minijuegos que gestionan su propia vida; revisa si afecta al juego libre.',
    'ped_armour_write': 'Normal en chalecos y spawns. Solo preocupa si restaura armadura justo después de un disparo.',
    'ped_health_write': 'Normal en curaciones/revive. Solo preocupa si se ejecuta en eventos de daño.',
    'runtime_damage_modifier': 'Otro recurso cambia el daño en ejecución: el resultado no será el del META.',
    'critical_hits_dynamic_toggle': 'Confirma que el valor nunca termine en false para jugadores.',
    'critical_hits_enabled': 'Informativo: este recurso activa critical hits.',
}


def _condition_hint(resources: Path, relative: str, line: int) -> str | None:
    """Si la llamada está dentro de un `if`, devuelve la condición (p. ej. config.disable.headshots)."""
    try:
        lines = (resources / relative).read_text(encoding='utf-8', errors='ignore').splitlines()
    except OSError:
        return None
    for index in range(line - 2, max(-1, line - 6), -1):
        match = _IF_RE.match(lines[index]) if 0 <= index < len(lines) else None
        if match:
            return match.group(1).strip()
    return None


class RuntimeAuditCache:
    """La auditoría runtime recorre miles de archivos (~8 s): se cachea hasta pedir refresco."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._data: dict[str, Any] | None = None

    def get(self, ws: Workspace, *, refresh: bool = False) -> dict[str, Any]:
        with self._lock:
            if self._data is not None and not refresh and self._data.get('root') == str(ws.runtime_path):
                return self._data
            started = time.perf_counter()
            report = scan_runtime_conflicts(ws.runtime_path)
            findings = []
            for item in report.findings:
                condition = _condition_hint(ws.runtime_path, item.path, item.line)
                findings.append({
                    'code': item.code, 'severity': item.severity, 'path': item.path, 'line': item.line,
                    'description': item.description, 'snippet': item.snippet, 'condition': condition,
                    'fix': _FIXES.get(item.code, ''),
                })
            self._data = {
                'root': str(ws.runtime_path), 'scanned_at': time.time(),
                'duration_ms': int((time.perf_counter() - started) * 1000),
                'files_scanned': report.files_scanned, 'hard': report.hard_blockers,
                'warnings': report.warnings, 'info': report.info, 'findings': findings,
            }
            return self._data


def profile_checks(repo: Any) -> list[dict[str, Any]]:
    results = []
    for profile_id in repo.ids():
        entry: dict[str, Any] = {'id': profile_id, 'issues': []}
        try:
            raw, _ = repo.read_raw(profile_id)
            entry['legacy'] = is_legacy(raw)
            profile = repo.load(profile_id)
            entry['issues'].extend(structural_issues(profile))
            extends = (profile.get('profile') or {}).get('extends')
            if extends and not repo.exists(extends):
                entry['issues'].append({'code': 'extends_missing', 'severity': 'error',
                                        'message': f'Hereda de “{extends}”, que no existe.',
                                        'fix': 'Corrige la herencia o restaura el perfil base.'})
            else:
                resolved = repo.resolved(profile)
                apply_external_profile(Settings.from_config(), to_engine(resolved))
        except ProfileError as exc:
            entry['issues'].append({'code': 'engine_rejected', 'severity': 'error', 'message': str(exc),
                                    'fix': 'Corrige el campo indicado.'})
        except Exception as exc:  # noqa: BLE001
            entry['issues'].append({'code': 'profile_error', 'severity': 'error', 'message': str(getattr(exc, 'message', exc))})
        results.append(entry)
    return results


def build_diagnostics(ws: Workspace, catalog: Any, repo: Any, runtime: dict[str, Any] | None,
                      active_preview: dict[str, Any] | None) -> dict[str, Any]:
    sections: list[dict[str, Any]] = []

    workspace_errors = validate_workspace(ws)
    sections.append({
        'id': 'workspace', 'title': 'Configuración y rutas',
        'issues': [{'code': 'workspace', 'severity': 'error', 'message': msg, 'fix': 'Corrígelo en Configuración.'} for msg in workspace_errors],
    })

    grouped: dict[str, dict[str, Any]] = {}
    for weapon in catalog.weapons.values():
        if weapon['internal']:
            continue
        for item in weapon['issues']:
            bucket = grouped.setdefault(item['code'], {'code': item['code'], 'severity': item['severity'],
                                                       'message': item['message'], 'fix': item.get('fix', ''),
                                                       'weapons': []})
            bucket['weapons'].append(weapon['name'])
    for bucket in grouped.values():
        if len(bucket['weapons']) > 1:
            bucket['message'] = _GROUP_MESSAGES.get(bucket['code'], bucket['message'])
    order = {'error': 0, 'warning': 1, 'info': 2}
    sections.append({
        'id': 'catalog', 'title': 'Armamento (ox_inventory + weapons.meta)',
        'issues': sorted([*catalog.global_issues, *grouped.values()], key=lambda i: (order.get(i['severity'], 9), -len(i.get('weapons', [])))),
    })

    profiles = profile_checks(repo)
    sections.append({
        'id': 'profiles', 'title': 'Perfiles',
        'profiles': profiles,
        'issues': [
            {**issue, 'message': f'[{p["id"]}] {issue["message"]}', 'profile': p['id']}
            for p in profiles for issue in p['issues']
        ],
    })

    active_issues: list[dict[str, Any]] = []
    if not repo.exists(ws.active_profile):
        active_issues.append({'code': 'active_missing', 'severity': 'error',
                              'message': f'El perfil activo “{ws.active_profile}” no existe.', 'fix': 'Elige otro en Configuración.'})
    elif active_preview is not None:
        files_changed = active_preview['summary']['files_changed']
        if files_changed:
            active_issues.append({
                'code': 'pack_differs', 'severity': 'warning',
                'message': f'El pack no coincide con el perfil activo: aplicarlo cambiaría {files_changed} archivo(s) y '
                           f'{active_preview["summary"]["weapons_changed"]} arma(s).',
                'fix': 'Revisa el Generador: o aplicas el perfil o actualizas el perfil con los cambios manuales.',
            })
        else:
            active_issues.append({'code': 'pack_matches', 'severity': 'ok',
                                  'message': 'El pack coincide exactamente con el perfil activo.'})
        active_issues.extend(active_preview.get('issues', []))
    sections.append({'id': 'active', 'title': f'Perfil activo ({ws.active_profile}) frente al pack', 'issues': active_issues})

    if runtime is not None:
        sections.append({
            'id': 'runtime', 'title': 'Scripts que alteran el daño en ejecución',
            'runtime': {k: v for k, v in runtime.items() if k != 'findings'},
            'issues': [
                {'code': f['code'], 'severity': {'hard': 'error', 'warning': 'warning'}.get(f['severity'], 'info'),
                 'message': f'{f["path"]}:{f["line"]} — {f["description"]}', 'fix': f['fix'],
                 'snippet': f['snippet'], 'condition': f['condition'], 'path': f['path'], 'line': f['line']}
                for f in runtime['findings']
            ],
        })

    totals = {'error': 0, 'warning': 0, 'info': 0}
    for section in sections:
        for item in section['issues']:
            if item.get('severity') in totals:
                totals[item['severity']] += 1
    return {'generated_at': time.time(), 'totals': totals, 'sections': sections}


_GROUP_MESSAGES = {
    'ox_without_meta': 'Armas registradas en ox_inventory sin weapons.meta en los packs configurados.',
    'meta_without_ox': 'Armas con weapons.meta que no están registradas en ox_inventory.',
    'duplicate_definition': 'Armas con más de una definición CWeaponInfo (gana la última que carga).',
    'ox_duplicate_key': 'Armas repetidas en ox_inventory/data/weapons.lua.',
    'repeated_tags': 'Bloques con tags directos repetidos.',
    'headshot_onetap': 'Armas que matan de un tiro a la cabeza sin blindaje (≥ 100 pts estimados).',
    'projectile': 'Armas de proyectil (el daño depende de AmmoInfo/explosión).',
    'no_group': 'Armas sin <Group> en el META.',
    'falloff_inverted': 'Armas con la caída de daño invertida.',
    'no_backup': 'META sin .bak (el original es el valor actual).',
    'meta_unregistered': 'META que no aparecen en ningún WEAPONINFO_FILE.',
    'zero_damage': 'Armas de fuego con daño 0.',
    'zero_network_modifier': 'Armas que no hacen daño a jugadores (modificador de red 0).',
    'ammo_unknown': 'Armas con una munición que no existe en ox_inventory.',
}
