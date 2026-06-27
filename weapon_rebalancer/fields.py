from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Literal

FieldKind = Literal['value_attr', 'ref_attr', 'text']


@dataclass(frozen=True)
class MetaField:
    key: str
    xml_tag: str
    kind: FieldKind
    aliases: tuple[str, ...] = field(default_factory=tuple)
    required_for_firearm: bool = False
    required_for_melee: bool = False
    description: str = ''

    @property
    def all_tags(self) -> tuple[str, ...]:
        return (self.xml_tag, *self.aliases)

    @property
    def tag_pattern(self) -> str:
        return '|'.join(re.escape(tag) for tag in self.all_tags)

    @property
    def pattern(self) -> re.Pattern[str]:
        # Algunos packs vienen con variantes de nombre/capitalización.
        # Ejemplo visto: NetworkHeadShotPlayerDamageModifier vs NetworkHeadshotPlayerDamageModifier.
        # Esto reemplaza conservando el tag real que tenga el archivo.
        if self.kind == 'value_attr':
            return re.compile(rf'(<(?:{self.tag_pattern})\b[^>]*?\bvalue=")([^"]+)("[^>]*/>)', re.IGNORECASE)
        if self.kind == 'ref_attr':
            return re.compile(rf'(<(?:{self.tag_pattern})\b[^>]*?\bref=")([^"]+)("[^>]*/>)', re.IGNORECASE)
        return re.compile(rf'(<(?:{self.tag_pattern})>)([^<]+)(</(?:{self.tag_pattern})>)', re.IGNORECASE)

    def xml_snippet(self, value: str) -> str:
        if self.kind == 'value_attr':
            return f'<{self.xml_tag} value="{value}" />'
        if self.kind == 'ref_attr':
            return f'<{self.xml_tag} ref="{value}" />'
        return f'<{self.xml_tag}>{value}</{self.xml_tag}>'


FIELDS: dict[str, MetaField] = {
    # Identity / structure
    'name': MetaField('name', 'Name', 'text', description='Nombre interno WEAPON_*. No cambiar salvo templates base.'),
    'model': MetaField('model', 'Model', 'text', description='Modelo del arma.'),
    'audio': MetaField('audio', 'Audio', 'text', description='Audio item usado por el arma.'),
    'slot': MetaField('slot', 'Slot', 'text', description='Slot interno.'),
    'wheel_slot': MetaField('wheel_slot', 'WheelSlot', 'text', description='Slot de rueda de armas.'),
    'group': MetaField('group', 'Group', 'text', description='Grupo: GROUP_PISTOL, GROUP_RIFLE, GROUP_MELEE, etc.'),
    'ammo_info': MetaField('ammo_info', 'AmmoInfo', 'ref_attr', description='Tipo de munición.'),
    'clip_size': MetaField('clip_size', 'ClipSize', 'value_attr', description='Balas por cargador.'),

    # Core damage
    'damage': MetaField('damage', 'Damage', 'value_attr', required_for_firearm=True, required_for_melee=True, description='Daño base.'),
    'weapon_range': MetaField('weapon_range', 'WeaponRange', 'value_attr', required_for_firearm=True, description='Rango útil del arma.'),
    'falloff_min': MetaField('falloff_min', 'DamageFallOffRangeMin', 'value_attr', required_for_firearm=True, description='Distancia donde empieza la caída de daño.'),
    'falloff_max': MetaField('falloff_max', 'DamageFallOffRangeMax', 'value_attr', required_for_firearm=True, description='Distancia donde termina la caída de daño.'),
    'falloff_modifier': MetaField('falloff_modifier', 'DamageFallOffModifier', 'value_attr', required_for_firearm=True, description='Multiplicador de caída de daño.'),

    # Headshot
    'headshot_player': MetaField('headshot_player', 'HeadShotDamageModifierPlayer', 'value_attr', description='Multiplicador de cabeza contra jugadores.'),
    'network_headshot': MetaField('network_headshot', 'NetworkHeadShotPlayerDamageModifier', 'value_attr', aliases=('NetworkHeadshotPlayerDamageModifier', 'NetworkHeadshotDamageModifierPlayer'), description='Multiplicador de cabeza en red.'),
    'headshot_ai': MetaField('headshot_ai', 'HeadShotDamageModifierAI', 'value_attr', description='Multiplicador de cabeza contra NPC.'),
    'min_headshot_player': MetaField('min_headshot_player', 'MinHeadShotDistancePlayer', 'value_attr', description='Distancia mínima para headshot contra jugadores.'),
    'max_headshot_player': MetaField('max_headshot_player', 'MaxHeadShotDistancePlayer', 'value_attr', description='Distancia máxima para headshot contra jugadores.'),
    'min_headshot_ai': MetaField('min_headshot_ai', 'MinHeadShotDistanceAI', 'value_attr', description='Distancia mínima para headshot contra NPC.'),
    'max_headshot_ai': MetaField('max_headshot_ai', 'MaxHeadShotDistanceAI', 'value_attr', description='Distancia máxima para headshot contra NPC.'),

    # Body modifiers
    'hit_limbs': MetaField('hit_limbs', 'HitLimbsDamageModifier', 'value_attr', description='Daño a extremidades.'),
    'network_hit_limbs': MetaField('network_hit_limbs', 'NetworkHitLimbsDamageModifier', 'value_attr', description='Daño a extremidades en red.'),
    'lightly_armoured': MetaField('lightly_armoured', 'LightlyArmouredDamageModifier', 'value_attr', description='Modificador contra armadura ligera.'),
    'vehicle_damage_modifier': MetaField('vehicle_damage_modifier', 'VehicleDamageModifier', 'value_attr', description='Daño contra vehículos.'),

    # Handling / feel
    'time_between_shots': MetaField('time_between_shots', 'TimeBetweenShots', 'value_attr', description='Tiempo entre disparos. Menor = más rápido.'),
    'lock_on_range': MetaField('lock_on_range', 'LockOnRange', 'value_attr', description='Rango de lock-on.'),
    'accuracy_spread': MetaField('accuracy_spread', 'AccuracySpread', 'value_attr', description='Dispersión base.'),
    'run_and_gun_accuracy_modifier': MetaField('run_and_gun_accuracy_modifier', 'RunAndGunAccuracyModifier', 'value_attr', description='Precisión corriendo/disparando.'),
    'accurate_mode_accuracy_modifier': MetaField('accurate_mode_accuracy_modifier', 'AccurateModeAccuracyModifier', 'value_attr', description='Precisión al apuntar con calma.'),
    'recoil_accuracy_max': MetaField('recoil_accuracy_max', 'RecoilAccuracyMax', 'value_attr', description='Límite de penalización por recoil.'),
    'recoil_error_time': MetaField('recoil_error_time', 'RecoilErrorTime', 'value_attr', description='Tiempo acumulando error de recoil.'),
    'recoil_recovery_rate': MetaField('recoil_recovery_rate', 'RecoilRecoveryRate', 'value_attr', description='Velocidad de recuperación del recoil.'),
    'recoil_shake_amplitude': MetaField('recoil_shake_amplitude', 'RecoilShakeAmplitude', 'value_attr', description='Sacudida visual al disparar.'),
    'recoil_accuracy_to_allow_headshot_ai': MetaField('recoil_accuracy_to_allow_headshot_ai', 'RecoilAccuracyToAllowHeadShotAI', 'value_attr', description='Precisión necesaria para headshot AI.'),

    # Reload / animations
    'reload_time_mp': MetaField('reload_time_mp', 'ReloadTimeMP', 'value_attr', description='Tiempo reload en MP si existe.'),
    'reload_time_sp': MetaField('reload_time_sp', 'ReloadTimeSP', 'value_attr', description='Tiempo reload en SP si existe.'),
    'anim_reload_rate': MetaField('anim_reload_rate', 'AnimReloadRate', 'value_attr', description='Velocidad de animación de recarga.'),
    'anim_fire_rate_modifier': MetaField('anim_fire_rate_modifier', 'AnimFireRateModifier', 'value_attr', description='Modificador de animación de disparo.'),

    # Advanced / flags
    'firing_pattern': MetaField('firing_pattern', 'FiringPattern', 'ref_attr', description='Patrón de disparo.'),
    'weapon_flags': MetaField('weapon_flags', 'WeaponFlags', 'text', description='Flags internas. Modificar con cuidado.'),
    'aim_fov': MetaField('aim_fov', 'AimFOV', 'value_attr', description='FOV al apuntar si existe.'),
    'first_person_scope_fov': MetaField('first_person_scope_fov', 'FirstPersonScopeFov', 'value_attr', description='FOV de mira en primera persona.'),
}

EXTRACT_NAME_RE = FIELDS['name'].pattern
EXTRACT_GROUP_RE = FIELDS['group'].pattern


def print_supported_fields() -> None:
    print('Campos soportados por el rebalancer:\n')
    for key, field in FIELDS.items():
        print(f'- {key:36s} -> <{field.xml_tag}> | {field.kind} | {field.description}')
