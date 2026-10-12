from __future__ import annotations

# Flags nominales conocidas de CWeaponInfo. El rebalancer no elimina flags que no
# conozca: las preserva exactamente y solo aplica add/remove solicitado.
KNOWN_WEAPON_FLAGS = (
    'CarriedInHand', 'Automatic', 'Silenced', 'FirstPersonScope',
    'ArmourPenetrating', 'ApplyBulletForce', 'Gun', 'CanLockonOnFoot',
    'CanLockonInVehicle', 'Homing', 'CanFreeAim', 'Heavy', 'TwoHanded',
    'Launched', 'MeleeBlade', 'MeleeClub', 'AnimReload', 'AnimCrouchFire',
    'CreateVisibleOrdnance', 'TreatAsOneHandedInCover', 'Thrown', 'Bomb',
    'UsableOnFoot', 'UsableUnderwater', 'UsableClimbing', 'UsableInCover',
    'AllowEarlyExitFromFireAnimAfterBulletFired', 'DisableRightHandIk',
    'DisableLeftHandIkInCover', 'DontSwapWeaponIfNoAmmo', 'DoesRevivableDamage',
    'NoFriendlyFireDamage', 'Detonator', 'DisplayRechargeTimeHUD',
    'OnlyFireOneShot', 'OnlyFireOneShotPerTriggerPress', 'UseLegDamageVoice',
    'CanBeFiredLikeGun', 'OnlyAllowFiring', 'NoLeftHandIK',
    'NoLeftHandIKWhenBlocked', 'Vehicle', 'EnforceAimingRestrictions',
    'ForceEjectShellAfterFiring', 'NonViolent', 'NonLethal', 'Scary',
    'AllowCloseQuarterKills', 'DisablePlayerBlockingInMP', 'StaticReticulePosition',
    'CanPerformArrest', 'AllowMeleeIntroAnim', 'ManualDetonation',
    'SuppressGunshotEvent', 'HiddenFromWeaponWheel',
    'AllowDriverLockOnToAmbientPeds', 'NeedsGunCockingInCover', 'ThrowOnly',
    'NoAutoRunWhenFiring', 'DisableIdleVariations', 'HasLowCoverReloads',
    'HasLowCoverSwaps', 'DontBreakRopes', 'CookWhileAiming',
    'UseLeftHandIkWhenAiming', 'DropWhenCooked', 'NotAWeapon',
    'RemoveEarlyWhenEnteringVehicles', 'DontBlendFireOutro',
    'DiscardWhenOutOfAmmo', 'DelayedFiringAfterAutoSwap',
    'EnforceFiringAngularThreshold', 'ForcesActionMode',
    'CreatesAPotentialExplosionEventWhenFired', 'CreateBulletExplosionWhenOutOfTime',
    'DelayedFiringAfterAutoSwapPreviousWeapon', 'DisableCombatRoll',
    'NoWheelStats', 'ProcessGripAnim', 'DisableStealth',
    'DangerousLookingMeleeWeapon', 'QuitTransitionToIdleIntroOnWeaponChange',
    'DisableLeftHandIkWhenOnFoot', 'IgnoreHelmets', 'Rpg', 'NoAmmoDisplay',
    'TorsoIKForWeaponBlock', 'LongWeapon', 'AssistedAimVehicleWeapon',
    'CanBlowUpVehicleAtZeroBodyHealth', 'IgnoreAnimReloadRateModifiers',
    'DisableIdleAnimationFilter', 'HomingToggle', 'ApplyVehicleDamageToEngine',
    'Turret', 'DisableAimAngleChecksForReticule',
    'AllowMovementDuringFirstPersonScope', 'DriveByMPOnly',
    'CreateWeaponWithNoModel', 'RemoveWhenUnequipped', 'BlockAmbientIdles',
    'NotUnarmed', 'UseFPSAimIK', 'DisableFPSScope', 'DisableFPSAimForScope',
    'EnableFPSRNGOnly', 'EnableFPSIdleOnly', 'MeleeHatchet',
    'UseAlternateFPDrivebyClipset', 'AttachFPSLeftHandIKToRight',
    'OnlyUseAimingInfoInFPS', 'UseFPSAnimatedRecoil', 'UseFPSSecondaryMotion',
    'HasFPSProjectileWeaponAnims', 'AllowMeleeBlock', 'DontPlayDryFireAnim',
    'SwapToUnarmedWhenOutOfThrownAmmo', 'PlayOutOfAmmoAnim',
    'DisableIdleAnimationFilterWhenReloading', 'OnFootHoming',
    'DamageCausesDisputes', 'UsePlaneExplosionDamageCapInMP',
    'FPSOnlyExitFireAnimAfterRecoilEnds', 'SkipVehiclePetrolTankDamage',
    'DontAutoSwapOnPickUp', 'DisableTorsoIKAboveAngleThreshold', 'MeleeFist',
    'NotAllowedForDriveby', 'AttachReloadObjectToRightHand',
    'CanBeAimedLikeGunWithoutFiring', 'MeleeMachete', 'HideReticule',
    'UseHolsterAnimation', 'BlockFirstPersonStateTransitionWhileFiring',
    'ForceFullFireAnimation', 'DisableLeftHandIkInDriveby', 'CanUseInVehMelee',
    'UseVehicleWeaponBoneForward', 'UseManualTargetingMode',
    'IgnoreTracerVfxMuzzleDirectionCheck', 'IgnoreHomingCloseThresholdCheck',
    'LockOnRequiresAim', 'DisableCameraPullAround', 'VehicleChargedLaunch',
    'ForcePedAsFiringEntity', 'FiringEntityIgnoresExplosionDamage',
)


def print_weapon_flags() -> None:
    print(f'WeaponFlags conocidas: {len(KNOWN_WEAPON_FLAGS)}\n')
    for flag in KNOWN_WEAPON_FLAGS:
        marker = '  <- casco' if flag in {'IgnoreHelmets', 'ArmourPenetrating'} else ''
        print(f'- {flag}{marker}')
