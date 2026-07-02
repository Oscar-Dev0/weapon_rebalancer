# Referencia de perfiles V5

## Orden de precedencia

1. Preset interno.
2. `defaults.fields`.
3. `groups.<GROUP>.fields`.
4. Config local por carpeta.
5. `weapons.<WEAPON>.fields`.
6. Política final de headshot.
7. Política de armas inofensivas.
8. Límites de seguridad.

Los scopes `defaults`, `groups` y `weapons` aceptan:

```json
{
  "fields": {},
  "meta": {},
  "weapon_flags": {
    "add": [],
    "remove": [],
    "create_if_missing": false
  },
  "headshot": {}
}
```

## Opciones de `headshot`

| Opción | Tipo | Función |
|---|---:|---|
| `mode` | string | `off`, `normal`, `onetap`. |
| `multiplier` | number | Aplica a jugador, red y NPC. |
| `player_multiplier` | number | Override local. |
| `network_multiplier` | number | Override de red. |
| `ai_multiplier` | number | Override para NPC. |
| `distance` | number | Distancia máxima del headshot. |
| `no_falloff` | boolean | Fuerza falloff `1.0` dentro de la distancia. |
| `sync_weapon_range` | boolean | Amplía `WeaponRange` cuando es menor. |
| `sync_lock_on_range` | boolean | Sincroniza lock-on. |
| `bypass_helmets` | boolean | Agrega la política META de casco. |
| `helmet_multiplier` | number | Piso de `LightlyArmouredDamageModifier`. V4 recomienda `1.0`, no `100.0`. |
| `force_penetration` | boolean | Fuerza `Penetration`. |
| `penetration` | number | Valor mínimo de penetración. |
| `add_ignore_helmets_flag` | boolean | Agrega `IgnoreHelmets`. |
| `add_armour_penetrating_flag` | boolean | Agrega `ArmourPenetrating`. |
| `target_effective_health` | number | Vida+armadura que debe superar el contrato. |
| `safety_margin` | number | Margen sobre el objetivo. |
| `minimum_base_damage` | number | Piso absoluto de daño base. |
| `auto_minimum_base_damage` | boolean | Calcula el piso necesario. |
| `repair_zero_network_modifier` | boolean | Repara modificador de red en cero. |
| `network_player_modifier_fallback` | number | Fallback de red. |
| `remove_nonlethal_flags` | boolean | Quita flags incompatibles. |
| `blocking_flags` | array | Flags que deben eliminarse. |

## Dependencia runtime

`mode = "onetap"` requiere que el ped acepte críticos. Ningún valor JSON puede anular en ejecución:

```lua
SetPedSuffersCriticalHits(PlayerPedId(), false)
```

Usa `--audit-runtime` para encontrarlo y `extras/os_headshot_guard` como compatibilidad temporal.

## Configuración por arma

```json
"weapons": {
  "WEAPON_CUSTOM_REVOLVER": {
    "fields": {
      "damage": 100.0,
      "weapon_range": 180.0,
      "time_between_shots": 0.45
    },
    "headshot": {
      "mode": "onetap",
      "distance": 180.0,
      "target_effective_health": 1000.0,
      "helmet_multiplier": 1.0
    },
    "weapon_flags": {
      "add": ["CanFreeAim"],
      "remove": [],
      "create_if_missing": true
    }
  }
}
```

## Config local por recurso

Puedes colocar `weapon_rebalance.json`, `weapon_balance.json`, `rebalance.json` o `.weapon_rebalance.json` dentro de una carpeta. Solo afecta los META debajo de esa carpeta.

## Restauración desde backup

```json
"restore": {
  "from_backup": true,
  "backup_suffix": ".bak"
}
```

Con `from_backup=true`, cada bloque se calcula desde `weapons.meta.bak`. El archivo actual solo se usa cuando el backup no existe o no contiene esa arma. Esto hace que ejecutar el perfil varias veces no acumule el multiplicador.

## Clasificación oficial/custom

```json
"weapon_classification": {
  "official_catalog": "cfx_weapon_models_2026_07_02",
  "official_additions": [],
  "official_removals": [],
  "custom_when_not_official": true,
  "custom": {
    "groups": ["GROUP_PISTOL", "GROUP_SMG", "GROUP_RIFLE"],
    "field_multipliers": {
      "damage": 1.15,
      "weapon_range": 1.15
    },
    "group_field_multipliers": {}
  }
}
```

Los multiplicadores usan el valor encontrado en el bloque original. Un arma oficial no recibe esta capa. `official_additions` sirve para declarar como oficial una variante local que no esté en el catálogo; `official_removals` permite tratar una entrada como custom.

`allow_ignored_weapons` elimina armas de la lista interna de exclusión para que el perfil pueda restaurarlas expresamente:

```json
"allow_ignored_weapons": ["WEAPON_RPG", "WEAPON_RAILGUN"]
```

## Reglas por familia

```json
"family_rules": [
  {
    "name": "revolver_torso",
    "contains": ["REVOLVER", "DOUBLEACTION"],
    "groups": ["GROUP_PISTOL"],
    "fields": {
      "damage": 350.0,
      "hit_limbs": 0.25
    }
  }
]
```

Una regla puede incluir `fields`, `field_multipliers`, `official_only` o `custom_only`. Los valores absolutos de `fields` se aplican después de los multiplicadores.

## V6: `baseline_repair`

```json
{
  "baseline_repair": {
    "enabled": true,
    "reference_roots": [],
    "repair_zero_or_missing": true,
    "repair_invalid_network_modifiers": true,
    "repair_disabled_headshots": true,
    "repair_invalid_ranges": true,
    "minimum_valid_damage": 0.01,
    "excluded_weapons": ["WEAPON_STUNGUN"],
    "official_values": {
      "WEAPON_PISTOL": {"damage": 26.0}
    },
    "group_fallbacks": {
      "GROUP_PISTOL": {
        "damage": 27.0,
        "weapon_range": 120.0,
        "headshot_player": 18.0,
        "network_headshot": 1.0
      }
    }
  }
}
```

La prioridad es: referencia exacta para oficial → valor válido del META → fallback de grupo únicamente cuando el valor está roto. El multiplicador custom se ejecuta después.

También puedes pasar una o más rutas por CLI:

```powershell
python run_rebalance.py --reference-root "references\snags_original\metas" ...
```
