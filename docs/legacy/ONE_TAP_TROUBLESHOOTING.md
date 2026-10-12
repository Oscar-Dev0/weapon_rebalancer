# Diagnóstico one-tap V4

## Caso: una gorra, casco o ropa tanquea el disparo

Ese síntoma normalmente indica que el headshot está entrando como daño corporal. Ejecuta primero:

```powershell
python run_rebalance.py --runtime-only --audit-runtime --runtime-root "C:\TxData\rebelion\resources" --runtime-report reports\runtime.json
```

### Bloqueos duros

#### `critical_hits_disabled`

Busca una línea parecida a:

```lua
SetPedSuffersCriticalHits(PlayerPedId(), false)
```

Cámbiala a `true`, elimina el loop o desactiva esa opción en el recurso responsable.

#### `weapon_damage_event_cancelled`

Un handler de `weaponDamageEvent` llama `CancelEvent()`. Revisa la condición: probablemente está cancelando más armas o zonas de las necesarias.

#### `damage_event_health_or_armour_restore`

El archivo procesa `CEventNetworkEntityDamage` y vuelve a ejecutar `SetEntityHealth`, `SetPedArmour` o `AddArmourToPed`. Eso es un antitank real y debe corregirse en su lógica.

## Verificar el META

```powershell
python run_rebalance.py --root "C:\RUTA\PACK" --profile profiles\rebelion_real_onetap_v4.json --strict-onetap-audit --report reports\meta.json
```

Debe mostrar:

```text
Auditoría one-tap: ok=N | fallos=0
```

## Revisar duplicados

Si el mismo `WEAPON_*` aparece en varios recursos, el último META cargado puede reemplazar el corregido. El reporte lista todas las rutas.

## Revisar manifest

El archivo debe estar registrado, por ejemplo:

```lua
files { 'weapons.meta' }
data_file 'WEAPONINFO_FILE_PATCH' 'weapons.meta'
```

## Reinicio correcto

1. reinicia el recurso del META;
2. reinicia el recurso conflictivo o el guard;
3. reconecta el cliente;
4. si persiste caché, reinicia el servidor y limpia caché del cliente de prueba.

## Guard mínimo

Instálalo únicamente cuando no puedas corregir inmediatamente el recurso que pone críticos en `false`:

```powershell
python run_rebalance.py --install-headshot-guard "C:\RUTA\resources\[standalone]\os_headshot_guard"
```

En `server.cfg`, asegúralo después de recursos de combate, safezone, apariencia y antitank:

```cfg
ensure os_headshot_guard
```

El guard no mata jugadores ni restaura estados; únicamente mantiene critical hits activos.

## Aislar un arma

```powershell
python run_rebalance.py --root "C:\RUTA\PACK" --profile profiles\rebelion_real_onetap_v4.json --only WEAPON_CUSTOMRIFLE --report reports\customrifle.json
```
