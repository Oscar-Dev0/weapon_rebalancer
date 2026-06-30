from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .profiles import MELEE_PRESETS, firearm_base, no_headshot
from .scanner import ScanConfig

ROOT = Path('/fivem/pruebas/resources/[streaming]/[PackArmas]')

ACTIVE_PRESET = 'pvp_lethal'
DRY_RUN = True
CREATE_BACKUP = True
WRITE_JSON_REPORT = False
REPORT_PATH = Path('weapon_rebalance_report.json')
SKIP_INVALID_FILES = True
SKIP_ON_MISSING_REQUIRED_TAGS = True

# Deep scan: busca .meta en subcarpetas aunque el paquete tenga estructura rara.
# También puede leer configs por carpeta: weapon_rebalance.json / weapon_balance.json / rebalance.json
SCAN = ScanConfig(
    recursive=True,
    include_bak=False,
    scan_all_meta=True,
    require_weapon_info=False,
    weapon_group_overrides={
        # 'WEAPON_CUSTOM_DAGGER': 'GROUP_MELEE',
        # 'WEAPON_CUSTOM_AR': 'GROUP_RIFLE',
    },
)

SKIP_BASENAMES = {
    'weaponanimations.meta',
    'weaponarchetypes.meta',
    'weaponcomponents.meta',
    'pedpersonality.meta',
}

SAFE_BOUNDS: dict[str, tuple[float, float]] = {
    # Los perfiles externos incluidos usan 100+ de daño; no deben recortarse silenciosamente.
    'damage': (0.0, 1000.0),
    'weapon_range': (0.1, 650.0),
    'falloff_min': (0.0, 650.0),
    'falloff_max': (0.1, 650.0),
    'falloff_modifier': (0.0, 2.0),
    'headshot_player': (0.0, 1500.0),
    'network_headshot': (0.0, 1500.0),
    'headshot_ai': (0.0, 1500.0),
    'network_player_damage_modifier': (0.0, 10.0),
    'network_ped_damage_modifier': (0.0, 10.0),
    'min_headshot_player': (0.0, 650.0),
    'max_headshot_player': (0.0, 650.0),
    'min_headshot_ai': (0.0, 650.0),
    'max_headshot_ai': (0.0, 650.0),
    'hit_limbs': (0.0, 2.0),
    'network_hit_limbs': (0.0, 2.0),
    # Este campo es un float real del CWeaponInfo. El límite anterior de 2.0
    # impedía crear perfiles META agresivos contra cascos/armadura ligera.
    'lightly_armoured': (0.0, 1000.0),
    'penetration': (0.0, 10.0),
    'vehicle_damage_modifier': (0.0, 5.0),
    'time_between_shots': (0.030, 2.500),
    'clip_size': (1.0, 250.0),
    'lock_on_range': (0.0, 500.0),
    'accuracy_spread': (0.0, 10.0),
    'run_and_gun_accuracy_modifier': (0.0, 10.0),
    'accurate_mode_accuracy_modifier': (0.0, 10.0),
    'recoil_accuracy_max': (0.0, 10.0),
    'recoil_error_time': (0.0, 10.0),
    'recoil_recovery_rate': (0.0, 10.0),
    'recoil_shake_amplitude': (0.0, 10.0),
    'reload_time_mp': (0.05, 20.0),
    'reload_time_sp': (0.05, 20.0),
    'anim_reload_rate': (0.05, 10.0),
    'anim_fire_rate_modifier': (0.05, 10.0),
    'aim_fov': (1.0, 120.0),
    'first_person_scope_fov': (1.0, 120.0),
}

# Perfiles independientes. 'original' conserva las etiquetas originales del meta.
RECOIL_PROFILE = 'normal'       # original, none, low, normal, high
ACCURACY_PROFILE = 'normal'     # original, laser, high, normal, low
DAMAGE_PROFILE = 'normal'       # original, none, head_only, low, normal, high, lethal
ARMOUR_PROFILE = 'max'          # original, none, normal, piercing, max
RANGE_PROFILE = 'normal'        # original, short, normal, long, very_long
FIRE_RATE_PROFILE = 'original'  # original, slow, normal, fast, very_fast
RELOAD_PROFILE = 'original'     # original, slow, normal, fast, very_fast
HEADSHOT_PROFILE = 'onetap'     # original, off, normal, onetap

@dataclass
class HeadshotConfig:
    # False = quita daño extra de cabeza globalmente.
    # True = habilita daño de cabeza completo según estos valores, aunque el preset base tenga 0.0.
    enabled: bool = False

    # Si enabled=True, estas armas aun quedan sin daño de cabeza.
    disabled_weapons: set[str] = field(default_factory=set)

    # Si enabled=False, solo estas armas pueden conservar headshot completo.
    allowed_weapons: set[str] = field(default_factory=set)

    # Modo de headshot:
    # - enabled=True + one_tap=False = headshot normal/balanceado.
    # - enabled=True + one_tap=True  = one tap real en cabeza.
    #
    # Importante GTA/FiveM:
    # 1.0 casi siempre se siente como daño normal.
    # 2.0 - 6.0 sirve para headshot fuerte pero no necesariamente one tap.
    # 18.0 suele comportarse como vanilla, pero en servers RP con armor/falloff puede no matar.
    # 300.0 fuerza one tap real dentro del rango configurado.
    one_tap: bool = False

    enabled_player_modifier: float = 4.0
    enabled_network_modifier: float = 4.0
    enabled_ai_modifier: float = 4.0

    one_tap_player_modifier: float = 300.0
    one_tap_network_modifier: float = 300.0
    one_tap_ai_modifier: float = 300.0

    # Si one_tap=False, estas armas serán one tap igualmente.
    one_tap_weapons: set[str] = field(default_factory=set)

    # Si one_tap=True, estas armas conservan headshot normal y NO one tap.
    no_one_tap_weapons: set[str] = field(default_factory=set)

    # Por seguridad RP, evita one tap en melee aunque one_tap=True.
    disable_one_tap_for_melee: bool = True

    # Si True, --enable-headshots fuerza los valores de arriba incluso si un preset/override tiene 0.0.
    # Este era el problema: antes enabled=True solo dejaba pasar el perfil, pero el perfil ya venía en 0.0.
    force_enabled_values: bool = True

    # Distancia máxima cuando se habilita y el perfil viene sin distancia o en 0.
    enabled_default_max_distance: float | None = None  # None = usar weapon_range si existe

    # ONE TAP - distancia real.
    # El problema de muchos packs es que solo subes el multiplicador, pero MaxHeadShotDistancePlayer
    # o DamageFallOffRangeMax se queda corto. Entonces de cerca funciona y lejos parece apagado.
    # None = usa weapon_range del perfil; número = fuerza esa distancia.
    one_tap_default_distance: float | None = 300.0

    # Si True, al activar one tap hace que WeaponRange, DamageFallOffRangeMin,
    # DamageFallOffRangeMax, MaxHeadShotDistancePlayer y MaxHeadShotDistanceAI trabajen en la
    # misma distancia. Eso evita que el one tap muera por falloff o por distancia de cabeza corta.
    one_tap_sync_distance_with_weapon_range: bool = True

    # Si True, dentro del radio one tap no aplica caída de daño.
    # Esto fuerza DamageFallOffModifier=1.0 y falloff_min/falloff_max a la distancia one tap.
    one_tap_force_no_falloff: bool = True

    # Si True, también sube LockOnRange si el meta lo tiene. No lo recomiendo para RP serio,
    # pero está disponible para pruebas/servidores PvP.
    one_tap_sync_lock_on_range: bool = False

    # Compatibilidad META para cascos nativos / peds marcados como lightly armoured.
    # No usa loops ni modifica vida: únicamente fuerza campos de CWeaponInfo.
    one_tap_through_helmets: bool = True

    # Se aplica a LightlyArmouredDamageModifier únicamente cuando one_tap está activo.
    # El valor anterior del proyecto quedaba limitado a 2.0 y algunos cascos absorbían el disparo.
    one_tap_helmet_damage_modifier: float = 100.0

    # Penetration no sustituye el multiplicador de cabeza, pero ayuda con metas custom
    # que modelan protecciones/objetos delante del bone de cabeza.
    one_tap_force_penetration: bool = True
    one_tap_penetration: float = 1.0

    # Si el META custom no trae estos tags, el rebalancer puede crearlos.
    create_missing_tags: bool = True
    create_missing_lightly_armoured_tag: bool = True
    create_missing_penetration_tag: bool = True

    # Flags META que realmente gobiernan la protección del casco. Se agregan
    # preservando todas las flags existentes del arma.
    one_tap_add_ignore_helmets_flag: bool = True
    one_tap_add_armour_penetrating_flag: bool = True
    create_missing_weapon_flags_tag: bool = True

    # Distancia máxima cuando se desactiva: 0 evita multiplicador por distancia.
    disabled_max_distance: float = 0.0

    # También desactiva daño de cabeza contra NPC.
    disable_ai_headshot: bool = True

    # Garantía matemática mínima para perfiles head-only o META con Damage=0.
    # El rebalancer calcula un piso de daño base para que el multiplicador de red
    # alcance esta vida efectiva con margen, sin subir innecesariamente el daño corporal.
    one_tap_auto_minimum_base_damage: bool = True
    one_tap_target_effective_health: float = 400.0
    one_tap_safety_margin: float = 1.25
    one_tap_minimum_base_damage: float = 0.35

    # Si NetworkPlayerDamageModifier existe en 0, cualquier multiplicador de cabeza
    # sigue dando 0. Solo se corrige cuando está ausente/cero, no se pisa un balance válido.
    one_tap_repair_zero_network_modifier: bool = True
    one_tap_network_player_modifier_fallback: float = 1.0
    create_missing_network_player_modifier_tag: bool = True

    # Flags que contradicen un arma letal. Solo se eliminan cuando el one-tap está
    # activo en un arma de fuego; no toca tasers, snowballs ni melee.
    one_tap_remove_nonlethal_flags: bool = True
    one_tap_blocking_flags: tuple[str, ...] = ('NonLethal', 'NonViolent')


HEADSHOT = HeadshotConfig(
    # Recomendado para RP: False.
    # Para headshot normal: pon enabled=True y one_tap=False.
    # Para one tap global: pon enabled=True y one_tap=True.
    enabled=True,
    one_tap=True,

    # Headshot normal: más daño en cabeza, pero no necesariamente mata de 1.
    enabled_player_modifier=4.0,
    enabled_network_modifier=4.0,
    enabled_ai_modifier=4.0,

    # One tap: cabeza letal tipo vanilla.
    # One tap garantizado: usa multiplicador alto para que no quede media vida por armor/falloff/red.
    one_tap_player_modifier=1500.0,
    one_tap_network_modifier=1500.0,
    one_tap_ai_modifier=1500.0,

    # Fuerza la ruta META contra cascos nativos sin instalar un antitank Lua.
    one_tap_through_helmets=True,
    one_tap_helmet_damage_modifier=100.0,
    one_tap_force_penetration=True,
    one_tap_penetration=1.0,

    disabled_weapons={
        # 'WEAPON_GLIZZYG26SWITCH',
    },
    allowed_weapons={
        # Ejemplo si global está off, pero quieres permitir cabeza en esta arma:
        # 'WEAPON_SNIPERRIFLE',
    },
    one_tap_weapons={
        # Ejemplo: solo esta será one tap aunque one_tap global esté False:
        # 'WEAPON_SNIPERRIFLE',
    },
    no_one_tap_weapons={
        # Ejemplo: si one_tap global está True, esta NO será one tap:
        # 'WEAPON_STUNGUN',
    },
)

# Armas recreativas/inofensivas que SI se procesan, pero se fuerzan a daño cero.
# Se aplican al final para que ningún perfil letal pueda sobrescribirlas.
HARMLESS_WEAPONS: set[str] = {
    'WEAPON_SNOWBALL',
    'WEAPON_BALL',
}

# Armas que no quieres tocar nunca.
IGNORE_WEAPONS: set[str] = {
    'WEAPON_RPG',
    'WEAPON_RAILGUN',
    'WEAPON_MINIGUN',
    'WEAPON_GRENADELAUNCHER',
}

# Si no está vacío, procesa solo estas armas.
ONLY_WEAPONS: set[str] = set()

# Multiplicadores de distancia por arma exacta.
# Se aplican sobre el perfil de su grupo, sin cambiar daño, recoil, spread ni otros valores.
# 1.5 = 50 % más distancia que las demás armas del mismo grupo.
WEAPON_RANGE_MULTIPLIERS: dict[str, float] = {
    # 'WEAPON_CUSTOM_LONG_PISTOL': 1.25,
}

# Multiplicadores por familia/nombre del arma.
# Esto permite mejorar armas vanilla y custom sin escribir cada nombre individualmente.
# La clave se busca dentro del nombre del arma, en mayúsculas.
WEAPON_FAMILY_RANGE_MULTIPLIERS: dict[str, float] = {
    'REVOLVER': 1.5,       # WEAPON_REVOLVER, WEAPON_REVOLVER_MK2, NAVYREVOLVER y custom
    'DOUBLEACTION': 1.5,   # WEAPON_DOUBLEACTION no contiene la palabra REVOLVER
}

# Overrides por arma. Puedes tocar daño, handling, clip, reload, recoil, spread, etc.
EXPLICIT_OVERRIDES: dict[str, dict[str, Any]] = {
    # Pistolas auto: controladas para RP, sin headshot extra por defecto.
    'WEAPON_APPISTOL': no_headshot(firearm_base(
        damage=12.0, weapon_range=95.0, falloff_max=80.0, falloff_modifier=0.35,
        headshot=0.0, limbs=0.58, armour=0.70, tbs=0.125,
        spread=1.15, recoil=1.05, recovery=0.95, vehicle_damage=0.18,
    )),
    'WEAPON_GLIZZYG26SWITCH': no_headshot(firearm_base(
        damage=10.0, weapon_range=85.0, falloff_max=70.0, falloff_modifier=0.30,
        headshot=0.0, limbs=0.55, armour=0.65, tbs=0.115,
        spread=1.35, recoil=1.15, recovery=0.90, vehicle_damage=0.15,
    )),

    # Melee vanilla/custom frecuentes.
    'WEAPON_DAGGER': MELEE_PRESETS['light_blade'],
    'WEAPON_KNIFE': MELEE_PRESETS['blade'],
    'WEAPON_SWITCHBLADE': MELEE_PRESETS['light_blade'],
    'WEAPON_BOTTLE': MELEE_PRESETS['light_blade'],
    'WEAPON_MACHETE': MELEE_PRESETS['heavy'],
    'WEAPON_HATCHET': MELEE_PRESETS['heavy'],
    'WEAPON_BATTLEAXE': MELEE_PRESETS['heavy'],
    'WEAPON_STONE_HATCHET': MELEE_PRESETS['heavy'],
    'WEAPON_BAT': MELEE_PRESETS['blunt'],
    'WEAPON_GOLFCLUB': MELEE_PRESETS['blunt'],
    'WEAPON_NIGHTSTICK': MELEE_PRESETS['blunt'],
    'WEAPON_POOLCUE': MELEE_PRESETS['blunt'],
    'WEAPON_CROWBAR': MELEE_PRESETS['tool'],
    'WEAPON_HAMMER': MELEE_PRESETS['tool'],
    'WEAPON_WRENCH': MELEE_PRESETS['tool'],
    'WEAPON_KNUCKLE': MELEE_PRESETS['fist'],
    'WEAPON_FLASHLIGHT': MELEE_PRESETS['flashlight'],
}

# Templates base opcionales para crear/reparar armas GTA base si faltan.
BASE_WEAPON_OVERRIDES: dict[str, dict[str, Any]] = {}

@dataclass
class Settings:
    root: Path
    active_preset: str
    dry_run: bool
    create_backup: bool
    write_json_report: bool
    report_path: Path
    skip_invalid_files: bool
    skip_on_missing_required_tags: bool
    skip_basenames: set[str]
    safe_bounds: dict[str, tuple[float, float]]
    headshot: HeadshotConfig
    ignore_weapons: set[str]
    harmless_weapons: set[str]
    only_weapons: set[str]
    weapon_types: set[str]
    explicit_overrides: dict[str, dict[str, Any]]
    weapon_range_multipliers: dict[str, float]
    weapon_family_range_multipliers: dict[str, float]
    base_weapon_overrides: dict[str, dict[str, Any]]
    recoil_profile: str
    accuracy_profile: str
    damage_profile: str
    armour_profile: str
    range_profile: str
    fire_rate_profile: str
    reload_profile: str
    headshot_profile: str
    current_group: str
    external_group_profiles: dict[str, dict[str, Any]]
    global_meta_overrides: dict[str, Any]
    group_meta_overrides: dict[str, dict[str, Any]]
    weapon_meta_overrides: dict[str, dict[str, Any]]
    global_flag_ops: dict[str, list[str] | bool]
    group_flag_ops: dict[str, dict[str, list[str] | bool]]
    weapon_flag_ops: dict[str, dict[str, list[str] | bool]]
    group_headshot_overrides: dict[str, dict[str, Any]]
    weapon_headshot_overrides: dict[str, dict[str, Any]]
    validation_options: dict[str, Any]
    scan: ScanConfig

    @classmethod
    def from_config(cls) -> 'Settings':
        return cls(
            root=ROOT,
            active_preset=ACTIVE_PRESET,
            dry_run=DRY_RUN,
            create_backup=CREATE_BACKUP,
            write_json_report=WRITE_JSON_REPORT,
            report_path=REPORT_PATH,
            skip_invalid_files=SKIP_INVALID_FILES,
            skip_on_missing_required_tags=SKIP_ON_MISSING_REQUIRED_TAGS,
            skip_basenames=set(SKIP_BASENAMES),
            safe_bounds=dict(SAFE_BOUNDS),
            headshot=deepcopy(HEADSHOT),
            ignore_weapons={w.upper() for w in IGNORE_WEAPONS},
            harmless_weapons={w.upper() for w in HARMLESS_WEAPONS},
            only_weapons={w.upper() for w in ONLY_WEAPONS},
            weapon_types=set(),
            explicit_overrides={k.upper(): v for k, v in EXPLICIT_OVERRIDES.items()},
            weapon_range_multipliers={k.upper(): float(v) for k, v in WEAPON_RANGE_MULTIPLIERS.items()},
            weapon_family_range_multipliers={k.upper(): float(v) for k, v in WEAPON_FAMILY_RANGE_MULTIPLIERS.items()},
            base_weapon_overrides=BASE_WEAPON_OVERRIDES,
            recoil_profile=RECOIL_PROFILE,
            accuracy_profile=ACCURACY_PROFILE,
            damage_profile=DAMAGE_PROFILE,
            armour_profile=ARMOUR_PROFILE,
            range_profile=RANGE_PROFILE,
            fire_rate_profile=FIRE_RATE_PROFILE,
            reload_profile=RELOAD_PROFILE,
            headshot_profile=HEADSHOT_PROFILE,
            current_group='',
            external_group_profiles={},
            global_meta_overrides={},
            group_meta_overrides={},
            weapon_meta_overrides={},
            global_flag_ops={'add': [], 'remove': [], 'create_if_missing': False},
            group_flag_ops={},
            weapon_flag_ops={},
            group_headshot_overrides={},
            weapon_headshot_overrides={},
            validation_options={
                'strict_unknown_fields': False,
                'fail_on_onetap_audit': False,
                'warn_duplicates': True,
                'warn_unregistered_meta': True,
            },
            scan=SCAN,
        )
