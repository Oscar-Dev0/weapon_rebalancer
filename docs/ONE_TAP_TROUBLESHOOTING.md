# Diagnóstico cuando el one-tap no se refleja en el servidor

## 1. Ejecutar auditoría estricta

```powershell
python run_rebalance.py --root "C:\RUTA\PACK" --profile profiles\rebelion_balanced_v3.json --report reports\audit.json --strict-onetap-audit
```

No apliques cambios hasta que el resumen indique `fallos=0`.

## 2. Revisar armas duplicadas

Si el mismo `WEAPON_*` aparece en dos recursos, el último META cargado puede sobrescribir el corregido. El reporte muestra todas las rutas detectadas.

## 3. Revisar el manifest

Cada archivo de arma debe estar cargado mediante un `data_file` compatible, normalmente:

```lua
data_file 'WEAPONINFO_FILE_PATCH' 'weapons.meta'
```

Un archivo presente en disco pero no registrado no afecta el juego. Decoración XML premium, funcionalidad cero.

## 4. Reiniciar realmente el recurso

Después de cambiar META:

1. detener el recurso;
2. iniciarlo de nuevo o reiniciar el servidor;
3. reconectar el cliente si conserva assets antiguos;
4. evitar probar con una definición duplicada cargada después.

## 5. Buscar recursos que desactivan críticos

En PowerShell, desde la carpeta de recursos:

```powershell
Get-ChildItem -Recurse -Include *.lua,*.js,*.ts,*.cs | Select-String -Pattern "SetPedSuffersCriticalHits|CEventNetworkEntityDamage|SetEntityHealth|SetPedArmour"
```

Una llamada a `SetPedSuffersCriticalHits(PlayerPedId(), false)` impide que el sistema de críticos del ped se comporte normalmente. El META no puede revertir una native ejecutada por otro recurso.

## 6. Cascos custom

`IgnoreHelmets`, `ArmourPenetrating` y `LightlyArmouredDamageModifier` cubren la protección nativa representada en `CWeaponInfo`. Un casco implementado por un script que resta daño o restaura armadura necesita corregirse en ese recurso específico.

## 7. Confirmar la arma exacta

Usa `--only` para aislarla:

```powershell
python run_rebalance.py --root "C:\RUTA\PACK" --profile profiles\rebelion_balanced_v3.json --only WEAPON_CUSTOMRIFLE --report reports\customrifle.json
```
