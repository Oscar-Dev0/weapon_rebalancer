# Referencia de perfiles V3

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
| `player_multiplier` | number | Override solo para jugador. |
| `network_multiplier` | number | Override de red. |
| `ai_multiplier` | number | Override para NPC. |
| `distance` | number | Distancia máxima del headshot. |
| `no_falloff` | boolean | Fuerza falloff 1.0 dentro de la distancia. |
| `sync_weapon_range` | boolean | Amplía `WeaponRange` si es menor. Nunca lo reduce. |
| `sync_lock_on_range` | boolean | Sincroniza lock-on; desactivado por defecto. |
| `bypass_helmets` | boolean | Activa ruta META contra casco. |
| `helmet_multiplier` | number | `LightlyArmouredDamageModifier`. |
| `force_penetration` | boolean | Fuerza `Penetration`. |
| `penetration` | number | Valor mínimo de penetración. |
| `target_effective_health` | number | Vida+armadura que debe superar. |
| `safety_margin` | number | Margen sobre el objetivo. |
| `minimum_base_damage` | number | Piso absoluto de daño base. |
| `auto_minimum_base_damage` | boolean | Calcula el piso necesario. |
| `repair_zero_network_modifier` | boolean | Repara modificador de red en cero. |
| `network_player_modifier_fallback` | number | Fallback de red. |
| `remove_nonlethal_flags` | boolean | Quita flags incompatibles. |
| `blocking_flags` | array | Flags que deben eliminarse. |

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
      "target_effective_health": 500.0
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
