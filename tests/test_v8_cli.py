"""Terminal: operaciones de edición, equivalencia con la web, salida sin color y bloqueo entre procesos."""
from __future__ import annotations

import io
import json
import subprocess
import sys
import tempfile
import unittest
from argparse import Namespace
from contextlib import redirect_stdout
from pathlib import Path

from weapon_rebalancer.api.server import Api
from weapon_rebalancer.cli import commands
from weapon_rebalancer.cli.main import main as cli_main
from weapon_rebalancer.cli.term import ANSI_RE, Term
from weapon_rebalancer.core.errors import Conflict
from weapon_rebalancer.profile_store.edit import apply_ops, summarize_changes
from weapon_rebalancer.profile_store.repository import ProfileRepository
from weapon_rebalancer.services.app import App
from weapon_rebalancer.services.catalog import CatalogService

from tests.fixtures_v7 import fake_server

BASE = {'schema_version': 8, 'profile': {'id': 'base', 'name': 'Base'}, 'engine_defaults': False,
        'modules': {'damage': 'configured', 'recoil': 'original', 'headshot': 'original', 'fire_rate': 'configured'},
        'groups': {'GROUP_RIFLE': {'fields': {'recoil_shake_amplitude': 0.5}}}}


class EditOpsTests(unittest.TestCase):
    def test_set_field_enables_module_after_confirmation(self) -> None:
        result = apply_ops(BASE, [{'op': 'set_field', 'scope': 'WEAPON_PISTOL', 'key': 'recoil_error_time', 'value': 0.1}], confirm_dormant=False)
        self.assertEqual(result['confirmations'][0]['modules'], ['recoil'])
        self.assertIn('GROUP_RIFLE.recoil_shake_amplitude', result['confirmations'][0]['dormant'][0])
        self.assertNotIn('weapons', result['profile'])  # no se aplicó sin confirmar
        result = apply_ops(BASE, [{'op': 'set_field', 'scope': 'WEAPON_PISTOL', 'key': 'recoil_error_time', 'value': 0.1}])
        self.assertEqual(result['profile']['modules']['recoil'], 'configured')
        self.assertEqual(result['profile']['weapons']['WEAPON_PISTOL']['fields']['recoil_error_time'], 0.1)

    def test_headshot_scope_declares_global_mode(self) -> None:
        result = apply_ops(BASE, [{'op': 'set_headshot', 'scope': 'GROUP_PISTOL', 'values': {'mode': 'onetap', 'multiplier': 2}}])
        self.assertEqual(result['profile']['modules']['headshot'], 'normal')
        self.assertEqual(result['profile']['headshot']['mode'], 'normal')  # nunca se hereda one-tap ×1500
        self.assertEqual(result['profile']['groups']['GROUP_PISTOL']['headshot'], {'mode': 'onetap', 'multiplier': 2})

    def test_lists_flags_qbx_and_inherit(self) -> None:
        result = apply_ops(BASE, [
            {'op': 'set_list', 'list': 'ignore_weapons', 'weapon': 'weapon_rpg'},
            {'op': 'add_flag', 'scope': 'WEAPON_PISTOL', 'flag': 'IgnoreHelmets'},
            {'op': 'remove_flag', 'scope': 'WEAPON_PISTOL', 'flag': 'ignorehelmets'},
            {'op': 'set_qbx_recoil', 'weapon': 'WEAPON_PISTOL', 'value': False},
            {'op': 'inherit_field', 'scope': 'GROUP_RIFLE', 'key': 'recoil_shake_amplitude'},
        ])
        profile = result['profile']
        self.assertEqual(profile['ignore_weapons'], ['WEAPON_RPG'])
        self.assertEqual(profile['weapons']['WEAPON_PISTOL']['weapon_flags']['remove'], ['ignorehelmets'])
        self.assertIs(profile['resources']['qbx_recoils']['WEAPON_PISTOL'], False)
        self.assertIsNone(profile['groups']['GROUP_RIFLE']['fields']['recoil_shake_amplitude'])
        paths = {c['path'] for c in summarize_changes(BASE, profile)}
        self.assertIn('resources.qbx_recoils.WEAPON_PISTOL', paths)


class CliWebEquivalenceTests(unittest.TestCase):
    def make_app(self, tmp: Path, ws) -> App:
        directory = tmp / 'profiles'
        (directory / 'official').mkdir(parents=True)
        (directory / 'official' / 'base.json').write_text(json.dumps(BASE), encoding='utf-8')
        app = App()
        app.repo = ProfileRepository(directory)
        app.catalog = CatalogService(lambda: ws)
        app.workspace = lambda: ws  # type: ignore[method-assign]
        return app

    def test_same_operations_same_result(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, fake_server(Path(tmp)) as (ws, _server, _pack):
            app = self.make_app(Path(tmp), ws)
            app.repo.derive('base', 'cli')
            app.repo.derive('base', 'web')
            term = Term(color=False, unicode=False, stream=io.StringIO())
            # Terminal
            args = Namespace(profile='cli', target='GROUP_PISTOL', assignments=['damage=21', 'clip_size=14'], yes=True, json=False)
            self.assertEqual(commands.cmd_set(app, term, args), 0)
            # Web: mismas operaciones por la API
            api = Api(app)
            _raw, sha = app.repo.read_raw('web')
            result = api.dispatch('POST', '/api/profiles/ops', {}, {'profile_id': 'web', 'ops': [
                {'op': 'set_field', 'scope': 'GROUP_PISTOL', 'key': 'damage', 'value': 21},
                {'op': 'set_field', 'scope': 'GROUP_PISTOL', 'key': 'clip_size', 'value': 14}]})
            api.dispatch('PUT', '/api/profiles/web', {}, {'profile': result['profile'], 'sha': sha})
            strip = lambda d: {k: v for k, v in d.items() if k != 'profile'}  # noqa: E731
            self.assertEqual(strip(app.repo.load('cli')), strip(app.repo.load('web')))
            # Generador: mismo plan para la misma configuración
            plan_cli = app.plan({'profile_id': 'cli'})['plan_hash']
            plan_web = api.dispatch('POST', '/api/generator/plan', {}, {'profile_id': 'web'})['plan_hash']
            self.assertEqual(plan_cli, plan_web)
            # Comparador: mismo resultado por la terminal (--json) y por la API
            buffer = io.StringIO()
            with redirect_stdout(buffer):
                commands.cmd_compare(app, term, Namespace(a='base', b='cli', weapon=None, keys=None, limit=40, json=True))
            via_api = api.dispatch('POST', '/api/profiles/compare', {}, {'a': {'profile_id': 'base'}, 'b': {'profile_id': 'cli'}})
            self.assertEqual(json.loads(buffer.getvalue())['effects'], json.loads(json.dumps(via_api['effects'], default=str)))

    def test_web_inherit_null_matches_cli_inherit(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, fake_server(Path(tmp)) as (ws, _server, _pack):
            app = self.make_app(Path(tmp), ws)
            app.repo.derive('base', 'cli')
            app.repo.derive('base', 'web')
            api = Api(app)
            # El panel recibe el perfil base resuelto para mostrar lo heredado.
            loaded = api.dispatch('GET', '/api/profiles/web', {}, None)
            self.assertEqual(loaded['base']['groups']['GROUP_RIFLE']['fields']['recoil_shake_amplitude'], 0.5)
            term = Term(color=False, unicode=False, stream=io.StringIO())
            commands.cmd_set(app, term, Namespace(profile='cli', target='GROUP_RIFLE', assignments=['recoil_shake_amplitude=inherit'], yes=True, json=False))
            _raw, sha = app.repo.read_raw('web')
            result = api.dispatch('POST', '/api/profiles/ops', {}, {'profile_id': 'web', 'ops': [
                {'op': 'inherit_field', 'scope': 'GROUP_RIFLE', 'key': 'recoil_shake_amplitude'}]})
            self.assertIn('base', result)
            api.dispatch('PUT', '/api/profiles/web', {}, {'profile': result['profile'], 'sha': sha})
            strip = lambda d: {k: v for k, v in d.items() if k != 'profile'}  # noqa: E731
            self.assertEqual(strip(app.repo.load('cli')), strip(app.repo.load('web')))
            self.assertIsNone(app.repo.load('web')['groups']['GROUP_RIFLE']['fields']['recoil_shake_amplitude'])
            self.assertNotIn('recoil_shake_amplitude', app.resolved(app.repo.load('web'))['groups'].get('GROUP_RIFLE', {}).get('fields', {}))

    def test_official_profile_cannot_be_edited_from_cli(self) -> None:
        from weapon_rebalancer.core.errors import Forbidden

        with tempfile.TemporaryDirectory() as tmp, fake_server(Path(tmp)) as (ws, _server, _pack):
            app = self.make_app(Path(tmp), ws)
            term = Term(color=False, stream=io.StringIO())
            with self.assertRaises(Forbidden):
                commands.cmd_set(app, term, Namespace(profile='base', target='global', assignments=['damage=1'], yes=True, json=False))


class TerminalOutputTests(unittest.TestCase):
    def test_no_color_has_no_ansi_and_ascii_fallback(self) -> None:
        stream = io.StringIO()
        term = Term(color=False, unicode=False, stream=stream)
        from weapon_rebalancer.cli import ui

        ui.banner(term, '9.9.9')
        ui.table(term, [ui.Column('A', 'a'), ui.Column('B', 'b', align='right')], [{'a': 'uno', 'b': 1.5}, {'a': 'dos', 'b': None}])
        out = stream.getvalue()
        self.assertFalse(ANSI_RE.search(out))
        self.assertIn('WEAPON REBALANCER', out)
        self.assertIn('N/D', out)  # nunca se inventa un dato ausente
        self.assertFalse(set(out) & set('╭╮╰╯─│✔✖▲●›❯↑↓…'))  # bordes y símbolos ASCII (el texto puede llevar acentos)

    def test_menu_without_tty_prints_help(self) -> None:
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            code = cli_main([])
        self.assertEqual(code, 0)
        self.assertIn('wr.py', buffer.getvalue())

    def test_cross_process_lock(self) -> None:
        from weapon_rebalancer.core import filelock, paths

        with tempfile.TemporaryDirectory() as tmp:
            script = (
                'import sys, time; from unittest import mock; from pathlib import Path\n'
                'from weapon_rebalancer.core import paths, filelock\n'
                f'with mock.patch.object(paths, "DATA_DIR", Path({tmp!r})):\n'
                '    with filelock.file_lock("prueba"):\n'
                '        print("ok", flush=True); time.sleep(3)\n'
            )
            holder = subprocess.Popen([sys.executable, '-c', script], cwd=str(Path(__file__).resolve().parents[1]), stdout=subprocess.PIPE, text=True)
            try:
                self.assertEqual(holder.stdout.readline().strip(), 'ok')
                from unittest import mock

                with mock.patch.object(paths, 'DATA_DIR', Path(tmp)):
                    with self.assertRaises(Conflict):
                        with filelock.file_lock('prueba', timeout=0.3):
                            pass
            finally:
                holder.wait(timeout=10)


if __name__ == '__main__':
    unittest.main()
