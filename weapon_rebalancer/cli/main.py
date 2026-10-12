"""Punto de entrada de `wr.py`: menú interactivo y comandos para automatización/SSH.

Sin argumentos en una terminal abre el estudio interactivo. Todos los comandos aceptan
`--json` cuando producen datos, y ninguno exige una terminal interactiva.

Códigos de salida: 0 correcto · 1 validación fallida o cancelado · 2 error de uso/aplicación · 130 interrumpido.
"""
from __future__ import annotations

import argparse
import sys

from ..core.errors import AppError
from . import commands, ui
from .term import Term

EPILOG = """ejemplos:
  wr.py                                     menú interactivo
  wr.py status                              estado del servidor
  wr.py weapons -q glock -p competitive     tabla de armas con un perfil aplicado
  wr.py weapon WEAPON_PISTOL                ficha con procedencia de cada valor
  wr.py profiles                            perfiles oficiales, servidor y usuario
  wr.py profile derive competitive mi_pvp   perfil derivado editable
  wr.py set mi_pvp GROUP_PISTOL damage=55   cambia un valor (pide confirmación)
  wr.py compare balanced competitive -w WEAPON_PISTOL
  wr.py simulate WEAPON_PISTOL:current WEAPON_PISTOL:proposed -p competitive
  wr.py validate flow_custom --preview
  wr.py generate -p flow_custom             vista previa (añade --apply para escribir)
"""


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog='wr.py', description='Weapon Rebalancer — FiveM Weapon Configuration Studio',
                                     epilog=EPILOG, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--no-color', action='store_true', help='Sin colores (también con NO_COLOR=1).')
    parser.add_argument('--ascii', action='store_true', help='Bordes y símbolos ASCII.')
    sub = parser.add_subparsers(dest='command')

    def add(name: str, func, help_text: str, json_out: bool = False) -> argparse.ArgumentParser:
        command = sub.add_parser(name, help=help_text, description=help_text)
        command.set_defaults(func=func)
        if json_out:
            command.add_argument('--json', action='store_true', help='Salida JSON (para scripts).')
        return command

    add('menu', None, 'Abre el estudio interactivo.')
    add('status', commands.cmd_status, 'Estado del servidor y del perfil activo.', True)

    p = add('weapons', commands.cmd_weapons, 'Tabla de armas con el perfil aplicado.', True)
    p.add_argument('-q', '--search', help='Texto a buscar en identificador o nombre.')
    p.add_argument('-c', '--category', help='Categoría (pistol, smg, rifle, sniper, shotgun, mg, melee…).')
    p.add_argument('-p', '--profile', help='Perfil (por defecto el activo).')
    p.add_argument('--changed', action='store_true', help='Solo las armas que el perfil cambia.')
    p.add_argument('--all', action='store_true', help='Incluir armas sin weapons.meta.')
    p.add_argument('--limit', type=int, default=0)

    p = add('weapon', commands.cmd_weapon, 'Ficha de un arma con la procedencia de cada valor.', True)
    p.add_argument('name')
    p.add_argument('-p', '--profile')
    p.add_argument('--all', action='store_true', help='Todos los parámetros, no solo los principales.')

    p = add('profiles', commands.cmd_profiles, 'Lista de perfiles.', True)
    p.add_argument('--all', action='store_true', help='Incluir los archivados (legacy).')

    p = add('profile', commands.cmd_profile, 'Gestión de un perfil.', True)
    actions = p.add_subparsers(dest='action', required=True)
    for name, help_text in (('show', 'Detalle'), ('activate', 'Marcar como activo'), ('validate', 'Validar'),
                            ('history', 'Historial'), ('affected', 'Armas afectadas')):
        a = actions.add_parser(name, help=help_text)
        a.add_argument('id')
        a.add_argument('--json', action='store_true')
        if name == 'validate':
            a.add_argument('--preview', action='store_true')
            a.add_argument('--limit', type=int, default=30)
    a = actions.add_parser('create', help='Perfil de usuario vacío o derivado')
    a.add_argument('new_id')
    a.add_argument('--name')
    a.add_argument('--description')
    a.add_argument('--extends')
    for name in ('derive', 'duplicate'):
        a = actions.add_parser(name, help='Derivado (hereda) o copia completa')
        a.add_argument('id')
        a.add_argument('new_id')
        a.add_argument('--name')
    a = actions.add_parser('rename', help='Renombrar (solo usuario)')
    a.add_argument('id')
    a.add_argument('new_id', nargs='?')
    a.add_argument('--name')
    a = actions.add_parser('delete', help='Mover a la papelera (solo usuario)')
    a.add_argument('id')
    a.add_argument('--yes', action='store_true')
    a = actions.add_parser('export', help='Exportar JSON')
    a.add_argument('id')
    a.add_argument('-o', '--output')
    a.add_argument('--resolved', action='store_true', help='Con la herencia aplicada.')
    a.add_argument('--legacy', action='store_true', help='Formato de la CLI antigua.')
    a.add_argument('--yes', action='store_true', help='Sobrescribir el archivo de salida.')
    a = actions.add_parser('import', help='Importar JSON como perfil de usuario')
    a.add_argument('file')
    a.add_argument('--id', dest='new_id')
    a.add_argument('--yes', action='store_true', help='Sobrescribir si existe (con respaldo).')
    a = actions.add_parser('restore', help='Restaurar una versión del historial')
    a.add_argument('id')
    a.add_argument('file')
    a.add_argument('--yes', action='store_true')

    for name, func, help_text in (('set', commands.cmd_set, 'Cambia campos: TARGET campo=valor (inherit = null, unset = quitar).'),
                                  ('headshot', commands.cmd_headshot, 'Política de cabeza: TARGET mode=onetap multiplier=1.5 distance=150')):
        p = add(name, func, help_text, True)
        p.add_argument('profile')
        p.add_argument('target', help='WEAPON_X, GROUP_X o global')
        p.add_argument('assignments', nargs='+')
        p.add_argument('--yes', action='store_true', help='Guardar sin preguntar.')

    p = add('compare', commands.cmd_compare, 'Compara perfiles (o original/current).', True)
    p.add_argument('a')
    p.add_argument('b')
    p.add_argument('-w', '--weapon', action='append', help='Arma concreta (se puede repetir).')
    p.add_argument('-k', '--keys', help='Campos separados por coma.')
    p.add_argument('--limit', type=int, default=40)

    p = add('simulate', commands.cmd_simulate, 'Simulador teórico: ARMA[:original|current|proposed] …', True)
    p.add_argument('weapons', nargs='+')
    p.add_argument('-p', '--profile')
    p.add_argument('--zone', choices=['torso', 'head', 'limbs'], default='torso')
    p.add_argument('--distance', type=float, default=15.0)
    p.add_argument('--armour', type=float, default=0.0)
    p.add_argument('--health', type=float, default=100.0)
    p.add_argument('--target', choices=['player', 'npc'], default='player')

    for name in ('validate', 'check'):
        p = add(name, commands.cmd_validate, 'Valida perfiles (todos si no indicas uno).', True)
        p.add_argument('profile', nargs='?')
        p.add_argument('--preview', action='store_true', help='Incluye efecto en el pack, repetibilidad y generador.')
        p.add_argument('--verbose', action='store_true')
        p.add_argument('--limit', type=int, default=15)

    p = add('generate', commands.cmd_generate, 'Vista previa del generador; --apply escribe (pide APLICAR).', True)
    p.add_argument('-p', '--profile')
    p.add_argument('--diff', metavar='RUTA', help='Muestra el diff de un archivo del plan.')
    p.add_argument('--apply', action='store_true')
    p.add_argument('--confirm', help='APLICAR (necesario sin terminal interactiva).')
    p.add_argument('--limit', type=int, default=20)

    add('transactions', commands.cmd_transactions, 'Historial de aplicaciones.', True)
    p = add('rollback', commands.cmd_rollback, 'Revierte una aplicación.')
    p.add_argument('id')
    p.add_argument('--confirm', required=True, help='APLICAR')

    p = add('params', commands.cmd_params, 'Documentación de parámetros.', True)
    p.add_argument('section', nargs='?')
    p.add_argument('--all', action='store_true', help='Incluir avanzados.')

    p = add('docs', commands.cmd_docs, 'Documentación: list | show PÁGINA | build')
    p.add_argument('action', nargs='?', default='list', choices=['list', 'show', 'build'])
    p.add_argument('slug', nargs='?')

    p = add('settings', commands.cmd_settings, 'Configuración: show | set clave=valor', True)
    p.add_argument('action', nargs='?', default='show', choices=['show', 'set'])
    p.add_argument('assignments', nargs='*')

    p = add('serve', None, 'Panel web local.')
    p.add_argument('--host')
    p.add_argument('--port', type=int)
    p = add('scan', None, 'Reescanea ox_inventory y los packs.', True)
    p = add('migrate', None, 'Migra a v8 los perfiles de usuario en formato antiguo.')
    p.add_argument('--write', action='store_true')
    sub.add_parser('rebalance', help='CLI original del motor (wr.py rebalance --help).')
    return parser


def _serve(args) -> int:
    from ..api.server import serve
    from ..core.workspace import load_workspace

    ws = load_workspace()
    serve(args.host or ws.server.host, args.port or ws.server.port)
    return 0


def _scan(app, term: Term, args) -> int:
    with ui.progress(term, 'Escaneando ox_inventory y los packs'):
        catalog = app.catalog.get(force=True)
    summary = catalog.summary()
    if args.json:
        commands.emit_json(summary)
        return 0
    ui.section(term, 'Escaneo', f'{summary["duration_ms"]} ms')
    ui.kv(term, [('Armas', f'{summary["weapons"]} ({summary["official"]} oficiales, {summary["custom"]} personalizadas)'),
                 ('META', f'{summary["meta_files"]} archivos · {summary["definitions"]} definiciones'),
                 ('Solo ox_inventory', str(summary['ox_only'])), ('Solo META', str(summary['meta_only'])),
                 ('Duplicadas', str(summary['duplicates'])), ('Recoil por script', str(summary['with_script_recoil']))])
    for label, count in sorted(summary['categories'].items(), key=lambda item: -item[1]):
        term.write(f'    {count:4d}  {label}')
    return 0


def _migrate(app, term: Term, args) -> int:
    for profile_id in app.repo.ids():
        result = app.repo.migrate_file(profile_id, dry_run=not args.write)
        state = 'migrado' if result.get('migrated') else ('se migraría' if result.get('would_migrate') else 'sin cambios')
        term.write(f'  {profile_id}: {state}')
    if not args.write:
        term.write('  ' + term.style('Vista previa: usa --write para migrar (la versión anterior queda en el historial).', 'muted'))
    return 0


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv[:1] == ['rebalance']:
        from .legacy import main as legacy_main

        sys.argv = ['wr.py rebalance', *argv[1:]]
        legacy_main()
        return 0
    parser = build_parser()
    args = parser.parse_args(argv)
    term = Term(color=False if args.no_color else None, unicode=False if args.ascii else None)
    if args.command == 'serve':
        return _serve(args)
    try:
        from ..services.app import App

        app = App()
        if args.command in (None, 'menu'):
            if not term.interactive:
                parser.print_help()
                return 0 if args.command is None else 2
            from .interactive import Studio

            return Studio(app, term).run()
        if args.command == 'scan':
            return _scan(app, term, args)
        if args.command == 'migrate':
            return _migrate(app, term, args)
        return int(args.func(app, term, args) or 0)
    except AppError as exc:
        term.write('  ' + ui.badge(term, 'error', exc.message))
        if exc.hint:
            term.write('     ' + term.style(f'{term.sym["arrow"]} {exc.hint}', 'muted'))
        if isinstance(exc.details, list):
            ui.issues(term, [d if isinstance(d, dict) else {'severity': 'error', 'message': str(d)} for d in exc.details], limit=15)
        return 2
    except KeyboardInterrupt:
        term.write('')
        term.write('  ' + term.style('Interrumpido. No se escribió nada pendiente.', 'muted'))
        return 130
    except BrokenPipeError:
        # La salida se cortó (p. ej. `wr.py weapons | head`): terminar en silencio.
        import os

        devnull = os.open(os.devnull, os.O_WRONLY)
        os.dup2(devnull, sys.stdout.fileno())
        return 0
