from __future__ import annotations

import json
import tempfile
import unittest
from dataclasses import asdict
from pathlib import Path

from weapon_rebalancer.engine.config import Settings
from weapon_rebalancer.core.errors import Conflict, ValidationFailed
from weapon_rebalancer.engine.profile_loader import apply_external_profile, load_profile
from weapon_rebalancer.profile_store.migrations import detect_version, downgrade_to_legacy, is_legacy, migrate
from weapon_rebalancer.profile_store.repository import ProfileRepository
from weapon_rebalancer.profile_store.resolver import resolve, to_engine
from weapon_rebalancer.profile_store.schema import blank_profile, structural_issues

from tests.fixtures_v7 import fake_server

PROFILES = Path(__file__).resolve().parents[1] / 'profiles' / 'legacy'


def settings_for(data: dict) -> dict:
    settings = Settings.from_config()
    apply_external_profile(settings, data)
    result = asdict(settings)
    result.pop('root', None)
    return result


class MigrationTests(unittest.TestCase):
    def test_every_bundled_profile_migrates_without_behaviour_change(self) -> None:
        for path in sorted(PROFILES.glob('*.json')):
            if path.name == 'catalog.json':
                continue
            with self.subTest(profile=path.name):
                legacy = load_profile(path)
                migrated, notes = migrate(legacy, path.stem)
                self.assertEqual(detect_version(migrated), 8)
                self.assertFalse(is_legacy(migrated))
                self.assertEqual(migrated['profile']['id'], path.stem)
                # el motor recibe exactamente la misma configuración
                self.assertEqual(settings_for(to_engine(migrated)), settings_for(legacy))
                # y la migración es reversible
                back = downgrade_to_legacy(migrated)
                self.assertEqual(settings_for(back), settings_for(legacy))
                if is_legacy(legacy):
                    self.assertTrue(notes)

    def test_blank_profile_touches_nothing(self) -> None:
        settings = Settings.from_config()
        apply_external_profile(settings, to_engine(blank_profile('x', 'X')))
        self.assertEqual(settings.explicit_overrides, {})
        self.assertEqual(settings.active_preset, 'none')
        self.assertEqual(settings.headshot_profile, 'original')


class ResolverTests(unittest.TestCase):
    def test_extends_merges_and_detects_cycles(self) -> None:
        base = {'profile': {'id': 'base'}, 'modules': {'damage': 'configured'}, 'groups': {'GROUP_PISTOL': {'fields': {'damage': 10, 'clip_size': 12}}}, 'ignore_weapons': ['A']}
        child = {'profile': {'id': 'hijo', 'extends': 'base'}, 'groups': {'GROUP_PISTOL': {'fields': {'damage': 20}}}, 'ignore_weapons': ['B']}
        store = {'base': base, 'hijo': child}
        resolved = resolve(child, store.__getitem__)
        self.assertEqual(resolved['groups']['GROUP_PISTOL']['fields'], {'damage': 20, 'clip_size': 12})
        self.assertEqual(resolved['ignore_weapons'], ['B'])  # las listas se reemplazan
        self.assertEqual(resolved['profile']['resolved_chain'], ['base', 'hijo'])
        loop = {'a': {'profile': {'id': 'a', 'extends': 'b'}}, 'b': {'profile': {'id': 'b', 'extends': 'a'}}}
        with self.assertRaises(ValidationFailed):
            resolve(loop['a'], loop.__getitem__)


class SchemaTests(unittest.TestCase):
    def test_structural_issues(self) -> None:
        issues = structural_issues({
            'decorativo': 1,
            'validation': {'require_runtime_critical_hits': True},
            'modules': {'damage': 'mucho', 'headshot': 'normal'},
            'weapons': {'WEAPON_X': {'fields': {'campo_falso': 1, 'damage': 'alto'}}},
            'resources': {'qbx_recoils': {'WEAPON_X': 50}},
        })
        codes = {i['code'] for i in issues}
        self.assertTrue({'unknown_top_level', 'validation_noop', 'module_value', 'unknown_field', 'field_type',
                         'qbx_value', 'headshot_mode_inherited'} <= codes)

    def test_clean_profile_has_no_issues(self) -> None:
        self.assertEqual(structural_issues(blank_profile('x', 'X')), [])


class RepositoryTests(unittest.TestCase):
    def make(self, tmp: str, server_editable: bool = True) -> tuple[ProfileRepository, Path]:
        directory = Path(tmp) / 'profiles'
        (directory / 'official').mkdir(parents=True)
        (directory / 'server').mkdir()
        (directory / 'official' / 'base.json').write_text(json.dumps({
            'schema_version': 8, 'profile': {'id': 'base', 'name': 'Base'},
            'modules': {'damage': 'configured', 'headshot': 'original'},
            'groups': {'GROUP_PISTOL': {'fields': {'damage': 10.0, 'clip_size': 12}}}}), encoding='utf-8')
        (directory / 'server' / 'srv.json').write_text(json.dumps({
            'schema_version': 8, 'profile': {'id': 'srv', 'name': 'Servidor', 'extends': 'base'},
            'groups': {'GROUP_PISTOL': {'fields': {'damage': 20.0}}}}), encoding='utf-8')
        return ProfileRepository(directory, server_editable=lambda: server_editable), directory

    def test_tiers_and_protection(self) -> None:
        from weapon_rebalancer.core.errors import Forbidden

        with tempfile.TemporaryDirectory() as tmp, fake_server(Path(tmp)):
            repo, _ = self.make(tmp)
            self.assertEqual(repo.tier('base'), 'official')
            self.assertFalse(repo.editable('base'))
            with self.assertRaises(Forbidden):
                repo.save('base', repo.load('base'))
            with self.assertRaises(Forbidden):
                repo.delete('srv')  # solo se borran perfiles de usuario
            self.assertTrue(repo.editable('srv'))
            repo.save('srv', repo.load('srv'))
            locked, _ = self.make(tmp + '/b', server_editable=False)
            with self.assertRaises(Forbidden):
                locked.save('srv', locked.load('srv'))

    def test_derive_history_conflict_trash(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, fake_server(Path(tmp)):
            repo, directory = self.make(tmp)
            repo.derive('base', 'mio')
            self.assertEqual(repo.tier('mio'), 'user')
            self.assertTrue((directory / 'user' / 'mio.json').is_file())
            resolved = repo.resolved('mio')
            self.assertEqual(resolved['groups']['GROUP_PISTOL']['fields'], {'damage': 10.0, 'clip_size': 12})
            data, sha = repo.read_raw('mio')
            data['groups'] = {'GROUP_PISTOL': {'fields': {'clip_size': None, 'damage': 15.0}}}  # null quita lo heredado
            repo.save('mio', data, expected_sha=sha)
            self.assertEqual(repo.resolved('mio')['groups']['GROUP_PISTOL']['fields'], {'damage': 15.0})
            with self.assertRaises(Conflict):
                repo.save('mio', data, expected_sha=sha)  # sha viejo: otra interfaz guardó antes
            history = repo.history('mio')
            self.assertEqual([h['action'] for h in history], ['edit', 'create'])
            repo.restore('mio', history[0]['file'])
            self.assertNotIn('groups', repo.load('mio'))
            repo.save('base2', {'profile': {'extends': 'mio'}})
            with self.assertRaises(Conflict):
                repo.delete('mio')  # mio tiene un derivado
            repo.delete('base2')
            result = repo.delete('mio')
            self.assertTrue(Path(result['trash']).is_file())
            self.assertFalse(repo.exists('mio'))

    def test_resolved_cache_invalidates_when_parent_changes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, fake_server(Path(tmp)):
            repo, directory = self.make(tmp)
            self.assertEqual(repo.resolved('srv')['groups']['GROUP_PISTOL']['fields']['clip_size'], 12)
            base_file = directory / 'official' / 'base.json'
            data = json.loads(base_file.read_text(encoding='utf-8'))
            data['groups']['GROUP_PISTOL']['fields']['clip_size'] = 30
            import os
            base_file.write_text(json.dumps(data), encoding='utf-8')
            os.utime(base_file, ns=(1, 1))
            self.assertEqual(repo.resolved('srv')['groups']['GROUP_PISTOL']['fields']['clip_size'], 30)

    def test_migration_of_user_legacy_file_can_be_reverted(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, fake_server(Path(tmp)):
            repo, directory = self.make(tmp)
            original = json.dumps({'name': 'L', 'schema_version': 4, 'modules': {'damage': 'original'}}, indent=2)
            (directory / 'user').mkdir(exist_ok=True)
            (directory / 'user' / 'l.json').write_text(original, encoding='utf-8')
            self.assertTrue(repo.summary('l')['legacy'])
            self.assertTrue(repo.migrate_file('l')['migrated'])
            self.assertEqual(repo.read_raw('l')[0]['schema_version'], 8)
            repo.revert_migration('l')
            self.assertEqual((directory / 'user' / 'l.json').read_text(encoding='utf-8'), original)

    def test_invalid_ids_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, fake_server(Path(tmp)):
            repo, _ = self.make(tmp)
            for bad in ('../x', 'Mayus', 'a/b', '', '.oculto'):
                with self.assertRaises(ValidationFailed):
                    repo.path(bad)


class ContradictionTests(unittest.TestCase):
    def test_detects_contradictions(self) -> None:
        issues = structural_issues({
            'ignore_weapons': ['WEAPON_A'], 'allow_ignored_weapons': ['WEAPON_A'],
            'weapons': {'WEAPON_A': {'fields': {'damage': 1.0}, 'weapon_flags': {'add': ['Automatic'], 'remove': ['automatic']}},
                        'WEAPON_B': {'headshot': {'mode': 'onetap'}}},
            'modules': {'headshot': 'original'},
            'fire_rate_damage_rules': [
                {'name': 'general', 'groups': [], 'max_time_between_shots': 0.5, 'damage': 10},
                {'name': 'rapida', 'groups': ['GROUP_SMG'], 'max_time_between_shots': 0.1, 'damage': 5},
            ],
        })
        codes = {i['code'] for i in issues}
        self.assertTrue({'list_conflict', 'ignored_but_configured', 'flag_conflict', 'headshot_scoped_noop', 'rule_unreachable'} <= codes)


if __name__ == '__main__':
    unittest.main()
