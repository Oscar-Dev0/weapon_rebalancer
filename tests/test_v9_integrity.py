"""Sello de integridad (cambios hechos a mano), paso a otro servidor y registro."""
from __future__ import annotations

import shutil
import tempfile
import unittest
from pathlib import Path

from weapon_rebalancer.core.errors import Conflict, ValidationFailed
from weapon_rebalancer.core.jsonlog import tail
from weapon_rebalancer.services import integrity, sync
from weapon_rebalancer.services.catalog import CatalogService
from weapon_rebalancer.services.generator import apply_plan, build_plan, list_transactions, rollback

from tests.fixtures_v7 import fake_server
from tests.test_v7_services import neutral_profile


def with_target(tmp: Path, ws, server: Path) -> Path:
    """Copia el servidor de prueba como «principal» y lo registra en sync_targets."""
    target = tmp / 'principal'
    shutil.copytree(server, target)
    ws.sync_targets = {'principal': str(target)}
    return target


class IntegrityTests(unittest.TestCase):
    def test_manual_change_detected_and_logged_once(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, fake_server(Path(tmp)) as (ws, _server, pack):
            self.assertFalse(integrity.check(ws)['sealed'])
            with self.assertRaises(ValidationFailed):
                integrity.seal(ws, reason='')
            integrity.seal(ws, reason='inicio')
            self.assertTrue(integrity.check(ws)['clean'])
            meta = pack / 'packB' / 'weapons.meta'
            meta.write_text(meta.read_text(encoding='utf-8').replace('Gun UsableOnFoot', 'Gun ArmourPenetrating'), encoding='utf-8')
            (pack / 'packB' / 'extra.meta').write_text('<x/>', encoding='utf-8')
            result = integrity.check(ws)
            self.assertEqual([m['path'] for m in result['modified']], [str(meta.relative_to(ws.server_path))])
            self.assertEqual(len(result['added']), 1)
            integrity.check(ws)                      # el mismo cambio no se registra dos veces
            events = [e for e in tail('changes') if e['event'] == 'integrity.manual_change']
            self.assertEqual(len(events), 1)
            self.assertEqual(events[0]['level'], 'warning')
            integrity.seal(ws, reason='revisado')
            self.assertTrue(integrity.check(ws)['clean'])

    def test_apply_and_rollback_reseal_only_their_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, fake_server(Path(tmp)) as (ws, _server, pack):
            integrity.seal(ws, reason='inicio')
            other = pack / 'packA' / 'fxmanifest.lua'
            other.write_text(other.read_text(encoding='utf-8') + '-- a mano\n', encoding='utf-8')
            catalog = CatalogService(lambda: ws).get()
            plan = build_plan(neutral_profile(weapons={'WEAPON_PISTOL': {'fields': {'damage': 15.0}}}), None, ws, catalog, 'prueba')
            apply_plan(plan, ws, 'APLICAR')
            after = integrity.check(ws, record=False)
            # lo que escribió la herramienta queda sellado; el cambio a mano sigue visible
            self.assertEqual([m['path'] for m in after['modified']], [str(other.relative_to(ws.server_path))])
            rollback(list_transactions()[0]['id'], ws, 'APLICAR')
            self.assertEqual(integrity.check(ws, record=False)['total'], 1)


class LegacyWriteTests(unittest.TestCase):
    def test_legacy_write_is_logged_and_sealed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, fake_server(Path(tmp)) as (ws, _server, pack):
            integrity.seal(ws, reason='inicio')
            before = integrity.scan(ws)
            meta = pack / 'packB' / 'weapons.meta'
            meta.write_text(meta.read_text(encoding='utf-8') + '\n', encoding='utf-8')
            changed = integrity.record_tool_write(ws, before, event='legacy.rebalance_write', reason='prueba', argv=['--write'])
            self.assertEqual(changed, [str(meta.relative_to(ws.server_path))])
            self.assertEqual(tail('changes')[-1]['event'], 'integrity.seal')
            self.assertTrue(any(e['event'] == 'legacy.rebalance_write' and e['total'] == 1 for e in tail('changes')))
            self.assertTrue(integrity.check(ws)['clean'])


class SyncTests(unittest.TestCase):
    def test_sync_copies_with_backup_seal_and_rollback(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, fake_server(Path(tmp)) as (ws, server, pack):
            target = with_target(Path(tmp), ws, server)
            meta = pack / 'packB' / 'weapons.meta'
            meta.write_text(meta.read_text(encoding='utf-8').replace('12.000000', '15.000000'), encoding='utf-8')
            (pack / 'packB' / 'nuevo.meta').write_text('<x/>', encoding='utf-8')
            (target / meta.relative_to(server).parent / 'solo_principal.meta').write_text('<y/>', encoding='utf-8')
            before = (target / meta.relative_to(server)).read_bytes()
            preview = sync.plan(ws, 'principal')
            self.assertEqual({c['status'] for c in preview['changes']}, {'cambia', 'nuevo'})
            self.assertEqual(len(preview['only_target']), 1)
            with self.assertRaises(ValidationFailed):
                sync.apply(ws, 'principal', 'no')
            result = sync.apply(ws, 'principal', 'APLICAR', reason='prueba')
            self.assertEqual(result['files'], 2)
            self.assertEqual((target / meta.relative_to(server)).read_bytes(), meta.read_bytes())
            self.assertTrue((target / meta.relative_to(server).parent / 'solo_principal.meta').is_file())  # no se borra
            self.assertTrue(integrity.check(ws, 'principal')['clean'])
            self.assertEqual(list_transactions()[0]['target'], 'principal')
            self.assertTrue(any(e['event'] == 'sync.apply' for e in tail('changes')))
            rollback(result['transaction'], ws, 'APLICAR')
            self.assertEqual((target / meta.relative_to(server)).read_bytes(), before)
            self.assertFalse((target / 'resources' / meta.relative_to(server / 'resources').parent / 'nuevo.meta').exists())

    def test_manual_change_in_target_blocks_without_force(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, fake_server(Path(tmp)) as (ws, server, pack):
            target = with_target(Path(tmp), ws, server)
            integrity.seal(ws, 'principal', reason='inicio')
            rel = (pack / 'packB' / 'weapons.meta').relative_to(server)
            (pack / rel.relative_to(pack.relative_to(server))).write_text('<a/>', encoding='utf-8')
            (target / rel).write_text('<arreglo_en_principal/>', encoding='utf-8')
            with self.assertRaises(Conflict):
                sync.apply(ws, 'principal', 'APLICAR')
            self.assertEqual((target / rel).read_text(encoding='utf-8'), '<arreglo_en_principal/>')
            result = sync.apply(ws, 'principal', 'APLICAR', force=True)
            self.assertTrue(result['applied'])

    def test_unknown_target(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, fake_server(Path(tmp)) as (ws, _server, _pack):
            with self.assertRaises(Exception):
                sync.plan(ws, 'principal')


if __name__ == '__main__':
    unittest.main()
