from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from weapon_rebalancer.adapters.fivem_pack import scan_pack
from weapon_rebalancer.adapters.lua_table import LuaExpr, parse_lua_return_table
from weapon_rebalancer.adapters.ox_inventory import load_ox_inventory
from weapon_rebalancer.adapters.qbx_recoils import load_qbx_recoils, render_qbx_recoils
from weapon_rebalancer.core.joaat import joaat, signed

from tests.fixtures_v7 import OX_WEAPONS, fake_server


class JoaatTests(unittest.TestCase):
    def test_known_hashes(self) -> None:
        self.assertEqual(joaat('WEAPON_PISTOL'), 453432689)
        self.assertEqual(joaat('weapon_pistol'), 453432689)  # sin distinción de mayúsculas, como en el juego
        self.assertEqual(signed(joaat('WEAPON_PISTOL_MK2')), -1075685676)


class LuaTableTests(unittest.TestCase):
    def test_parses_literals_comments_and_duplicates(self) -> None:
        table = parse_lua_return_table(OX_WEAPONS)
        weapons = table.get('Weapons')
        self.assertIn('WEAPON_CUSTOMGUN', weapons.items)
        self.assertEqual(weapons.get('WEAPON_CUSTOMGUN').get('label'), 'Custom "Gun"')
        self.assertNotIn('WEAPON_COMENTADA', weapons.items)
        self.assertEqual([d[0] for d in weapons.duplicates], ['WEAPON_PISTOL'])
        self.assertEqual(weapons.get('WEAPON_PISTOL').get('label'), 'Pistol (duplicada)')  # en Lua gana la última

    def test_expressions_are_preserved(self) -> None:
        table = parse_lua_return_table("return { a = joaat('X'), b = 1 + 2, c = -0x10, d = [[largo]] }")
        self.assertIsInstance(table.get('a'), LuaExpr)
        self.assertEqual(table.get('a').raw, "joaat('X')")
        self.assertIsInstance(table.get('b'), LuaExpr)
        self.assertEqual(table.get('c'), -16)
        self.assertEqual(table.get('d'), 'largo')


class OxInventoryTests(unittest.TestCase):
    def test_load(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, fake_server(Path(tmp)) as (ws, _server, _pack):
            data = load_ox_inventory(ws.ox_path)
            self.assertEqual(data.errors, [])
            self.assertEqual(data.weapons['WEAPON_PISTOL'].hash, 453432689)
            self.assertEqual(data.ammo, {'ammo-9': '9mm'})
            self.assertEqual(len(data.duplicates), 1)
            component = data.components['at_clip_test']
            self.assertIn(joaat('COMPONENT_TEST_CLIP_01'), component.hashes)
            self.assertIn(-1234567 & 0xFFFFFFFF, component.hashes)

    def test_missing_file_reports_error(self) -> None:
        data = load_ox_inventory(Path('/no/existe'))
        self.assertTrue(data.errors)


class QbxRecoilsTests(unittest.TestCase):
    def test_load_and_render_preserves_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, fake_server(Path(tmp)) as (ws, _server, _pack):
            path = ws.qbx_recoils_path
            data = load_qbx_recoils(path)
            self.assertEqual(data.value_for('WEAPON_PISTOL'), 0.3)
            self.assertIsNone(data.value_for('WEAPON_APPISTOL'))  # comentada = inactiva
            text, notes = render_qbx_recoils(path, {'WEAPON_PISTOL': 0.45, 'WEAPON_CUSTOMGUN': 0.2})
            self.assertIn('[453432689] = 0.45,', text)
            self.assertIn("--['weapon_pistol']", text)
            self.assertIn(f'[{signed(joaat("WEAPON_CUSTOMGUN"))}] = 0.2,', text)
            self.assertIn('-- [584646201] = 0.3,', text)  # se conserva la entrada comentada
            self.assertTrue(text.rstrip().endswith('return recoils'))
            self.assertEqual(len(notes), 2)
            path.write_text(text, encoding='utf-8')
            self.assertEqual(load_qbx_recoils(path).value_for('WEAPON_CUSTOMGUN'), 0.2)
            removed, _ = render_qbx_recoils(path, {'WEAPON_PISTOL': None})
            path.write_text(removed, encoding='utf-8')
            self.assertIsNone(load_qbx_recoils(path).value_for('WEAPON_PISTOL'))


class PackScanTests(unittest.TestCase):
    def test_values_original_and_registration(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, fake_server(Path(tmp)) as (ws, _server, _pack):
            snapshot = scan_pack(ws.pack_paths)
            by_path = {(d.weapon, d.resource): d for d in snapshot.definitions}
            pistol = by_path[('WEAPON_PISTOL', 'packA')]
            self.assertEqual(pistol.values['damage'], 10.0)
            self.assertEqual(pistol.original['damage'], 26.0)
            self.assertEqual(pistol.values['time_between_shots'], 0.18)  # campo después de AttachPoints anidados
            self.assertIn('Gun', pistol.values['weapon_flags'])
            self.assertTrue(pistol.registered)
            self.assertEqual(pistol.components, ['COMPONENT_TEST_CLIP_01'])
            other = by_path[('WEAPON_PISTOL', 'packB')]
            self.assertFalse(other.registered)  # packB no tiene fxmanifest con WEAPONINFO_FILE
            self.assertFalse(other.has_backup)
            self.assertIsNone(other.original)


if __name__ == '__main__':
    unittest.main()
