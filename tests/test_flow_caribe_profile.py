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


def block(
    weapon: str,
    group: str,
    damage: float,
    cadence: float,
    *,
    flags: str = 'Gun UsableOnFoot',
    firing_pattern: str = 'FIRING_PATTERN_SINGLE_SHOT',
    anim_fire_rate_modifier: float = 1.0,
) -> str:
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
      <AnimFireRateModifier value="{anim_fire_rate_modifier:.6f}" />
      <FiringPattern ref="{firing_pattern}" />
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
      <WeaponFlags>{flags}</WeaponFlags>
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
    def _run(self, *items: str):
        temp = tempfile.TemporaryDirectory()
        root = Path(temp.name)
        path = root / 'weapons.meta'
        path.write_text(meta(*items), encoding='utf-8')
        settings = Settings.from_config()
        settings.root = root
        settings.dry_run = False
        settings.create_backup = False
        settings.ignore_weapons.clear()
        apply_external_profile(settings, load_profile(PROFILE_PATH))
        report = RebalanceEngine(settings).run()
        return temp, path.read_text(encoding='utf-8'), report

    def test_fixed_pistols_and_snipers_keep_onetap_while_others_are_bounded(self) -> None:
        temp, output, report = self._run(
            block('WEAPON_GLIZZYG17', 'GROUP_PISTOL', 80.0, 0.08),
            block('WEAPON_COMBATPISTOL', 'GROUP_PISTOL', 80.0, 0.20),
            block('WEAPON_PISTOL50', 'GROUP_PISTOL', 80.0, 0.08),
            block('WEAPON_TEST_RIFLE', 'GROUP_RIFLE', 20.0, 0.10),
            block('WEAPON_TEST_SHOTGUN', 'GROUP_SHOTGUN', 20.0, 0.80),
            block('WEAPON_TEST_SNIPER', 'GROUP_SNIPER', 20.0, 1.20),
        )
        try:
            # Fixed rapid pistol: body damage is reduced by cadence, but its whitelist
            # one-tap is authoritative. Dynamic multiplier accounts for 0.72 falloff.
            self.assertAlmostEqual(value(output, 'WEAPON_GLIZZYG17', 'Damage'), 6.0)
            self.assertAlmostEqual(value(output, 'WEAPON_GLIZZYG17', 'TimeBetweenShots'), 0.08)
            self.assertAlmostEqual(value(output, 'WEAPON_GLIZZYG17', 'HeadShotDamageModifierPlayer'), 23.148148, places=5)
            self.assertAlmostEqual(value(output, 'WEAPON_GLIZZYG17', 'NetworkHeadShotPlayerDamageModifier'), 23.148148, places=5)

            # Fixed normal pistol is also one-tap, using only the multiplier required
            # by its final 15 body damage and falloff.
            self.assertAlmostEqual(value(output, 'WEAPON_COMBATPISTOL', 'Damage'), 10.0)
            self.assertAlmostEqual(value(output, 'WEAPON_COMBATPISTOL', 'HeadShotDamageModifierPlayer'), 13.888889, places=5)

            # .50 remains triple body damage and fixed one-tap; because its body damage
            # is much higher it needs a much smaller dynamic headshot multiplier.
            self.assertAlmostEqual(value(output, 'WEAPON_PISTOL50', 'Damage'), 30.0)
            self.assertAlmostEqual(value(output, 'WEAPON_PISTOL50', 'WeaponRange'), 220.0)
            self.assertAlmostEqual(value(output, 'WEAPON_PISTOL50', 'HeadShotDamageModifierPlayer'), 3.875969, places=5)

            # Non-whitelisted rifle and shotgun stay bounded to 1.5x.
            self.assertAlmostEqual(value(output, 'WEAPON_TEST_RIFLE', 'Damage'), 13.0)
            self.assertAlmostEqual(value(output, 'WEAPON_TEST_RIFLE', 'HeadShotDamageModifierPlayer'), 1.5)
            self.assertAlmostEqual(value(output, 'WEAPON_TEST_SHOTGUN', 'Damage'), 15.0)
            self.assertAlmostEqual(value(output, 'WEAPON_TEST_SHOTGUN', 'HeadShotDamageModifierPlayer'), 1.5)

            # Snipers are explicitly allowed one-tap as a group.
            self.assertAlmostEqual(value(output, 'WEAPON_TEST_SNIPER', 'Damage'), 40.0)
            self.assertAlmostEqual(value(output, 'WEAPON_TEST_SNIPER', 'HeadShotDamageModifierPlayer'), 2.717391, places=5)

            # Fixed one-tap + tiro-a-tiro now receives visible recoil.
            self.assertAlmostEqual(value(output, 'WEAPON_COMBATPISTOL', 'RecoilAccuracyMax'), 0.30)
            self.assertAlmostEqual(value(output, 'WEAPON_COMBATPISTOL', 'RecoilShakeAmplitude'), 0.28)
            self.assertAlmostEqual(value(output, 'WEAPON_TEST_SNIPER', 'RecoilAccuracyMax'), 0.75)
            self.assertAlmostEqual(value(output, 'WEAPON_TEST_SNIPER', 'RecoilShakeAmplitude'), 0.65)
            self.assertAlmostEqual(value(output, 'WEAPON_COMBATPISTOL', 'AccuracySpread'), 0.05)
            self.assertEqual(report.onetap_audit_failed, 0)
        finally:
            temp.cleanup()


    def test_onetap_single_shot_gets_recoil_but_automatic_onetap_stays_near_zero(self) -> None:
        temp, output, report = self._run(
            block('WEAPON_COMBATPISTOL', 'GROUP_PISTOL', 80.0, 0.20),
            block('WEAPON_GLIZZYG17', 'GROUP_PISTOL', 80.0, 0.20, flags='Gun UsableOnFoot Automatic'),
            block('WEAPON_PISTOL_MK2', 'GROUP_PISTOL', 80.0, 0.10),
            block('WEAPON_TEST_SNIPER', 'GROUP_SNIPER', 80.0, 1.00),
        )
        try:
            # Semi-auto one-tap gets visible recoil even if cadence is fast.
            self.assertAlmostEqual(value(output, 'WEAPON_COMBATPISTOL', 'RecoilAccuracyMax'), 0.30)
            self.assertAlmostEqual(value(output, 'WEAPON_COMBATPISTOL', 'RecoilShakeAmplitude'), 0.28)
            self.assertAlmostEqual(value(output, 'WEAPON_PISTOL_MK2', 'RecoilAccuracyMax'), 0.30)
            self.assertAlmostEqual(value(output, 'WEAPON_PISTOL_MK2', 'RecoilShakeAmplitude'), 0.28)

            # Automatic one-tap allowlist weapon remains near-zero recoil.
            self.assertAlmostEqual(value(output, 'WEAPON_GLIZZYG17', 'RecoilAccuracyMax'), 0.003)
            self.assertAlmostEqual(value(output, 'WEAPON_GLIZZYG17', 'RecoilShakeAmplitude'), 0.001)

            # Sniper one-tap gets heavier single-shot recoil.
            self.assertAlmostEqual(value(output, 'WEAPON_TEST_SNIPER', 'RecoilAccuracyMax'), 0.75)
            self.assertAlmostEqual(value(output, 'WEAPON_TEST_SNIPER', 'RecoilShakeAmplitude'), 0.65)
            self.assertTrue(any('recoil:onetap_single_shot' in f for c in report.changes for f in c.changed_fields))
        finally:
            temp.cleanup()

    def test_normal_is_the_damage_ceiling_and_fast_weapons_scale_down(self) -> None:
        temp, output, _ = self._run(
            block('WEAPON_PISTOL_NORMAL_TEST', 'GROUP_PISTOL', 99.0, 0.20),
            block('WEAPON_PISTOL_QUICK_TEST', 'GROUP_PISTOL', 99.0, 0.17),
            block('WEAPON_PISTOL_EXTREME_TEST', 'GROUP_PISTOL', 99.0, 0.08),
            block('WEAPON_SMG_NORMAL_TEST', 'GROUP_SMG', 99.0, 0.20, flags='Gun UsableOnFoot'),
            block('WEAPON_RIFLE_NORMAL_TEST', 'GROUP_RIFLE', 99.0, 0.20),
            block('WEAPON_RIFLE_EXTREME_TEST', 'GROUP_RIFLE', 99.0, 0.07),
            block('WEAPON_SNIPER_NORMAL_TEST', 'GROUP_SNIPER', 99.0, 1.00),
            block('WEAPON_SNIPER_FAST_TEST', 'GROUP_SNIPER', 99.0, 0.45),
        )
        try:
            self.assertAlmostEqual(value(output, 'WEAPON_PISTOL_NORMAL_TEST', 'Damage'), 10.0)
            self.assertAlmostEqual(value(output, 'WEAPON_PISTOL_QUICK_TEST', 'Damage'), 9.0)
            self.assertAlmostEqual(value(output, 'WEAPON_PISTOL_EXTREME_TEST', 'Damage'), 6.0)
            # GROUP_SMG is intentionally always treated non-normal, so it receives the safety cap.
            self.assertAlmostEqual(value(output, 'WEAPON_SMG_NORMAL_TEST', 'Damage'), 13.0)
            self.assertAlmostEqual(value(output, 'WEAPON_RIFLE_NORMAL_TEST', 'Damage'), 15.0)
            self.assertAlmostEqual(value(output, 'WEAPON_RIFLE_EXTREME_TEST', 'Damage'), 11.0)
            self.assertAlmostEqual(value(output, 'WEAPON_SNIPER_NORMAL_TEST', 'Damage'), 40.0)
            self.assertAlmostEqual(value(output, 'WEAPON_SNIPER_FAST_TEST', 'Damage'), 34.0)
        finally:
            temp.cleanup()

    def test_automatic_pattern_and_anim_modifier_are_independent_rapid_signals(self) -> None:
        temp, output, _ = self._run(
            # Slow raw cadence, but Automatic flag => no one-tap.
            block('WEAPON_AUTO_FLAG', 'GROUP_RIFLE', 20.0, 0.25, flags='Gun UsableOnFoot Automatic'),
            # Slow raw cadence, but FULL_AUTO pattern => no one-tap.
            block('WEAPON_AUTO_PATTERN', 'GROUP_RIFLE', 20.0, 0.25, firing_pattern='FIRING_PATTERN_FULL_AUTO'),
            # Raw 0.20 looks normal, modifier 1.5 makes effective cadence 0.133s => fast.
            block('WEAPON_ANIM_FAST', 'GROUP_PISTOL', 20.0, 0.20, anim_fire_rate_modifier=1.5),
            # Slow random pistol is NOT on the explicit Flow Caribe allowlist.
            block('WEAPON_TRUE_NORMAL', 'GROUP_PISTOL', 20.0, 0.20),
            # SMG is always treated as non-normal even if a bad custom META claims a slow cadence.
            block('WEAPON_SMG_FAKE_SLOW', 'GROUP_SMG', 20.0, 0.30),
        )
        try:
            self.assertAlmostEqual(value(output, 'WEAPON_AUTO_FLAG', 'Damage'), 14.0)
            self.assertAlmostEqual(value(output, 'WEAPON_AUTO_FLAG', 'HeadShotDamageModifierPlayer'), 1.5)
            self.assertAlmostEqual(value(output, 'WEAPON_AUTO_PATTERN', 'HeadShotDamageModifierPlayer'), 1.5)
            self.assertAlmostEqual(value(output, 'WEAPON_ANIM_FAST', 'Damage'), 8.0)
            self.assertAlmostEqual(value(output, 'WEAPON_ANIM_FAST', 'HeadShotDamageModifierPlayer'), 1.5)
            self.assertAlmostEqual(value(output, 'WEAPON_TRUE_NORMAL', 'HeadShotDamageModifierPlayer'), 1.5)
            self.assertAlmostEqual(value(output, 'WEAPON_SMG_FAKE_SLOW', 'Damage'), 13.0)
            self.assertAlmostEqual(value(output, 'WEAPON_SMG_FAKE_SLOW', 'HeadShotDamageModifierPlayer'), 1.5)
        finally:
            temp.cleanup()


    def test_nested_items_do_not_hide_real_automatic_weapon_flags(self) -> None:
        realistic = '''    <Item type="CWeaponInfo">
      <Name>WEAPON_RUSOGLOCK</Name>
      <Model>w_pi_rusoglock</Model>
      <Audio>AUDIO_ITEM_APPISTOL</Audio>
      <Group>GROUP_PISTOL</Group>
      <Damage value="80.000000" />
      <NetworkPlayerDamageModifier value="1.000000" />
      <HeadShotDamageModifierPlayer value="1500.000000" />
      <NetworkHeadShotPlayerDamageModifier value="1500.000000" />
      <OverrideForces>
        <Item>
          <BoneTag>BONETAG_HEAD</BoneTag>
          <NetworkPlayerDamageModifier value="9.000000" />
          <Penetration value="9.000000" />
          <WeaponFlags>IgnoreHelmets ArmourPenetrating</WeaponFlags>
        </Item>
      </OverrideForces>
      <Penetration value="0.010000" />
      <BulletsInBatch value="1" />
      <BulletsPerAnimLoop value="1" />
      <TimeBetweenShots value="0.180000" />
      <AnimFireRateModifier value="1.000000" />
      <RecoilAccuracyMax value="0.500000" />
      <RecoilErrorTime value="0.500000" />
      <RecoilRecoveryRate value="1.000000" />
      <RecoilShakeAmplitude value="0.687500" />
      <RecoilShakeHashFirstPerson>FPS_SMG_RECOIL_SHAKE</RecoilShakeHashFirstPerson>
      <StatName>APPISTOL</StatName>
      <NmShotTuningSet>BurstFire</NmShotTuningSet>
      <WeaponFlags>CarriedInHand Automatic Gun UsableOnFoot</WeaponFlags>
    </Item>'''
        temp, output, report = self._run(realistic)
        try:
            from weapon_rebalancer.meta_utils import read_field_value, read_weapon_flags
            from weapon_rebalancer.scanner import ScanConfig, extract_weapon_blocks

            blocks = extract_weapon_blocks(Path('weapons.meta'), output, ScanConfig(), [])
            self.assertEqual(len(blocks), 1)
            weapon_block = blocks[0]
            self.assertEqual(weapon_block.weapon, 'WEAPON_RUSOGLOCK')
            self.assertAlmostEqual(read_field_value(weapon_block.text, 'time_between_shots'), 0.18)
            self.assertIn('Automatic', read_weapon_flags(weapon_block.text))
            self.assertAlmostEqual(read_field_value(weapon_block.text, 'headshot_player'), 1.5)
            self.assertAlmostEqual(read_field_value(weapon_block.text, 'network_headshot'), 1.5)
            self.assertAlmostEqual(read_field_value(weapon_block.text, 'recoil_shake_amplitude'), 0.001)
            self.assertTrue(any('fire_rate_class:automatic_or_pattern' in f for c in report.changes for f in c.changed_fields))
        finally:
            temp.cleanup()


    def test_strict_allowlist_blocks_external_onetap_override(self) -> None:
        temp = tempfile.TemporaryDirectory()
        try:
            root = Path(temp.name)
            path = root / 'weapons.meta'
            path.write_text(meta(block('WEAPON_RANDOM_GLOCK', 'GROUP_PISTOL', 20.0, 0.25)), encoding='utf-8')
            settings = Settings.from_config()
            settings.root = root
            settings.dry_run = False
            settings.create_backup = False
            settings.ignore_weapons.clear()
            apply_external_profile(settings, load_profile(PROFILE_PATH))
            # Simulate a local/package override trying to force one-tap back on.
            settings.weapon_headshot_overrides['WEAPON_RANDOM_GLOCK'] = {
                'mode': 'onetap', 'multiplier': 1500.0, 'distance': 150.0
            }
            report = RebalanceEngine(settings).run()
            output = path.read_text(encoding='utf-8')
            self.assertAlmostEqual(value(output, 'WEAPON_RANDOM_GLOCK', 'HeadShotDamageModifierPlayer'), 1.5)
            self.assertAlmostEqual(value(output, 'WEAPON_RANDOM_GLOCK', 'NetworkHeadShotPlayerDamageModifier'), 1.5)
            self.assertTrue(any('headshot_player' in f for c in report.changes for f in c.changed_fields))
        finally:
            temp.cleanup()

    def test_headshot_is_exactly_fifty_percent_above_body_damage(self) -> None:
        temp, output, _ = self._run(
            block('WEAPON_DAMAGE10', 'GROUP_RIFLE', 10.0, 0.25),
        )
        try:
            body = value(output, 'WEAPON_DAMAGE10', 'Damage')
            multiplier = value(output, 'WEAPON_DAMAGE10', 'HeadShotDamageModifierPlayer')
            network_multiplier = value(output, 'WEAPON_DAMAGE10', 'NetworkHeadShotPlayerDamageModifier')
            self.assertAlmostEqual(multiplier, 1.5)
            self.assertAlmostEqual(network_multiplier, 1.5)
            self.assertAlmostEqual(body * multiplier, body * 1.5)
        finally:
            temp.cleanup()

    def test_fixed_weapon_cannot_be_downgraded_by_external_headshot_override(self) -> None:
        temp = tempfile.TemporaryDirectory()
        try:
            root = Path(temp.name)
            path = root / 'weapons.meta'
            path.write_text(meta(block('WEAPON_COMBATPISTOL', 'GROUP_PISTOL', 10.0, 0.25)), encoding='utf-8')
            settings = Settings.from_config()
            settings.root = root
            settings.dry_run = False
            settings.create_backup = False
            settings.ignore_weapons.clear()
            apply_external_profile(settings, load_profile(PROFILE_PATH))
            settings.weapon_headshot_overrides['WEAPON_COMBATPISTOL'] = {
                'mode': 'normal', 'multiplier': 1.0, 'distance': 150.0
            }
            RebalanceEngine(settings).run()
            output = path.read_text(encoding='utf-8')
            self.assertGreater(value(output, 'WEAPON_COMBATPISTOL', 'HeadShotDamageModifierPlayer'), 1.5)
            self.assertAlmostEqual(value(output, 'WEAPON_COMBATPISTOL', 'HeadShotDamageModifierPlayer'), 13.888889, places=5)
            self.assertAlmostEqual(value(output, 'WEAPON_COMBATPISTOL', 'NetworkHeadShotPlayerDamageModifier'), 13.888889, places=5)
        finally:
            temp.cleanup()


if __name__ == '__main__':
    unittest.main()

# v6.11 regression tests are attached dynamically to keep compatibility with the
# existing unittest module layout in older releases.
def _test_v611_exact_damage_multipliers_keep_onetap_recoil(self) -> None:
    temp, output, report = self._run(
        block('WEAPON_PISTOL50', 'GROUP_PISTOL', 80.0, 0.20),
        block('WEAPON_GADGETPISTOL', 'GROUP_PISTOL', 80.0, 0.20),
        block('WEAPON_REVOLVER', 'GROUP_PISTOL', 80.0, 0.50),
        block('WEAPON_REVOLVER_MK2_TEST', 'GROUP_PISTOL', 80.0, 0.50),
    )
    try:
        # Gadget keeps the heavy .50 base/handling and multiplies its 30 damage by x7.
        for tag in (
            'WeaponRange', 'DamageFallOffRangeMin', 'DamageFallOffRangeMax',
            'DamageFallOffModifier', 'AccuracySpread',
        ):
            self.assertAlmostEqual(
                value(output, 'WEAPON_GADGETPISTOL', tag),
                value(output, 'WEAPON_PISTOL50', tag),
                places=6,
                msg=f'GadgetPistol no conserva el perfil pesado de PISTOL50 en {tag}',
            )
        self.assertAlmostEqual(value(output, 'WEAPON_PISTOL50', 'Damage'), 30.0)
        self.assertAlmostEqual(value(output, 'WEAPON_GADGETPISTOL', 'Damage'), 210.0)
        self.assertAlmostEqual(
            value(output, 'WEAPON_GADGETPISTOL', 'Damage') / value(output, 'WEAPON_PISTOL50', 'Damage'),
            7.0,
        )
        self.assertAlmostEqual(value(output, 'WEAPON_GADGETPISTOL', 'WeaponRange'), 220.0)
        self.assertGreaterEqual(
            value(output, 'WEAPON_GADGETPISTOL', 'Damage') * value(output, 'WEAPON_GADGETPISTOL', 'HeadShotDamageModifierPlayer'),
            100.0,
        )
        self.assertAlmostEqual(value(output, 'WEAPON_GADGETPISTOL', 'RecoilAccuracyMax'), 0.30)
        self.assertAlmostEqual(value(output, 'WEAPON_GADGETPISTOL', 'RecoilShakeAmplitude'), 0.28)

        # Revolver stays fixed one-tap and multiplies the normal pistol base 10 by x6 (=60).
        self.assertAlmostEqual(value(output, 'WEAPON_REVOLVER', 'Damage'), 60.0)
        self.assertGreaterEqual(
            value(output, 'WEAPON_REVOLVER', 'Damage') * value(output, 'WEAPON_REVOLVER', 'HeadShotDamageModifierPlayer'),
            100.0,
        )
        # Exact match: similarly named variants do not inherit REVOLVER x6.
        self.assertAlmostEqual(value(output, 'WEAPON_REVOLVER_MK2_TEST', 'Damage'), 10.0)
        self.assertAlmostEqual(value(output, 'WEAPON_REVOLVER', 'RecoilAccuracyMax'), 0.30)
        self.assertAlmostEqual(value(output, 'WEAPON_REVOLVER', 'RecoilShakeAmplitude'), 0.28)
        self.assertEqual(report.onetap_audit_failed, 0)
    finally:
        temp.cleanup()

FlowCaribeProfileTests.test_v611_exact_damage_multipliers_keep_onetap_recoil = _test_v611_exact_damage_multipliers_keep_onetap_recoil


# v6.12 regression: REVOLVER_MK2 is an explicit x6 + fixed one-tap weapon,
# while similarly named custom variants still do not inherit it.
def _test_v612_revolver_mk2_exact_x6_and_onetap_recoil(self) -> None:
    temp, output, report = self._run(
        block('WEAPON_REVOLVER', 'GROUP_PISTOL', 80.0, 0.50),
        block('WEAPON_REVOLVER_MK2', 'GROUP_PISTOL', 80.0, 0.50),
        block('WEAPON_REVOLVER_MK2_TEST', 'GROUP_PISTOL', 80.0, 0.50),
    )
    try:
        self.assertAlmostEqual(value(output, 'WEAPON_REVOLVER', 'Damage'), 60.0)
        self.assertAlmostEqual(value(output, 'WEAPON_REVOLVER_MK2', 'Damage'), 60.0)
        self.assertAlmostEqual(value(output, 'WEAPON_REVOLVER_MK2_TEST', 'Damage'), 10.0)

        for weapon in ('WEAPON_REVOLVER', 'WEAPON_REVOLVER_MK2'):
            self.assertGreaterEqual(
                value(output, weapon, 'Damage') * value(output, weapon, 'HeadShotDamageModifierPlayer'),
                100.0,
            )
            self.assertAlmostEqual(value(output, weapon, 'RecoilAccuracyMax'), 0.30)
            self.assertAlmostEqual(value(output, weapon, 'RecoilShakeAmplitude'), 0.28)
        self.assertEqual(report.onetap_audit_failed, 0)
    finally:
        temp.cleanup()

FlowCaribeProfileTests.test_v612_revolver_mk2_exact_x6_and_onetap_recoil = _test_v612_revolver_mk2_exact_x6_and_onetap_recoil
