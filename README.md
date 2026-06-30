# Weapon Rebalancer META — perfiles externos

Herramienta para modificar `weapons.meta` sin recursos FiveM, sin Lua, sin base de datos, sin KVP y sin guardar estados en ejecución.

## Uso rápido

Primero ejecuta en modo prueba:

```powershell
python run_rebalance.py --root "C:\TxData\rebelion\resources\[Streaming]\[PackArmas]" --profile profiles\rebelion_server.json
```

Cuando el resumen sea correcto, escribe los cambios:

```powershell
python run_rebalance.py --root "C:\TxData\rebelion\resources\[Streaming]\[PackArmas]" --profile profiles\rebelion_server.json --write
```

El programa crea `.bak` antes de modificar cada META.

---

## Perfiles incluidos

### 1. `profiles/rebelion_server.json`

Perfil principal de Rebelion Server:

- Pistolas: aproximadamente **2 impactos al torso** con 200 HP base.
- Rifles: aproximadamente **5 impactos al torso** con 200 HP base.
- Escopetas: **1 disparo al pecho a muy corta distancia**, dependiendo de cuántos perdigones conecten.
- Headshot: multiplicador de jugador, red y NPC en `1500.0`.
- One tap contra casco nativo: `LightlyArmouredDamageModifier = 100.0` y `Penetration = 1.0` configurables.
- Recoil bajo.
- Precisión normal.
- Headshot sin caída de daño dentro del rango configurado.

Comando:

```powershell
python run_rebalance.py --root "C:\RUTA\[PackArmas]" --profile profiles\rebelion_server.json --write
```

### 2. `profiles/pvp_no_tank.json`

Perfil PvP más agresivo:

- Penetración META máxima configurada.
- Headshot `1500x`.
- Precisión alta.
- Recoil bajo.
- Menor caída de daño en pistolas, SMG, rifles y MG.
- Escopeta letal únicamente cerca.

```powershell
python run_rebalance.py --root "C:\RUTA\[PackArmas]" --profile profiles\pvp_no_tank.json --write
```

### 3. `profiles/head_only.json`

Daño corporal casi nulo y cabeza letal:

- Cuerpo: `0.2`.
- Extremidades: `0.0`.
- Vehículos: `0.0`.
- Cabeza: `1500x`.

No se usa daño base `0.0`, porque en GTA el headshot multiplica el daño base: `0 × 1500 = 0`.

### 4. `profiles/no_body_or_head_damage.json`

Daño absolutamente nulo. También desactiva el daño de cabeza.

---

## Todo se modifica desde JSON

No necesitas editar archivos Python. Cada perfil acepta estas secciones:

```json
{
  "name": "Mi perfil",
  "base_preset": "rp_balanced",
  "modules": {
    "damage": "normal",
    "armour": "max",
    "recoil": "low",
    "accuracy": "normal",
    "range": "normal",
    "fire_rate": "original",
    "reload": "original",
    "headshot": "onetap"
  },
  "headshot": {
    "mode": "onetap",
    "multiplier": 1500.0,
    "distance": 300.0,
    "no_falloff": true,
    "create_missing_tags": true
  },
  "groups": {},
  "weapons": {},
  "ignore_weapons": []
}
```

### Valores formales por módulo

| Módulo | Valores disponibles |
|---|---|
| `damage` | `original`, `none`, `head_only`, `low`, `normal`, `high`, `lethal` |
| `armour` | `original`, `none`, `normal`, `piercing`, `max` |
| `recoil` | `original`, `none`, `low`, `normal`, `high` |
| `accuracy` | `original`, `laser`, `high`, `normal`, `low` |
| `range` | `original`, `short`, `normal`, `long`, `very_long` |
| `fire_rate` | `original`, `slow`, `normal`, `fast`, `very_fast` |
| `reload` | `original`, `slow`, `normal`, `fast`, `very_fast` |
| `headshot` | `original`, `off`, `normal`, `onetap` |

`original` significa que el programa no toca los tags de esa sección.

---

## Valores por familia de arma

Dentro de `groups` puedes configurar:

- `GROUP_PISTOL`
- `GROUP_SMG`
- `GROUP_RIFLE`
- `GROUP_MG`
- `GROUP_SHOTGUN`
- `GROUP_SNIPER`
- `GROUP_MELEE`

Ejemplo personalizado:

```json
"GROUP_PISTOL": {
  "damage": 100.0,
  "weapon_range": 115.0,
  "falloff_min": 85.0,
  "falloff_max": 115.0,
  "falloff_modifier": 0.72,
  "hit_limbs": 0.55,
  "network_hit_limbs": 0.55,
  "lightly_armoured": 2.0,
  "vehicle_damage_modifier": 0.20,
  "time_between_shots": 0.18
}
```

## Override por arma exacta

```json
"weapons": {
  "WEAPON_PISTOL": {
    "damage": 90.0,
    "recoil_accuracy_max": 0.20
  },
  "WEAPON_REVOLVER": {
    "damage": 120.0,
    "weapon_range": 165.0
  }
}
```

Los overrides exactos se aplican después del grupo.

---

## Campos META soportados

Daño y cuerpo:

- `Damage`
- `HitLimbsDamageModifier`
- `NetworkHitLimbsDamageModifier`
- `LightlyArmouredDamageModifier`
- `VehicleDamageModifier`

Headshot:

- `HeadShotDamageModifierPlayer`
- `NetworkHeadShotPlayerDamageModifier`
- `HeadShotDamageModifierAI`
- distancias mínimas y máximas de headshot

Manejo:

- recoil
- dispersión
- precisión corriendo
- precisión apuntando
- cadencia
- recarga
- alcance
- caída de daño
- lock-on cuando exista

Consulta la lista completa:

```powershell
python run_rebalance.py --list-fields
```

---

## Límite real de “no tanqueable” usando solo META

`LightlyArmouredDamageModifier`, los multiplicadores de headshot y `Penetration` cubren la ruta META de cascos nativos. Los perfiles one tap incluidos fuerzan estos campos al final para que los overrides de grupo no los vuelvan a bajar. No existe, sin embargo, un tag universal en `weapons.meta` que pueda contradecir un script externo que desactive críticos o cancele daño.

Si otro recurso cancela daño, desactiva críticos, restaura vida/armor o implementa un casco personalizado, ese comportamiento ocurre después o fuera del META. Este paquete no incluye scripts por decisión de diseño.

Los conteos de impactos son objetivos de balance sobre 200 HP estándar. Pueden variar por:

- armor adicional;
- health modificado;
- distancia y falloff;
- cantidad de perdigones de escopeta;
- multiplicadores de otros recursos;
- flags propios de armas custom.

---

## Recomendación de trabajo

1. Haz una copia del pack.
2. Ejecuta sin `--write`.
3. Revisa armas detectadas y campos faltantes.
4. Ejecuta con `--write`.
5. Reinicia el recurso o el servidor.
6. Prueba sin armor, con armor y a varias distancias.

---

## Armas inofensivas protegidas

Los perfiles incluyen una protección final para armas recreativas. Aunque uses `rebelion_server`, `pvp_no_tank`, daño letal o headshot `1500x`, estas armas se fuerzan a daño cero:

```json
"harmless_weapons": [
  "WEAPON_SNOWBALL",
  "WEAPON_BALL"
]
```

La protección deja en `0.0`:

- daño base;
- daño de cabeza de jugador, red y NPC;
- daño a extremidades;
- modificador contra armadura;
- daño a vehículos;
- caída de daño ofensiva.

Puedes agregar cualquier arma custom inofensiva sin tocar Python:

```json
"harmless_weapons": [
  "WEAPON_SNOWBALL",
  "WEAPON_BALL",
  "WEAPON_MI_OBJETO_CUSTOM"
]
```

Si excepcionalmente quieres devolverle daño a una de las protegidas por defecto:

```json
"allow_damage_weapons": [
  "WEAPON_BALL"
]
```

`harmless_weapons` se aplica al final, por lo que tiene prioridad sobre módulos, grupos y overrides por arma.

---

## Escaneo obligatorio de armas inofensivas

Las armas incluidas en `harmless_weapons` se buscan en **todos los archivos `.meta` detectados**.
La corrección tiene prioridad sobre:

- el perfil activo;
- grupos desconocidos (`UNKNOWN`);
- filtros `--only` y `--weapontype`;
- `ignore_weapons`;
- configuraciones locales por carpeta;
- overrides letales por arma.

Cuando encuentra `WEAPON_SNOWBALL` o `WEAPON_BALL`, revisa su bloque `CWeaponInfo`. Si cualquiera de sus modificadores ofensivos tiene daño, lo reemplaza por `0.0` al ejecutar con `--write`.

Campos limpiados:

```text
Damage
HitLimbsDamageModifier
NetworkHitLimbsDamageModifier
LightlyArmouredDamageModifier
VehicleDamageModifier
HeadShotDamageModifierPlayer
NetworkHeadShotPlayerDamageModifier
HeadShotDamageModifierAI
MinHeadShotDistancePlayer
MaxHeadShotDistancePlayer
MinHeadShotDistanceAI
MaxHeadShotDistanceAI
DamageFallOffModifier
```

Prueba primero sin escribir:

```powershell
python run_rebalance.py --root "C:\RUTA\[PackArmas]" --profile profiles\rebelion_server.json
```

Después aplica la limpieza real:

```powershell
python run_rebalance.py --root "C:\RUTA\[PackArmas]" --profile profiles\rebelion_server.json --write
```

En el reporte aparecerá la razón:

```text
harmless_weapon_damage_forced_to_zero
```

---

## One tap contra cascos nativos por META

Los perfiles `rebelion_server.json`, `pvp_no_tank.json` y `head_only.json` incluyen ahora una política específica para cascos:

```json
"headshot": {
  "mode": "onetap",
  "multiplier": 1500.0,
  "distance": 300.0,
  "no_falloff": true,
  "create_missing_tags": true,
  "bypass_helmets": true,
  "helmet_multiplier": 100.0,
  "force_penetration": true,
  "penetration": 1.0,
  "create_missing_armour_tag": true,
  "create_missing_penetration_tag": true
}
```

Cuando `mode` es `onetap` y `bypass_helmets` está activo, el generador fuerza al final de cada arma:

- `HeadShotDamageModifierPlayer`;
- `NetworkHeadShotPlayerDamageModifier`;
- `HeadShotDamageModifierAI`;
- distancias de headshot;
- `LightlyArmouredDamageModifier`;
- `Penetration`.

Los tags se insertan aunque el META custom no los tenga. El límite interno anterior de `LightlyArmouredDamageModifier = 2.0` fue eliminado; ahora el valor configurable puede llegar hasta `1000.0`.

### Comando recomendado

```powershell
python run_rebalance.py `
  --root "C:\TxData\rebelion\resources\[Streaming]\[PackArmas]" `
  --profile profiles\rebelion_server.json `
  --write
```

También se puede forzar desde CLI:

```powershell
python run_rebalance.py `
  --root "C:\RUTA\[PackArmas]" `
  --profile profiles\rebelion_server.json `
  --onetap-through-helmets `
  --helmet-multiplier 100 `
  --helmet-penetration 1 `
  --write
```

Para desactivar únicamente esta política:

```powershell
python run_rebalance.py --root "C:\RUTA\[PackArmas]" --profile profiles\rebelion_server.json --no-onetap-through-helmets --write
```

### Verificación después de ejecutar

Dentro de cada arma procesada deben aparecer valores similares a estos:

```xml
<HeadShotDamageModifierPlayer value="1500.000000" />
<NetworkHeadShotPlayerDamageModifier value="1500.000000" />
<LightlyArmouredDamageModifier value="100.000000" />
<Penetration value="1.000000" />
```

Reinicia por completo el recurso que transmite los META. Un simple `refresh` no siempre obliga al cliente a recargar datos ya transmitidos.

### Límite importante

Esta solución trabaja únicamente con `CWeaponInfo`/META y no instala ningún loop de vida, armor o daño. Sin embargo, ningún valor de `weapons.meta` puede reactivar críticos si otro recurso ejecuta `SetPedSuffersCriticalHits(ped, false)` o cancela el daño antes de que GTA aplique el multiplicador.

Antes de instalar un “antitank”, busca el recurso que está apagando los críticos:

```powershell
Get-ChildItem "C:\TxData\rebelion\resources" -Recurse -File -Include *.lua,*.js,*.ts,*.cs |
  Select-String -Pattern "SetPedSuffersCriticalHits|EBD76F2359F190AC"
```

Si aparece una llamada con `false` o `0`, corrige solo ese recurso. Es mucho más seguro que poner otro loop peleándose con él cada frame; dos scripts contradiciéndose son básicamente un deadlock con uniforme de GTA.

### Pruebas incluidas

```powershell
python -m unittest discover -s tests -v
```

Las pruebas cubren:

- casco con tag existente;
- casco con tag faltante;
- desactivación por perfil;
- armas recreativas con daño cero.

---

# META completo — versión 2

Esta versión ya no está limitada al pequeño grupo inicial de daño/recoil. Incluye:

- **133 campos escalares conocidos de `CWeaponInfo`** organizados por identidad, daño, red, cabeza, alcance, fuerzas, proyectiles, precisión, recoil, recarga, cadencia, cámara, vibración, HUD y animaciones.
- **146 `WeaponFlags` nominales conocidas**.
- Edición incremental de `WeaponFlags`: agrega o elimina flags sin borrar las originales.
- Overrides dinámicos para tags custom/no catalogados mediante `meta`.
- Soporte para atributos múltiples, por ejemplo vectores `x/y/z`.
- Inventario completo de todos los `.meta` del pack, incluyendo `weaponcomponents.meta`, `weaponarchetypes.meta`, animaciones y archivos custom.
- Generación automática de un perfil reutilizable desde los `CWeaponInfo` reales encontrados.

## Solución META reforzada para cascos

Cuando el modo one-tap y `bypass_helmets` están activos, el rebalancer fuerza al final:

```text
HeadShotDamageModifierPlayer
NetworkHeadShotPlayerDamageModifier
HeadShotDamageModifierAI
LightlyArmouredDamageModifier
Penetration
WeaponFlags += IgnoreHelmets
WeaponFlags += ArmourPenetrating
```

No reemplaza `WeaponFlags`: conserva `Gun`, `AnimReload`, `Automatic`, `TwoHanded`, flags de primera persona y cualquier flag custom existente.

Configuración:

```json
"headshot": {
  "mode": "onetap",
  "multiplier": 1500.0,
  "distance": 300.0,
  "no_falloff": true,
  "bypass_helmets": true,
  "helmet_multiplier": 100.0,
  "force_penetration": true,
  "penetration": 1.0,
  "add_ignore_helmets_flag": true,
  "add_armour_penetrating_flag": true,
  "create_missing_weapon_flags_tag": true
}
```

## Ver todos los campos soportados

```powershell
python run_rebalance.py --list-fields
```

## Ver todas las WeaponFlags conocidas

```powershell
python run_rebalance.py --list-flags
```

## Exportar TODA la información de los META

Este comando no modifica archivos. Genera un JSON con todos los `.meta`, rutas XML, atributos, textos, catálogo de tags y errores de parseo:

```powershell
python run_rebalance.py `
  --root "C:\TxData\rebelion\resources\[Streaming]\[PackArmas]" `
  --export-meta "meta_inventory.json" `
  --export-only
```

## Generar un perfil completo desde el pack real

```powershell
python run_rebalance.py `
  --root "C:\TxData\rebelion\resources\[Streaming]\[PackArmas]" `
  --export-full-profile "perfil_pack_completo.json" `
  --export-only
```

El perfil exportado conserva por arma:

- todos los campos estándar reconocidos;
- tags escalares desconocidos dentro de `meta`;
- atributos XML directos;
- `WeaponFlags`;
- archivo de origen;
- grupo detectado;
- fuentes duplicadas, cuando la misma arma aparece más de una vez.

## Nuevo formato recomendado del perfil

```json
{
  "defaults": {
    "fields": {},
    "meta": {},
    "weapon_flags": {
      "add": [],
      "remove": [],
      "create_if_missing": false
    }
  },
  "groups": {
    "GROUP_RIFLE": {
      "fields": {
        "damage": 40.0,
        "weapon_range": 250.0,
        "network_player_damage_modifier": 1.0
      },
      "meta": {
        "CustomScalarTag": {
          "kind": "value_attr",
          "value": 1.0,
          "create_if_missing": false
        },
        "CustomVector": {
          "attributes": {
            "x": 0.0,
            "y": 0.0,
            "z": 0.0
          },
          "create_if_missing": false
        }
      },
      "weapon_flags": {
        "add": ["IgnoreHelmets", "ArmourPenetrating"],
        "remove": [],
        "create_if_missing": true
      }
    }
  },
  "weapons": {
    "WEAPON_CUSTOM": {
      "fields": {
        "clip_size": 30,
        "recoil_accuracy_max": 0.3
      },
      "meta": {},
      "weapon_flags": {
        "add": [],
        "remove": ["NonLethal"],
        "create_if_missing": false
      }
    }
  }
}
```

### Formatos de `meta`

Valor simple, reemplaza automáticamente `value`, `ref` o texto cuando el tag existe:

```json
"meta": {
  "CustomTag": 5.0
}
```

Tipo explícito:

```json
"meta": {
  "CustomTag": {
    "kind": "value_attr",
    "value": 5.0,
    "create_if_missing": false
  }
}
```

Tipos admitidos:

- `value_attr`: `<Tag value="5.0" />`
- `ref_attr`: `<Tag ref="NAME" />`
- `text`: `<Tag>NAME</Tag>`
- `attributes`: mediante `{"attributes": {"x": ..., "y": ...}}`

Por seguridad, los tags dinámicos no se insertan salvo que declares `create_if_missing: true`. Reemplazar un valor existente es seguro; inventar una estructura que GTA espera anidada puede convertir el arranque en una ruleta rusa con XML.

## Plantilla completa incluida

```text
profiles/full_meta_template.json
```

Contiene el catálogo completo, formatos de ejemplo, referencias de campos y lista de flags conocidas. La sección `_field_reference` es documentación y no se aplica al META.

## Validación estricta

```json
"validation": {
  "strict_unknown_fields": true
}
```

Con esta opción, un nombre incorrecto dentro de `fields` detiene el proceso. Para tags XML no catalogados debes usar `meta`.
