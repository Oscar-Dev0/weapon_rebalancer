from __future__ import annotations

import json
import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

from weapon_rebalancer.config import Settings
from weapon_rebalancer.profile_loader import apply_external_profile, load_profile
from weapon_rebalancer.rebalance import RebalanceEngine


PROJECT_ROOT = Path(__file__).resolve().parents[1]
META_TEMPLATE = '''<?xml version="1.0" encoding="UTF-8"?>
<CWeaponInfoBlob>
  <Infos>
    <Item type="CWeaponInfo">
      <Name>{weapon}</Name>
      <Model>w_pi_test</Model>
      <Group>{group}</Group>
      <Damage value="25.000000" />
      <HitLimbsDamageModifier value="0.500000" />
      <NetworkHitLimbsDamageModifier value="0.500000" />
      {armour_tag}
      <WeaponRange value="50.000000" />
      <DamageFallOffRangeMin value="25.000000" />
      <DamageFallOffRangeMax value="50.000000" />
      <DamageFallOffModifier value="0.500000" />
      <TimeBetweenShots value="0.200000" />
      <AccuracySpread value="1.000000" />
      <RunAndGunAccuracyModifier value="1.000000" />
      <AccurateModeAccuracyModifier value="1.000000" />
      <RecoilAccuracyMax value="1.000000" />
      <RecoilErrorTime value="1.000000" />
      <RecoilRecoveryRate value="1.000000" />
      <RecoilShakeAmplitude value="1.000000" />
      <VehicleDamageModifier value="1.000000" />
      <WeaponFlags>Gun UsableOnFoot</WeaponFlags>
    </Item>
  </Infos>
</CWeaponInfoBlob>
'''


class HelmetOneTapTests(unittest.TestCase):
    def _run_profile(
        self,
        profile: dict,
        *,
        weapon: str = 'WEAPON_TESTPISTOL',
        group: str = 'GROUP_PISTOL',
        armour_tag: str = '',
    ) -> tuple[str, object]:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            meta = root / 'weapons.meta'
            meta.write_text(
                META_TEMPLATE.format(
                    weapon=weapon,
                    group=group,
                    armour_tag=armour_tag,
                ),
                encoding='utf-8',
            )

            settings = Settings.from_config()
            settings.root = root
            settings.dry_run = False
            settings.create_backup = False
            apply_external_profile(settings, profile)

            report = RebalanceEngine(settings).run()
            content = meta.read_text(encoding='utf-8')
            ET.fromstring(content)
            return content, report

    def test_rebelion_profile_forces_helmet_fields_and_keeps_configured_damage(self) -> None:
        profile = load_profile(PROJECT_ROOT / 'profiles/rebelion_server.json')
        content, report = self._run_profile(profile)

        self.assertIn('<Damage value="100.000000" />', content)
        self.assertIn('<HeadShotDamageModifierPlayer value="1500.000000" />', content)
        self.assertIn('<NetworkHeadShotPlayerDamageModifier value="1500.000000" />', content)
        self.assertIn('<LightlyArmouredDamageModifier value="100.000000" />', content)
        self.assertIn('<Penetration value="1.000000" />', content)
        self.assertEqual(report.files_changed, 1)

    def test_existing_armour_tag_is_replaced_not_clamped_to_two(self) -> None:
        profile = load_profile(PROJECT_ROOT / 'profiles/pvp_no_tank.json')
        content, _ = self._run_profile(
            profile,
            armour_tag='<LightlyArmouredDamageModifier value="0.750000" />',
        )

        self.assertEqual(content.count('<LightlyArmouredDamageModifier'), 1)
        self.assertIn('<LightlyArmouredDamageModifier value="100.000000" />', content)

    def test_bypass_helmets_can_be_disabled_from_json(self) -> None:
        profile = load_profile(PROJECT_ROOT / 'profiles/rebelion_server.json')
        profile = json.loads(json.dumps(profile))
        profile['headshot']['bypass_helmets'] = False

        content, _ = self._run_profile(
            profile,
            armour_tag='<LightlyArmouredDamageModifier value="0.750000" />',
        )

        self.assertIn('<LightlyArmouredDamageModifier value="2.000000" />', content)
        self.assertNotIn('<LightlyArmouredDamageModifier value="100.000000" />', content)

    def test_harmless_weapon_stays_at_zero_even_with_helmet_bypass(self) -> None:
        profile = load_profile(PROJECT_ROOT / 'profiles/rebelion_server.json')
        content, _ = self._run_profile(
            profile,
            weapon='WEAPON_SNOWBALL',
            group='GROUP_THROWN',
            armour_tag='<LightlyArmouredDamageModifier value="0.750000" />',
        )

        self.assertIn('<Damage value="0.000000" />', content)
        self.assertIn('<HeadShotDamageModifierPlayer value="0.000000" />', content)
        self.assertIn('<LightlyArmouredDamageModifier value="0.000000" />', content)
        self.assertIn('<Penetration value="0.000000" />', content)


if __name__ == '__main__':
    unittest.main()
