# Migración de perfiles 2026-10-12_v8

Informe generado por `weapon_rebalancer/profile_store/legacy_migration.py`. Los archivos originales están intactos en `profiles/legacy/` y en `data/backups/`. Cada resultado se verificó ejecutando el motor sobre el pack real.

## Destino de cada perfil antiguo

| Perfil antiguo | Destino | Motivo |
| --- | --- | --- |
| `flow_caribe` | **flow_custom** | Sin cambios de comportamiento |
| `full_meta_template` | archivado | Plantilla de ejemplo (WEAPON_EXAMPLE); la reemplazan el Constructor y los perfiles derivados. |
| `head_only` | pendiente `legacy_head_only` (hereda de realistic) | Configuración única conservada sin cambios (también cubre headshot_focus_onetap, headshot_focus_real_onetap_v4) |
| `headshot_focus_onetap` | archivado | Equivalente exacto de head_only (se conserva como pendiente “head_only”). |
| `headshot_focus_real_onetap_v4` | archivado | Equivalente exacto de head_only (se conserva como pendiente “head_only”). |
| `no_body_or_head_damage` | pendiente `legacy_no_body_or_head_damage` (hereda de balanced) | Configuración única conservada sin cambios |
| `original_body_real_onetap` | pendiente `legacy_original_body_real_onetap` (hereda de competitive) | Configuración única conservada sin cambios (también cubre original_body_real_onetap_v4) |
| `original_body_real_onetap_v4` | archivado | Equivalente exacto de original_body_real_onetap (se conserva como pendiente “original_body_real_onetap”). |
| `profile_template` | archivado | Plantilla de ejemplo (WEAPON_EXAMPLE); la reemplazan el Constructor y los perfiles derivados. |
| `pvp_competitive_onetap` | **competitive** | Sin cambios de comportamiento |
| `pvp_hardcore_onetap` | pendiente `legacy_pvp_hardcore_onetap` (hereda de competitive) | Configuración única conservada sin cambios |
| `pvp_no_tank` | archivado | Equivalente exacto de pvp_competitive_onetap → competitive. |
| `rebelion_balanced_v3` | pendiente `legacy_rebelion_balanced_v3` (hereda de competitive) | Configuración única conservada sin cambios (también cubre rebelion_real_onetap_v4, rebelion_server) |
| `rebelion_real_onetap_v4` | archivado | Equivalente exacto de rebelion_balanced_v3 (se conserva como pendiente “rebelion_balanced_v3”). |
| `rebelion_server` | archivado | Equivalente exacto de rebelion_balanced_v3 (se conserva como pendiente “rebelion_balanced_v3”). |
| `rp_serious_onetap` | **realistic** | modules.recoil: normal → high (retroceso más exigente). |
| `vanilla_normal_custom_plus15_revolver_onetap` | pendiente `legacy_vanilla_normal_custom_plus15_revolver_onetap` (hereda de balanced) | Configuración única conservada sin cambios |
| `vanilla_repair_custom_plus15_absolute_v6` | **balanced** | Multiplicadores para armas personalizadas {'damage': 1.15, 'weapon_range': 1.15, 'falloff_min': 1.15, 'falloff_max': 1.15, 'max_headshot_player': 1.15, 'max_headshot_ai': 1.15} → 1.0 (sin ventaja para custom).; Regla de familia retirada: ['revolver_one_shot_torso'] (revólver/doble acción a 350 de daño, decisión de otro servidor). |

> `rebelion_balanced_v3` y `rebelion_real_onetap_v4` se habían quitado de la carpeta el 2026-10-12 22:30 (fuera de la herramienta). Se recuperaron de git **solo en `profiles/legacy/`** (archivo de solo lectura, no son perfiles activos) para conservar el inventario y las pruebas del motor.

## Verificaciones

| Perfil | Comprobación | Resultado |
| --- | --- | --- |
| flow_custom | Configuración del motor idéntica a la fuente (fuente `flow_caribe`) | ✔ |
| competitive | Resultado en el pack idéntico a la fuente (fuente `pvp_competitive_onetap`) | ✔ |
| realistic | Solo difiere en los 4 campos de recoil (fuente `rp_serious_onetap`) | ✔ · 197 armas, campos recoil_accuracy_max, recoil_error_time, recoil_recovery_rate, recoil_shake_amplitude |
| balanced | Solo difiere en los cambios documentados (fuente `vanilla_repair_custom_plus15_absolute_v6`) | ✔ · 108 armas, campos damage, falloff_max, falloff_min, falloff_modifier, hit_limbs, lightly_armoured, max_headshot_ai, max_headshot_player, network_hit_limbs, weapon_range |
| pendientes | Configuración del motor idéntica a cada fuente | ✔ |

## Cambios de diseño en los oficiales

### balanced
Fuente: `vanilla_repair_custom_plus15_absolute_v6`

- Multiplicadores para armas personalizadas {'damage': 1.15, 'weapon_range': 1.15, 'falloff_min': 1.15, 'falloff_max': 1.15, 'max_headshot_player': 1.15, 'max_headshot_ai': 1.15} → 1.0 (sin ventaja para custom).
- Regla de familia retirada: ['revolver_one_shot_torso'] (revólver/doble acción a 350 de daño, decisión de otro servidor).

### realistic
Fuente: `rp_serious_onetap`

- modules.recoil: normal → high (retroceso más exigente).
- Se quitaron 60 valores por categoría que el motor descartaba o reescribía siempre (los pisa el preset del módulo o la política de cabeza one-tap). No cambian el resultado.

### competitive
Fuente: `pvp_competitive_onetap` · hereda de `realistic`

- Ninguno: comportamiento idéntico.
- Se quitaron 60 valores por categoría que el motor descartaba o reescribía siempre (los pisa el preset del módulo o la política de cabeza one-tap). No cambian el resultado.

### flow_custom
Fuente: `flow_caribe` · hereda de `competitive`

- Ninguno: comportamiento idéntico.
- Descartado `validation.require_runtime_critical_hits`: el motor no lo lee (no tenía efecto).
- Guarda solo sus diferencias: 20454 bytes frente a 21139 del original.

## Inventario de los perfiles antiguos

| Perfil | schema | Grupos | Armas | Campos sin efecto | Módulos |
| --- | --- | --- | --- | --- | --- |
| `flow_caribe` | 3 | 6 | 26 | 0 | damage=configured, armour=configured, recoil=configured, accuracy=configured, range=configured, fire_rate=original, reload=original, headshot=normal |
| `full_meta_template` | 3 | 1 | 1 | 6 | damage=configured, armour=configured, recoil=configured, accuracy=configured, range=configured, fire_rate=configured, reload=configured, headshot=onetap |
| `head_only` | 3 | 6 | 0 | 60 | damage=head_only, armour=normal, recoil=normal, accuracy=normal, range=configured, fire_rate=configured, reload=original, headshot=onetap |
| `headshot_focus_onetap` | 3 | 6 | 0 | 60 | damage=head_only, armour=normal, recoil=normal, accuracy=normal, range=configured, fire_rate=configured, reload=original, headshot=onetap |
| `headshot_focus_real_onetap_v4` | 4 | 6 | 0 | 60 | damage=head_only, armour=normal, recoil=normal, accuracy=normal, range=configured, fire_rate=configured, reload=original, headshot=onetap |
| `no_body_or_head_damage` | 3 | 0 | 0 | 0 | damage=none, armour=none, recoil=original, accuracy=original, range=original, fire_rate=original, reload=original, headshot=off |
| `original_body_real_onetap` | 3 | 6 | 0 | 0 | damage=original, armour=original, recoil=original, accuracy=original, range=original, fire_rate=original, reload=original, headshot=onetap |
| `original_body_real_onetap_v4` | 4 | 6 | 0 | 0 | damage=original, armour=original, recoil=original, accuracy=original, range=original, fire_rate=original, reload=original, headshot=onetap |
| `profile_template` | 3 | 1 | 1 | 3 | damage=configured, armour=configured, recoil=configured, accuracy=configured, range=configured, fire_rate=configured, reload=original, headshot=onetap |
| `pvp_competitive_onetap` | 3 | 6 | 0 | 60 | damage=configured, armour=normal, recoil=low, accuracy=high, range=configured, fire_rate=configured, reload=original, headshot=onetap |
| `pvp_hardcore_onetap` | 3 | 6 | 0 | 60 | damage=configured, armour=piercing, recoil=low, accuracy=high, range=configured, fire_rate=configured, reload=fast, headshot=onetap |
| `pvp_no_tank` | 3 | 6 | 0 | 60 | damage=configured, armour=normal, recoil=low, accuracy=high, range=configured, fire_rate=configured, reload=original, headshot=onetap |
| `rebelion_balanced_v3` | 3 | 6 | 0 | 18 | damage=configured, armour=configured, recoil=configured, accuracy=configured, range=configured, fire_rate=configured, reload=original, headshot=onetap |
| `rebelion_real_onetap_v4` | 4 | 6 | 0 | 18 | damage=configured, armour=configured, recoil=configured, accuracy=configured, range=configured, fire_rate=configured, reload=original, headshot=onetap |
| `rebelion_server` | 3 | 6 | 0 | 18 | damage=configured, armour=configured, recoil=configured, accuracy=configured, range=configured, fire_rate=configured, reload=original, headshot=onetap |
| `rp_serious_onetap` | 3 | 6 | 0 | 60 | damage=configured, armour=normal, recoil=normal, accuracy=normal, range=configured, fire_rate=configured, reload=original, headshot=onetap |
| `vanilla_normal_custom_plus15_revolver_onetap` | 5 | 0 | 0 | 0 | damage=original, armour=original, recoil=original, accuracy=original, range=original, fire_rate=original, reload=original, headshot=original |
| `vanilla_repair_custom_plus15_absolute_v6` | 7 | 0 | 0 | 0 | damage=original, armour=original, recoil=original, accuracy=original, range=original, fire_rate=original, reload=original, headshot=original |

## Pendientes de revisión

Están en `pending/`. Son deltas sobre un perfil oficial que reproducen exactamente su perfil antiguo. Para usar uno: `python3 wr.py profile import profiles/migrations/2026-10-12_v8/pending/<archivo>.json --id <nuevo_id>`.

