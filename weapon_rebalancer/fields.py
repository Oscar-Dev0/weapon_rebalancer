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
    safe_insert: bool = False
    section: str = 'advanced'
    description: str = ''

    @property
    def all_tags(self) -> tuple[str, ...]:
        return (self.xml_tag, *self.aliases)

    @property
    def tag_pattern(self) -> str:
        return '|'.join(re.escape(tag) for tag in self.all_tags)

    @property
    def pattern(self) -> re.Pattern[str]:
        if self.kind == 'value_attr':
            return re.compile(rf'(<(?:{self.tag_pattern})\b[^>]*?\bvalue=")([^"]+)("[^>]*/>)', re.IGNORECASE)
        if self.kind == 'ref_attr':
            return re.compile(rf'(<(?:{self.tag_pattern})\b[^>]*?\bref=")([^"]+)("[^>]*/>)', re.IGNORECASE)
        return re.compile(rf'(<(?:{self.tag_pattern})>)([^<]*)(</(?:{self.tag_pattern})>)', re.IGNORECASE)

    def xml_snippet(self, value: str) -> str:
        if self.kind == 'value_attr':
            return f'<{self.xml_tag} value="{value}" />'
        if self.kind == 'ref_attr':
            return f'<{self.xml_tag} ref="{value}" />'
        return f'<{self.xml_tag}>{value}</{self.xml_tag}>'


def F(
    key: str,
    tag: str,
    kind: FieldKind = 'value_attr',
    *,
    aliases: tuple[str, ...] = (),
    firearm: bool = False,
    melee: bool = False,
    insert: bool = False,
    section: str = 'advanced',
    description: str = '',
) -> MetaField:
    return MetaField(
        key=key,
        xml_tag=tag,
        kind=kind,
        aliases=aliases,
        required_for_firearm=firearm,
        required_for_melee=melee,
        safe_insert=insert,
        section=section,
        description=description,
    )


# Catálogo amplio de hojas escalares de CWeaponInfo. Las estructuras complejas
# (Fx, AttachPoints, OverrideForces, vectores, arrays, etc.) se inventarían mal si
# se insertaran a ciegas; el exportador las inventaría completas y `meta` permite
# reemplazar hojas exactas existentes sin destruir su XML padre.
FIELDS: dict[str, MetaField] = {
    # Identity / structure
    'name': F('name', 'Name', 'text', section='identity', description='Nombre interno WEAPON_*.'),
    'model': F('model', 'Model', 'text', section='identity', description='Modelo del arma.'),
    'audio': F('audio', 'Audio', 'text', section='identity', description='Audio item.'),
    'slot': F('slot', 'Slot', 'text', section='identity', description='Slot interno.'),
    'damage_type': F('damage_type', 'DamageType', 'text', section='identity', description='BULLET, MELEE, EXPLOSIVE, etc.'),
    'fire_type': F('fire_type', 'FireType', 'text', section='identity', description='INSTANT_HIT, PROJECTILE, etc.'),
    'wheel_slot': F('wheel_slot', 'WheelSlot', 'text', section='identity'),
    'group': F('group', 'Group', 'text', section='identity'),
    'ammo_info': F('ammo_info', 'AmmoInfo', 'ref_attr', section='identity'),
    'aiming_info': F('aiming_info', 'AimingInfo', 'ref_attr', section='identity'),
    'clip_size': F('clip_size', 'ClipSize', section='ammo'),

    # Core damage / networking
    'damage': F('damage', 'Damage', firearm=True, melee=True, insert=True, section='damage'),
    'damage_time': F('damage_time', 'DamageTime', section='damage'),
    'damage_time_in_vehicle': F('damage_time_in_vehicle', 'DamageTimeInVehicle', section='damage'),
    'damage_time_in_vehicle_headshot': F('damage_time_in_vehicle_headshot', 'DamageTimeInVehicleHeadShot', section='damage'),
    'network_player_damage_modifier': F('network_player_damage_modifier', 'NetworkPlayerDamageModifier', insert=True, section='damage'),
    'network_ped_damage_modifier': F('network_ped_damage_modifier', 'NetworkPedDamageModifier', section='damage'),
    'hit_limbs': F('hit_limbs', 'HitLimbsDamageModifier', insert=True, section='damage'),
    'network_hit_limbs': F('network_hit_limbs', 'NetworkHitLimbsDamageModifier', insert=True, section='damage'),
    'lightly_armoured': F('lightly_armoured', 'LightlyArmouredDamageModifier', insert=True, section='damage'),
    'vehicle_damage_modifier': F('vehicle_damage_modifier', 'VehicleDamageModifier', insert=True, section='damage'),
    'penetration': F('penetration', 'Penetration', insert=True, section='damage'),
    'killshot_impulse_scale': F('killshot_impulse_scale', 'KillshotImpulseScale', section='damage'),
    'knockdown_count': F('knockdown_count', 'KnockdownCount', section='damage'),

    # Range / falloff / AI awareness
    'weapon_range': F('weapon_range', 'WeaponRange', firearm=True, insert=True, section='range'),
    'lock_on_range': F('lock_on_range', 'LockOnRange', section='range'),
    'ai_sound_range': F('ai_sound_range', 'AiSoundRange', section='range'),
    'ai_potential_blast_event_range': F('ai_potential_blast_event_range', 'AiPotentialBlastEventRange', section='range'),
    'falloff_min': F('falloff_min', 'DamageFallOffRangeMin', firearm=True, insert=True, section='range'),
    'falloff_max': F('falloff_max', 'DamageFallOffRangeMax', firearm=True, insert=True, section='range'),
    'falloff_modifier': F('falloff_modifier', 'DamageFallOffModifier', firearm=True, insert=True, section='range'),

    # Headshot
    'headshot_player': F('headshot_player', 'HeadShotDamageModifierPlayer', insert=True, section='headshot'),
    'network_headshot': F(
        'network_headshot', 'NetworkHeadShotPlayerDamageModifier',
        aliases=('NetworkHeadshotPlayerDamageModifier', 'NetworkHeadshotDamageModifierPlayer'),
        insert=True, section='headshot',
    ),
    'headshot_ai': F('headshot_ai', 'HeadShotDamageModifierAI', insert=True, section='headshot'),
    'recoil_accuracy_to_allow_headshot_player': F('recoil_accuracy_to_allow_headshot_player', 'RecoilAccuracyToAllowHeadShotPlayer', section='headshot'),
    'recoil_accuracy_to_allow_headshot_ai': F('recoil_accuracy_to_allow_headshot_ai', 'RecoilAccuracyToAllowHeadShotAI', section='headshot'),
    'min_headshot_player': F('min_headshot_player', 'MinHeadShotDistancePlayer', insert=True, section='headshot'),
    'max_headshot_player': F('max_headshot_player', 'MaxHeadShotDistancePlayer', insert=True, section='headshot'),
    'min_headshot_ai': F('min_headshot_ai', 'MinHeadShotDistanceAI', insert=True, section='headshot'),
    'max_headshot_ai': F('max_headshot_ai', 'MaxHeadShotDistanceAI', insert=True, section='headshot'),

    # Force / projectile / pellets
    'force': F('force', 'Force', section='force'),
    'force_hit_ped': F('force_hit_ped', 'ForceHitPed', section='force'),
    'force_hit_vehicle': F('force_hit_vehicle', 'ForceHitVehicle', section='force'),
    'force_hit_flying_heli': F('force_hit_flying_heli', 'ForceHitFlyingHeli', section='force'),
    'force_max_strength_mult': F('force_max_strength_mult', 'ForceMaxStrengthMult', section='force'),
    'force_falloff_range_start': F('force_falloff_range_start', 'ForceFalloffRangeStart', section='force'),
    'force_falloff_range_end': F('force_falloff_range_end', 'ForceFalloffRangeEnd', section='force'),
    'force_falloff_min': F('force_falloff_min', 'ForceFalloffMin', section='force'),
    'projectile_force': F('projectile_force', 'ProjectileForce', section='force'),
    'frag_impulse': F('frag_impulse', 'FragImpulse', section='force'),
    'vertical_launch_adjustment': F('vertical_launch_adjustment', 'VerticalLaunchAdjustment', section='projectile'),
    'drop_forward_velocity': F('drop_forward_velocity', 'DropForwardVelocity', section='projectile'),
    'speed': F('speed', 'Speed', section='projectile'),
    'bullets_in_batch': F('bullets_in_batch', 'BulletsInBatch', section='projectile'),
    'batch_spread': F('batch_spread', 'BatchSpread', section='projectile'),
    'bullet_direction_offset_degrees': F('bullet_direction_offset_degrees', 'BulletDirectionOffsetInDegrees', section='projectile'),
    'bullet_direction_pitch_offset': F('bullet_direction_pitch_offset', 'BulletDirectionPitchOffset', section='projectile'),
    'bullet_direction_pitch_homing_offset': F('bullet_direction_pitch_homing_offset', 'BulletDirectionPitchHomingOffset', section='projectile'),

    # Accuracy / recoil
    'accuracy_spread': F('accuracy_spread', 'AccuracySpread', section='accuracy'),
    'accurate_mode_accuracy_modifier': F('accurate_mode_accuracy_modifier', 'AccurateModeAccuracyModifier', section='accuracy'),
    'run_and_gun_accuracy_modifier': F('run_and_gun_accuracy_modifier', 'RunAndGunAccuracyModifier', section='accuracy'),
    'run_and_gun_accuracy_min_override': F('run_and_gun_accuracy_min_override', 'RunAndGunAccuracyMinOverride', section='accuracy'),
    'recoil_accuracy_max': F('recoil_accuracy_max', 'RecoilAccuracyMax', section='recoil'),
    'recoil_error_time': F('recoil_error_time', 'RecoilErrorTime', section='recoil'),
    'recoil_recovery_rate': F('recoil_recovery_rate', 'RecoilRecoveryRate', section='recoil'),
    'recoil_shake_amplitude': F('recoil_shake_amplitude', 'RecoilShakeAmplitude', section='recoil'),
    'explosion_shake_amplitude': F('explosion_shake_amplitude', 'ExplosionShakeAmplitude', section='recoil'),
    'min_time_between_recoil_shakes': F('min_time_between_recoil_shakes', 'MinTimeBetweenRecoilShakes', section='recoil'),
    'ik_recoil_displacement': F('ik_recoil_displacement', 'IkRecoilDisplacement', section='recoil'),
    'ik_recoil_displacement_scope': F('ik_recoil_displacement_scope', 'IkRecoilDisplacementScope', section='recoil'),
    'ik_recoil_scale_backward': F('ik_recoil_scale_backward', 'IkRecoilDisplacementScaleBackward', section='recoil'),
    'ik_recoil_scale_vertical': F('ik_recoil_scale_vertical', 'IkRecoilDisplacementScaleVertical', section='recoil'),

    # Fire rate / reload / spin
    'time_between_shots': F('time_between_shots', 'TimeBetweenShots', section='fire_rate'),
    'cached_fire_window': F('cached_fire_window', 'TimeLeftBetweenShotsWhereShouldFireIsCached', section='fire_rate'),
    'spin_up_time': F('spin_up_time', 'SpinUpTime', section='fire_rate'),
    'spin_time': F('spin_time', 'SpinTime', section='fire_rate'),
    'spin_down_time': F('spin_down_time', 'SpinDownTime', section='fire_rate'),
    'alternate_wait_time': F('alternate_wait_time', 'AlternateWaitTime', section='fire_rate'),
    'reload_time_mp': F('reload_time_mp', 'ReloadTimeMP', section='reload'),
    'reload_time_sp': F('reload_time_sp', 'ReloadTimeSP', section='reload'),
    'vehicle_reload_time': F('vehicle_reload_time', 'VehicleReloadTime', section='reload'),
    'anim_reload_rate': F('anim_reload_rate', 'AnimReloadRate', section='reload'),
    'bullets_per_anim_loop': F('bullets_per_anim_loop', 'BulletsPerAnimLoop', section='reload'),
    'anim_fire_rate_modifier': F('anim_fire_rate_modifier', 'AnimFireRateModifier', section='fire_rate'),

    # Bullet bending / aim assistance
    'bullet_bending_near_radius': F('bullet_bending_near_radius', 'BulletBendingNearRadius', section='aim'),
    'bullet_bending_far_radius': F('bullet_bending_far_radius', 'BulletBendingFarRadius', section='aim'),
    'bullet_bending_zoomed_radius': F('bullet_bending_zoomed_radius', 'BulletBendingZoomedRadius', section='aim'),
    'fp_bullet_bending_near_radius': F('fp_bullet_bending_near_radius', 'FirstPersonBulletBendingNearRadius', section='aim'),
    'fp_bullet_bending_far_radius': F('fp_bullet_bending_far_radius', 'FirstPersonBulletBendingFarRadius', section='aim'),
    'fp_bullet_bending_zoomed_radius': F('fp_bullet_bending_zoomed_radius', 'FirstPersonBulletBendingZoomedRadius', section='aim'),

    # Camera / FOV
    'camera_fov': F('camera_fov', 'CameraFov', section='camera'),
    'aim_fov': F('aim_fov', 'AimFOV', aliases=('AimFov',), section='camera'),
    'first_person_aim_fov_min': F('first_person_aim_fov_min', 'FirstPersonAimFovMin', section='camera'),
    'first_person_aim_fov_max': F('first_person_aim_fov_max', 'FirstPersonAimFovMax', section='camera'),
    'first_person_scope_fov': F('first_person_scope_fov', 'FirstPersonScopeFov', section='camera'),
    'first_person_scope_attachment_fov': F('first_person_scope_attachment_fov', 'FirstPersonScopeAttachmentFov', section='camera'),
    'zoom_factor_accurate_mode': F('zoom_factor_accurate_mode', 'ZoomFactorForAccurateMode', section='camera'),
    'default_camera_hash': F('default_camera_hash', 'DefaultCameraHash', 'text', section='camera'),
    'aim_camera_hash': F('aim_camera_hash', 'AimCameraHash', 'text', section='camera'),
    'fire_camera_hash': F('fire_camera_hash', 'FireCameraHash', 'text', section='camera'),
    'cover_camera_hash': F('cover_camera_hash', 'CoverCameraHash', 'text', section='camera'),
    'cover_ready_camera_hash': F('cover_ready_camera_hash', 'CoverReadyToFireCameraHash', 'text', section='camera'),
    'run_and_gun_camera_hash': F('run_and_gun_camera_hash', 'RunAndGunCameraHash', 'text', section='camera'),
    'recoil_shake_hash': F('recoil_shake_hash', 'RecoilShakeHash', 'text', section='camera'),
    'recoil_shake_hash_fp': F('recoil_shake_hash_fp', 'RecoilShakeHashFirstPerson', 'text', section='camera'),
    'accuracy_offset_shake_hash': F('accuracy_offset_shake_hash', 'AccuracyOffsetShakeHash', 'text', section='camera'),

    # Rumble
    'initial_rumble_duration': F('initial_rumble_duration', 'InitialRumbleDuration', section='rumble'),
    'initial_rumble_intensity': F('initial_rumble_intensity', 'InitialRumbleIntensity', section='rumble'),
    'initial_rumble_trigger': F('initial_rumble_trigger', 'InitialRumbleIntensityTrigger', section='rumble'),
    'rumble_duration': F('rumble_duration', 'RumbleDuration', section='rumble'),
    'rumble_intensity': F('rumble_intensity', 'RumbleIntensity', section='rumble'),
    'rumble_trigger': F('rumble_trigger', 'RumbleIntensityTrigger', section='rumble'),
    'rumble_damage_intensity': F('rumble_damage_intensity', 'RumbleDamageIntensity', section='rumble'),
    'initial_rumble_duration_fps': F('initial_rumble_duration_fps', 'InitialRumbleDurationFps', section='rumble'),
    'initial_rumble_intensity_fps': F('initial_rumble_intensity_fps', 'InitialRumbleIntensityFps', section='rumble'),
    'rumble_duration_fps': F('rumble_duration_fps', 'RumbleDurationFps', section='rumble'),
    'rumble_intensity_fps': F('rumble_intensity_fps', 'RumbleIntensityFps', section='rumble'),

    # HUD / names / misc
    'reticule_min_size_standing': F('reticule_min_size_standing', 'ReticuleMinSizeStanding', section='hud'),
    'reticule_min_size_crouched': F('reticule_min_size_crouched', 'ReticuleMinSizeCrouched', section='hud'),
    'reticule_scale': F('reticule_scale', 'ReticuleScale', section='hud'),
    'reticule_style_hash': F('reticule_style_hash', 'ReticuleStyleHash', 'text', section='hud'),
    'first_person_reticule_style_hash': F('first_person_reticule_style_hash', 'FirstPersonReticuleStyleHash', 'text', section='hud'),
    'pickup_hash': F('pickup_hash', 'PickupHash', 'text', section='identity'),
    'mp_pickup_hash': F('mp_pickup_hash', 'MPPickupHash', 'text', section='identity'),
    'human_name_hash': F('human_name_hash', 'HumanNameHash', 'text', section='identity'),
    'movement_mode_conditional_idle': F('movement_mode_conditional_idle', 'MovementModeConditionalIdle', 'text', section='animation'),
    'stat_name': F('stat_name', 'StatName', 'text', section='identity'),
    'nm_shot_tuning_set': F('nm_shot_tuning_set', 'NmShotTuningSet', 'text', section='animation'),
    'firing_pattern': F('firing_pattern', 'FiringPattern', 'ref_attr', section='fire_rate'),
    'weapon_flags': F('weapon_flags', 'WeaponFlags', 'text', insert=True, section='flags'),
    'ammo_diminishing_rate': F('ammo_diminishing_rate', 'AmmoDiminishingRate', section='ammo'),
    'aiming_breathing_weight': F('aiming_breathing_weight', 'AimingBreathingAdditiveWeight', section='animation'),
    'firing_breathing_weight': F('firing_breathing_weight', 'FiringBreathingAdditiveWeight', section='animation'),
}

EXTRACT_NAME_RE = FIELDS['name'].pattern
EXTRACT_GROUP_RE = FIELDS['group'].pattern


def print_supported_fields() -> None:
    print(f'Campos CWeaponInfo soportados: {len(FIELDS)}\n')
    current = None
    for key, meta_field in sorted(FIELDS.items(), key=lambda item: (item[1].section, item[0])):
        if meta_field.section != current:
            current = meta_field.section
            print(f'[{current}]')
        insert = ' | insertable' if meta_field.safe_insert else ''
        print(f'- {key:42s} -> <{meta_field.xml_tag}> | {meta_field.kind}{insert}')
