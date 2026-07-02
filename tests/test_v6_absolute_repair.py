from __future__ import annotations

import re
import tempfile
from pathlib import Path

from weapon_rebalancer.config import Settings
from weapon_rebalancer.profile_loader import apply_external_profile, load_profile
from weapon_rebalancer.rebalance import RebalanceEngine
from weapon_rebalancer.runtime_guard import collect_expected_damage, generate_damage_guard

PROJECT_ROOT = Path(__file__).resolve().parents[1]
PROFILE = PROJECT_ROOT / 'profiles' / 'vanilla_repair_custom_plus15_absolute_v6.json'


def block(name: str, group: str, damage: float | None, weapon_range: float | None = 100.0, *, headshot: float = 3.0) -> str:
    damage_tag = '' if damage is None else f'<Damage value="{damage:.6f}" />'
    range_tag = '' if weapon_range is None else f'<WeaponRange value="{weapon_range:.6f}" />'
    return f'''<Item type="CWeaponInfo">
<Name>{name}</Name><Model>w_test</Model><Group>{group}</Group>
{damage_tag}
<NetworkPlayerDamageModifier value="0.000000" />
<NetworkPedDamageModifier value="0.000000" />
<HitLimbsDamageModifier value="0.750000" />
<NetworkHitLimbsDamageModifier value="0.750000" />
<LightlyArmouredDamageModifier value="0.750000" />
<VehicleDamageModifier value="2.000000" />
<Penetration value="1.000000" />
{range_tag}
<DamageFallOffRangeMin value="0.000000" />
<DamageFallOffRangeMax value="0.000000" />
<DamageFallOffModifier value="0.000000" />
<HeadShotDamageModifierPlayer value="{headshot:.6f}" />
<NetworkHeadShotPlayerDamageModifier value="0.000000" />
<HeadShotDamageModifierAI value="0.000000" />
<MinHeadShotDistancePlayer value="0.000000" />
<MaxHeadShotDistancePlayer value="0.000000" />
<MinHeadShotDistanceAI value="0.000000" />
<MaxHeadShotDistanceAI value="0.000000" />
<WeaponFlags>Gun UsableOnFoot</WeaponFlags>
</Item>'''


def meta(*blocks: str) -> str:
    return '<?xml version="1.0"?><CWeaponInfoBlob><Infos>' + ''.join(blocks) + '</Infos></CWeaponInfoBlob>'


def value(text: str, weapon: str, tag: str) -> float:
    match = re.search(rf'<Item type="CWeaponInfo">(?:(?!</Item>).)*?<Name>{weapon}</Name>(.*?)</Item>', text, re.S)
    assert match
    field = re.search(rf'<{tag} value="([^"]+)"', match.group(0))
    assert field
    return float(field.group(1))


def settings(root: Path) -> Settings:
    result = Settings.from_config()
    result.root = root
    result.dry_run = False
    result.create_backup = False
    apply_external_profile(result, load_profile(PROFILE))
    return result


def test_custom_zero_damage_uses_group_base_then_plus_15() -> None:
    with tempfile.TemporaryDirectory() as temp:
        root = Path(temp)
        path = root / 'weapons.meta'
        path.write_text(meta(block('WEAPON_OSCAR_ZERO', 'GROUP_PISTOL', 0.0, 0.0, headshot=0.0)), encoding='utf-8')
        RebalanceEngine(settings(root)).run()
        output = path.read_text(encoding='utf-8')
        assert value(output, 'WEAPON_OSCAR_ZERO', 'Damage') == 31.05
        assert value(output, 'WEAPON_OSCAR_ZERO', 'WeaponRange') == 138.0
        assert value(output, 'WEAPON_OSCAR_ZERO', 'NetworkPlayerDamageModifier') == 1.0
        assert value(output, 'WEAPON_OSCAR_ZERO', 'HeadShotDamageModifierPlayer') == 18.0
        assert value(output, 'WEAPON_OSCAR_ZERO', 'NetworkHeadShotPlayerDamageModifier') == 1.0


def test_official_core_damage_is_repaired_without_custom_multiplier() -> None:
    with tempfile.TemporaryDirectory() as temp:
        root = Path(temp)
        path = root / 'weapons.meta'
        path.write_text(meta(block('WEAPON_PISTOL', 'GROUP_PISTOL', 999.0, 100.0)), encoding='utf-8')
        RebalanceEngine(settings(root)).run()
        output = path.read_text(encoding='utf-8')
        assert value(output, 'WEAPON_PISTOL', 'Damage') == 26.0
        assert value(output, 'WEAPON_PISTOL', 'WeaponRange') == 100.0


def test_revolver_torso_rule_wins_after_repair() -> None:
    with tempfile.TemporaryDirectory() as temp:
        root = Path(temp)
        path = root / 'weapons.meta'
        path.write_text(meta(block('WEAPON_REVOLVER', 'GROUP_PISTOL', 0.0, 120.0)), encoding='utf-8')
        RebalanceEngine(settings(root)).run()
        output = path.read_text(encoding='utf-8')
        assert value(output, 'WEAPON_REVOLVER', 'Damage') == 350.0
        assert value(output, 'WEAPON_REVOLVER', 'HitLimbsDamageModifier') == 0.25



def test_custom_prefilled_damage_is_normalized_before_plus_15() -> None:
    with tempfile.TemporaryDirectory() as temp:
        root = Path(temp)
        path = root / 'weapons.meta'
        path.write_text(meta(block('WEAPON_OSCAR_OVERPOWERED', 'GROUP_PISTOL', 80.0, 600.0, headshot=1000.0)), encoding='utf-8')
        RebalanceEngine(settings(root)).run()
        output = path.read_text(encoding='utf-8')
        assert value(output, 'WEAPON_OSCAR_OVERPOWERED', 'Damage') == 31.05
        assert value(output, 'WEAPON_OSCAR_OVERPOWERED', 'WeaponRange') == 138.0
        assert value(output, 'WEAPON_OSCAR_OVERPOWERED', 'HeadShotDamageModifierPlayer') == 18.0
        assert value(output, 'WEAPON_OSCAR_OVERPOWERED', 'NetworkPlayerDamageModifier') == 1.0
        assert value(output, 'WEAPON_OSCAR_OVERPOWERED', 'LightlyArmouredDamageModifier') == 0.75
        assert value(output, 'WEAPON_OSCAR_OVERPOWERED', 'VehicleDamageModifier') == 0.35
        assert value(output, 'WEAPON_OSCAR_OVERPOWERED', 'Penetration') == 0.01


def test_custom_normalization_is_idempotent() -> None:
    with tempfile.TemporaryDirectory() as temp:
        root = Path(temp)
        path = root / 'weapons.meta'
        path.write_text(meta(block('WEAPON_OSCAR_REPEAT', 'GROUP_RIFLE', 200.0, 900.0)), encoding='utf-8')
        configured = settings(root)
        RebalanceEngine(configured).run()
        once = path.read_text(encoding='utf-8')
        RebalanceEngine(configured).run()
        twice = path.read_text(encoding='utf-8')
        assert once == twice
        assert value(twice, 'WEAPON_OSCAR_REPEAT', 'Damage') == 34.5
        assert value(twice, 'WEAPON_OSCAR_REPEAT', 'WeaponRange') == 345.0

def test_generated_guard_contains_absolute_expected_damage() -> None:
    with tempfile.TemporaryDirectory() as temp:
        root = Path(temp)
        path = root / 'weapons.meta'
        path.write_text(meta(block('WEAPON_OSCAR_CUSTOM', 'GROUP_RIFLE', 40.0, 200.0)), encoding='utf-8')
        configured = settings(root)
        RebalanceEngine(configured).run()
        expected = collect_expected_damage(root, configured.scan, configured.skip_basenames)
        destination = root / 'os_weapon_damage_guard'
        generate_damage_guard(destination, expected)
        config = (destination / 'config.lua').read_text(encoding='utf-8')
        client = (destination / 'client.lua').read_text(encoding='utf-8')
        assert '["WEAPON_OSCAR_CUSTOM"] = 34.500000' in config
        assert 'GetWeaponDamage' in client
        assert 'SetWeaponDamageModifier' in client
        assert 'SetPlayerWeaponDamageModifier' in client
