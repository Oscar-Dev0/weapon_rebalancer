from __future__ import annotations

import re
import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

from weapon_rebalancer.config import Settings
from weapon_rebalancer.profile_loader import apply_external_profile, load_profile
from weapon_rebalancer.rebalance import RebalanceEngine
from weapon_rebalancer.vanilla_weapons import CATALOG_ID, OFFICIAL_WEAPONS


PROJECT_ROOT = Path(__file__).resolve().parents[1]
PROFILE_PATH = PROJECT_ROOT / 'profiles' / 'vanilla_normal_custom_plus15_revolver_onetap.json'


def weapon_block(weapon: str, group: str, damage: float, weapon_range: float = 100.0) -> str:
    return f'''    <Item type="CWeaponInfo">
      <Name>{weapon}</Name>
      <Model>w_test</Model>
      <Group>{group}</Group>
      <Damage value="{damage:.6f}" />
      <NetworkPlayerDamageModifier value="1.000000" />
      <NetworkPedDamageModifier value="1.000000" />
      <HitLimbsDamageModifier value="0.750000" />
      <NetworkHitLimbsDamageModifier value="0.750000" />
      <LightlyArmouredDamageModifier value="0.750000" />
      <WeaponRange value="{weapon_range:.6f}" />
      <DamageFallOffRangeMin value="{weapon_range * 0.5:.6f}" />
      <DamageFallOffRangeMax value="{weapon_range * 0.9:.6f}" />
      <DamageFallOffModifier value="0.500000" />
      <HeadShotDamageModifierPlayer value="3.000000" />
      <NetworkHeadShotPlayerDamageModifier value="3.000000" />
      <HeadShotDamageModifierAI value="2.000000" />
      <MinHeadShotDistancePlayer value="0.000000" />
      <MaxHeadShotDistancePlayer value="{weapon_range:.6f}" />
      <MinHeadShotDistanceAI value="0.000000" />
      <MaxHeadShotDistanceAI value="{weapon_range:.6f}" />
      <WeaponFlags>Gun UsableOnFoot</WeaponFlags>
    </Item>'''


def meta(*blocks: str) -> str:
    return '<?xml version="1.0" encoding="UTF-8"?>\n<CWeaponInfoBlob>\n  <Infos>\n' + '\n'.join(blocks) + '\n  </Infos>\n</CWeaponInfoBlob>\n'


def value_for(text: str, weapon: str, tag: str) -> float:
    block_match = re.search(
        rf'<Item type="CWeaponInfo">(?:(?!</Item>).)*?<Name>{re.escape(weapon)}</Name>(?P<body>.*?)</Item>',
        text,
        re.DOTALL,
    )
    if not block_match:
        raise AssertionError(f'No se encontró {weapon}')
    tag_match = re.search(rf'<{re.escape(tag)} value="([^"]+)"', block_match.group(0))
    if not tag_match:
        raise AssertionError(f'No se encontró {tag} en {weapon}')
    return float(tag_match.group(1))


class CustomClassifierV5Tests(unittest.TestCase):
    def _settings(self, root: Path) -> Settings:
        settings = Settings.from_config()
        settings.root = root
        settings.dry_run = False
        settings.create_backup = True
        apply_external_profile(settings, load_profile(PROFILE_PATH))
        return settings

    def test_catalog_contains_representative_official_weapons(self) -> None:
        self.assertEqual(CATALOG_ID, 'cfx_weapon_models_2026_07_02')
        for weapon in (
            'WEAPON_PISTOL',
            'WEAPON_REVOLVER',
            'WEAPON_TECPISTOL',
            'WEAPON_BATTLERIFLE',
            'WEAPON_SNOWLAUNCHER',
        ):
            self.assertIn(weapon, OFFICIAL_WEAPONS)

    def test_restores_official_and_buffs_only_custom_by_fifteen_percent(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            path = root / 'weapons.meta'
            original = meta(
                weapon_block('WEAPON_PISTOL', 'GROUP_PISTOL', 25.0, 100.0),
                weapon_block('WEAPON_OSCAR_CUSTOM', 'GROUP_PISTOL', 40.0, 100.0),
                weapon_block('WEAPON_REVOLVER', 'GROUP_PISTOL', 70.0, 120.0),
                weapon_block('WEAPON_OSCAR_REVOLVER', 'GROUP_PISTOL', 90.0, 110.0),
            )
            touched = meta(
                weapon_block('WEAPON_PISTOL', 'GROUP_PISTOL', 999.0, 600.0),
                weapon_block('WEAPON_OSCAR_CUSTOM', 'GROUP_PISTOL', 999.0, 600.0),
                weapon_block('WEAPON_REVOLVER', 'GROUP_PISTOL', 1.0, 10.0),
                weapon_block('WEAPON_OSCAR_REVOLVER', 'GROUP_PISTOL', 1.0, 10.0),
            )
            path.write_text(touched, encoding='utf-8')
            Path(str(path) + '.bak').write_text(original, encoding='utf-8')

            report = RebalanceEngine(self._settings(root)).run()
            output = path.read_text(encoding='utf-8')
            ET.fromstring(output)

            # Oficial: regresa exactamente al backup, sin +15%.
            self.assertAlmostEqual(value_for(output, 'WEAPON_PISTOL', 'Damage'), 25.0)
            self.assertAlmostEqual(value_for(output, 'WEAPON_PISTOL', 'WeaponRange'), 100.0)
            self.assertAlmostEqual(value_for(output, 'WEAPON_PISTOL', 'HeadShotDamageModifierPlayer'), 3.0)

            # Custom: daño y distancias originales multiplicados por 1.15.
            self.assertAlmostEqual(value_for(output, 'WEAPON_OSCAR_CUSTOM', 'Damage'), 46.0)
            self.assertAlmostEqual(value_for(output, 'WEAPON_OSCAR_CUSTOM', 'WeaponRange'), 115.0)
            self.assertAlmostEqual(value_for(output, 'WEAPON_OSCAR_CUSTOM', 'DamageFallOffRangeMin'), 57.5)
            self.assertAlmostEqual(value_for(output, 'WEAPON_OSCAR_CUSTOM', 'DamageFallOffRangeMax'), 103.5)
            self.assertAlmostEqual(value_for(output, 'WEAPON_OSCAR_CUSTOM', 'MaxHeadShotDistancePlayer'), 115.0)
            self.assertAlmostEqual(value_for(output, 'WEAPON_OSCAR_CUSTOM', 'HeadShotDamageModifierPlayer'), 3.0)

            # Revólver oficial y custom: torso letal, extremidades reducidas.
            for revolver in ('WEAPON_REVOLVER', 'WEAPON_OSCAR_REVOLVER'):
                self.assertAlmostEqual(value_for(output, revolver, 'Damage'), 350.0)
                self.assertAlmostEqual(value_for(output, revolver, 'HitLimbsDamageModifier'), 0.25)
                self.assertAlmostEqual(value_for(output, revolver, 'NetworkHitLimbsDamageModifier'), 0.25)
                self.assertAlmostEqual(value_for(output, revolver, 'LightlyArmouredDamageModifier'), 1.0)
                self.assertAlmostEqual(value_for(output, revolver, 'DamageFallOffModifier'), 1.0)
                self.assertAlmostEqual(value_for(output, revolver, 'HeadShotDamageModifierPlayer'), 3.0)

            restored = [change for change in report.changes if 'restored_from_backup' in change.changed_fields]
            self.assertEqual(len(restored), 4)

    def test_official_heavy_and_recreational_weapons_restore_without_custom_buff(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            path = root / 'weapons.meta'
            original = meta(
                weapon_block('WEAPON_RPG', 'GROUP_HEAVY', 100.0, 250.0),
                weapon_block('WEAPON_SNOWBALL', 'GROUP_THROWN', 5.0, 20.0),
            )
            touched = meta(
                weapon_block('WEAPON_RPG', 'GROUP_HEAVY', 1.0, 10.0),
                weapon_block('WEAPON_SNOWBALL', 'GROUP_THROWN', 0.0, 1.0),
            )
            path.write_text(touched, encoding='utf-8')
            Path(str(path) + '.bak').write_text(original, encoding='utf-8')

            report = RebalanceEngine(self._settings(root)).run()
            output = path.read_text(encoding='utf-8')
            self.assertAlmostEqual(value_for(output, 'WEAPON_RPG', 'Damage'), 100.0)
            self.assertAlmostEqual(value_for(output, 'WEAPON_RPG', 'WeaponRange'), 250.0)
            self.assertAlmostEqual(value_for(output, 'WEAPON_SNOWBALL', 'Damage'), 5.0)
            self.assertEqual(report.files_changed, 1)

    def test_profile_is_idempotent_when_original_backup_exists(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            path = root / 'weapons.meta'
            original = meta(weapon_block('WEAPON_OSCAR_CUSTOM', 'GROUP_RIFLE', 40.0, 200.0))
            path.write_text(original, encoding='utf-8')
            Path(str(path) + '.bak').write_text(original, encoding='utf-8')

            settings = self._settings(root)
            RebalanceEngine(settings).run()
            first = path.read_text(encoding='utf-8')
            RebalanceEngine(settings).run()
            second = path.read_text(encoding='utf-8')
            self.assertEqual(first, second)
            self.assertAlmostEqual(value_for(second, 'WEAPON_OSCAR_CUSTOM', 'Damage'), 46.0)
            self.assertAlmostEqual(value_for(second, 'WEAPON_OSCAR_CUSTOM', 'WeaponRange'), 230.0)

    def test_missing_backup_uses_current_meta_and_reports_warning(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            path = root / 'weapons.meta'
            path.write_text(
                meta(weapon_block('WEAPON_OSCAR_CUSTOM', 'GROUP_PISTOL', 20.0, 80.0)),
                encoding='utf-8',
            )
            report = RebalanceEngine(self._settings(root)).run()
            output = path.read_text(encoding='utf-8')
            self.assertAlmostEqual(value_for(output, 'WEAPON_OSCAR_CUSTOM', 'Damage'), 23.0)
            self.assertAlmostEqual(value_for(output, 'WEAPON_OSCAR_CUSTOM', 'WeaponRange'), 92.0)
            self.assertTrue(any('no existe' in warning and 'usa su contenido actual' in warning for warning in report.warnings))


if __name__ == '__main__':
    unittest.main()
