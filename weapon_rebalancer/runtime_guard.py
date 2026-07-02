from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

from .meta_utils import read_field_value, read_text
from .scanner import ScanConfig, discover_meta_paths, extract_weapon_blocks


def collect_expected_damage(root: Path, scan: ScanConfig, skip_basenames: set[str]) -> dict[str, float]:
    """Lee la definición final visible por orden de archivos y devuelve daño absoluto esperado."""
    expected: dict[str, float] = {}
    for path in discover_meta_paths(root, scan, skip_basenames):
        for block in extract_weapon_blocks(path, read_text(path), scan, []):
            value = read_field_value(block.text, 'damage')
            if isinstance(value, (int, float)) and not isinstance(value, bool) and float(value) >= 0.0:
                expected[block.weapon.upper()] = float(value)
    return expected


def _lua_string(value: str) -> str:
    return json.dumps(value, ensure_ascii=False)


def generate_damage_guard(
    destination: Path,
    expected_damage: dict[str, float],
    *,
    force: bool = False,
) -> Path:
    if destination.exists():
        if not force:
            raise FileExistsError(f'La ruta ya existe: {destination}')
        shutil.rmtree(destination)
    destination.mkdir(parents=True, exist_ok=True)

    entries = '\n'.join(
        f'    [{_lua_string(name)}] = {value:.6f},'
        for name, value in sorted(expected_damage.items())
        if value > 0.0
    )
    config = f'''Config = {{}}

Config.Enabled = true
Config.Debug = false
Config.DebugCommand = 'osweaponstatus'
Config.EnforcePlayerModifier = true
Config.EnableCriticalHits = true
Config.ReapplyEveryFrame = true

-- Generado desde los META ya reparados. Nombre -> daño absoluto esperado.
Config.ExpectedDamage = {{
{entries}
}}
'''
    client = r'''local expectedByHash = {}
local lastStatus = nil

CreateThread(function()
    for weaponName, expected in pairs(Config.ExpectedDamage or {}) do
        expectedByHash[joaat(weaponName)] = { name = weaponName, damage = tonumber(expected) or 0.0 }
    end
end)

local function applyCurrentWeapon()
    if not Config.Enabled then return end

    local playerId = PlayerId()
    local ped = PlayerPedId()
    if Config.EnforcePlayerModifier then
        SetPlayerWeaponDamageModifier(playerId, 1.0)
    end
    if Config.EnableCriticalHits then
        SetPedSuffersCriticalHits(ped, true)
    end

    local _, weaponHash = GetCurrentPedWeapon(ped, true)
    local entry = expectedByHash[weaponHash]
    if not entry then
        lastStatus = { hash = weaponHash, name = 'NO_CONFIGURADA', loaded = GetWeaponDamage(weaponHash, 0), expected = nil, modifier = 1.0 }
        return
    end

    local loaded = tonumber(GetWeaponDamage(weaponHash, 0)) or 0.0
    local modifier = 1.0
    if loaded > 0.0001 and entry.damage > 0.0 then
        modifier = entry.damage / loaded
    end

    -- Se reaplica para neutralizar recursos que cambian el modificador durante el gameplay.
    SetWeaponDamageModifier(weaponHash, modifier)
    lastStatus = { hash = weaponHash, name = entry.name, loaded = loaded, expected = entry.damage, modifier = modifier }
end

CreateThread(function()
    while true do
        applyCurrentWeapon()
        Wait(Config.ReapplyEveryFrame and 0 or 250)
    end
end)

RegisterCommand(Config.DebugCommand or 'osweaponstatus', function()
    if not lastStatus then
        print('[os_weapon_damage_guard] Sin estado todavía.')
        return
    end
    print(('[os_weapon_damage_guard] weapon=%s hash=%s loaded=%.4f expected=%s modifier=%.6f'):format(
        lastStatus.name,
        tostring(lastStatus.hash),
        tonumber(lastStatus.loaded) or 0.0,
        lastStatus.expected and ('%.4f'):format(lastStatus.expected) or 'N/A',
        tonumber(lastStatus.modifier) or 1.0
    ))
end, false)
'''
    fxmanifest = """fx_version 'cerulean'\ngame 'gta5'\nlua54 'yes'\n\nauthor 'OscarDev'\ndescription 'Guard de daño absoluto generado por weapon_rebalancer V6'\nversion '6.0.0'\n\nshared_script 'config.lua'\nclient_script 'client.lua'\n"""
    readme = """# os_weapon_damage_guard\n\nColoca este recurso después de todos los recursos de armas y daño en `server.cfg`:\n\n```cfg\nensure tus_armas\nensure os_weapon_damage_guard\n```\n\nComando cliente: `/osweaponstatus`\n\nMuestra daño cargado, daño esperado y multiplicador aplicado para el arma actual.\n"""
    (destination / 'config.lua').write_text(config, encoding='utf-8')
    (destination / 'client.lua').write_text(client, encoding='utf-8')
    (destination / 'fxmanifest.lua').write_text(fxmanifest, encoding='utf-8')
    (destination / 'README.md').write_text(readme, encoding='utf-8')
    return destination
