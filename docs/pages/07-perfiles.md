---
slug: perfiles
title: Perfiles JSON
group: Perfiles
description: Formato v8, precedencia, herencia, excepciones, reglas avanzadas, validaciones e historial.
---
# Perfiles JSON

Un perfil es un archivo JSON que describe qué cambiar. Lo leen el panel, la [terminal](12-terminal.md) y `run_rebalance.py --profile`. Los cuatro perfiles principales están descritos en [Perfiles oficiales](06-perfiles-oficiales.md).

## Niveles y protección {#niveles}

| Nivel | Carpeta | Quién lo edita |
| --- | --- | --- |
| **Oficial** | `profiles/official/` | Nadie: protegido. Para cambiarlo, crea un derivado |
| **Servidor** | `profiles/server/` | Editable (`flow_caribe`) si `server_profiles_editable` está activo en Configuración. No se renombra ni se borra |
| **Usuario** | `profiles/user/` | Totalmente editable: crear, renombrar, borrar (va a la papelera) |
| **Archivado** | `profiles/legacy/` | Solo lectura. Vacío desde la 7.3.0: los perfiles anteriores a la v7.1 se borraron (respaldo en `/fivem/backups/`) |

Al intentar editar un perfil protegido, el panel y la terminal ofrecen **crear un perfil derivado**: un perfil de usuario con `"extends": "<oficial>"` que hereda todo y solo guarda tus cambios. Los perfiles importados también van siempre a `profiles/user/`.

`profiles/schemas/profile.schema.json` describe el formato (JSON Schema 2020-12); cada perfil lo referencia con `"$schema"` para que los editores (por ejemplo VS Code) autocompleten y validen.

## Formato v8

```json
{
  "$schema": "../schemas/profile.schema.json",
  "schema_version": 8,
  "profile": {
    "id": "pvp_competitivo",
    "name": "PvP competitivo",
    "short_name": "PvP",
    "description": "TTK corto en pistolas, rifles controlados.",
    "objective": "Que gane quien acierta primero.",
    "audience": "Arenas y eventos PvP.",
    "features": ["Pistolas a 3 disparos"],
    "warnings": ["One-tap requiere critical hits activos."],
    "extends": "competitive",
    "tags": ["pvp"],
    "revision": 3
  },
  "engine_defaults": false,
  "modules": { "damage": "configured", "recoil": "configured", "headshot": "normal" },
  "headshot": { "mode": "normal", "multiplier": 1.5 },
  "defaults": { "fields": {} },
  "groups": { "GROUP_PISTOL": { "fields": { "damage": 12.0 } } },
  "weapons": {
    "WEAPON_PISTOL50": {
      "fields": { "damage": 30.0, "time_between_shots": 0.3 },
      "headshot": { "mode": "onetap", "dynamic_multiplier_from_damage": true },
      "weapon_flags": { "add": ["IgnoreHelmets"], "remove": [] }
    }
  },
  "ignore_weapons": [],
  "harmless_weapons": [],
  "resources": { "qbx_recoils": { "WEAPON_PISTOL50": 0.6 } }
}
```

Todas las claves salvo `$schema`, `profile`, `schema_version` y `resources` son las que lee el motor (las mismas de las versiones 3–7). Los nombres de campo (`damage`, `time_between_shots`…) están en la [Referencia de parámetros](#parametros).

> [!WARNING]
> No guardes claves decorativas: una clave que el motor no lee no tiene efecto. El validador las marca (por ejemplo `validation.require_runtime_critical_hits`, que aparece en algunos perfiles antiguos y nunca se usó).

## Precedencia {#precedencia}

![Precedencia](img/precedencia.svg)

1. Lo que el perfil no toca queda como está en el META (o en el `.bak` si usas `restore.from_backup`).
2. `defaults.fields` (global).
3. `groups.GROUP_X.fields`. **Si el perfil no define la categoría**, se usa el preset interno (`base_preset`) siempre que `engine_defaults` esté activo. Ojo: el preset pisa los valores globales.
4. Configuración local por carpeta (`weapon_rebalance.json` dentro del pack).
5. `weapons.WEAPON_X.fields`.
6. Módulos: `original` descarta la sección; los presets recalculan sus campos.
7. Reparación base, multiplicadores para custom, reglas por cadencia, multiplicadores exactos y reglas por familia.
8. Política de cabeza (y one-tap).
9. Armas inofensivas, límites del motor, tags XML exactos y flags.

## Módulos

| Módulo | Valores | Qué hace |
| --- | --- | --- |
| `damage` | original, configured, normal, none, head_only, low, high, lethal | `low/high/lethal` multiplican el daño del perfil |
| `armour` | original, configured, none, normal, piercing, max | Fija `LightlyArmouredDamageModifier` |
| `recoil` | original, configured, none, low, normal, high | Los presets escriben 4 campos de recoil |
| `accuracy` | original, configured, laser, high, normal, low | Los presets escriben 3 campos de precisión |
| `range` | original, configured, short, normal, long, very_long | Escala alcance y caída |
| `fire_rate` | original, configured, slow, normal, fast, very_fast | Escala `TimeBetweenShots` |
| `reload` | original, configured, slow, normal, fast, very_fast | Escala tiempos de recarga |
| `headshot` | original, off, normal, onetap | Activa la política de cabeza |

Si el perfil no declara un módulo, se usa el valor por defecto de `config.py` (recoil `normal`, armour `max`, headshot `onetap`…). Por eso los perfiles nuevos los declaran todos.

## engine_defaults {#engine-defaults}

- `false` (perfiles creados en el panel): no se hereda nada de `config.py`. Lo no configurado queda intacto.
- `true` (perfiles antiguos): se heredan el preset `pvp_lethal`, overrides de cuerpo a cuerpo y multiplicadores de alcance por familia de `config.py`.

> [!DANGER]
> Con `engine_defaults: true` y `modules.headshot` activo, si no declaras `headshot.mode` el motor usa **one-tap ×1500** en todas las armas procesadas. El validador lo avisa.

## Herencia {#herencia}

`profile.extends` apunta a un perfil base. Primero se resuelve el base (y el base de este, si lo tiene) y luego el derivado lo sobrescribe, con las reglas de **JSON Merge Patch** (RFC 7386):

- Los objetos se combinan clave a clave.
- Las listas se **reemplazan** enteras (`ignore_weapons`, `fire_rate_damage_rules`…).
- Un valor `null` **quita** lo heredado: `"damage": null` en un arma hace que deje de usar el daño que traía el base para ella. En la terminal es `campo=inherit`; en el panel, el botón **No heredar** del parámetro (la fila queda marcada *no hereda*).
- Quitar una clave del derivado (`campo=unset` o el icono ↶) vuelve a heredar el valor del base.
- La resolución es determinista: mismo archivo, mismo resultado. Se detectan ciclos, bases inexistentes y cadenas de más de 6 niveles (error **Bloqueante**).
- No se puede borrar un perfil del que heredan otros. Si renombras un perfil de usuario, los derivados editables se actualizan solos.

Ejemplo: `flow_caribe` hereda de `competitive`, que hereda de `realistic`. La cadena se ve en **Perfiles → detalle** o con `wr.py profile show flow_caribe`.

### Procedencia de cada valor {#procedencia}

El panel (ficha del arma, comparador) y la terminal (`wr.py weapon`, `wr.py compare`) indican de dónde sale cada valor efectivo:

| Marca | Significado |
| --- | --- |
| **P** del perfil | Lo declara el perfil abierto |
| **H** heredado | Viene de un perfil base (se nombra cuál y si es por arma, categoría o global) |
| **S** sobrescrito | El perfil cambia un valor que heredaba |
| **R** regla | Lo fija el motor: preset de módulo, regla por cadencia o familia, multiplicador exacto, normalización de custom, reparación base o política de cabeza |
| **O** original | El META actual, sin cambios |
| **X** sin efecto | Declarado pero descartado (módulo en `original`, arma omitida o inofensiva) |

## Excepciones {#excepciones}

| Lista | Efecto |
| --- | --- |
| `ignore_weapons` | El motor no toca esas armas |
| `allow_ignored_weapons` | Quita armas de la lista interna (RPG, RAILGUN, MINIGUN, GRENADELAUNCHER) |
| `harmless_weapons` | Daño y multiplicadores a 0 al final de todo |
| `allow_damage_weapons` | Quita armas de la lista interna de inofensivas (SNOWBALL, BALL) |

## Recursos: qbx_recoils {#qbx}

`resources.qbx_recoils` fija el recoil vertical de cámara por arma en `qbx_smallresources/qbx_recoils/config.lua`:

| Valor | Efecto |
| --- | --- |
| número (0–10) | Escribe ese valor en la entrada del arma |
| `false` | Quita la entrada: el arma deja de tener recoil por script |
| sin clave | No toca la entrada |
| `null` | En un derivado, deja de aplicar lo que declaraba el perfil base (no toca la entrada) |

## Resultado repetible {#repetible}

Aplicar el mismo perfil dos veces debería dar el mismo resultado. No pasa si usas multiplicadores sobre el valor del META sin fijar un valor base: cada aplicación multiplica otra vez. La vista previa lo comprueba ejecutando el motor dos veces; si falla verás *no repetible*. Soluciones:

- Activar `restore.from_backup` (cada arma parte de su `.bak`).
- Fijar el valor base en el perfil (por ejemplo el daño de la categoría) y multiplicar sobre él.

## Reglas avanzadas

Estas secciones se editan en **Constructor → Reglas avanzadas**. Antes de aceptarse, el motor las valida.

### fire_rate_damage_rules {#fire_rate_damage_rules}

Lista ordenada de reglas `{name, groups, min_time_between_shots, max_time_between_shots, damage}`. La primera que coincide con el `TimeBetweenShots` efectivo del arma fija su daño. Un daño explícito por arma tiene prioridad.

### fire_rate_classifier {#fire_rate_classifier}

Clasifica las armas por cadencia (tiempo entre disparos, flag `Automatic`, patrón de disparo y señales secundarias). Permite quitar el one-tap a las armas rápidas, limitar su daño (`non_normal_damage_caps`), fijar una lista permitida de one-tap y aplicar recoil visible a las armas one-tap tiro a tiro.

### weapon_field_multipliers {#weapon_field_multipliers}

`{"WEAPON_X": {"damage": 6.0}}`: multiplica el valor ya resuelto de ese campo, solo en esa arma exacta.

### family_rules {#family_rules}

Reglas por nombre: `{name, contains: ["REVOLVER"], groups, official_only, custom_only, fields, field_multipliers}`.

### weapon_classification {#weapon_classification}

Distingue armas oficiales (catálogo de Cfx.re) de personalizadas y aplica multiplicadores solo a las personalizadas. `multiplier_base: group_reference` normaliza contra un valor de referencia del grupo en vez de multiplicar el valor que trae el arma.

### baseline_repair {#baseline_repair}

Repara valores rotos (daño o modificador de red en 0, alcance ausente) antes de aplicar el resto. Puede usar packs de referencia vanilla (`reference_roots`).

### meta {#meta}

`{"Tag": valor}` o `{"Tag": {"value": 1, "kind": "value_attr", "create_if_missing": false}}`: reemplaza hojas XML exactas que no están en el catálogo de campos. Úsalo con cuidado; no tiene validación de rango.

## Validaciones {#validaciones}

| Código | Qué significa |
| --- | --- |
| `unknown_top_level` | Clave de primer nivel que el motor no lee |
| `validation_noop` | Opción de `validation` sin efecto |
| `module_value` | Valor de módulo inválido |
| `unknown_field` / `field_type` | Campo inexistente o no numérico |
| `engine_rejected` | El motor rechaza el perfil (mensaje exacto del motor) |
| `module_original` | Valor en una sección con el módulo en `original` |
| `module_preset_overrides` | Un preset pisa el valor |
| `clamped` | Valor fuera de límites: se recorta |
| `value_overridden` | Otra regla del perfil cambia el valor (informativo) |
| `unknown_weapon` / `unknown_group` | Arma o grupo sin META en el pack |
| `weapon_skipped` | El arma tiene valores pero el motor la omite |
| `not_idempotent` | Aplicarlo dos veces da otro resultado |
| `headshot_mode_inherited` | Política de cabeza activa sin modo declarado |
| `qbx_value` | Valor de `qbx_recoils` fuera de 0–10 |
| `inheritance` | Ciclo, base inexistente o cadena demasiado larga |
| `list_conflict` | La misma arma está en una lista y en su excepción (`ignore_weapons` y `allow_ignored_weapons`, o `harmless_weapons` y `allow_damage_weapons`) |
| `ignored_but_configured` | Arma en `ignore_weapons` con valores configurados: no se aplicarán |
| `flag_conflict` | La misma flag se agrega y se quita a la vez (gana quitar) |
| `headshot_list_conflict` | Arma a la vez en `one_tap_weapons` y `no_one_tap_weapons` (o en `allowed_weapons` y `disabled_weapons`) |
| `headshot_scoped_noop` | Política de cabeza por arma o categoría con el módulo `headshot` en `original` |
| `rule_unreachable` | Regla de cadencia que nunca coincide porque otra anterior la cubre |
| `rule_duplicate_name` | Dos reglas con el mismo nombre |
| `null_without_parent` | `null` en un perfil sin base: no quita nada |

Cada aviso tiene un nivel:

- **Bloqueante**: el perfil no se puede guardar, activar ni aplicar hasta corregirlo.
- **Advertencia**: se puede guardar, pero probablemente no hace lo que esperas.
- **Recomendación**: informativo (por ejemplo, una regla intencional que cambia un valor declarado).

## Historial y versiones

Cada guardado copia la versión anterior a `data/history/<id>/` y registra la acción (edición, creación, importación, migración, restauración, renombrado). Desde **Perfiles → Historial** puedes ver cualquier versión y restaurarla: se recupera el archivo byte a byte y la versión actual queda guardada.

Borrar mueve el perfil a `data/trash/`. En la terminal: `wr.py profile history ID` y `wr.py profile restore ID ARCHIVO`.

### Ediciones simultáneas {#concurrencia}

El panel y la terminal guardan con un bloqueo entre procesos (`data/locks/`) y comprueban que el archivo no haya cambiado desde que lo abriste. Si otra persona guardó antes, tu guardado se rechaza con un **conflicto** en lugar de pisar su cambio: recarga el perfil y repite. Las escrituras son atómicas (un corte no deja un JSON a medias).

## Importar, exportar y comparar

- **Importar** acepta perfiles v3–v8; se validan y migran.
- **Exportar** ofrece el perfil tal cual, **resuelto** (con la herencia aplicada) o en **formato legacy** para la CLI antigua.
- **Comparar** ejecuta ambos perfiles con el motor y muestra qué armas y campos terminarían distintos, además de las diferencias del JSON.

## Migración desde versiones anteriores

### Perfiles v3–v7 importados

Un archivo en formato antiguo se lee migrado en memoria y pasa a v8 al importarlo o guardarlo:

1. Detecta el formato (sin bloque `profile` = legacy).
2. Mueve `name` y `description` a `profile` y añade `engine_defaults: true` para conservar el comportamiento.
3. Guarda el archivo anterior en el historial.
4. Se puede revertir (**Revertir migración** o restaurar la versión).

Para migrar los perfiles de usuario que sigan en formato antiguo: **Perfiles → Migrar legacy a v8** o `python3 wr.py migrate --write`.

### Reorganización 7.1 (18 → 4 perfiles) {#reorganizacion}

Los 18 perfiles anteriores se consolidaron en los cuatro principales. Ninguno se perdió:

- Cada resultado se verificó ejecutando el motor sobre el pack real.
- Desde la 7.3.0 (2026-10-17) los perfiles legacy y la migración se borraron del repo; hay respaldo en `/fivem/backups/weapon_rebalancer_limpieza_2026-10-17/`. Un pendiente se recupera con `wr.py profile import <archivo> --id <nuevo_id>`.

Detalle y tabla de destinos en [Perfiles oficiales → Migración](06-perfiles-oficiales.md#migracion).
