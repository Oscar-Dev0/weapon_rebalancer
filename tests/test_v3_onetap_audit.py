from __future__ import annotations

import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

from weapon_rebalancer.config import Settings
from weapon_rebalancer.profile_loader import apply_external_profile, load_profile
from weapon_rebalancer.rebalance import RebalanceEngine


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def meta_text(
    weapon: str = 'WEAPON_TEST',
    group: str = 'GROUP_RIFLE',
    damage: float = 25.0,
    network_modifier: float = 1.0,
    flags: str = 'Gun UsableOnFoot AnimReload',
) -> str:
    return f'''<?xml version="1.0" encoding="UTF-8"?>
<CWeaponInfoBlob>
  <Infos>
    <Item type="CWeaponInfo">
      <Name>{weapon}</Name>
      <Model>w_test</Model>
      <DamageType>BULLET</DamageType>
      <FireType>INSTANT_HIT</FireType>
      <Group>{group}</Group>
      <Damage value="{damage:.6f}" />
      <NetworkPlayerDamageModifier value="{network_modifier:.6f}" />
      <HeadShotDamageModifierPlayer value="1.000000" />
      <NetworkHeadShotPlayerDamageModifier value="1.000000" />
      <LightlyArmouredDamageModifier value="0.750000" />
      <Penetration value="0.010000" />
      <WeaponRange value="60.000000" />
      <DamageFallOffRangeMin value="25.000000" />
      <DamageFallOffRangeMax value="60.000000" />
      <DamageFallOffModifier value="0.500000" />
      <WeaponFlags>{flags}</WeaponFlags>
    </Item>
  </Infos>
</CWeaponInfoBlob>
'''


class V3OneTapAuditTests(unittest.TestCase):
    def _run(self, profile_name: str, text: str) -> tuple[str, object]:
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        root = Path(temp.name)
        resource = root / 'weapon_pack'
        resource.mkdir()
        (resource / 'fxmanifest.lua').write_text(
            "fx_version 'cerulean'\ngame 'gta5'\nfiles {'weapons.meta'}\ndata_file 'WEAPONINFO_FILE_PATCH' 'weapons.meta'\n",
            encoding='utf-8',
        )
        meta = resource / 'weapons.meta'
        meta.write_text(text, encoding='utf-8')

        settings = Settings.from_config()
        settings.root = root
        settings.dry_run = False
        settings.create_backup = False
        settings.ignore_weapons.clear()
        apply_external_profile(settings, load_profile(PROJECT_ROOT / 'profiles' / profile_name))
        report = RebalanceEngine(settings).run()
        output = meta.read_text(encoding='utf-8')
        ET.fromstring(output)
        return output, report

    def test_group_distance_keeps_shotgun_short(self) -> None:
        output, report = self._run(
            'rebelion_balanced_v3.json',
            meta_text(group='GROUP_SHOTGUN'),
        )
        self.assertIn('<MaxHeadShotDistancePlayer value="30.000000" />', output)
        self.assertIn('<WeaponRange value="30.000000" />', output)
        self.assertNotIn('<MaxHeadShotDistancePlayer value="300.000000" />', output)
        self.assertEqual(report.onetap_audit_failed, 0)
        self.assertEqual(report.onetap_audit_passed, 1)

    def test_zero_network_modifier_is_repaired_and_head_only_gets_safe_floor(self) -> None:
        output, report = self._run(
            'headshot_focus_onetap.json',
            meta_text(damage=0.0, network_modifier=0.0),
        )
        self.assertIn('<NetworkPlayerDamageModifier value="1.000000" />', output)
        self.assertIn('<Damage value="0.833334" />', output)
        self.assertEqual(report.onetap_audit_failed, 0)
        change = next(c for c in report.changes if c.weapon == 'WEAPON_TEST')
        self.assertGreaterEqual(float(change.onetap_metrics['estimated_network_headshot_damage']), 1250.0)

    def test_nonlethal_flags_are_removed_only_for_onetap_firearm(self) -> None:
        output, report = self._run(
            'pvp_competitive_onetap.json',
            meta_text(flags='Gun NonLethal NonViolent AnimReload'),
        )
        self.assertNotIn('NonLethal', output)
        self.assertNotIn('NonViolent', output)
        self.assertIn('IgnoreHelmets', output)
        self.assertIn('ArmourPenetrating', output)
        self.assertEqual(report.onetap_audit_failed, 0)

    def test_duplicate_weapon_definitions_are_reported(self) -> None:
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        root = Path(temp.name)
        for index in (1, 2):
            resource = root / f'pack_{index}'
            resource.mkdir()
            (resource / 'fxmanifest.lua').write_text(
                "data_file 'WEAPONINFO_FILE_PATCH' 'weapons.meta'\n",
                encoding='utf-8',
            )
            (resource / 'weapons.meta').write_text(meta_text(weapon='WEAPON_DUPLICATE'), encoding='utf-8')

        settings = Settings.from_config()
        settings.root = root
        settings.dry_run = True
        settings.ignore_weapons.clear()
        apply_external_profile(settings, load_profile(PROJECT_ROOT / 'profiles' / 'rebelion_balanced_v3.json'))
        report = RebalanceEngine(settings).run()
        self.assertIn('WEAPON_DUPLICATE', report.duplicate_weapons)
        self.assertEqual(len(report.duplicate_weapons['WEAPON_DUPLICATE']), 2)

    def test_unregistered_meta_is_reported(self) -> None:
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        root = Path(temp.name)
        resource = root / 'orphan_pack'
        resource.mkdir()
        (resource / 'weapons.meta').write_text(meta_text(), encoding='utf-8')

        settings = Settings.from_config()
        settings.root = root
        settings.dry_run = True
        settings.ignore_weapons.clear()
        apply_external_profile(settings, load_profile(PROJECT_ROOT / 'profiles' / 'rebelion_balanced_v3.json'))
        report = RebalanceEngine(settings).run()
        self.assertIn('orphan_pack/weapons.meta', report.unregistered_meta_files)

    def test_original_body_profile_preserves_existing_damage(self) -> None:
        output, report = self._run(
            'original_body_real_onetap.json',
            meta_text(damage=23.0),
        )
        self.assertIn('<Damage value="23.000000" />', output)
        self.assertIn('<HeadShotDamageModifierPlayer value="1500.000000" />', output)
        self.assertEqual(report.onetap_audit_failed, 0)

    def test_weapon_headshot_scope_overrides_group_distance(self) -> None:
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        root = Path(temp.name)
        meta = root / 'weapons.meta'
        meta.write_text(meta_text(weapon='WEAPON_SPECIAL'), encoding='utf-8')
        settings = Settings.from_config()
        settings.root = root
        settings.dry_run = False
        settings.create_backup = False
        settings.ignore_weapons.clear()
        profile = load_profile(PROJECT_ROOT / 'profiles' / 'rebelion_balanced_v3.json')
        profile['weapons'] = {
            'WEAPON_SPECIAL': {
                'fields': {},
                'headshot': {'mode': 'onetap', 'distance': 175.0}
            }
        }
        apply_external_profile(settings, profile)
        report = RebalanceEngine(settings).run()
        output = meta.read_text(encoding='utf-8')
        self.assertIn('<MaxHeadShotDistancePlayer value="175.000000" />', output)
        self.assertEqual(report.onetap_audit_failed, 0)

    def test_duplicate_definitions_inside_same_file_are_reported(self) -> None:
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        root = Path(temp.name)
        resource = root / 'same_file'
        resource.mkdir()
        (resource / 'fxmanifest.lua').write_text(
            "data_file 'WEAPONINFO_FILE_PATCH' 'weapons.meta'\n",
            encoding='utf-8',
        )
        first = meta_text(weapon='WEAPON_DOUBLE')
        second_block = meta_text(weapon='WEAPON_DOUBLE').split('<Infos>', 1)[1].split('</Infos>', 1)[0]
        combined = first.replace('</Infos>', second_block + '</Infos>', 1)
        (resource / 'weapons.meta').write_text(combined, encoding='utf-8')
        settings = Settings.from_config()
        settings.root = root
        settings.dry_run = True
        settings.ignore_weapons.clear()
        apply_external_profile(settings, load_profile(PROJECT_ROOT / 'profiles' / 'rebelion_balanced_v3.json'))
        report = RebalanceEngine(settings).run()
        self.assertIn('WEAPON_DOUBLE', report.duplicate_weapons)
        self.assertEqual(len(report.duplicate_weapons['WEAPON_DOUBLE']), 2)


if __name__ == '__main__':
    unittest.main()
