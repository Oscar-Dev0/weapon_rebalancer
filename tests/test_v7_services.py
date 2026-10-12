from __future__ import annotations

import json
import tempfile
import time
import unittest
from pathlib import Path

from weapon_rebalancer.core.errors import Conflict, Forbidden, ValidationFailed
from weapon_rebalancer.core.paths import PathGuard
from weapon_rebalancer.core.workspace import validate_workspace
from weapon_rebalancer.services import simulator
from weapon_rebalancer.services.catalog import CatalogService
from weapon_rebalancer.services.generator import apply_plan, build_plan, list_transactions, rollback
from weapon_rebalancer.services.preview import preview

from tests.fixtures_v7 import fake_server


def neutral_profile(**extra):
    profile = {
        'engine_defaults': False,
        'modules': {'damage': 'configured', 'armour': 'configured', 'recoil': 'configured', 'accuracy': 'configured',
                    'range': 'configured', 'fire_rate': 'configured', 'reload': 'configured', 'headshot': 'original'},
        'harmless_weapons': [], 'ignore_weapons': [],
    }
    profile.update(extra)
    return profile


class WorkspaceTests(unittest.TestCase):
    def test_pack_must_be_inside_server(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, fake_server(Path(tmp)) as (ws, _server, _pack):
            self.assertEqual(validate_workspace(ws), [])
            outside = Path(tmp) / 'fuera'
            outside.mkdir()
            ws.pack_roots = [str(outside)]
            self.assertTrue(any('dentro del servidor' in e for e in validate_workspace(ws)))

    def test_path_guard(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / 'pack'
            root.mkdir()
            guard = PathGuard([root], 'prueba')
            guard.check(root / 'a.meta')
            with self.assertRaises(Forbidden):
                guard.check(root / '..' / 'escape.meta')


class CatalogTests(unittest.TestCase):
    def test_cross_reference_and_issues(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, fake_server(Path(tmp)) as (ws, _server, _pack):
            service = CatalogService(lambda: ws)
            catalog = service.get()
            pistol = catalog.weapons['WEAPON_PISTOL']
            codes = {i['code'] for i in pistol['issues']}
            self.assertIn('duplicate_definition', codes)
            self.assertIn('ox_duplicate_key', codes)
            self.assertIn('meta_unregistered', codes)
            self.assertEqual(pistol['qbx_recoil'], 0.3)
            self.assertEqual(pistol['components'][0]['ox_item'], 'at_clip_test')
            custom = catalog.weapons['WEAPON_CUSTOMGUN']
            self.assertTrue(custom['custom'])
            self.assertIn('ammo_unknown', {i['code'] for i in custom['issues']})
            self.assertIn('ox_without_meta', {i['code'] for i in catalog.weapons['WEAPON_ONLYOX']['issues']})
            # caché: misma firma -> mismo objeto; cambiar un archivo -> reescaneo
            self.assertIs(service.get(), catalog)
            meta_file = Path(ws.pack_roots[0]) / 'packB' / 'weapons.meta'
            time.sleep(0.01)
            meta_file.write_text(meta_file.read_text(encoding='utf-8').replace('12.000000', '13.000000'), encoding='utf-8')
            self.assertIsNot(service.get(), catalog)

    def test_headshot_onetap_detected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, fake_server(Path(tmp)) as (ws, _server, _pack):
            catalog = CatalogService(lambda: ws).get()
            # packA: 10 × 13.888889 ≈ 139 ≥ 100 -> mata de un tiro a la cabeza
            onetap = [i for i in catalog.weapons['WEAPON_PISTOL']['issues'] if i['code'] == 'headshot_onetap']
            self.assertEqual(len(onetap), 1)
            self.assertAlmostEqual(onetap[0]['value'], 138.89, places=1)
            # la personalizada (30 × 1.5 = 45) no lo dispara
            self.assertNotIn('headshot_onetap', {i['code'] for i in catalog.weapons['WEAPON_CUSTOMGUN']['issues']})


class PreviewTests(unittest.TestCase):
    def test_proposed_values_and_effect_issues(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, fake_server(Path(tmp)) as (ws, _server, _pack):
            catalog = CatalogService(lambda: ws).get()
            profile = neutral_profile(
                modules={**neutral_profile()['modules'], 'fire_rate': 'original'},
                weapons={'WEAPON_CUSTOMGUN': {'fields': {'damage': 22.0, 'time_between_shots': 0.2}},
                         'WEAPON_NOEXISTE': {'fields': {'damage': 5.0}}},
            )
            result = preview(profile, ws, catalog).data
            custom = result['weapons']['WEAPON_CUSTOMGUN']
            self.assertEqual(custom['proposed']['damage'], 22.0)
            self.assertEqual(custom['changes']['damage'], {'current': 30.0, 'proposed': 22.0})
            self.assertEqual(custom['proposed']['time_between_shots'], 0.1)  # fire_rate original: no se aplica
            codes = [i['code'] for i in result['issues']]
            self.assertIn('module_original', codes)
            self.assertIn('unknown_weapon', codes)
            self.assertTrue(result['idempotency']['idempotent'])

    def test_multiplier_without_restore_is_not_idempotent(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, fake_server(Path(tmp)) as (ws, _server, _pack):
            catalog = CatalogService(lambda: ws).get()
            profile = neutral_profile(weapon_field_multipliers={'WEAPON_CUSTOMGUN': {'damage': 2.0}},
                                      weapons={'WEAPON_CUSTOMGUN': {'fields': {'clip_size': 30}}})
            result = preview(profile, ws, catalog).data
            self.assertEqual(result['weapons']['WEAPON_CUSTOMGUN']['proposed']['damage'], 60.0)
            self.assertFalse(result['idempotency']['idempotent'])
            self.assertIn('not_idempotent', [i['code'] for i in result['issues']])

    def test_engine_rejects_invalid_profile(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, fake_server(Path(tmp)) as (ws, _server, _pack):
            catalog = CatalogService(lambda: ws).get()
            with self.assertRaises(ValidationFailed):
                preview({'modules': {'damage': 'inventado'}}, ws, catalog)


class SimulatorTests(unittest.TestCase):
    values = {
        'damage': 25.0, 'network_player_damage_modifier': 1.0, 'network_headshot': 2.0, 'headshot_player': 3.0,
        'network_hit_limbs': 0.5, 'weapon_range': 100.0, 'falloff_min': 20.0, 'falloff_max': 60.0,
        'falloff_modifier': 0.5, 'max_headshot_player': 50.0, 'time_between_shots': 0.2, 'clip_size': 3,
        'reload_time_mp': 2.0,
    }

    def test_falloff(self) -> None:
        self.assertEqual(simulator.falloff_factor(self.values, 10), 1.0)
        self.assertAlmostEqual(simulator.falloff_factor(self.values, 40), 0.75)
        self.assertEqual(simulator.falloff_factor(self.values, 80), 0.5)
        self.assertEqual(simulator.falloff_factor(self.values, 120), 0.0)

    def test_zones_and_ttk(self) -> None:
        head = simulator.simulate_weapon(self.values, simulator.Assumptions(zone='head', distance=10))
        self.assertEqual(head['damage']['per_shot'], 50.0)
        self.assertEqual(head['shots_to_kill'], 2)
        far_head = simulator.simulate_weapon(self.values, simulator.Assumptions(zone='head', distance=55))
        self.assertIn('fuera de la distancia', far_head['damage']['note'])
        torso = simulator.simulate_weapon(self.values, simulator.Assumptions(zone='torso', distance=10, armour=50))
        self.assertEqual(torso['shots_to_kill'], 6)  # 150 de vida+blindaje / 25
        self.assertAlmostEqual(torso['ttk'], 5 * 0.2 + 1 * 2.0)  # una recarga con cargador de 3
        self.assertAlmostEqual(torso['rpm'], 300.0)

    def test_assumption_validation(self) -> None:
        with self.assertRaises(ValidationFailed):
            simulator.Assumptions.parse({'distance': -1})


class GeneratorTests(unittest.TestCase):
    def test_apply_and_rollback_roundtrip(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, fake_server(Path(tmp)) as (ws, _server, pack):
            target = pack / 'packB' / 'weapons.meta'
            before = target.read_bytes()
            qbx_before = ws.qbx_recoils_path.read_bytes()
            catalog = CatalogService(lambda: ws).get()
            profile = neutral_profile(weapons={'WEAPON_PISTOL': {'fields': {'damage': 15.0}}})
            plan = build_plan(profile, {'qbx_recoils': {'WEAPON_PISTOL': 0.5}}, ws, catalog, 'prueba')
            self.assertEqual(plan.preview['blocking'], [])
            self.assertEqual(set(plan.kinds.values()), {'meta', 'qbx_recoils'})
            with self.assertRaises(ValidationFailed):
                apply_plan(plan, ws, 'no')
            result = apply_plan(plan, ws, 'APLICAR')
            self.assertTrue(result['applied'])
            self.assertIn('<Damage value="15.000000" />', target.read_text(encoding='utf-8'))
            self.assertTrue(Path(str(target) + '.bak').is_file())  # se creó el .bak que faltaba
            self.assertIn('= 0.5,', ws.qbx_recoils_path.read_text(encoding='utf-8'))
            tx = list_transactions()[0]
            self.assertEqual(tx['status'], 'applied')
            rollback(tx['id'], ws, 'APLICAR')
            self.assertEqual(target.read_bytes(), before)
            self.assertEqual(ws.qbx_recoils_path.read_bytes(), qbx_before)
            self.assertFalse(Path(str(target) + '.bak').exists())  # .bak creado por la transacción eliminado
            self.assertEqual(list_transactions()[0]['status'], 'rolled_back')

    def test_plan_rejected_if_file_changed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, fake_server(Path(tmp)) as (ws, _server, pack):
            catalog = CatalogService(lambda: ws).get()
            plan = build_plan(neutral_profile(weapons={'WEAPON_PISTOL': {'fields': {'damage': 15.0}}}), None, ws, catalog, 'prueba')
            target = pack / 'packB' / 'weapons.meta'
            target.write_text(target.read_text(encoding='utf-8') + '\n', encoding='utf-8')
            with self.assertRaises(Conflict):
                apply_plan(plan, ws, 'APLICAR')

    def test_non_utf8_file_is_blocked(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, fake_server(Path(tmp)) as (ws, _server, pack):
            target = pack / 'packB' / 'weapons.meta'
            target.write_bytes(target.read_bytes().replace(b'<Model>', b'<!-- \xff -->\n      <Model>', 1))
            catalog = CatalogService(lambda: ws).get()
            plan = build_plan(neutral_profile(weapons={'WEAPON_PISTOL': {'fields': {'damage': 15.0}}}), None, ws, catalog, 'prueba')
            self.assertTrue(any('UTF-8' in b['message'] for b in plan.preview['blocking']))
            with self.assertRaises(ValidationFailed):
                apply_plan(plan, ws, 'APLICAR')

    def test_nothing_to_apply(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, fake_server(Path(tmp)) as (ws, _server, _pack):
            catalog = CatalogService(lambda: ws).get()
            plan = build_plan(neutral_profile(), None, ws, catalog, 'prueba')
            self.assertFalse(apply_plan(plan, ws, 'APLICAR')['applied'])


if __name__ == '__main__':
    unittest.main()

_ = json


class EngineReportTests(unittest.TestCase):
    def test_annotations_do_not_count_as_changes(self) -> None:
        from weapon_rebalancer.engine.config import Settings
        from weapon_rebalancer.engine.profile_loader import apply_external_profile
        from weapon_rebalancer.engine.rebalance import RebalanceEngine

        with tempfile.TemporaryDirectory() as tmp, fake_server(Path(tmp)) as (ws, _server, pack):
            settings = Settings.from_config()
            apply_external_profile(settings, neutral_profile(fire_rate_classifier={'enabled': True, 'groups': ['GROUP_RIFLE']},
                                                             weapons={'WEAPON_CUSTOMGUN': {'fields': {'clip_size': 12}}}))
            settings.root = pack
            report = RebalanceEngine(settings, capture={}).run()
            annotated = [c for c in report.changes if any(f.startswith('fire_rate_class') for f in c.changed_fields)]
            self.assertTrue(annotated)
            self.assertFalse(any(c.content_changed for c in annotated))
            self.assertEqual(report.weapons_changed, 0)
            self.assertEqual(report.files_changed, 0)
