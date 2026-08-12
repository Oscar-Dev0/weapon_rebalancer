from __future__ import annotations

import re
import tempfile
import unittest
from pathlib import Path

from weapon_rebalancer.config import Settings
from weapon_rebalancer.profile_loader import apply_external_profile, load_profile
from weapon_rebalancer.rebalance import RebalanceEngine


PROJECT_ROOT = Path(__file__).resolve().parents[1]
PROFILE_PATH = PROJECT_ROOT / 'profiles' / 'flow_caribe.json'


def block(weapon: str, group: str, damage: float, cadence: float) -> str:
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
      <Penetration value="0.100000" />
      <VehicleDamageModifier value="0.200000" />
      <WeaponRange value="100.000000" />
      <DamageFallOffRangeMin value="60.000000" />
      <DamageFallOffRangeMax value="100.000000" />
      <DamageFallOffModifier value="0.500000" />
      <TimeBetweenShots value="{cadence:.6f}" />
      <AccuracySpread value="1.000000" />
      <RunAndGunAccuracyModifier value="1.000000" />
      <AccurateModeAccuracyModifier value="1.000000" />
      <RecoilAccuracyMax value="1.000000" />
      <RecoilErrorTime value="1.000000" />
      <RecoilRecoveryRate value="1.000000" />
      <RecoilShakeAmplitude value="1.000000" />
      <HeadShotDamageModifierPlayer value="1.000000" />
      <NetworkHeadShotPlayerDamageModifier value="1.000000" />
      <HeadShotDamageModifierAI value="1.000000" />
      <MinHeadShotDistancePlayer value="0.000000" />
      <MaxHeadShotDistancePlayer value="100.000000" />
      <MinHeadShotDistanceAI value="0.000000" />
      <MaxHeadShotDistanceAI value="100.000000" />
      <WeaponFlags>Gun UsableOnFoot</WeaponFlags>
    </Item>'''


def meta(*blocks: str) -> str:
    return '<?xml version="1.0" encoding="UTF-8"?>\n<CWeaponInfoBlob>\n  <Infos>\n' + '\n'.join(blocks) + '\n  </Infos>\n</CWeaponInfoBlob>\n'


def value(text: str, weapon: str, tag: str) -> float:
    match = re.search(
        rf'<Item type="CWeaponInfo">(?:(?!</Item>).)*?<Name>{re.escape(weapon)}</Name>(?P<body>.*?)</Item>',
        text,
        re.DOTALL,
    )
    if not match:
        raise AssertionError(f'No se encontró {weapon}')
    tag_match = re.search(rf'<{re.escape(tag)} value="([^"]+)"', match.group(0))
    if not tag_match:
        raise AssertionError(f'No se encontró {tag} en {weapon}')
    return float(tag_match.group(1))


class FlowCaribeProfileTests(unittest.TestCase):
    def test_cadence_scaling_fifty_override_and_long_guns(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            path = root / 'weapons.meta'
            path.write_text(meta(
                block('WEAPON_GLIZZYG17', 'GROUP_PISTOL', 80.0, 0.08),
                block('WEAPON_COMBATPISTOL', 'GROUP_PISTOL', 80.0, 0.20),
                block('WEAPON_PISTOL50', 'GROUP_PISTOL', 80.0, 0.08),
                block('WEAPON_TEST_RIFLE', 'GROUP_RIFLE', 20.0, 0.10),
                block('WEAPON_TEST_SHOTGUN', 'GROUP_SHOTGUN', 20.0, 0.80),
                block('WEAPON_TEST_SNIPER', 'GROUP_SNIPER', 20.0, 1.20),
            ), encoding='utf-8')

            settings = Settings.from_config()
            settings.root = root
            settings.dry_run = False
            settings.create_backup = False
            settings.ignore_weapons.clear()
            apply_external_profile(settings, load_profile(PROFILE_PATH))
            report = RebalanceEngine(settings).run()
            output = path.read_text(encoding='utf-8')

            # Pistola extremadamente rápida: daño reducido por cadencia sin tocar la cadencia.
            self.assertAlmostEqual(value(output, 'WEAPON_GLIZZYG17', 'Damage'), 4.0)
            self.assertAlmostEqual(value(output, 'WEAPON_GLIZZYG17', 'TimeBetweenShots'), 0.08)

            # Pistola normal/lenta: daño base del perfil.
            self.assertAlmostEqual(value(output, 'WEAPON_COMBATPISTOL', 'Damage'), 6.0)
            self.assertAlmostEqual(value(output, 'WEAPON_COMBATPISTOL', 'TimeBetweenShots'), 0.20)

            # .50 gana al algoritmo de cadencia y conserva su daño/alcance especial.
            self.assertAlmostEqual(value(output, 'WEAPON_PISTOL50', 'Damage'), 18.0)
            self.assertAlmostEqual(value(output, 'WEAPON_PISTOL50', 'WeaponRange'), 220.0)

            self.assertAlmostEqual(value(output, 'WEAPON_TEST_RIFLE', 'Damage'), 8.0)
            self.assertAlmostEqual(value(output, 'WEAPON_TEST_SHOTGUN', 'Damage'), 9.0)
            self.assertAlmostEqual(value(output, 'WEAPON_TEST_SNIPER', 'Damage'), 9.0)

            # Recoil prácticamente nulo, precisión alta y one-tap de cabeza.
            self.assertAlmostEqual(value(output, 'WEAPON_COMBATPISTOL', 'RecoilAccuracyMax'), 0.003)
            self.assertAlmostEqual(value(output, 'WEAPON_COMBATPISTOL', 'RecoilShakeAmplitude'), 0.001)
            self.assertAlmostEqual(value(output, 'WEAPON_COMBATPISTOL', 'AccuracySpread'), 0.05)
            self.assertAlmostEqual(value(output, 'WEAPON_COMBATPISTOL', 'HeadShotDamageModifierPlayer'), 1500.0)
            self.assertAlmostEqual(value(output, 'WEAPON_COMBATPISTOL', 'MaxHeadShotDistancePlayer'), 150.0)

            # no_falloff=false: el one-tap no destruye el falloff corporal configurado.
            self.assertAlmostEqual(value(output, 'WEAPON_COMBATPISTOL', 'DamageFallOffModifier'), 0.72)
            self.assertEqual(report.onetap_audit_failed, 0)


if __name__ == '__main__':
    unittest.main()
