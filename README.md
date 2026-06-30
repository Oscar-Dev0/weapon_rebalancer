# Weapon Rebalancer META V3

Requiere **Python 3.10 o superior**.

Herramienta offline para analizar y modificar `weapons.meta` de FiveM/GTA V sin añadir loops Lua, antitank, base de datos ni estados en ejecución.

La V3 separa dos objetivos:

1. **One-tap real a cabeza por META**, incluyendo cascos nativos.
2. **Balance corporal configurable**, con perfiles distintos para RP y PvP.

## Inicio rápido

Validar perfiles y ejecutar pruebas:

```powershell
python run_rebalance.py --validate-profiles profiles
python -m unittest discover -s tests -v
```

Vista previa recomendada para Rebelion:

```powershell
python run_rebalance.py `
  --root "C:\TxData\rebelion\resources\[Streaming]\[PackArmas]" `
  --profile "profiles\rebelion_balanced_v3.json" `
  --report "reports\rebelion_preview.json" `
  --strict-onetap-audit
```

Aplicar cambios:

```powershell
python run_rebalance.py `
  --root "C:\TxData\rebelion\resources\[Streaming]\[PackArmas]" `
  --profile "profiles\rebelion_balanced_v3.json" `
  --write `
  --report "reports\rebelion_apply.json" `
  --strict-onetap-audit
```

Antes de modificar cada archivo se crea una copia `.meta.bak` o `.bak`, según la ruta original.

## Qué fuerza el one-tap

Cuando una arma queda en modo `onetap`, el motor V3:

- establece los multiplicadores de cabeza de jugador, red y NPC;
- sincroniza la distancia máxima de cabeza por grupo o arma;
- controla el falloff dentro de la distancia configurada;
- fuerza `LightlyArmouredDamageModifier` para cascos nativos;
- fuerza `Penetration`;
- agrega `IgnoreHelmets` y `ArmourPenetrating` sin borrar las demás `WeaponFlags`;
- elimina `NonLethal` y `NonViolent` únicamente en armas de fuego configuradas como letales;
- repara `NetworkPlayerDamageModifier=0`;
- calcula un piso mínimo de `Damage` para evitar el clásico `0 × 1500 = 0`;
- audita el resultado final generado, no solo la configuración solicitada.

El piso automático se calcula así:

```text
vida_objetivo × margen_seguridad
─────────────────────────────────
multiplicador_red × modificador_red
```

Con los valores predeterminados, el objetivo es superar **400 puntos efectivos** con un margen de **1.25**, es decir, al menos **500 puntos estimados** en la ruta de red.

## Perfiles incluidos

| Perfil | Uso recomendado |
|---|---|
| `rebelion_balanced_v3.json` | Rebelion: pistola 2 al torso, rifle 5, cabeza one-tap. |
| `rp_serious_onetap.json` | RP táctico con TTK corporal largo y recoil natural. |
| `pvp_competitive_onetap.json` | PvP competitivo con 3–5 impactos corporales. |
| `pvp_hardcore_onetap.json` | PvP agresivo con 2–4 impactos corporales. |
| `headshot_focus_onetap.json` | Cuerpo casi sin daño; la cabeza decide el combate. |
| `original_body_real_onetap.json` | Conserva el daño corporal original y corrige el headshot. |
| `no_body_or_head_damage.json` | Daño completamente desactivado. |

Lista desde CLI:

```powershell
python run_rebalance.py --list-profiles
```

## Distancia one-tap por grupo

La distancia ya no es obligatoriamente global. Ejemplo:

```json
"groups": {
  "GROUP_PISTOL": {
    "fields": {
      "damage": 67.0,
      "weapon_range": 130.0
    },
    "headshot": {
      "mode": "onetap",
      "distance": 130.0
    }
  },
  "GROUP_SHOTGUN": {
    "fields": {
      "damage": 36.0,
      "weapon_range": 30.0
    },
    "headshot": {
      "mode": "onetap",
      "distance": 30.0
    }
  }
}
```

Así una escopeta no hereda accidentalmente los 300–600 metros de un rifle o francotirador.

## Diferencia entre `original` y `configured`

- `original`: no toca los tags XML de ese módulo.
- `configured`: aplica exactamente los valores escritos en `defaults`, `groups` o `weapons`.
- perfiles como `low`, `normal`, `high`, `fast`, etc.: aplican overlays predefinidos.

Ejemplo:

```json
"modules": {
  "damage": "configured",
  "armour": "max",
  "recoil": "configured",
  "accuracy": "configured",
  "range": "configured",
  "fire_rate": "configured",
  "reload": "original",
  "headshot": "onetap"
}
```

Valores disponibles:

| Módulo | Valores |
|---|---|
| `damage` | `original`, `configured`, `none`, `head_only`, `low`, `normal`, `high`, `lethal` |
| `armour` | `original`, `configured`, `none`, `normal`, `piercing`, `max` |
| `recoil` | `original`, `configured`, `none`, `low`, `normal`, `high` |
| `accuracy` | `original`, `configured`, `laser`, `high`, `normal`, `low` |
| `range` | `original`, `configured`, `short`, `normal`, `long`, `very_long` |
| `fire_rate` | `original`, `configured`, `slow`, `normal`, `fast`, `very_fast` |
| `reload` | `original`, `configured`, `slow`, `normal`, `fast`, `very_fast` |
| `headshot` | `original`, `off`, `normal`, `onetap` |

## Auditoría automática

Cada ejecución detecta:

- definiciones `WEAPON_*` duplicadas en varios META o repetidas en el mismo archivo;
- META sin un `data_file 'WEAPONINFO_FILE...'` visible en su manifest más cercano;
- daño base cero;
- modificador de red cero;
- multiplicadores de cabeza ausentes o en cero;
- distancia de cabeza o falloff insuficientes;
- protección de casco insuficiente;
- flags `IgnoreHelmets` o `ArmourPenetrating` ausentes;
- flags no letales que contradicen el perfil;
- daño estimado menor que la vida efectiva objetivo.

Usa `--strict-onetap-audit` para devolver error cuando una arma no pase la auditoría.

## Modificación META completa

El catálogo incluye **133 campos estándar de `CWeaponInfo`** y **146 `WeaponFlags` conocidas**.

```powershell
python run_rebalance.py --list-fields
python run_rebalance.py --list-flags
```

Para tags custom no catalogados:

```json
"meta": {
  "CustomScalarTag": {
    "kind": "value_attr",
    "value": 9.5,
    "create_if_missing": false
  },
  "CustomVector": {
    "attributes": {
      "x": 1.0,
      "y": 2.0,
      "z": 3.0
    }
  }
}
```

## Exportar todo el pack

```powershell
python run_rebalance.py `
  --root "C:\RUTA\[PackArmas]" `
  --export-meta "exports\meta_inventory.json" `
  --export-full-profile "exports\perfil_pack_completo.json" `
  --export-only
```

- `meta_inventory.json`: hojas, atributos, rutas XML y catálogo de tags.
- `perfil_pack_completo.json`: perfil reutilizable de todas las armas encontradas.

## Armas inofensivas

Estas armas se fuerzan a daño cero al final, incluso bajo perfiles letales:

```json
"harmless_weapons": [
  "WEAPON_SNOWBALL",
  "WEAPON_BALL"
]
```

## Límite honesto del META

Esta herramienta corrige la ruta disponible en `weapons.meta`. No puede contradecir un recurso externo que, en ejecución:

- llame `SetPedSuffersCriticalHits(ped, false)`;
- cancele `CEventNetworkEntityDamage`;
- restaure vida o armadura después del impacto;
- implemente un casco custom fuera del sistema nativo;
- cargue después otra definición duplicada del mismo `WEAPON_*`.

La V3 reporta los problemas de carga y duplicados que sí puede detectar, sin instalar un script que pelee cada frame contra otros recursos.

Consulta `docs/ONE_TAP_TROUBLESHOOTING.md` cuando el reporte diga `ONETAP OK` pero el comportamiento dentro del servidor siga siendo distinto.
