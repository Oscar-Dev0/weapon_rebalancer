from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from weapon_rebalancer.config import Settings
from weapon_rebalancer.fields import FIELDS
from weapon_rebalancer.inventory import export_full_profile, export_meta_inventory
from weapon_rebalancer.profile_loader import apply_external_profile
from weapon_rebalancer.rebalance import RebalanceEngine


META = '''<?xml version="1.0" encoding="UTF-8"?>
<CWeaponInfoBlob>
  <Infos>
    <Item type="CWeaponInfo">
      <Name>WEAPON_TESTRIFLE</Name>
      <Model>w_ar_test</Model>
      <Audio>AUDIO_ITEM_RIFLE</Audio>
      <Slot>SLOT_TEST</Slot>
      <DamageType>BULLET</DamageType>
      <FireType>INSTANT_HIT</FireType>
      <WheelSlot>WHEEL_RIFLE</WheelSlot>
      <Group>GROUP_RIFLE</Group>
      <AmmoInfo ref="AMMO_RIFLE" />
      <ClipSize value="30" />
      <Damage value="40.0" />
      <NetworkPlayerDamageModifier value="1.0" />
      <HeadShotDamageModifierPlayer value="2.0" />
      <NetworkHeadShotPlayerDamageModifier value="2.0" />
      <LightlyArmouredDamageModifier value="1.0" />
      <Penetration value="0.1" />
      <CustomScalarTag value="2.0" />
      <CustomVector x="1.0" y="2.0" z="3.0" />
      <WeaponFlags>CarriedInHand Gun CanFreeAim AnimReload</WeaponFlags>
    </Item>
  </Infos>
</CWeaponInfoBlob>
'''


class FullMetaTests(unittest.TestCase):
    def make_root(self) -> tuple[tempfile.TemporaryDirectory[str], Path, Path]:
        temp = tempfile.TemporaryDirectory()
        root = Path(temp.name)
        resource = root / 'test_weapon'
        resource.mkdir()
        meta = resource / 'weapons.meta'
        meta.write_text(META, encoding='utf-8')
        return temp, root, meta

    def test_catalog_is_broad(self) -> None:
        self.assertGreaterEqual(len(FIELDS), 100)
        for key in ('network_player_damage_modifier', 'force_hit_ped', 'camera_fov', 'weapon_flags'):
            self.assertIn(key, FIELDS)

    def test_onetap_adds_helmet_flags_without_destroying_existing_flags(self) -> None:
        temp, root, meta = self.make_root()
        self.addCleanup(temp.cleanup)
        settings = Settings.from_config()
        settings.root = root
        settings.dry_run = False
        settings.ignore_weapons.clear()
        settings.external_group_profiles = {'GROUP_RIFLE': {'damage': 40.0}}
        settings.headshot_profile = 'onetap'
        settings.headshot.enabled = True
        settings.headshot.one_tap = True
        RebalanceEngine(settings).run()
        text = meta.read_text(encoding='utf-8')
        self.assertIn('CarriedInHand', text)
        self.assertIn('AnimReload', text)
        self.assertIn('IgnoreHelmets', text)
        self.assertIn('ArmourPenetrating', text)

    def test_dynamic_meta_replaces_unknown_scalar_and_vector(self) -> None:
        temp, root, meta = self.make_root()
        self.addCleanup(temp.cleanup)
        settings = Settings.from_config()
        settings.root = root
        settings.dry_run = False
        settings.ignore_weapons.clear()
        settings.headshot_profile = 'original'
        apply_external_profile(settings, {
            'modules': {'damage': 'original', 'armour': 'original', 'recoil': 'original', 'accuracy': 'original', 'range': 'original', 'fire_rate': 'original', 'reload': 'original', 'headshot': 'original'},
            'groups': {
                'GROUP_RIFLE': {
                    'fields': {},
                    'meta': {
                        'CustomScalarTag': {'kind': 'value_attr', 'value': 9.5},
                        'CustomVector': {'attributes': {'x': 4.0, 'z': 8.0}},
                    },
                }
            },
            'ignore_weapons': [], 'harmless_weapons': [], 'allow_damage_weapons': [],
        })
        RebalanceEngine(settings).run()
        text = meta.read_text(encoding='utf-8')
        self.assertIn('<CustomScalarTag value="9.5" />', text)
        self.assertIn('x="4.0"', text)
        self.assertIn('y="2.0"', text)
        self.assertIn('z="8.0"', text)

    def test_exports_all_meta_information_and_reusable_profile(self) -> None:
        temp, root, _ = self.make_root()
        self.addCleanup(temp.cleanup)
        inventory_path = root / 'inventory.json'
        profile_path = root / 'full_profile.json'
        inventory = export_meta_inventory(root, inventory_path)
        profile = export_full_profile(root, profile_path)
        self.assertEqual(inventory['summary']['meta_files'], 1)
        self.assertIn('CustomScalarTag', inventory['tag_catalog'])
        weapon = profile['weapons']['WEAPON_TESTRIFLE']
        self.assertEqual(weapon['fields']['damage'], 40.0)
        self.assertEqual(weapon['meta']['CustomScalarTag']['value'], 2.0)
        self.assertIn('Gun', weapon['weapon_flags']['add'])
        json.loads(inventory_path.read_text(encoding='utf-8'))
        json.loads(profile_path.read_text(encoding='utf-8'))


if __name__ == '__main__':
    unittest.main()
