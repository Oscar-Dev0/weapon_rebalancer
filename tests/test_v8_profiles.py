"""Migración a los cuatro perfiles v8: equivalencias verificadas con el motor."""
from __future__ import annotations

import json
import unittest
from pathlib import Path

from weapon_rebalancer.core.workspace import load_workspace
from weapon_rebalancer.profile_store.legacy_migration import (
    build, engine_settings, output_diff, strip_meta,
)
from weapon_rebalancer.profile_store.migrations import migrate
from weapon_rebalancer.profile_store.repository import ProfileRepository
from weapon_rebalancer.profile_store.resolver import deep_merge, merge_diff, to_engine
from weapon_rebalancer.profile_store.schema import MODULE_PRESET_KEYS, structural_issues

ROOT = Path(__file__).resolve().parents[1]
PROFILES = ROOT / 'profiles'
LEGACY = PROFILES / 'legacy'
PENDING = PROFILES / 'migrations' / '2026-10-12_v8' / 'pending'


def legacy_engine(name: str) -> dict:
    return strip_meta(migrate(json.loads((LEGACY / f'{name}.json').read_text(encoding='utf-8')), name)[0])


def resolved_engine(repo: ProfileRepository, profile_id: str) -> dict:
    engine = to_engine(repo.resolved(profile_id))
    engine.pop('name', None)
    return engine


class MergePatchTests(unittest.TestCase):
    def test_null_removes_and_diff_roundtrips(self) -> None:
        base = {'a': 1, 'b': {'x': 1, 'y': 2}, 'l': [1, 2], 'gone': True}
        target = {'a': 2, 'b': {'x': 1, 'z': 3}, 'l': [3], 'new': {'k': 1}}
        delta = merge_diff(base, target)
        self.assertEqual(delta, {'gone': None, 'a': 2, 'b': {'y': None, 'z': 3}, 'l': [3], 'new': {'k': 1}})
        self.assertEqual(deep_merge(base, delta), target)


class OfficialProfilesTests(unittest.TestCase):
    repo = ProfileRepository()

    def test_four_main_profiles_exist_and_are_valid(self) -> None:
        rows = {r['id']: r for r in self.repo.list()}
        self.assertEqual({k: v['tier'] for k, v in rows.items() if v['tier'] in {'official', 'server'}},
                         {'balanced': 'official', 'realistic': 'official', 'competitive': 'official', 'flow_custom': 'server'})
        for profile_id in ('balanced', 'realistic', 'competitive', 'flow_custom'):
            with self.subTest(profile=profile_id):
                summary = rows[profile_id]
                for key in ('name', 'short_name', 'description', 'objective', 'audience'):
                    self.assertTrue(summary[key], f'{profile_id} sin {key}')
                self.assertTrue(summary['features'])
                issues = [i for i in structural_issues(self.repo.resolved(profile_id)) if i['severity'] in {'error', 'warning'}]
                self.assertEqual(issues, [])

    def test_flow_custom_reproduces_flow_caribe_exactly(self) -> None:
        self.assertEqual(engine_settings(resolved_engine(self.repo, 'flow_custom')), engine_settings(legacy_engine('flow_caribe')))

    def test_flow_custom_only_stores_differences(self) -> None:
        own = json.loads((PROFILES / 'server' / 'flow_custom.json').read_text(encoding='utf-8'))
        self.assertTrue(own['profile']['extends'])
        engine_part = {k: v for k, v in own.items() if k not in {'$schema', 'schema_version', 'profile'}}
        self.assertLess(len(json.dumps(engine_part)), len(json.dumps(legacy_engine('flow_caribe'))))

    def test_pending_deltas_reproduce_their_sources(self) -> None:
        for path in sorted(PENDING.glob('*.json')):
            with self.subTest(pending=path.name):
                data = json.loads(path.read_text(encoding='utf-8'))
                base = resolved_engine(self.repo, data['profile']['extends'])
                delta = {k: v for k, v in data.items() if k not in {'$schema', 'schema_version', 'profile'}}
                self.assertEqual(engine_settings(deep_merge(base, delta)), engine_settings(legacy_engine(data['profile']['migrated_from'])))

    def test_every_legacy_profile_is_accounted_for(self) -> None:
        report = json.loads((PROFILES / 'migrations' / '2026-10-12_v8' / 'report.json').read_text(encoding='utf-8'))
        mapped = {v['source'] for v in report['official'].values()}
        legacy = {p.stem for p in LEGACY.glob('*.json') if p.name != 'catalog.json'}
        self.assertEqual(legacy, mapped | set(report['pending']) | set(report['archived']))


@unittest.skipUnless(load_workspace().pack_paths and load_workspace().pack_paths[0].is_dir(), 'requiere el pack real')
class OutputEquivalenceTests(unittest.TestCase):
    repo = ProfileRepository()
    ws = load_workspace()

    def test_competitive_equals_pvp_competitive(self) -> None:
        self.assertEqual(output_diff(resolved_engine(self.repo, 'competitive'), legacy_engine('pvp_competitive_onetap'), self.ws), {})

    def test_realistic_differs_only_in_recoil(self) -> None:
        diff = output_diff(resolved_engine(self.repo, 'realistic'), legacy_engine('rp_serious_onetap'), self.ws)
        self.assertTrue(diff)
        self.assertTrue(all(set(fields) <= MODULE_PRESET_KEYS['recoil'] for fields in diff.values()))

    def test_migration_is_reproducible(self) -> None:
        result = build(LEGACY, self.ws, check_output=False)
        for profile_id, data in result['outputs'].items():
            tier = 'server' if profile_id == 'flow_custom' else 'official'
            on_disk = json.loads((PROFILES / tier / f'{profile_id}.json').read_text(encoding='utf-8'))
            for item in (data, on_disk):
                item['profile'].pop('created_at', None)
                item['profile'].pop('updated_at', None)
                item['profile'].pop('revision', None)
            self.assertEqual(data, on_disk, profile_id)


if __name__ == '__main__':
    unittest.main()
