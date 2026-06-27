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
- Armadura ligera/casco nativo: `LightlyArmouredDamageModifier = 2.0`.
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

`LightlyArmouredDamageModifier = 2.0` y un headshot alto mejoran el daño contra armadura ligera y cascos nativos. No existe un tag universal en `weapons.meta` que obligue a ignorar cualquier sistema de armadura creado por scripts externos.

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
