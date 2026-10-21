"""Terminal interactiva de `wr.py`: menús con flechas, búsqueda, confirmaciones y pantallas.

Funciona en Linux, Windows y por SSH. Si la terminal no admite teclas especiales (o no es una
terminal), los menús pasan a modo numerado con `input()`. Ctrl+C vuelve atrás de forma segura:
nada se escribe sin una confirmación explícita.
"""
from __future__ import annotations

from argparse import Namespace
from copy import deepcopy
from typing import Any, Callable, Sequence

from ..core.errors import AppError
from . import commands, ui
from .term import Term, pad, raw_mode, read_key, truncate

Option = tuple[Any, str, str]  # (valor, etiqueta, detalle)
BACK = object()


# ---- primitivas ----------------------------------------------------------------
def _fallback_select(term: Term, title: str, options: Sequence[Option]) -> Any:
    term.write('')
    term.write('  ' + term.style(title, 'title'))
    for index, (_value, label, detail) in enumerate(options, start=1):
        term.write(f'  [{index}] {label}' + (f'  {term.style(detail, "muted")}' if detail else ''))
    term.write('  [0] Volver')
    answer = input('  Opción: ').strip()
    if not answer.isdigit() or int(answer) == 0 or int(answer) > len(options):
        return None
    return options[int(answer) - 1][0]


def select(term: Term, title: str, options: Sequence[Option], *, header: Callable[[], None] | None = None,
           subtitle: str = '', footer: str = '', default: int = 0, shortcuts: dict[str, Any] | None = None) -> Any:
    """Menú con flechas. Devuelve el valor elegido o None (volver). `/` busca; números eligen directo."""
    if not term.interactive:
        if header:
            header()
        return _fallback_select(term, title, options)
    query = ''
    searching = False
    cursor = default
    top = 0
    try:
        with raw_mode():
            while True:
                visible = [o for o in options if query.lower() in f'{o[1]} {o[2]}'.lower()] if query else list(options)
                cursor = max(0, min(cursor, len(visible) - 1))
                term.clear()
                if header:
                    header()
                term.write('')
                term.write('  ' + term.style(title, 'title') + (f'  {term.style(subtitle, "muted")}' if subtitle else ''))
                if query or searching:
                    term.write('  ' + term.style('Buscar: ', 'info') + query + (term.style('▏', 'accent') if searching else '')
                               + term.style(f'   {len(visible)} resultado(s)', 'muted'))
                used = 9 if header is None else 22
                room = max(5, term.height() - used)
                if cursor < top:
                    top = cursor
                if cursor >= top + room:
                    top = cursor - room + 1
                width = term.width() - 6
                for index in range(top, min(len(visible), top + room)):
                    _value, label, detail = visible[index]
                    text = label + (f'  {term.style(detail, "muted")}' if detail else '')
                    if index == cursor:
                        term.write('  ' + term.style(term.sym['pointer'], 'accent') + ' ' + term.style(pad(truncate(label, width), min(width, max(len(label), 20))), 'select')
                                   + (f'  {term.style(detail, "muted")}' if detail and len(label) < width - 10 else ''))
                    else:
                        term.write('    ' + truncate(text, width))
                if not visible:
                    term.write('    ' + term.style('Sin resultados.', 'muted'))
                if len(visible) > room:
                    term.write('  ' + term.style(f'  {top + 1}–{min(len(visible), top + room)} de {len(visible)}', 'muted'))
                term.write('')
                term.write('  ' + term.style(footer or '↑↓ mover · Enter elegir · / buscar · Esc volver', 'muted'))
                key = read_key()
                if searching:
                    if key == 'enter':
                        searching = False
                        continue
                    if key == 'esc':
                        searching, query = False, ''
                        continue
                    if key == 'backspace':
                        query = query[:-1]
                        continue
                    if key == 'space' or (len(key) == 1 and key.isprintable()):
                        query += ' ' if key == 'space' else key
                        cursor = 0
                        continue
                if key in {'up', 'k'}:
                    cursor = (cursor - 1) % max(1, len(visible))
                elif key in {'down', 'j', 'tab'}:
                    cursor = (cursor + 1) % max(1, len(visible))
                elif key == 'pgdn':
                    cursor = min(len(visible) - 1, cursor + room)
                elif key == 'pgup':
                    cursor = max(0, cursor - room)
                elif key == 'home':
                    cursor = 0
                elif key == 'end':
                    cursor = len(visible) - 1
                elif key in {'enter', 'right'} and visible:
                    return visible[cursor][0]
                elif key in {'esc', 'left', 'q', 'backspace'}:
                    if query:
                        query = ''
                        continue
                    return None
                elif key == '/':
                    searching = True
                elif shortcuts and key in shortcuts:
                    return shortcuts[key]
    except KeyboardInterrupt:
        return None


def multiselect(term: Term, title: str, options: Sequence[Option], *, limit: int | None = None) -> list[Any]:
    chosen: list[Any] = []
    while True:
        marked = [(value, f'{term.sym["check_on"] if value in chosen else term.sym["check_off"]} {label}', detail) for value, label, detail in options]
        done = ('__done__', term.style(f'{term.sym["ok"]} Listo ({len(chosen)} elegidas)', 'ok'), '')
        value = select(term, title, [done, *marked], subtitle=f'máx. {limit}' if limit else '',
                       footer='Enter marca/desmarca · / buscar · Listo para terminar · Esc cancelar')
        if value is None:
            return []
        if value == '__done__':
            return chosen
        if value in chosen:
            chosen.remove(value)
        elif not limit or len(chosen) < limit:
            chosen.append(value)


def prompt(term: Term, label: str, default: str | None = None) -> str | None:
    suffix = f' [{default}]' if default not in (None, '') else ''
    try:
        answer = input(f'  {term.style(label, "info")}{suffix}: ').strip()
    except (KeyboardInterrupt, EOFError):
        term.write('')
        return None
    if not answer:
        return default
    return answer


def confirm(term: Term, question: str, default: bool = False) -> bool:
    hint = 'S/n' if default else 's/N'
    if not term.interactive:
        return default
    term.stream.write(f'  {term.style("?", "warn")} {question} ({hint}) ')
    term.stream.flush()
    try:
        with raw_mode():
            while True:
                key = read_key()
                if key in {'s', 'S', 'y', 'Y'}:
                    term.write('sí')
                    return True
                if key in {'n', 'N', 'esc', 'q'}:
                    term.write('no')
                    return False
                if key == 'enter':
                    term.write('sí' if default else 'no')
                    return default
    except KeyboardInterrupt:
        term.write('no')
        return False


def typed_confirm(term: Term, message: str, word: str = 'APLICAR') -> str | None:
    term.write('  ' + term.style(message, 'warn'))
    answer = prompt(term, f'Escribe {word} para continuar (vacío cancela)')
    return word if answer == word else None


def pause(term: Term, text: str = 'Pulsa una tecla para volver') -> None:
    if not term.interactive:
        return
    term.stream.write('\n  ' + term.style(text, 'muted'))
    term.stream.flush()
    try:
        with raw_mode():
            read_key()
    except KeyboardInterrupt:
        pass
    term.write('')


def safe(term: Term, action: Callable[[], Any]) -> Any:
    """Ejecuta una acción mostrando los errores de la aplicación sin cerrar la terminal."""
    try:
        return action()
    except AppError as exc:
        term.write('')
        term.write('  ' + ui.badge(term, 'error', exc.message))
        if exc.hint:
            term.write('     ' + term.style(f'{term.sym["arrow"]} {exc.hint}', 'muted'))
        if isinstance(exc.details, list):
            ui.issues(term, [d if isinstance(d, dict) else {'severity': 'error', 'message': str(d)} for d in exc.details], limit=10)
        pause(term)
    except KeyboardInterrupt:
        term.write('')
        term.write('  ' + term.style('Cancelado.', 'muted'))
    return None


def ns(**kwargs: Any) -> Namespace:
    defaults = {'json': False, 'yes': False, 'limit': 0, 'preview': True, 'verbose': True}
    return Namespace(**{**defaults, **kwargs})


# ---- aplicación interactiva ---------------------------------------------------------
class Studio:
    def __init__(self, app, term: Term) -> None:
        self.app = app
        self.term = term
        self._status: dict[str, Any] | None = None

    def status(self, refresh: bool = False) -> dict[str, Any]:
        if self._status is None or refresh:
            with ui.progress(self.term, 'Analizando el servidor'):
                self._status = commands.status_data(self.app)
        return self._status

    def header(self) -> None:
        from ..services.app import version

        ui.banner(self.term, version())
        commands.render_status(self.app, self.term, self.status())

    # ---- menú principal ----
    def run(self) -> int:
        items = [
            ('weapons', '[1]  Explorador de armas', 'buscar, filtrar y ver procedencia'),
            ('editor', '[2]  Editor de armas', 'cambiar parámetros por arma, categoría o global'),
            ('profiles', '[3]  Perfiles', 'oficiales, servidor, usuario, historial'),
            ('compare', '[4]  Comparar perfiles', 'también contra original/actual'),
            ('simulate', '[5]  Simulador de balance', 'daño, TTK, DPS'),
            ('validate', '[6]  Validar configuración', 'errores, advertencias y recomendaciones'),
            ('generate', '[7]  Generar recurso FiveM', 'vista previa, diff y aplicar'),
            ('docs', '[8]  Documentación', ''),
            ('settings', '[9]  Configuración', 'rutas, perfil activo, permisos'),
            ('exit', '[0]  Salir', ''),
        ]
        shortcuts = {str(i): key for i, (key, _l, _d) in zip([1, 2, 3, 4, 5, 6, 7, 8, 9, 0], items)}
        self.status()
        while True:
            choice = select(self.term, 'MENÚ PRINCIPAL', items, header=self.header, shortcuts=shortcuts,
                            footer='↑↓ o número · Enter elegir · Esc salir')
            if choice in (None, 'exit'):
                self.term.clear()
                self.term.write('  ' + self.term.style('Hasta luego.', 'muted'))
                return 0
            getattr(self, f'screen_{choice}')()

    # ---- explorador ----
    def pick_profile(self, title: str, *, editable_only: bool = False, extra: Sequence[Option] = ()) -> Any:
        active = self.app.workspace().active_profile
        options = list(extra)
        for row in self.app.repo.list():
            if editable_only and not row['editable']:
                continue
            tag = f'{row["tier_label"]}{" · protegido" if not row["editable"] else ""}{" · activo" if row["id"] == active else ""}'
            options.append((row['id'], f'{row["name"]}  ({row["id"]})', tag))
        return select(self.term, title, options)

    def screen_weapons(self, profile: str | None = None) -> None:
        profile = profile or self.app.workspace().active_profile
        category = ''
        while True:
            data = safe(self.term, lambda: self.app.weapon_rows({'profile_id': profile}))
            if not data:
                return
            rows = commands.filter_rows([r for r in data['rows'] if r['in_meta']], category=category)
            rows.sort(key=lambda r: (r['category'], r['name']))
            options: list[Option] = [
                ('__profile', self.term.style(f'Perfil aplicado: {profile}', 'info'), 'cambiar'),
                ('__category', self.term.style(f'Categoría: {category or "todas"}', 'info'), 'filtrar'),
            ]
            for row in rows:
                damage = f'{commands.ui.fmt(row["damage_original"])}→{commands.ui.fmt(row["damage_effective"])}'
                rpm = f'{round(row["rpm_effective"])} rpm' if row['rpm_effective'] else 'N/D rpm'
                label = f'{pad(row["name"], 28)} {pad(truncate(row["label"], 22), 22)}'
                detail = f'{pad(row["category"], 18)} daño {pad(damage, 12)} {pad(rpm, 9)} {row["profile_state"]}'
                options.append((row['name'], label, detail))
            choice = select(self.term, 'EXPLORADOR DE ARMAS', options, subtitle=f'{len(rows)} armas con META · / para buscar')
            if choice is None:
                return
            if choice == '__profile':
                profile = self.pick_profile('Perfil para calcular los valores') or profile
            elif choice == '__category':
                cats = sorted({(r['category_id'], r['category']) for r in data['rows'] if r['in_meta']}, key=lambda c: c[1])
                picked = select(self.term, 'Categoría', [('', 'Todas', ''), *[(cid, label, '') for cid, label in cats]])
                category = picked if picked is not None else category
            else:
                self.screen_weapon_detail(choice, profile)

    def screen_weapon_detail(self, weapon: str, profile: str) -> None:
        while True:
            self.term.clear()
            safe(self.term, lambda: commands.cmd_weapon(self.app, self.term, ns(name=weapon, profile=profile, all=False)))
            choice = select(self.term, 'Acciones', [
                ('edit', 'Editar esta arma', 'en un perfil editable'),
                ('compare', 'Comparar con los valores originales', ''),
                ('simulate', 'Simular (actual vs perfil)', ''),
                ('all', 'Ver todos los parámetros', ''),
            ], header=lambda: None)
            if choice is None:
                return
            if choice == 'edit':
                self.screen_editor(weapon=weapon)
            elif choice == 'compare':
                self.term.clear()
                safe(self.term, lambda: commands.cmd_compare(self.app, self.term, ns(a='original', b=profile, weapon=[weapon], keys=None, limit=5)))
                pause(self.term)
            elif choice == 'simulate':
                self.term.clear()
                safe(self.term, lambda: commands.cmd_simulate(self.app, self.term, ns(
                    weapons=[f'{weapon}:original', f'{weapon}:current', f'{weapon}:proposed'], profile=profile,
                    zone='torso', distance=15.0, armour=0.0, health=100.0, target='player')))
                pause(self.term)
            elif choice == 'all':
                self.term.clear()
                safe(self.term, lambda: commands.cmd_weapon(self.app, self.term, ns(name=weapon, profile=profile, all=True)))
                pause(self.term)

    # ---- editor ----
    def ensure_editable_profile(self) -> str | None:
        extra = [('__derive', self.term.style('+ Crear un perfil derivado de otro', 'ok'), 'hereda todo y guarda solo tus cambios')]
        choice = self.pick_profile('¿Qué perfil quieres editar?', editable_only=True, extra=extra)
        if choice != '__derive':
            return choice
        base = self.pick_profile('Perfil base del derivado')
        if not base:
            return None
        new_id = prompt(self.term, 'Identificador del nuevo perfil (minúsculas, números, - y _)')
        if not new_id:
            return None
        if safe(self.term, lambda: self.app.repo.derive(base, new_id)) is None:
            return None
        return new_id

    def screen_editor(self, weapon: str | None = None, profile_id: str | None = None) -> None:
        profile_id = profile_id or self.ensure_editable_profile()
        if not profile_id:
            return
        raw, sha = self.app.repo.read_raw(profile_id)
        saved = self.app.repo.load(profile_id)
        draft = deepcopy(saved)
        scope = None
        while True:
            if not weapon:
                rows = self.app.weapon_rows({'profile_id': profile_id, 'profile': draft})['rows']
                options = [(r['name'], f'{pad(r["name"], 28)} {truncate(r["label"], 24)}', r['category']) for r in rows if r['in_meta']]
                weapon = select(self.term, 'Elige un arma', options, subtitle='/ para buscar')
                if not weapon:
                    if self._discard_ok(saved, draft):
                        return
                    continue
            detail = self.app.catalog.weapon_detail(weapon)
            scope = scope or {'type': 'weapon', 'name': weapon}
            pending = len(self._changes(saved, draft))
            sections = [('damage', 'Daño'), ('headshot', 'Cabeza (política)'), ('range', 'Alcance y caída'), ('fire_rate', 'Cadencia'),
                        ('recoil', 'Recoil'), ('accuracy', 'Precisión'), ('ammo', 'Munición y recarga'), ('projectile', 'Proyectil'),
                        ('advanced', 'Avanzados')]
            scope_text = {'weapon': f'esta arma ({weapon})', 'group': f'categoría {detail["group"]}', 'defaults': 'global'}[scope['type']]
            options: list[Option] = [(key, label, '') for key, label in sections]
            options += [
                ('__scope', self.term.style(f'Ámbito: {scope_text}', 'info'), 'cambiar'),
                ('__weapon', self.term.style('Cambiar de arma', 'info'), ''),
                ('__review', self.term.style(f'Revisar cambios pendientes ({pending})', 'warn' if pending else 'muted'), ''),
                ('__save', self.term.style('Guardar perfil', 'ok'), 'muestra la comparación y pide confirmación'),
                ('__discard', self.term.style('Descartar y salir', 'err'), ''),
            ]
            choice = select(self.term, f'EDITOR · {profile_id} · {weapon}', options,
                            subtitle=f'{pending} cambio(s) sin guardar' if pending else 'sin cambios')
            if choice is None or choice == '__discard':
                if self._discard_ok(saved, draft):
                    return
            elif choice == '__weapon':
                weapon, scope = None, None
            elif choice == '__scope':
                picked = select(self.term, 'Aplicar los cambios a', [
                    ({'type': 'weapon', 'name': weapon}, f'Esta arma ({weapon})', 'weapons.' + weapon),
                    ({'type': 'group', 'name': detail['group']}, f'Toda la categoría {detail["group"]}', 'groups.' + str(detail['group'])),
                    ({'type': 'defaults', 'name': '*'}, 'Global (todas las armas procesadas)', 'defaults'),
                ])
                scope = picked or scope
            elif choice == '__review':
                self.term.clear()
                ui.section(self.term, 'Cambios pendientes', profile_id)
                commands.render_changes(self.term, self._changes(saved, draft))
                pause(self.term)
            elif choice == '__save':
                if self._save(profile_id, saved, draft, sha):
                    raw, sha = self.app.repo.read_raw(profile_id)
                    saved = self.app.repo.load(profile_id)
                    draft = deepcopy(saved)
            elif choice == 'headshot':
                draft = self._edit_headshot(profile_id, draft, scope) or draft
            else:
                draft = self._edit_section(profile_id, draft, weapon, scope, choice) or draft

    def _changes(self, saved: dict[str, Any], draft: dict[str, Any]) -> list[dict[str, Any]]:
        from ..profile_store.edit import summarize_changes

        return summarize_changes(saved, draft)

    def _discard_ok(self, saved: dict[str, Any], draft: dict[str, Any]) -> bool:
        if not self._changes(saved, draft):
            return True
        return confirm(self.term, 'Hay cambios sin guardar. ¿Descartarlos?')

    def _save(self, profile_id: str, saved: dict[str, Any], draft: dict[str, Any], sha: str) -> bool:
        self.term.clear()
        changes = self._changes(saved, draft)
        ui.section(self.term, f'Guardar {profile_id}', 'estado anterior → nuevo')
        commands.render_changes(self.term, changes)
        if not changes:
            pause(self.term)
            return False
        validation = self.app.validate_profile(draft)
        ui.section(self.term, 'Validación')
        ui.issues(self.term, validation['issues'], empty='Sin problemas.')
        if not validation['valid']:
            self.term.write('  ' + ui.badge(self.term, 'error', 'Hay errores bloqueantes: no se puede guardar.'))
            pause(self.term)
            return False
        with ui.progress(self.term, 'Calculando el efecto en el pack'):
            preview = safe(self.term, lambda: self.app.preview_profile(draft, profile_id))
        if preview:
            s = preview['summary']
            self.term.write('  ' + self.term.style(f'Al aplicarlo cambiarían {s["files_changed"]} archivos y {s["weapons_changed"]} armas.', 'muted'))
        if not confirm(self.term, 'Guardar el perfil? (la versión actual queda en el historial)'):
            return False
        result = safe(self.term, lambda: self.app.save_profile(profile_id, draft, sha=sha, note='terminal: editor'))
        if result:
            self.term.write('  ' + ui.badge(self.term, 'ok', 'Guardado.'))
            self._status = None
            pause(self.term)
            return True
        return False

    def _apply(self, profile_id: str, draft: dict[str, Any], ops: list[dict[str, Any]]) -> dict[str, Any] | None:
        result = safe(self.term, lambda: self.app.apply_ops({'profile_id': profile_id, 'profile': draft, 'ops': ops}))
        if result is None:
            return None
        if result['confirmations']:
            lines = [d for c in result['confirmations'] for d in c['dormant']]
            self.term.write('')
            self.term.write('  ' + ui.badge(self.term, 'warning', 'Activar el módulo también activará valores que hoy no tienen efecto:'))
            for line in lines[:25]:
                self.term.write(f'     {self.term.sym["bullet"]} {line}')
            if not confirm(self.term, '¿Continuar?'):
                return None
            result = safe(self.term, lambda: self.app.apply_ops({'profile_id': profile_id, 'profile': draft, 'ops': ops, 'confirm_dormant': True}))
            if result is None:
                return None
        for notice in result['notices']:
            self.term.write('  ' + ui.badge(self.term, 'info', notice))
        return result['profile']

    def _edit_section(self, profile_id: str, draft: dict[str, Any], weapon: str, scope: dict[str, Any], section: str) -> dict[str, Any] | None:
        from ..catalog.params import PARAMS
        from ..profile_store.edit import get_field

        while True:
            explained = safe(self.term, lambda: self.app.explain(weapon, {'profile_id': profile_id, 'profile': draft}))
            if not explained:
                return draft
            specs = [p for p in PARAMS.values() if p.editable and p.value_type in {'number', 'integer'}
                     and (p.section == section or (section == 'advanced' and p.advanced and p.section not in {'headshot'}))
                     and (section == 'advanced' or not p.advanced) and p.section != 'headshot']
            options = []
            for spec in specs:
                item = explained['fields'].get(spec.key, {})
                declared = get_field(draft, scope, spec.key)
                mark = self.term.style('● ', 'accent') if declared is not None else '  '
                detail = (f'orig {commands.ui.fmt(item.get("original"))} · actual {commands.ui.fmt(item.get("current"))} · '
                          f'efectivo {commands.ui.fmt(item.get("effective"))} {spec.unit}')
                options.append((spec.key, f'{mark}{pad(spec.label, 38)}', detail))
            key = select(self.term, f'{section.upper()} · {weapon}', options, subtitle='● = declarado en este ámbito')
            if key is None:
                return draft
            spec = PARAMS[key]
            item = explained['fields'].get(key, {})
            self.term.clear()
            ui.section(self.term, spec.label, f'<{spec.tag}> · {spec.key}')
            rows = [('Qué controla', spec.description or 'N/D')]
            if spec.notes:
                rows.append(('Nota', spec.notes))
            rows += [('Unidad', spec.unit or '—'),
                     ('Rango del editor', f'{spec.slider_min:g} – {spec.slider_max:g}' if spec.slider_min is not None else 'N/D'),
                     ('Límite del motor', f'{spec.hard_min:g} – {spec.hard_max:g}' if spec.hard_min is not None else 'sin límite'),
                     ('Original (.bak)', commands.ui.fmt(item.get('original'))), ('Actual (META)', commands.ui.fmt(item.get('current'))),
                     ('Efectivo', commands.ui.fmt(item.get('effective'))), ('Procedencia', item.get('label', 'N/D')),
                     ('En este ámbito', commands.ui.fmt(get_field(draft, scope, key)))]
            commands.ui.kv(self.term, rows)
            self.term.write('')
            self.term.write('  ' + self.term.style('Escribe un número · “q” quitar del ámbito · “h” heredar sin valor (derivados) · vacío cancelar', 'muted'))
            answer = prompt(self.term, 'Nuevo valor')
            if answer in (None, ''):
                continue
            if answer.lower() == 'q':
                ops = [{'op': 'unset_field', 'scope': scope, 'key': key}]
            elif answer.lower() == 'h':
                ops = [{'op': 'inherit_field', 'scope': scope, 'key': key}]
            else:
                try:
                    value = float(answer.replace(',', '.'))
                except ValueError:
                    self.term.write('  ' + ui.badge(self.term, 'error', 'No es un número.'))
                    pause(self.term)
                    continue
                if spec.value_type == 'integer':
                    value = int(round(value))
                ops = [{'op': 'set_field', 'scope': scope, 'key': key, 'value': value}]
            updated = self._apply(profile_id, draft, ops)
            if updated is None:
                pause(self.term)
                continue
            after = safe(self.term, lambda: self.app.explain(weapon, {'profile_id': profile_id, 'profile': updated}, keys=[key]))
            if after:
                new = after['fields'][key]
                self.term.write('  ' + self.term.style('Vista previa: ', 'info') + f'{commands.ui.fmt(item.get("effective"))} '
                                f'{self.term.sym["arrow"]} {self.term.style(commands.ui.fmt(new.get("effective")), "value")}  '
                                + self.term.style(new.get('label', ''), 'muted'))
            draft = updated
            pause(self.term, 'Cambio en el borrador (aún sin guardar). Pulsa una tecla')

    def _edit_headshot(self, profile_id: str, draft: dict[str, Any], scope: dict[str, Any]) -> dict[str, Any] | None:
        mode = select(self.term, 'Política de cabeza', [
            ('inherit' if scope['type'] != 'defaults' else 'original', 'Heredar / no tocar', ''),
            ('off', 'Sin multiplicador de cabeza', ''), ('normal', 'Headshot normal', ''), ('onetap', 'One-tap', ''),
        ])
        if mode is None:
            return draft
        values: dict[str, Any] = {'mode': mode}
        if mode in {'normal', 'onetap'}:
            for key, label in (('multiplier', 'Multiplicador (vacío = heredar)'),
                               ('distance', 'Distancia máxima en m (vacío = heredar, «alcance» = la del arma)')):
                answer = prompt(self.term, label)
                if answer and key == 'distance' and answer.strip().lower() in {'alcance', 'weapon_range'}:
                    values[key] = 'weapon_range'
                elif answer:
                    try:
                        values[key] = float(answer.replace(',', '.'))
                    except ValueError:
                        pass
        return self._apply(profile_id, draft, [{'op': 'set_headshot', 'scope': scope, 'values': values}])

    # ---- perfiles ----
    def screen_profiles(self) -> None:
        show_legacy = False
        while True:
            active = self.app.workspace().active_profile
            rows = self.app.repo.list(include_legacy=show_legacy)
            options: list[Option] = [
                ('__new', self.term.style('+ Nuevo perfil de usuario', 'ok'), 'vacío, copia o derivado'),
                ('__import', self.term.style('+ Importar JSON', 'ok'), 'incluye los pendientes de migración'),
                ('__legacy', self.term.style(f'{"Ocultar" if show_legacy else "Mostrar"} archivados', 'info'), ''),
            ]
            for row in rows:
                tag = f'{row["tier_label"]}{" · protegido" if not row["editable"] else ""}{" · hereda de " + row["extends"] if row.get("extends") else ""}'
                options.append((row['id'], f'{"★ " if row["id"] == active else "  "}{pad(row["name"], 30)} {row["id"]}', tag))
            choice = select(self.term, 'PERFILES', options, subtitle='★ = activo')
            if choice is None:
                return
            if choice == '__legacy':
                show_legacy = not show_legacy
            elif choice == '__new':
                self._new_profile()
            elif choice == '__import':
                path = prompt(self.term, 'Ruta del archivo JSON')
                if path:
                    new_id = prompt(self.term, 'Identificador del perfil de usuario')
                    safe(self.term, lambda: commands.cmd_profile(self.app, self.term, ns(action='import', file=path, new_id=new_id)))
                    pause(self.term)
            else:
                self.screen_profile_detail(choice)

    def _new_profile(self) -> None:
        mode = select(self.term, 'Nuevo perfil', [('blank', 'Vacío', 'no toca nada hasta que configures algo'),
                                                  ('derive', 'Derivado de otro', 'hereda y guarda solo diferencias (recomendado)'),
                                                  ('copy', 'Copia completa de otro', '')])
        if not mode:
            return
        base = None
        if mode != 'blank':
            base = self.pick_profile('Perfil de origen')
            if not base:
                return
        new_id = prompt(self.term, 'Identificador (minúsculas, números, - y _)')
        if not new_id:
            return
        name = prompt(self.term, 'Nombre visible', new_id)
        if mode == 'blank':
            safe(self.term, lambda: self.app.repo.create(new_id, name or new_id))
        elif mode == 'derive':
            safe(self.term, lambda: self.app.repo.derive(base, new_id, name))
        else:
            safe(self.term, lambda: self.app.repo.duplicate(base, new_id, name))
        if self.app.repo.exists(new_id):
            self.term.write('  ' + ui.badge(self.term, 'ok', f'Perfil “{new_id}” creado en profiles/user/.'))
            pause(self.term)

    def screen_profile_detail(self, profile_id: str) -> None:
        while True:
            summary = self.app.repo.summary(profile_id)
            editable = summary['editable']
            actions: list[Option] = [('activate', 'Activar este perfil', ''), ('validate', 'Validar', 'incluye vista previa y generador'),
                                     ('affected', 'Armas afectadas', ''), ('compare', 'Comparar con…', ''),
                                     ('derive', 'Crear perfil derivado', 'para modificarlo sin tocar este'),
                                     ('duplicate', 'Duplicar', ''), ('export', 'Exportar JSON', ''), ('history', 'Historial / restaurar', '')]
            if editable:
                actions[4:4] = [('edit', 'Editar armas', ''), ('meta', 'Editar nombre y descripción', '')]
            if summary['tier'] == 'user':
                actions += [('rename', 'Renombrar', ''), ('delete', self.term.style('Borrar (papelera)', 'err'), '')]
            choice = select(self.term, 'Acciones', actions, header=lambda: self._profile_header(profile_id))
            if choice is None:
                return
            term = self.term
            if choice == 'activate':
                if safe(term, lambda: self.app.activate(profile_id)):
                    term.write('  ' + ui.badge(term, 'ok', f'Perfil activo: {profile_id}'))
                    self._status = None
                    pause(term)
            elif choice == 'validate':
                term.clear()
                safe(term, lambda: commands.cmd_validate(self.app, term, ns(id=profile_id, preview=True, limit=30)))
                pause(term)
            elif choice == 'affected':
                term.clear()
                safe(term, lambda: commands.cmd_profile(self.app, term, ns(action='affected', id=profile_id)))
                pause(term)
            elif choice == 'compare':
                other = self.pick_profile('Comparar con', extra=[('original', 'Valores originales (.bak)', ''), ('current', 'META actual', '')])
                if other:
                    term.clear()
                    safe(term, lambda: commands.cmd_compare(self.app, term, ns(a=other, b=profile_id, weapon=None, keys=None, limit=25)))
                    pause(term)
            elif choice == 'derive' or choice == 'duplicate':
                new_id = prompt(term, 'Identificador del nuevo perfil')
                if new_id:
                    method = self.app.repo.derive if choice == 'derive' else self.app.repo.duplicate
                    if safe(term, lambda: method(profile_id, new_id)):
                        term.write('  ' + ui.badge(term, 'ok', f'Creado “{new_id}”.'))
                        pause(term)
            elif choice == 'edit':
                self.screen_editor(profile_id=profile_id)
            elif choice == 'meta':
                self._edit_meta(profile_id)
            elif choice == 'export':
                path = prompt(term, 'Archivo de salida', f'{profile_id}.json')
                kind = select(term, 'Formato', [('own', 'Tal cual (con herencia)', ''), ('resolved', 'Resuelto (sin herencia)', ''), ('legacy', 'Legacy (CLI antigua)', '')])
                if path and kind:
                    safe(term, lambda: commands.cmd_profile(self.app, term, ns(action='export', id=profile_id, output=path,
                                                                           resolved=kind == 'resolved', legacy=kind == 'legacy', yes=False)))
                    pause(term)
            elif choice == 'history':
                self._history(profile_id)
            elif choice == 'rename':
                new_id = prompt(term, 'Nuevo identificador', profile_id)
                if new_id and safe(term, lambda: self.app.repo.rename(profile_id, new_id)):
                    return
            elif choice == 'delete':
                if confirm(term, f'¿Mover “{profile_id}” a la papelera?') and safe(term, lambda: self.app.repo.delete(profile_id)):
                    return

    def _profile_header(self, profile_id: str) -> None:
        commands.render_profile(self.app, self.term, profile_id)

    def _edit_meta(self, profile_id: str) -> None:
        summary = self.app.repo.summary(profile_id)
        ops = []
        for key, label in (('name', 'Nombre visible'), ('short_name', 'Nombre corto'), ('description', 'Descripción'),
                           ('objective', 'Objetivo de balanceo'), ('audience', 'Público')):
            answer = prompt(self.term, label, summary.get(key) or '')
            if answer is not None and answer != (summary.get(key) or ''):
                ops.append({'op': 'set_meta', 'key': key, 'value': answer})
        if ops:
            safe(self.term, lambda: commands.commit_ops(self.app, self.term, profile_id, ops, yes=False, json_out=False))
            pause(self.term)

    def _history(self, profile_id: str) -> None:
        entries = [e for e in self.app.repo.history(profile_id)]
        options = [(e.get('file'), f'{e["ts"]}  {pad(e["action"], 12)} rev {e.get("revision") or "-"}', e.get('note') or '') for e in entries if e.get('file')]
        if not options:
            self.term.write('  ' + self.term.style('Sin versiones anteriores.', 'muted'))
            pause(self.term)
            return
        choice = select(self.term, f'Historial de {profile_id}', options, subtitle='Enter restaura esa versión (pide confirmación)')
        if choice and confirm(self.term, 'Restaurar esa versión? (la actual queda en el historial)'):
            if safe(self.term, lambda: self.app.repo.restore(profile_id, choice)):
                self.term.write('  ' + ui.badge(self.term, 'ok', 'Versión restaurada.'))
                pause(self.term)

    # ---- comparar, simular, validar, generar ----
    def screen_compare(self) -> None:
        extra = [('original', 'Valores originales (.bak)', 'GTA V / pack sin modificar'), ('current', 'META actual', 'lo que hay hoy en el servidor')]
        a = self.pick_profile('Comparar: lado A', extra=extra)
        if not a:
            return
        b = self.pick_profile('Comparar: lado B', extra=extra)
        if not b:
            return
        weapon = prompt(self.term, 'Arma concreta (vacío = todas)')
        self.term.clear()
        with ui.progress(self.term, 'Calculando ambos lados con el motor'):
            result = safe(self.term, lambda: self.app.compare(commands.side(a), commands.side(b), weapons=[weapon.upper()] if weapon else None,
                                                              keys=commands.KEY_FIELDS if weapon else None))
        if result:
            commands.render_comparison(self.app, self.term, result, limit=30)
        pause(self.term)

    def screen_simulate(self) -> None:
        rows = self.app.weapon_rows({'profile_id': self.app.workspace().active_profile})['rows']
        options = [(r['name'], f'{pad(r["name"], 28)} {truncate(r["label"], 22)}', r['category']) for r in rows if r['in_meta']]
        weapons = multiselect(self.term, 'Armas a simular', options, limit=4)
        if not weapons:
            return
        sources = multiselect(self.term, 'Valores', [('original', 'Original (.bak)', ''), ('current', 'Actual (META)', ''),
                                                     ('proposed', 'Propuesto por un perfil', '')], limit=3) or ['current']
        profile = self.pick_profile('Perfil para “propuesto”') if 'proposed' in sources else None
        zone = select(self.term, 'Zona de impacto', [('torso', 'Torso', ''), ('head', 'Cabeza', ''), ('limbs', 'Extremidades', '')]) or 'torso'
        distance = prompt(self.term, 'Distancia (m)', '15') or '15'
        armour = prompt(self.term, 'Blindaje (0–100)', '0') or '0'
        series = [f'{w}:{s}' for w in weapons for s in sources]
        self.term.clear()
        safe(self.term, lambda: commands.cmd_simulate(self.app, self.term, ns(weapons=series[:8], profile=profile, zone=zone,
                                                                         distance=float(distance), armour=float(armour), health=100.0, target='player')))
        pause(self.term)

    def screen_validate(self) -> None:
        profile = self.pick_profile('Validar perfil', extra=[('__all', 'Todos los perfiles', '')])
        if not profile:
            return
        self.term.clear()
        args = ns(id=None if profile == '__all' else profile, profile=None, preview=profile != '__all', limit=30, verbose=profile != '__all')
        safe(self.term, lambda: commands.cmd_validate(self.app, self.term, args))
        pause(self.term)

    def screen_generate(self) -> None:
        choice = select(self.term, 'GENERAR RECURSO FIVEM', [('plan', 'Vista previa y aplicar un perfil', ''),
                                                             ('history', 'Historial de aplicaciones / revertir', '')])
        if choice == 'plan':
            profile = self.pick_profile('Perfil a generar')
            if not profile:
                return
            self.term.clear()
            with ui.progress(self.term, 'Ejecutando el motor sobre una copia en memoria'):
                plan = safe(self.term, lambda: self.app.plan({'profile_id': profile}))
            if not plan:
                return
            while True:
                self.term.clear()
                safe(self.term, lambda: commands.cmd_generate(self.app, self.term, ns(profile=profile, diff=None, apply=False, confirm=None, limit=15)))
                action = select(self.term, 'Acciones', [('diff', 'Ver diff de un archivo', ''), ('apply', self.term.style('Aplicar al servidor', 'warn'), 'pide escribir APLICAR')], header=lambda: None)
                if action is None:
                    return
                if action == 'diff':
                    files = [(f['path'], f['path'].split('/resources/')[-1], f['kind']) for f in plan['files_detail']]
                    path = select(self.term, 'Archivo', files)
                    if path:
                        from .docs import render_page

                        render_page(self.term, {'title': path.split('/resources/')[-1], 'description': 'diff (actual → propuesto)',
                                                'content': '```\n' + self.app.plan_diff(plan['plan_hash'], path)['diff'] + '\n```'})
                else:
                    word = typed_confirm(self.term, f'Se escribirán {plan["summary"]["files_to_write"]} archivos del servidor (con respaldo).')
                    if word:
                        result = safe(self.term, lambda: self.app.apply({'plan_hash': plan['plan_hash'], 'confirm': word}))
                        if result:
                            self.term.write('  ' + ui.badge(self.term, 'ok', f'Aplicado. Transacción {result.get("transaction", "")}.'))
                            self._status = None
                            pause(self.term)
                            return
        elif choice == 'history':
            rows = self.app.transactions()
            options = [(r['id'], f'{r["created_at"]}  {pad(str(r["profile"]), 16)} {r["files"]} archivos', r['status']) for r in rows]
            picked = select(self.term, 'Transacciones', options, subtitle='Enter = revertir (pide APLICAR)')
            if picked:
                word = typed_confirm(self.term, 'Se restaurarán los archivos de esa transacción.')
                if word and safe(self.term, lambda: self.app.rollback({'id': picked, 'confirm': word})):
                    self.term.write('  ' + ui.badge(self.term, 'ok', 'Revertida.'))
                    self._status = None
                    pause(self.term)

    def screen_docs(self) -> None:
        from .docs import list_pages, render_page

        pages = list_pages()
        while True:
            slug = select(self.term, 'DOCUMENTACIÓN', [(p['slug'], f'{pad(p["title"], 34)}', p['group']) for p in pages])
            if not slug:
                return
            render_page(self.term, next(p for p in pages if p['slug'] == slug))

    def screen_settings(self) -> None:
        from ..core.workspace import update_workspace

        while True:
            ws = self.app.workspace().to_dict()
            keys = ['active_profile', 'server_profiles_editable', 'server_root', 'pack_roots', 'ox_inventory_dir', 'qbx_recoils_file', 'runtime_audit_root']
            options = [(k, pad(k, 26), ', '.join(ws[k]) if isinstance(ws[k], list) else str(ws[k])) for k in keys]
            key = select(self.term, 'CONFIGURACIÓN', options, subtitle='data/workspace.json · compartida con la web')
            if not key:
                return
            if key == 'active_profile':
                value = self.pick_profile('Perfil activo')
                if value:
                    safe(self.term, lambda: self.app.activate(value))
            elif key == 'server_profiles_editable':
                safe(self.term, lambda: update_workspace({key: not ws[key]}))
            else:
                current = ', '.join(ws[key]) if isinstance(ws[key], list) else ws[key]
                value = prompt(self.term, key, current)
                if value is not None:
                    safe(self.term, lambda: update_workspace({key: [v.strip() for v in value.split(',') if v.strip()] if isinstance(ws[key], list) else value}))
            self.app.catalog.invalidate()
            self._status = None
