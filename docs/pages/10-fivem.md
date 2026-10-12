---
slug: fivem
title: FiveM: qué controla cada cosa
group: FiveM
description: META, natives y recursos: cómo llega cada valor al juego y qué hay que reiniciar.
---
# FiveM: qué controla cada cosa

## Los weapons.meta

Cada arma se define en un bloque `<Item type="CWeaponInfo">` dentro de un `weapons.meta`. FiveM solo lo carga si el `fxmanifest.lua` del recurso lo declara:

```lua
data_file 'WEAPONINFO_FILE' 'meta/weapons.meta'
```

- Los cambios se aplican **al reiniciar el recurso** que contiene el META (los clientes lo vuelven a cargar).
- Si un arma está definida en **dos META**, gana la última que carga FiveM. El panel avisa de las duplicadas y el generador edita todas las copias igual.
- Un META que no aparece en ningún `WEAPONINFO_FILE` no se carga: el Diagnóstico lo marca como `meta_unregistered`.
- El motor edita el texto en su sitio (no reserializa el XML): comentarios, formato y bloques anidados (`OverrideForces`, `AttachPoints`) se conservan.

## ox_inventory

`ox_inventory/data/weapons.lua` define los **ítems**: nombre `WEAPON_*`, etiqueta, peso, desgaste (`durability`), munición (`ammoname`) y componentes. El hash que usa es `joaat(model o nombre)`.

ox_inventory **no** define daño, cadencia ni recoil. El panel lo usa para identificar armas y lo cruza con los META:

| Situación | Significado |
| --- | --- |
| En ox, sin META | El ítem existe pero el arma no está instalada en los packs configurados |
| En META, sin ox | El arma existe pero no se puede obtener como ítem |
| Clave repetida en weapons.lua | En Lua gana la última entrada |
| `ammoname` inexistente | El arma no podrá recargar con munición del inventario |

El panel nunca escribe en ox_inventory.

## Critical hits (cabeza)

Los multiplicadores de cabeza solo se aplican si el ped tiene *critical hits* activos:

```lua
SetPedSuffersCriticalHits(ped, true)
```

Si un script los pone en `false`, un disparo a la cabeza hace daño de torso aunque el META diga ×1500. **Diagnóstico → Auditar scripts** busca esas llamadas y muestra si están dentro de un `if` (por ejemplo `qbx_ignore` solo lo hace si `config.disable.headshots` está activo).

`os_headshot_guard` reafirma los critical hits (en este servidor, una vez por segundo).

## qbx_recoils {#qbx-recoils}

`qbx_smallresources/qbx_recoils` aplica el **recoil vertical de cámara**: mientras disparas sube la cámara con `SetGameplayCamRelativePitch` según un valor por arma en `config.lua`:

```lua
[453432689] = 0.3,   --['weapon_pistol']
```

- La clave es el hash del arma con signo.
- El valor son grados aproximados que sube la cámara por disparo detectado. 0.1–0.3 es suave; 0.5–0.9, fuerte.
- Las armas sin entrada no tienen recoil vertical por script (es el caso de casi todas las armas personalizadas).
- El generador edita solo las líneas de las armas que indiques y conserva comentarios y entradas desactivadas.
- Para aplicarlo hay que **reiniciar `qbx_smallresources`**.

## Guard de daño (opcional)

Si el Diagnóstico muestra recursos que cambian el daño en ejecución (`SetWeaponDamageModifier`, `SetPlayerWeaponDamageModifier`), el generador puede crear `os_weapon_damage_guard`: un recurso cliente que reaplica el daño esperado cada 250 ms. No hace falta para que el META funcione.

## Qué reiniciar después de aplicar

| Cambiaste | Reinicia |
| --- | --- |
| `weapons.meta` de un pack | El recurso de ese pack (o todos los de `[PackArmas]`) |
| `qbx_recoils` | `qbx_smallresources` |
| El guard de daño | `os_weapon_damage_guard` (y agrégalo a `server.cfg`) |

> [!NOTE]
> Los jugadores conectados necesitan volver a cargar el recurso: reiniciarlo desde txAdmin lo hace para todos.
