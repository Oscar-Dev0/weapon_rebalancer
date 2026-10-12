"""Servidor FiveM de prueba en una carpeta temporal (pack, ox_inventory y qbx_recoils)."""
from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
from unittest import mock

from weapon_rebalancer.core import paths as core_paths
from weapon_rebalancer.core.workspace import Workspace


def weapon_block(weapon: str, group: str, damage: float, *, tbs: float = 0.18, head: float = 1.5,
                 weapon_range: float = 120.0, flags: str = 'Gun UsableOnFoot', extra: str = '') -> str:
    return f'''    <Item type="CWeaponInfo">
      <Name>{weapon}</Name>
      <Model>w_test</Model>
      <Group>{group}</Group>
      <FireType>INSTANT_HIT</FireType>
      <ClipSize value="12" />
      <Damage value="{damage:.6f}" />
      <NetworkPlayerDamageModifier value="1.000000" />
      <NetworkPedDamageModifier value="1.000000" />
      <HitLimbsDamageModifier value="0.500000" />
      <NetworkHitLimbsDamageModifier value="0.500000" />
      <LightlyArmouredDamageModifier value="1.000000" />
      <WeaponRange value="{weapon_range:.6f}" />
      <DamageFallOffRangeMin value="20.000000" />
      <DamageFallOffRangeMax value="60.000000" />
      <DamageFallOffModifier value="0.500000" />
      <HeadShotDamageModifierPlayer value="{head:.6f}" />
      <NetworkHeadShotPlayerDamageModifier value="{head:.6f}" />
      <HeadShotDamageModifierAI value="{head:.6f}" />
      <MinHeadShotDistancePlayer value="0.000000" />
      <MaxHeadShotDistancePlayer value="{weapon_range:.6f}" />
      <MinHeadShotDistanceAI value="0.000000" />
      <MaxHeadShotDistanceAI value="{weapon_range:.6f}" />
      <TimeBetweenShots value="{tbs:.6f}" />
      <ReloadTimeMP value="1.500000" />
      <RecoilShakeAmplitude value="0.300000" />
      <AccuracySpread value="1.000000" />
      <AttachPoints>
        <Item>
          <AttachBone>WAPClip</AttachBone>
          <Components>
            <Item><Name>COMPONENT_TEST_CLIP_01</Name><Default value="true" /></Item>
          </Components>
        </Item>
      </AttachPoints>
{extra}      <WeaponFlags>{flags}</WeaponFlags>
    </Item>'''


def meta(*blocks: str) -> str:
    return ('<?xml version="1.0" encoding="UTF-8"?>\n<CWeaponInfoBlob>\n  <Infos>\n  <Item>\n  <Infos>\n'
            + '\n'.join(blocks) + '\n  </Infos>\n  </Item>\n  </Infos>\n</CWeaponInfoBlob>\n')


OX_WEAPONS = '''return {
    Weapons = {
        ['WEAPON_PISTOL'] = {
            label = 'Pistol',
            weight = 1130,
            durability = 0.0325, -- comentario
            ammoname = 'ammo-9',
        },
        ["WEAPON_CUSTOMGUN"] = {
            label = "Custom \\"Gun\\"",
            weight = 900,
            ammoname = 'ammo-inexistente',
        },
        ['WEAPON_ONLYOX'] = { label = 'Solo inventario', weight = 1 },
        ['WEAPON_PISTOL'] = { label = 'Pistol (duplicada)', weight = 1, ammoname = 'ammo-9' },
        --[[ ['WEAPON_COMENTADA'] = { label = 'no' }, ]]
    },
    Components = {
        ['at_clip_test'] = {
            label = 'Cargador',
            type = 'magazine',
            client = { component = { `COMPONENT_TEST_CLIP_01`, -1234567 }, usetime = 2500 },
        },
    },
    Ammo = {
        ['ammo-9'] = { label = '9mm', weight = 7 },
    },
}
'''

QBX_RECOILS = '''local recoils = {
    -- Pistolas
    [453432689] = 0.3,			--['weapon_pistol']
    -- [584646201] = 0.3,		--['weapon_appistol']
}

return recoils
'''


@contextmanager
def fake_server(tmp: Path):
    """Crea el servidor y redirige data/ a la carpeta temporal."""
    server = tmp / 'server'
    pack = server / 'resources' / '[streaming]' / '[PackArmas]'
    resource = pack / 'packA'
    (resource / 'meta').mkdir(parents=True)
    (resource / 'fxmanifest.lua').write_text("fx_version 'cerulean'\ngame 'gta5'\ndata_file 'WEAPONINFO_FILE' 'meta/weapons.meta'\n", encoding='utf-8')
    original = meta(
        weapon_block('WEAPON_PISTOL', 'GROUP_PISTOL', 26.0),
        weapon_block('WEAPON_CUSTOMGUN', 'GROUP_RIFLE', 30.0, tbs=0.1),
    )
    current = meta(
        weapon_block('WEAPON_PISTOL', 'GROUP_PISTOL', 10.0, head=13.888889),
        weapon_block('WEAPON_CUSTOMGUN', 'GROUP_RIFLE', 30.0, tbs=0.1),
    )
    (resource / 'meta' / 'weapons.meta').write_text(current, encoding='utf-8')
    (resource / 'meta' / 'weapons.meta.bak').write_text(original, encoding='utf-8')
    other = pack / 'packB'
    other.mkdir()
    (other / 'weapons.meta').write_text(meta(weapon_block('WEAPON_PISTOL', 'GROUP_PISTOL', 12.0)), encoding='utf-8')

    ox = server / 'resources' / '[ox]' / 'ox_inventory'
    (ox / 'data').mkdir(parents=True)
    (ox / 'data' / 'weapons.lua').write_text(OX_WEAPONS, encoding='utf-8')
    qbx = server / 'resources' / '[qbx]' / 'qbx_smallresources' / 'qbx_recoils'
    qbx.mkdir(parents=True)
    (qbx / 'config.lua').write_text(QBX_RECOILS, encoding='utf-8')

    ws = Workspace(server_root=str(server), pack_roots=[str(pack)], ox_inventory_dir=str(ox),
                   qbx_recoils_file=str(qbx / 'config.lua'), active_profile='prueba')
    data = tmp / 'data'
    with mock.patch.object(core_paths, 'DATA_DIR', data):
        yield ws, server, pack
