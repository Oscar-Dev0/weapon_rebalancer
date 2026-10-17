"""Comandos no interactivos de `wr.py`. Toda la lógica vive en `services.App` (la misma que usa la web)."""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

from ..core.errors import AppError, ValidationFailed
from . import ui
from .term import Term

# Campos que muestran por defecto la ficha del arma y el comparador.
KEY_FIELDS = ['damage', 'network_player_damage_modifier', 'network_headshot', 'hit_limbs', 'weapon_range', 'falloff_min',
              'falloff_max', 'falloff_modifier', 'time_between_shots', 'anim_fire_rate_modifier', 'clip_size',
              'reload_time_mp', 'accuracy_spread', 'recoil_accuracy_max', 'recoil_shake_amplitude', 'recoil_recovery_rate',
              'bullets_in_batch', 'lightly_armoured']


def emit_json(data: Any) -> None:
    sys.stdout.write(json.dumps(data, ensure_ascii=False, indent=2, default=str) + '\n')


def profile_body(app, profile: str | None) -> dict[str, Any]:
    return {'profile_id': profile or app.workspace().active_profile}


def parse_value(text: str) -> Any:
    lowered = text.strip().lower()
    if lowered in {'inherit', 'heredar', 'null'}:
        return None
    if lowered in {'true', 'sí', 'si', 'yes'}:
        return True
    if lowered in {'false', 'no'}:
        return False
    try:
        number = float(text)
        return int(number) if number.is_integer() and '.' not in text else number
    except ValueError:
        return text


# ---- estado -------------------------------------------------------------------
def status_data(app) -> dict[str, Any]:
    status = app.status()
    active = status['active_profile']
    validation = {'valid': False, 'issues': []}
    pending = None
    name = active
    if app.repo.exists(active):
        profile = app.repo.load(active)
        name = (profile.get('profile') or {}).get('name') or active
        validation = app.validate_profile(profile)
        try:
            pending = app.preview_profile(profile, active)['summary']['files_changed']
        except AppError:
            pending = None
    try:
        integrity_data = app.integrity_check({'server': 'local'})
    except AppError:
        integrity_data = None
    return {'status': status, 'active_name': name, 'validation': validation, 'pending_files': pending,
            'integrity': integrity_data}


def integrity_text(term: Term, data: dict[str, Any] | None) -> str:
    if not data:
        return 'N/D'
    if not data['sealed']:
        return ui.badge(term, 'warning', 'sin sello (wr.py integrity seal --reason …)')
    if data['clean']:
        return ui.badge(term, 'ok', 'ninguno desde el último sello')
    return ui.badge(term, 'warning', f'{data["total"]} archivo(s) cambiados fuera de la herramienta (wr.py integrity)')


def render_status(app, term: Term, data: dict[str, Any] | None = None) -> None:
    data = data or status_data(app)
    status, catalog = data['status'], data['status']['catalog']
    ox = catalog.get('ox') or {}
    validation = data['validation']
    errors = sum(1 for i in validation['issues'] if i['severity'] == 'error')
    warnings = sum(1 for i in validation['issues'] if i['severity'] == 'warning')
    if errors:
        valid = ui.badge(term, 'error', f'{errors} bloqueantes')
    elif warnings:
        valid = ui.badge(term, 'warning', f'Correcta con {warnings} advertencias')
    else:
        valid = ui.badge(term, 'ok', 'Correcta')
    pending = data['pending_files']
    pending_text = 'N/D' if pending is None else (ui.badge(term, 'ok', 'Ninguno: el pack coincide') if pending == 0
                                                  else ui.badge(term, 'warning', f'{pending} archivo(s) por aplicar'))
    ui.section(term, 'Estado del servidor')
    ui.kv(term, [
        ('Inventario', f'ox_inventory {term.style(f"({ox.get("weapons", 0)} ítems de arma)", "muted")}' if ox else ui.badge(term, 'error', 'no configurado')),
        ('Armas', f'{term.style(catalog["weapons"], "value")} detectadas {term.style(f"· {catalog["custom"]} personalizadas · {catalog["meta_files"]} META", "muted")}'),
        ('Perfil activo', f'{term.style(data["active_name"], "accent")} {term.style(f"({status["active_profile"]})", "muted")}'),
        ('Validación', valid),
        ('Cambios pendientes', pending_text),
        ('Cambios a mano', integrity_text(term, data.get('integrity'))),
    ])


def cmd_status(app, term: Term, args) -> int:
    data = status_data(app)
    if args.json:
        emit_json(data)
        return 0
    render_status(app, term, data)
    return 0


# ---- armas -------------------------------------------------------------------
def weapons_columns(term: Term) -> list[ui.Column]:
    def state_style(row, cell):
        state = row['profile_state']
        role = 'accent' if state.startswith('cambia') else 'ok' if state == 'al día' else 'muted'
        return term.style(cell, role)

    def valid_style(row, cell):
        return term.style(cell, {'ok': 'ok', 'aviso': 'warn', 'error': 'err'}.get(row['validation'], 'muted'))

    def damage_style(row, cell):
        a, b = row['damage_current'], row['damage_effective']
        if isinstance(a, (int, float)) and isinstance(b, (int, float)) and abs(a - b) > 1e-6:
            return term.style(cell, 'ok' if b > a else 'err')
        return cell

    return [
        ui.Column('Identificador', 'name', max_width=30),
        ui.Column('Nombre', 'label', max_width=24),
        ui.Column('Categoría', 'category', max_width=20),
        ui.Column('Daño orig.', 'damage_original', align='right', min_width=9),
        ui.Column('Daño perfil', 'damage_effective', align='right', min_width=10, style=damage_style),
        ui.Column('RPM', lambda r: round(r['rpm_effective']) if r['rpm_effective'] else None, align='right', min_width=5),
        ui.Column('Perfil', 'profile_state', max_width=12, style=state_style),
        ui.Column('Estado', lambda r: {'ok': f'{term.sym["ok"]} ok', 'aviso': f'{term.sym["warn"]} aviso', 'error': f'{term.sym["err"]} error'}[r['validation']],
                  max_width=9, style=valid_style),
    ]


def filter_rows(rows: list[dict[str, Any]], *, query: str = '', category: str = '', changed: bool = False) -> list[dict[str, Any]]:
    q = query.lower()
    result = []
    for row in rows:
        if q and q not in f'{row["name"]} {row["label"]}'.lower():
            continue
        if category and category.lower() not in (row['category_id'], row['category'].lower()):
            continue
        if changed and not row['changes']:
            continue
        result.append(row)
    return result


def cmd_weapons(app, term: Term, args) -> int:
    data = app.weapon_rows(profile_body(app, args.profile))
    rows = filter_rows(data['rows'], query=args.search or '', category=args.category or '', changed=args.changed)
    if not args.all:
        rows = [r for r in rows if r['in_meta']]
    rows.sort(key=lambda r: (r['category'], r['name']))
    if args.json:
        emit_json({'profile': data['profile'], 'rows': rows[: args.limit] if args.limit else rows})
        return 0
    ui.section(term, 'Armamento', f'perfil {data["profile"]} · {len(rows)} armas')
    ui.table(term, weapons_columns(term), rows[: args.limit] if args.limit else rows)
    if args.limit and len(rows) > args.limit:
        term.write('  ' + term.style(f'… {len(rows) - args.limit} más (usa --limit 0 para verlas todas)', 'muted'))
    return 0


def render_explain(term: Term, data: dict[str, Any], params: dict[str, Any]) -> None:
    rows = []
    for key, item in data['fields'].items():
        spec = params.get(key) or {}
        rows.append({**item, 'key': key, 'param': spec.get('label', key), 'unit': spec.get('unit', ''), 'source': item.get('label')})

    def eff_style(row, cell):
        a, b = row.get('current'), row.get('effective')
        if isinstance(a, (int, float)) and isinstance(b, (int, float)) and abs(a - b) > 1e-6:
            return term.style(cell, 'accent')
        return cell

    ui.table(term, [
        ui.Column('Parámetro', 'param', max_width=34),
        ui.Column('Original', 'original', align='right', min_width=8),
        ui.Column('Actual', 'current', align='right', min_width=8),
        ui.Column('Efectivo', 'effective', align='right', min_width=8, style=eff_style),
        ui.Column('Unidad', 'unit', max_width=6),
        ui.Column('', lambda r: r.get('status'), min_width=3, max_width=3, fmt_value=lambda s: '',
                  style=lambda r, c: ui.status_tag(term, r.get('status'))),
        ui.Column('Procedencia', 'source', max_width=70),
    ], rows)
    term.write('  ' + term.style('Leyenda: ', 'muted') + ui.status_legend(term))


def cmd_weapon(app, term: Term, args) -> int:
    body = profile_body(app, args.profile)
    detail = app.catalog.weapon_detail(args.name)
    if detail is None:
        raise ValidationFailed(f'{args.name.upper()} no existe en el catálogo.', hint='Busca con: wr.py weapons -q texto')
    data = app.explain(args.name, body) if detail['in_meta'] else None
    if not args.all and data:
        data['fields'] = {k: v for k, v in data['fields'].items() if k in KEY_FIELDS}
    if args.json:
        emit_json({'weapon': detail, 'explain': data})
        return 0
    from ..catalog.params import PARAMS

    params = {key: spec.to_dict() for key, spec in PARAMS.items()}
    ui.section(term, detail['label'], f'{detail["name"]} · {detail["category"]["label"]} · {"personalizada" if detail["custom"] else "oficial"}')
    ox = detail.get('ox') or {}
    ui.kv(term, [
        ('Hash', f'{detail["hash"]} ({detail["hash_signed"]})'),
        ('ox_inventory', f'{ox.get("label")} · munición {ox.get("ammoname") or "N/D"}' if ox else ui.badge(term, 'warning', 'no registrada')),
        ('Definiciones META', ', '.join(d['relative'] for d in detail['definitions']) or 'ninguna'),
        ('Recoil por script', ui.fmt(detail.get('qbx_recoil'))),
        ('Perfil', f'{body["profile_id"]} (cadena: {" → ".join(data["chain"])})' if data else body['profile_id']),
    ])
    if data:
        if not data['processed']:
            term.write('  ' + ui.badge(term, 'info', f'El perfil no procesa esta arma ({data.get("skipped_reason") or "sin regla"}).'))
        term.write('')
        render_explain(term, data, params)
    if detail['issues']:
        ui.section(term, 'Problemas')
        ui.issues(term, detail['issues'])
    return 0


# ---- perfiles -----------------------------------------------------------------
def profile_columns(term: Term, active: str) -> list[ui.Column]:
    return [
        ui.Column('Nivel', 'tier_label', max_width=10, style=lambda r, c: term.style(c, {'official': 'info', 'server': 'accent', 'user': 'ok', 'legacy': 'muted'}[r['tier']])),
        ui.Column('Identificador', lambda r: f'{r["id"]}{" ★" if r["id"] == active else ""}', max_width=48),
        ui.Column('Nombre', 'name', max_width=30),
        ui.Column('Hereda de', 'extends', max_width=14),
        ui.Column('Editable', lambda r: 'sí' if r.get('editable') else 'protegido', max_width=10,
                  style=lambda r, c: term.style(c, 'ok' if r.get('editable') else 'muted')),
        ui.Column('Rev.', 'revision', align='right', min_width=4),
    ]


def cmd_profiles(app, term: Term, args) -> int:
    rows = app.repo.list(include_legacy=args.all)
    active = app.workspace().active_profile
    if args.json:
        emit_json({'active': active, 'profiles': rows})
        return 0
    ui.section(term, 'Perfiles', '★ = activo · usa --all para ver los archivados')
    ui.table(term, profile_columns(term, active), rows)
    return 0


def render_profile(app, term: Term, profile_id: str) -> dict[str, Any]:
    summary = app.repo.summary(profile_id)
    profile = app.repo.load(profile_id)
    validation = app.validate_profile(profile)
    chain = app.resolved(profile)['profile'].get('resolved_chain')
    ui.section(term, summary['name'], f'{summary["tier_label"]} · {profile_id}{" · protegido" if not summary["editable"] else ""}')
    ui.kv(term, [
        ('Nombre corto', summary.get('short_name') or 'N/D'),
        ('Descripción', summary.get('description') or 'N/D'),
        ('Objetivo', summary.get('objective') or 'N/D'),
        ('Público', summary.get('audience') or 'N/D'),
        ('Herencia', ' → '.join(chain or [profile_id])),
        ('Revisión', f'{summary["revision"]} · {summary["updated_at"]}'),
        ('Validación', ui.counts_line(term, validation['issues'])),
    ])
    if summary.get('features'):
        term.write('  ' + term.style('Características', 'muted'))
        for item in summary['features']:
            term.write(f'    {term.sym["bullet"]} {item}')
    if summary.get('warnings'):
        term.write('  ' + term.style('Advertencias', 'muted'))
        for item in summary['warnings']:
            term.write(f'    {term.style(term.sym["warn"], "warn")} {item}')
    return {'summary': summary, 'validation': validation, 'chain': chain}


def cmd_profile(app, term: Term, args) -> int:
    action = args.action
    repo = app.repo
    if action == 'show':
        if args.json:
            emit_json({'summary': repo.summary(args.id), 'profile': repo.load(args.id), 'validation': app.validate_profile(repo.load(args.id))})
            return 0
        render_profile(app, term, args.id)
        return 0
    if action == 'activate':
        result = app.activate(args.id)
        term.write('  ' + ui.badge(term, 'ok', f'Perfil activo: {result["active_profile"]}'))
        return 0
    if action in {'create', 'derive', 'duplicate'}:
        if action == 'create':
            result = repo.create(args.new_id, args.name or args.new_id, args.description or '', extends=args.extends)
        elif action == 'derive':
            result = repo.derive(args.id, args.new_id, args.name)
        else:
            result = repo.duplicate(args.id, args.new_id, args.name)
        term.write('  ' + ui.badge(term, 'ok', f'Perfil de usuario “{result["id"]}” creado en profiles/user/.'))
        return 0
    if action == 'rename':
        repo.rename(args.id, args.new_id or args.id, args.name)
        term.write('  ' + ui.badge(term, 'ok', 'Perfil renombrado.'))
        return 0
    if action == 'delete':
        if not args.yes:
            raise ValidationFailed('Borrar requiere --yes.', hint='El perfil se mueve a data/trash/.')
        result = repo.delete(args.id)
        term.write('  ' + ui.badge(term, 'ok', f'Movido a la papelera: {result["trash"]}'))
        return 0
    if action == 'validate':
        return cmd_validate(app, term, args)
    if action == 'export':
        data = repo.export(args.id, resolved=args.resolved, legacy=args.legacy)
        text = json.dumps(data, ensure_ascii=False, indent=2) + '\n'
        if args.output:
            target = Path(args.output)
            if target.exists() and not args.yes:
                raise ValidationFailed(f'{target} ya existe.', hint='Usa --yes para sobrescribirlo.')
            target.write_text(text, encoding='utf-8')
            term.write('  ' + ui.badge(term, 'ok', f'Exportado a {target}'))
        else:
            sys.stdout.write(text)
        return 0
    if action == 'import':
        content = Path(args.file).read_text(encoding='utf-8')
        result = repo.import_profile(args.new_id or Path(args.file).stem.removeprefix('legacy_'), content, overwrite=args.yes)
        term.write('  ' + ui.badge(term, 'ok', f'Importado como perfil de usuario “{result["id"]}”.'))
        for note in result.get('notes') or []:
            term.write('  ' + term.style(note, 'muted'))
        return 0
    if action == 'history':
        entries = repo.history(args.id)
        if args.json:
            emit_json(entries)
            return 0
        ui.section(term, f'Historial de {args.id}')
        ui.table(term, [ui.Column('Fecha', 'ts', max_width=25), ui.Column('Acción', 'action', max_width=14),
                        ui.Column('Rev.', 'revision', align='right'), ui.Column('Archivo', 'file', max_width=46),
                        ui.Column('Nota', 'note', max_width=40)], entries)
        return 0
    if action == 'restore':
        if not args.yes:
            raise ValidationFailed('Restaurar requiere --yes (la versión actual queda en el historial).')
        repo.restore(args.id, args.file)
        term.write('  ' + ui.badge(term, 'ok', 'Versión restaurada.'))
        return 0
    if action == 'affected':
        rows = app.affected({'profile_id': args.id})
        if args.json:
            emit_json(rows)
            return 0
        ui.section(term, f'Armas afectadas por {args.id}', f'{len(rows)} armas cambiarían frente al META actual')
        ui.table(term, [ui.Column('Arma', 'weapon', max_width=34), ui.Column('Categoría', 'group', max_width=16),
                        ui.Column('Campos', lambda r: ', '.join(r['fields']), max_width=90)], rows)
        return 0
    raise ValidationFailed(f'Acción desconocida: {action}')


def parse_assignments(items: list[str]) -> list[tuple[str, Any]]:
    result = []
    for item in items:
        if '=' not in item:
            raise ValidationFailed(f'“{item}” no tiene la forma campo=valor.')
        key, value = item.split('=', 1)
        result.append((key.strip(), parse_value(value)))
    return result


def render_changes(term: Term, changes: list[dict[str, Any]]) -> None:
    if not changes:
        term.write('  ' + term.style('Sin cambios.', 'muted'))
        return
    for change in changes:
        before = ui.fmt(change['before']) if change['before'] is not None else '—'
        after = ui.fmt(change['after']) if change['after'] is not None else '—'
        term.write(f'  {term.style(change["path"], "info")}  {term.style(before, "muted")} {term.sym["arrow"]} {term.style(after, "value")}')


def commit_ops(app, term: Term, profile_id: str, ops: list[dict[str, Any]], *, yes: bool, json_out: bool) -> int:
    from .interactive import confirm

    repo = app.repo
    repo.ensure_editable(profile_id)
    _raw, sha = repo.read_raw(profile_id)
    result = app.apply_ops({'profile_id': profile_id, 'ops': ops, 'confirm_dormant': yes})
    if result['confirmations']:
        lines = [d for c in result['confirmations'] for d in c['dormant']]
        if json_out:
            emit_json({'needs_confirmation': result['confirmations']})
            return 1
        ui.section(term, 'Confirmación necesaria')
        term.write('  Activar el módulo también activará estos valores que hoy no tienen efecto:')
        for line in lines[:30]:
            term.write(f'    {term.sym["bullet"]} {line}')
        if not (term.interactive and confirm(term, '¿Continuar igualmente?')):
            term.write('  ' + term.style('Cancelado. Repite con --yes para confirmarlo.', 'muted'))
            return 1
        result = app.apply_ops({'profile_id': profile_id, 'ops': ops, 'confirm_dormant': True})
    if json_out and yes:
        saved = app.save_profile(profile_id, result['profile'], sha=sha, note='terminal: wr.py set')
        emit_json({'changes': result['changes'], 'notices': result['notices'], 'saved': saved})
        return 0
    ui.section(term, f'Cambios en {profile_id}')
    render_changes(term, result['changes'])
    for notice in result['notices']:
        term.write('  ' + ui.badge(term, 'info', notice))
    ui.issues(term, [i for i in result['validation']['issues'] if i['severity'] != 'info'], empty='Validación correcta.')
    if not result['changes']:
        return 0
    if not result['validation']['valid']:
        term.write('  ' + ui.badge(term, 'error', 'No se guarda: hay errores bloqueantes.'))
        return 1
    if not yes and not (term.interactive and confirm(term, 'Guardar estos cambios?')):
        term.write('  ' + term.style('No se guardó nada. Usa --yes para guardar sin preguntar.', 'muted'))
        return 1
    app.save_profile(profile_id, result['profile'], sha=sha, note='terminal')
    term.write('  ' + ui.badge(term, 'ok', f'Guardado. La versión anterior está en el historial de {profile_id}.'))
    return 0


def cmd_set(app, term: Term, args) -> int:
    ops = []
    for key, value in parse_assignments(args.assignments):
        if value is None:
            ops.append({'op': 'inherit_field', 'scope': args.target, 'key': key})
        elif isinstance(value, str) and value.lower() in {'unset', 'quitar'}:
            ops.append({'op': 'unset_field', 'scope': args.target, 'key': key})
        else:
            ops.append({'op': 'set_field', 'scope': args.target, 'key': key, 'value': value})
    return commit_ops(app, term, args.profile, ops, yes=args.yes, json_out=args.json)


def cmd_headshot(app, term: Term, args) -> int:
    values = dict(parse_assignments(args.assignments))
    return commit_ops(app, term, args.profile, [{'op': 'set_headshot', 'scope': args.target, 'values': values}],
                      yes=args.yes, json_out=args.json)


# ---- comparar, simular, validar --------------------------------------------------
def side(value: str) -> dict[str, Any]:
    return {'source': value} if value in {'original', 'current'} else {'profile_id': value}


def render_comparison(app, term: Term, result: dict[str, Any], *, limit: int = 40) -> None:
    summary = result['summary']
    ui.section(term, f'{result["a"]}  vs  {result["b"]}',
               f'{summary["weapons_affected"]} arma(s) con resultado distinto' + (f' · {summary["structural_changes"]} diferencias en el JSON' if 'structural_changes' in summary else ''))
    shown = 0
    for effect in result['effects']:
        fields = {k: v for k, v in effect['fields'].items() if v['direction'] != 'same' or 'a_status' in v}
        if not fields:
            continue
        shown += 1
        if shown > limit:
            term.write('  ' + term.style(f'… {len(result["effects"]) - limit} armas más (usa -w ARMA o --json)', 'muted'))
            break
        term.write('')
        term.write('  ' + term.style(effect['weapon'], 'title'))
        from ..catalog.params import PARAMS

        rows = [{'key': k, 'param': PARAMS[k].label if k in PARAMS else k, **v} for k, v in fields.items()]
        ui.table(term, [
            ui.Column('Parámetro', 'param', max_width=36),
            ui.Column(str(result['a'])[:16], 'a', align='right', min_width=10,
                      style=lambda r, c: ui.status_tag(term, r.get('a_status')) + c if r.get('a_status') else c),
            ui.Column(str(result['b'])[:16], 'b', align='right', min_width=10,
                      style=lambda r, c: ui.status_tag(term, r.get('b_status')) + c if r.get('b_status') else c),
            ui.Column('', 'direction', max_width=9, fmt_value=lambda v: '', style=lambda r, c: ui.direction(term, r['direction'])),
        ], rows, indent=4)
    if any('a_status' in f for e in result['effects'] for f in e['fields'].values()):
        term.write('')
        term.write('  ' + term.style('Leyenda: ', 'muted') + ui.status_legend(term))


def cmd_compare(app, term: Term, args) -> int:
    keys = args.keys.split(',') if args.keys else None
    result = app.compare(side(args.a), side(args.b), weapons=args.weapon or None, keys=keys or (KEY_FIELDS if args.weapon else None))
    if args.json:
        emit_json(result)
        return 0
    render_comparison(app, term, result, limit=args.limit)
    return 0


def cmd_simulate(app, term: Term, args) -> int:
    series = []
    for item in args.weapons:
        name, _, source = item.partition(':')
        series.append({'name': name.upper(), 'source': source or 'current'})
    body = {'weapons': series, 'profile_id': args.profile or app.workspace().active_profile, 'series': False,
            'assumptions': {'zone': args.zone, 'distance': args.distance, 'armour': args.armour, 'health': args.health, 'target': args.target}}
    result = app.simulate(body)
    if args.json:
        emit_json(result)
        return 0
    a = result['assumptions']
    ui.section(term, 'Simulador (teórico)', f'{a["target"]} · {a["zone"]} · {a["distance"]:g} m · vida {a["health"]:g} · blindaje {a["armour"]:g}')
    rows = [{'serie': f'{r["name"]} ({r["source"]})', **r['result'], 'per_shot': r['result']['damage']['per_shot'],
             'note': r['result']['damage']['note'], 'delta': r.get('delta') or {}} for r in result['results']]

    def delta(row, key):
        value = row['delta'].get(key)
        return '' if value is None or abs(value) < 0.05 or row is rows[0] else f' ({value:+.0f}%)'

    ui.table(term, [
        ui.Column('Serie', 'serie', max_width=40),
        ui.Column('Daño/disparo', lambda r: f'{ui.fmt(r["per_shot"], 2)}{delta(r, "per_shot")}', align='right', min_width=12),
        ui.Column('Disparos', 'shots_to_kill', align='right'),
        ui.Column('TTK', lambda r: f'{r["ttk"]:.2f} s{delta(r, "ttk")}' if r['ttk'] is not None else None, align='right', min_width=8),
        ui.Column('RPM', lambda r: round(r['rpm']) if r['rpm'] else None, align='right'),
        ui.Column('DPS', lambda r: ui.fmt(r['dps'], 1), align='right'),
        ui.Column('Nota', 'note', max_width=40, fmt_value=lambda v: v or ''),
    ], rows)
    term.write('  ' + term.style(result['disclaimer'], 'muted'))
    return 0


def cmd_validate(app, term: Term, args) -> int:
    ids = [args.id] if getattr(args, 'id', None) else ([getattr(args, 'profile', None)] if getattr(args, 'profile', None) else app.repo.ids())
    report = []
    failures = 0
    for profile_id in ids:
        profile = app.repo.load(profile_id)
        validation = app.validate_profile(profile)
        entry: dict[str, Any] = {'id': profile_id, **validation}
        if validation['valid'] and getattr(args, 'preview', False):
            data = app.preview_profile(profile, profile_id)
            entry['effect_issues'] = data['issues']
            entry['summary'] = data['summary']
            entry['idempotent'] = data['idempotency'].get('idempotent', True)
            try:
                plan = app.plan({'profile_id': profile_id})
                entry['generator_blocking'] = plan.get('blocking') or []
            except AppError as exc:
                entry['generator_blocking'] = [{'message': exc.message}]
        failures += not validation['valid'] or bool(entry.get('generator_blocking'))
        report.append(entry)
    if getattr(args, 'json', False):
        emit_json(report)
        return 1 if failures else 0
    for entry in report:
        ok = entry['valid'] and not entry.get('generator_blocking')
        all_issues = entry['issues'] + entry.get('effect_issues', [])
        term.write('')
        term.write('  ' + (ui.badge(term, 'ok', entry['id']) if ok else ui.badge(term, 'error', entry['id'])) + '   ' + ui.counts_line(term, all_issues))
        if 'summary' in entry:
            s = entry['summary']
            term.write('     ' + term.style(f'Aplicarlo cambiaría {s["files_changed"]} archivos / {s["weapons_changed"]} armas · '
                                            f'repetible: {"sí" if entry["idempotent"] else "NO"} · generador: '
                                            f'{"compatible" if not entry.get("generator_blocking") else "BLOQUEADO"}', 'muted'))
        if all_issues and (len(report) == 1 or getattr(args, 'verbose', False)):
            ui.issues(term, all_issues, limit=getattr(args, 'limit', 15) or 15)
        for block in entry.get('generator_blocking') or []:
            term.write('     ' + ui.badge(term, 'error', block.get('message', '')))
    return 1 if failures else 0


# ---- generar ---------------------------------------------------------------------
def cmd_generate(app, term: Term, args) -> int:
    from .interactive import typed_confirm

    profile_id = args.profile or app.workspace().active_profile
    with ui.progress(term, 'Ejecutando el motor sobre una copia en memoria'):
        plan = app.plan({'profile_id': profile_id})
    if args.diff:
        sys.stdout.write(app.plan_diff(plan['plan_hash'], args.diff)['diff'] + '\n')
        return 0
    if args.json and not args.apply:
        emit_json(plan)
        return 0
    s = plan['summary']
    ui.section(term, f'Generador · {profile_id}', f'plan {plan["plan_hash"][:12]}')
    ui.kv(term, [('Archivos a escribir', str(s['files_to_write'])), ('Armas que cambian', str(s['weapons_changed'])),
                 ('One-tap', f'{s["onetap_passed"]}/{s["onetap_total"]}'),
                 ('Repetible', 'sí' if plan['idempotency'].get('idempotent', True) else 'NO')], label_width=20)
    for block in plan.get('blocking') or []:
        term.write('  ' + ui.badge(term, 'error', f'{block["path"]}: {block["message"]}'))
    if plan['files_detail']:
        ui.table(term, [ui.Column('Archivo', lambda r: r['path'].split('/resources/')[-1], max_width=90),
                        ui.Column('Tipo', 'kind', max_width=12)], plan['files_detail'][: args.limit or None])
    ui.issues(term, [i for i in plan['issues'] if i['severity'] != 'info'], empty='Sin avisos de efecto.')
    drift = app.integrity_check({'server': 'local'})
    if drift['sealed'] and not drift['clean']:
        term.write('  ' + ui.badge(term, 'warning', f'{drift["total"]} archivo(s) de armas se cambiaron a mano desde el último sello '
                                   '(wr.py integrity). El perfil se aplica encima de esos cambios.'))
    if not args.apply:
        term.write('  ' + term.style('Vista previa: no se escribió nada. Usa --apply para aplicar (pide escribir APLICAR).', 'muted'))
        return 0
    if not s['files_to_write']:
        term.write('  ' + ui.badge(term, 'ok', 'Nada que aplicar: el servidor ya coincide con el perfil.'))
        return 0
    word = args.confirm or (typed_confirm(term, 'Escribe APLICAR para escribir en el servidor') if term.interactive else None)
    if word != 'APLICAR':
        term.write('  ' + term.style('Cancelado. En modo no interactivo usa --confirm APLICAR.', 'muted'))
        return 1
    result = app.apply({'plan_hash': plan['plan_hash'], 'confirm': word})
    if args.json:
        emit_json(result)
        return 0
    term.write('  ' + ui.badge(term, 'ok', f'Aplicado: {result["files"]} archivos, {result["weapons"]} armas. Transacción {result["transaction"]}.'))
    term.write('  ' + term.style('Reinicia los recursos de armas (y qbx_smallresources si cambió qbx_recoils).', 'muted'))
    return 0


def cmd_transactions(app, term: Term, args) -> int:
    rows = app.transactions()
    if args.json:
        emit_json(rows)
        return 0
    ui.section(term, 'Historial de aplicaciones')
    ui.table(term, [ui.Column('Transacción', 'id', max_width=40), ui.Column('Fecha', 'created_at', max_width=25),
                    ui.Column('Perfil', 'profile', max_width=20), ui.Column('Archivos', 'files', align='right'),
                    ui.Column('Estado', 'status', max_width=20)], rows)
    return 0


def cmd_rollback(app, term: Term, args) -> int:
    result = app.rollback({'id': args.id, 'confirm': args.confirm or ''})
    term.write('  ' + ui.badge(term, 'ok', f'Revertida {result["transaction"]}: {result["files"]} archivos.'))
    return 0


# ---- integridad, paso a otro servidor y registro ------------------------------------
def render_integrity(term: Term, data: dict[str, Any], limit: int = 30) -> None:
    label = 'este servidor' if data['label'] == 'local' else data['label']
    if not data['sealed']:
        term.write('  ' + ui.badge(term, 'warning', f'{label}: sin sello todavía. Crea uno con: wr.py integrity seal --reason "…"'
                                   + ('' if data['label'] == 'local' else f' --server {data["label"]}')))
        return
    if data['clean']:
        term.write('  ' + ui.badge(term, 'ok', f'{label}: sin cambios hechos a mano desde el sello del {data["sealed_at"]}.'))
        return
    term.write('  ' + ui.badge(term, 'warning', f'{label}: {data["total"]} archivo(s) de armas cambiados FUERA de la herramienta '
                               f'desde el sello del {data["sealed_at"]}.'))
    rows = ([{**m, 'estado': 'modificado'} for m in data['modified']] + [{**a, 'estado': 'nuevo'} for a in data['added']]
            + [{**r, 'estado': 'borrado', 'modified_at': ''} for r in data['removed']])
    ui.table(term, [ui.Column('Archivo', lambda r: r['path'].split('resources/')[-1], max_width=80),
                    ui.Column('Estado', 'estado', max_width=11), ui.Column('Modificado', 'modified_at', max_width=25)],
             rows[: limit or None])
    term.write('  ' + term.style('Quedó en el registro (wr.py registro). Si el cambio es correcto, pásalo a un perfil y '
                                 'aplícalo; o séllalo con: wr.py integrity seal --reason "…"', 'muted'))


def cmd_integrity(app, term: Term, args) -> int:
    body = {'server': args.server}
    if args.action == 'seal':
        if not args.reason:
            raise ValidationFailed('Indica el motivo con --reason: queda en el registro.')
        result = app.integrity_seal({**body, 'reason': args.reason})
        if args.json:
            emit_json(result)
            return 0
        term.write('  ' + ui.badge(term, 'ok', f'Sello {result["scope"]} de {result["label"]}: {result["files"]} archivos.'))
        return 0
    data = app.integrity_check(body)
    if args.json:
        emit_json(data)
        return 0
    ui.section(term, 'Integridad de las armas', 'cambios hechos fuera de weapon_rebalancer')
    render_integrity(term, data, args.limit)
    return 0 if data['sealed'] and data['clean'] else 1


def cmd_sync(app, term: Term, args) -> int:
    from .interactive import typed_confirm

    plan = app.sync_plan({'target': args.target})
    if args.json and not args.apply:
        emit_json(plan)
        return 0
    ui.section(term, f'Paso a {args.target}', plan['target_root'])
    ui.kv(term, [('Archivos a copiar', str(len(plan['changes']))),
                 ('Solo en el destino', f'{len(plan["only_target"])} (no se tocan)'),
                 ('Sello del destino', 'sí' if plan['target_sealed'] else 'no (se crea al pasar)')], label_width=20)
    if plan['source_drift']:
        term.write('  ' + ui.badge(term, 'warning', f'Este servidor tiene {plan["source_drift"]} archivo(s) cambiados a mano: '
                                   'también se pasarían. Revisa wr.py integrity.'))
    for path in plan['conflicts'][:15]:
        term.write('  ' + ui.badge(term, 'error', f'Cambiado a mano en {args.target}: {path}'))
    if plan['changes']:
        ui.table(term, [ui.Column('Archivo', lambda r: r['path'].split('resources/')[-1], max_width=90),
                        ui.Column('Estado', 'status', max_width=8)], plan['changes'][: args.limit or None])
    if not args.apply:
        term.write('  ' + term.style('Vista previa: no se copió nada. Usa --apply para pasar (pide escribir APLICAR).', 'muted'))
        return 0
    if not plan['changes']:
        term.write('  ' + ui.badge(term, 'ok', f'{args.target} ya coincide con este servidor.'))
        return 0
    word = args.confirm or (typed_confirm(term, f'Escribe APLICAR para copiar a {args.target}') if term.interactive else None)
    if word != 'APLICAR':
        term.write('  ' + term.style('Cancelado. En modo no interactivo usa --confirm APLICAR.', 'muted'))
        return 1
    result = app.sync_apply({'target': args.target, 'confirm': word, 'force': args.force, 'reason': args.reason})
    if args.json:
        emit_json(result)
        return 0
    term.write('  ' + ui.badge(term, 'ok', f'Pasado a {args.target}: {result["files"]} archivos. Transacción {result["transaction"]} '
                               '(se revierte con wr.py rollback).'))
    term.write('  ' + term.style(f'Reinicia el servidor {args.target} para que cargue las armas.', 'muted'))
    return 0


REGISTRO_LABELS = {'generator.apply': 'Aplicación de perfil', 'generator.rollback': 'Reversión', 'generator.guard': 'Guard generado',
                   'sync.apply': 'Paso a otro servidor', 'sync.apply_failed': 'Paso fallido (revertido)',
                   'integrity.seal': 'Sello', 'integrity.manual_change': 'CAMBIO A MANO detectado',
                   'integrity.seal_failed': 'Sello fallido', 'generator.apply_failed': 'Aplicación fallida (revertida)',
                   'legacy.rebalance_write': 'CLI ANTIGUA escribió (sin transacción)'}


def registro_detail(entry: dict[str, Any]) -> str:
    event = entry.get('event')
    if event == 'generator.apply':
        weapons = entry.get('weapons')
        count = len(weapons) if isinstance(weapons, dict) else weapons
        return f'{entry.get("profile")} · {entry.get("files")} archivos · {count} armas · {entry.get("tx")}'
    if event == 'sync.apply':
        files = entry.get('files')
        return f'→ {entry.get("target")} · {len(files) if isinstance(files, list) else files} archivos · {entry.get("tx")}' + \
            (' · FORZADO' if entry.get('forced') else '') + (f' · {entry["reason"]}' if entry.get('reason') else '')
    if event == 'integrity.manual_change':
        files = (entry.get('modified') or []) + (entry.get('added') or []) + (entry.get('removed') or [])
        sample = ', '.join(Path(f).parent.name or f for f in files[:3])
        return f'{entry.get("server")} · {len(files)} archivo(s): {sample}{"…" if len(files) > 3 else ""} · último {entry.get("newest")}'
    if event == 'integrity.seal':
        return f'{entry.get("server")} · {entry.get("scope")} · {entry.get("files")} archivos · {entry.get("reason")}'
    if event == 'legacy.rebalance_write':
        return f'{entry.get("total")} archivo(s) · {" ".join(entry.get("argv") or [])}'[:160]
    if event == 'generator.rollback':
        return f'{entry.get("server", "local")} · {entry.get("files")} archivos · {entry.get("tx")}'
    return ' · '.join(f'{k}={v}' for k, v in entry.items() if k not in {'ts', 'level', 'event'})[:160]


def cmd_registro(app, term: Term, args) -> int:
    rows = list(reversed(app.changes_log(args.limit)))
    if args.json:
        emit_json(rows)
        return 0
    ui.section(term, 'Registro de cambios en las armas', 'data/logs/changes.jsonl · lo más nuevo primero')
    if not rows:
        term.write('  ' + term.style('Sin registros todavía.', 'muted'))
        return 0

    def event_style(row, cell):
        return term.style(cell, 'warn' if row.get('level') == 'warning' else 'err' if row.get('level') == 'error' else 'accent')

    ui.table(term, [ui.Column('Fecha', 'ts', max_width=25),
                    ui.Column('Qué', lambda r: REGISTRO_LABELS.get(r.get('event'), r.get('event')), max_width=26, style=event_style),
                    ui.Column('Detalle', registro_detail, max_width=110)], rows)
    return 0


# ---- parámetros, documentación y ajustes ----------------------------------------------
def cmd_params(app, term: Term, args) -> int:
    from ..catalog.params import METHODS, PARAMS, SECTIONS

    specs = [p for p in PARAMS.values() if (not args.section or p.section == args.section) and (args.all or not p.advanced)]
    if args.json:
        emit_json([p.to_dict() for p in specs])
        return 0
    for section in SECTIONS:
        items = [p for p in specs if p.section == section['id']]
        if not items:
            continue
        ui.section(term, section['label'], section['summary'])
        for spec in items:
            limits = f' · límite {spec.hard_min:g}–{spec.hard_max:g}' if spec.hard_min is not None else ''
            term.write(f'  {term.style(spec.key, "info")}  {spec.label} {term.style(f"[{METHODS[spec.method]["label"]}] <{spec.tag}> {spec.unit}{limits}", "muted")}')
            if spec.description:
                term.write(f'      {spec.description}')
    return 0


def cmd_docs(app, term: Term, args) -> int:
    from .docs import list_pages, render_page

    if args.action == 'build':
        from docs.tools.build_docs import build

        term.write('  ' + ui.badge(term, 'ok', f'docs/js/docs-data.js regenerado: {build()} páginas.'))
        return 0
    pages = list_pages()
    if args.action == 'show' and args.slug:
        page = next((p for p in pages if p['slug'] == args.slug), None)
        if page is None:
            raise ValidationFailed(f'No existe la página “{args.slug}”.', hint='Lista las páginas con: wr.py docs list')
        render_page(term, page)
        return 0
    ui.section(term, 'Documentación', 'wr.py docs show <página>  ·  también en el panel web y docs/index.html')
    ui.table(term, [ui.Column('Página', 'slug', max_width=22), ui.Column('Título', 'title', max_width=34),
                    ui.Column('Grupo', 'group', max_width=18), ui.Column('Descripción', 'description', max_width=70)], pages)
    return 0


SETTINGS_KEYS = {'server_root', 'ox_inventory_dir', 'qbx_recoils_file', 'runtime_audit_root', 'guard_destination',
                 'active_profile', 'server_profiles_editable', 'pack_roots', 'reference_roots'}


def cmd_settings(app, term: Term, args) -> int:
    from ..core.workspace import update_workspace, validate_workspace

    if args.action == 'set':
        changes = {}
        for key, value in parse_assignments(args.assignments):
            if key.startswith('sync_targets.'):
                targets = dict(changes.get('sync_targets') or app.workspace().sync_targets)
                name = key.split('.', 1)[1].strip()
                if value in (None, ''):
                    targets.pop(name, None)
                else:
                    targets[name] = str(value)
                changes['sync_targets'] = targets
                continue
            if key not in SETTINGS_KEYS:
                raise ValidationFailed(f'Ajuste desconocido: {key}.', hint=f'Ajustes: {", ".join(sorted(SETTINGS_KEYS))}.')
            if key in {'pack_roots', 'reference_roots'}:
                value = [v for v in str(value).split(',') if v]
            changes[key] = value
        update_workspace(changes)
        app.catalog.invalidate()
        term.write('  ' + ui.badge(term, 'ok', 'Configuración guardada.'))
    ws = app.workspace()
    if args.json:
        emit_json({'workspace': ws.to_dict(), 'errors': validate_workspace(ws)})
        return 0
    ui.section(term, 'Configuración', 'data/workspace.json · compartida con el panel web')
    data = ws.to_dict()
    def shown(v):
        if isinstance(v, list):
            return ', '.join(v)
        if isinstance(v, dict):
            return ', '.join(f'{k}={x}' for k, x in v.items()) or '(ninguno)'
        return str(v)
    ui.kv(term, [(k, shown(v)) for k, v in data.items() if k not in {'schema', 'server'}], label_width=26)
    errors = validate_workspace(ws)
    ui.issues(term, [{'severity': 'error', 'message': e} for e in errors], empty='Todas las rutas son válidas.')
    return 0
