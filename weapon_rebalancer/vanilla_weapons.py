from __future__ import annotations

"""Catálogo de armas oficiales publicado por Cfx.re/FiveM.

Se usa únicamente para clasificar un CWeaponInfo como oficial o custom. No contiene
valores de daño: los valores vanilla se recuperan del backup original del META.
"""

CATALOG_ID = 'cfx_weapon_models_2026_07_02'
SOURCE_URL = 'https://docs.fivem.net/docs/game-references/weapon-models/'

OFFICIAL_WEAPONS: frozenset[str] = frozenset({
    # Heavy
    'WEAPON_SNOWLAUNCHER',
    'WEAPON_COMPACTLAUNCHER',
    'WEAPON_MINIGUN',
    'WEAPON_GRENADELAUNCHER_SMOKE',
    'WEAPON_HOMINGLAUNCHER',
    'WEAPON_RAILGUN',
    'WEAPON_FIREWORK',
    'WEAPON_GRENADELAUNCHER',
    'WEAPON_RPG',
    'WEAPON_RAYMINIGUN',
    'WEAPON_EMPLAUNCHER',
    'WEAPON_RAILGUNXM3',

    # Shotguns / long guns listed around shotgun and sniper sections
    'WEAPON_COMBATSHOTGUN',
    'WEAPON_AUTOSHOTGUN',
    'WEAPON_PUMPSHOTGUN',
    'WEAPON_HEAVYSHOTGUN',
    'WEAPON_PUMPSHOTGUN_MK2',
    'WEAPON_SAWNOFFSHOTGUN',
    'WEAPON_BULLPUPSHOTGUN',
    'WEAPON_ASSAULTSHOTGUN',
    'WEAPON_DBSHOTGUN',
    'WEAPON_MUSKET',

    # Snipers / marksman
    'WEAPON_SNIPERRIFLE',
    'WEAPON_HEAVYSNIPER_MK2',
    'WEAPON_HEAVYSNIPER',
    'WEAPON_MARKSMANRIFLE_MK2',
    'WEAPON_PRECISIONRIFLE',
    'WEAPON_MARKSMANRIFLE',

    # Fire extinguisher / thrown
    'WEAPON_FIREEXTINGUISHER',
    'WEAPON_SNOWBALL',
    'WEAPON_BALL',
    'WEAPON_MOLOTOV',
    'WEAPON_STICKYBOMB',
    'WEAPON_FLARE',
    'WEAPON_GRENADE',
    'WEAPON_BZGAS',
    'WEAPON_PROXMINE',
    'WEAPON_PIPEBOMB',
    'WEAPON_ACIDPACKAGE',
    'WEAPON_SMOKEGRENADE',

    # Pistols / revolvers
    'WEAPON_VINTAGEPISTOL',
    'WEAPON_PISTOL',
    'WEAPON_PISTOLXM3',
    'WEAPON_APPISTOL',
    'WEAPON_CERAMICPISTOL',
    'WEAPON_FLAREGUN',
    'WEAPON_GADGETPISTOL',
    'WEAPON_COMBATPISTOL',
    'WEAPON_SNSPISTOL_MK2',
    'WEAPON_NAVYREVOLVER',
    'WEAPON_DOUBLEACTION',
    'WEAPON_PISTOL50',
    'WEAPON_RAYPISTOL',
    'WEAPON_SNSPISTOL',
    'WEAPON_PISTOL_MK2',
    'WEAPON_REVOLVER',
    'WEAPON_REVOLVER_MK2',
    'WEAPON_HEAVYPISTOL',
    'WEAPON_MARKSMANPISTOL',

    # SMGs
    'WEAPON_COMBATPDW',
    'WEAPON_MICROSMG',
    'WEAPON_TECPISTOL',
    'WEAPON_SMG',
    'WEAPON_SMG_MK2',
    'WEAPON_MINISMG',
    'WEAPON_MACHINEPISTOL',
    'WEAPON_ASSAULTSMG',

    # Cans
    'WEAPON_FERTILIZERCAN',
    'WEAPON_PETROLCAN',
    'WEAPON_HAZARDCAN',

    # Melee
    'WEAPON_WRENCH',
    'WEAPON_STONE_HATCHET',
    'WEAPON_GOLFCLUB',
    'WEAPON_HAMMER',
    'WEAPON_CANDYCANE',
    'WEAPON_NIGHTSTICK',
    'WEAPON_CROWBAR',
    'WEAPON_FLASHLIGHT',
    'WEAPON_DAGGER',
    'WEAPON_POOLCUE',
    'WEAPON_BAT',
    'WEAPON_KNIFE',
    'WEAPON_BATTLEAXE',
    'WEAPON_STUNROD',
    'WEAPON_MACHETE',
    'WEAPON_SWITCHBLADE',
    'WEAPON_HATCHET',
    'WEAPON_BOTTLE',
    'WEAPON_KNUCKLE',

    # Hacking / stun
    'WEAPON_HACKINGDEVICE',
    'WEAPON_STUNGUN',
    'WEAPON_STUNGUN_MP',

    # Rifles
    'WEAPON_ASSAULTRIFLE_MK2',
    'WEAPON_COMPACTRIFLE',
    'WEAPON_BATTLERIFLE',
    'WEAPON_BULLPUPRIFLE',
    'WEAPON_CARBINERIFLE',
    'WEAPON_BULLPUPRIFLE_MK2',
    'WEAPON_SPECIALCARBINE_MK2',
    'WEAPON_MILITARYRIFLE',
    'WEAPON_ADVANCEDRIFLE',
    'WEAPON_ASSAULTRIFLE',
    'WEAPON_SPECIALCARBINE',
    'WEAPON_HEAVYRIFLE',
    'WEAPON_TACTICALRIFLE',
    'WEAPON_CARBINERIFLE_MK2',

    # Machine guns
    'WEAPON_RAYCARBINE',
    'WEAPON_GUSENBERG',
    'WEAPON_COMBATMG',
    'WEAPON_MG',
    'WEAPON_COMBATMG_MK2',

    # Misc
    'WEAPON_UNARMED',
    'WEAPON_METALDETECTOR',
})

CATALOGS: dict[str, frozenset[str]] = {
    CATALOG_ID: OFFICIAL_WEAPONS,
}


def get_catalog(catalog_id: str) -> frozenset[str]:
    try:
        return CATALOGS[catalog_id]
    except KeyError as exc:
        known = ', '.join(sorted(CATALOGS))
        raise KeyError(f'Catálogo oficial desconocido: {catalog_id}. Disponibles: {known}') from exc
