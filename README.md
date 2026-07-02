# Weapon Rebalancer META V6

Requiere **Python 3.10 o superior**.

## Perfil recomendado: reparación absoluta + custom 15%

La V6 corrige el problema principal de la V5: ya no depende únicamente de un `.meta.bak` que podría estar modificado. Puede cargar un paquete original de `weapons.meta`, copiar los valores absolutos de las armas oficiales, reparar armas custom con daño/rango en cero y luego aplicar el `+15%`.

### Uso rápido

1. Previsualiza:

```bat
preview_vanilla_repair_v6.bat
```

2. Aplica y genera el guard runtime:

```bat
apply_vanilla_repair_v6.bat
```

También puedes indicar rutas manualmente:

```bat
apply_vanilla_repair_v6.bat "C:\TxData\rebelion\resources\[Streaming]\[PackArmas]" "C:\TxData\rebelion\resources\[OscarDev]\os_weapon_damage_guard"
```

3. Agrega el guard al **final** del bloque de recursos de armas/combate:

```cfg
ensure os_weapon_damage_guard
```

4. Dentro del juego ejecuta:

```text
/osweaponstatus
```

El comando muestra el hash/nombre actual, el daño que FiveM reporta como cargado, el daño absoluto esperado y el multiplicador aplicado.

## Qué repara V6

- restaura armas oficiales desde `--reference-root` cuando hay un paquete original disponible;
- usa una tabla de daños vanilla del núcleo como respaldo;
- repara `Damage=0`, tags ausentes y modificadores de red en cero;
- repara alcance, falloff y headshot deshabilitado accidentalmente;
- aplica `×1.15` únicamente a armas custom de grupos de fuego;
- deja el headshot normal/original, sin el multiplicador global `1500`;
- aplica `350` al torso de revólveres y reduce extremidades a `0.25`;
- detecta componentes con multiplicadores de daño distintos de `1.0`;
- marca armas `PROJECTILE`, porque pueden depender de `AmmoInfo`/explosión y no solamente de `<Damage>`;
- genera `os_weapon_damage_guard` para neutralizar modificadores runtime por arma/jugador.

## Paquete de referencia

El descargador usa el proyecto público `CyCoSnag/snag_weapon_metas`, que incluye META originales de GTAV y DLC. Para instalarlo manualmente:

```powershell
powershell -ExecutionPolicy Bypass -File .\references\download_original_gtav_metas.ps1
```

Después:

```powershell
python run_rebalance.py `
  --root "C:\TxData\rebelion\resources\[Streaming]\[PackArmas]" `
  --profile "profiles\vanilla_repair_custom_plus15_absolute_v6.json" `
  --reference-root "references\snags_original\metas" `
  --write `
  --generate-damage-guard "C:\TxData\rebelion\resources\[OscarDev]\os_weapon_damage_guard" `
  --force-install
```

## Orden de cálculo

```text
paquete original / referencia
          ↓
reparación de valores cero o ausentes
          ↓
+15% solamente para custom
          ↓
reglas de familia (revólver)
          ↓
validación, auditorías y guard runtime
```

La V6 incluye **32 pruebas automáticas**.

---

## Documentación histórica V5/V4

Requiere **Python 3.10 o superior**.

## Perfil recomendado V5: default original + custom 15%

Para volver a los valores anteriores y aplicar solamente una ventaja moderada a las armas custom:

```powershell
python run_rebalance.py `
  --root "C:\TxData\rebelion\resources\[Streaming]\[PackArmas]" `
  --profile "profiles\vanilla_normal_custom_plus15_revolver_onetap.json" `
  --write `
  --report "reports\vanilla_custom_plus15_apply.json"
```

También puedes usar `preview_vanilla_custom_plus15.bat` y luego `apply_vanilla_custom_plus15.bat`.

El perfil usa `weapons.meta.bak` como fuente original. Si un archivo no tiene backup, mantiene su contenido actual como base y lo muestra en las advertencias del reporte. Las armas oficiales se reconocen con el catálogo de modelos de Cfx.re; únicamente las armas no incluidas en ese catálogo y pertenecientes a grupos de fuego reciben el `+15%`.


La V4 separa correctamente las dos capas que intervienen en un headshot de FiveM:

1. **META:** daño corporal, multiplicadores de cabeza, alcance, falloff, casco nativo y flags del arma.
2. **Runtime:** scripts que habilitan/deshabilitan críticos, cancelan daño o restauran vida/armadura.

Subir `HeadShotDamageModifierPlayer` a 1500 no sirve si otro recurso ejecuta `SetPedSuffersCriticalHits(..., false)`. La V4 detecta ese conflicto y ofrece un guard mínimo opcional que no modifica vida, armadura ni daño manual.

## Flujo recomendado para Rebelion

### 1. Auditar todos los scripts del servidor

Ejecuta:

```powershell
python run_rebalance.py `
  --runtime-only `
  --audit-runtime `
  --runtime-root "C:\TxData\rebelion\resources" `
  --runtime-report "reports\rebelion_runtime_audit.json"
```

O abre:

```text
audit_rebelion_runtime.bat
```

Prioridad del reporte:

- `[X] critical_hits_disabled`: desactiva el daño crítico; es la causa típica de que una gorra o cualquier ropa parezca tanquear.
- `[X] weapon_damage_event_cancelled`: cancela el daño antes de que el META tenga efecto.
- `[X] damage_event_health_or_armour_restore`: vuelve a poner vida/armadura después del disparo.
- `[!] ped_armour_write`: un recurso de ropa, chalecos o estados escribe armadura.
- `[!] runtime_damage_modifier`: otro script cambia el daño en ejecución.

### 2. Previsualizar el perfil META V4

```powershell
python run_rebalance.py `
  --root "C:\TxData\rebelion\resources\[Streaming]\[PackArmas]" `
  --profile "profiles\rebelion_real_onetap_v4.json" `
  --strict-onetap-audit `
  --report "reports\rebelion_v4_preview.json"
```

### 3. Aplicar el META

```powershell
python run_rebalance.py `
  --root "C:\TxData\rebelion\resources\[Streaming]\[PackArmas]" `
  --profile "profiles\rebelion_real_onetap_v4.json" `
  --write `
  --strict-onetap-audit `
  --report "reports\rebelion_v4_apply.json"
```

El programa crea copias `.bak` antes de escribir.

### 4. Corregir el bloqueo runtime

La solución limpia es cambiar o eliminar la línea que coloca críticos en `false`.

Cuando no puedas editar el recurso conflictivo, instala el guard mínimo:

```powershell
python run_rebalance.py `
  --install-headshot-guard "C:\TxData\rebelion\resources\[standalone]\os_headshot_guard"
```

Después agrega al final del bloque de combate en `server.cfg`:

```cfg
ensure os_headshot_guard
```

También está disponible:

```text
install_headshot_guard_rebelion.bat
```

## Qué hace el guard y qué no hace

`extras/os_headshot_guard` solo ejecuta:

```lua
SetPedSuffersCriticalHits(PlayerPedId(), true)
```

No contiene:

- `SetEntityHealth`;
- `SetPedArmour`;
- `AddArmourToPed`;
- `ApplyDamageToPed`;
- `CancelEvent`;
- lógica para matar manualmente;
- eventos servidor-cliente de daño.

`Config.Mode = 'strict'` reafirma el estado cada frame cuando otro recurso usa `Wait(0)` con `false`. Es una sola native y debe iniciarse después del recurso conflictivo. La corrección definitiva sigue siendo eliminar el conflicto original.

## Corrección de armadura y ropa en V4

Las versiones anteriores usaban:

```xml
<LightlyArmouredDamageModifier value="100.000000" />
```

Ese valor era demasiado agresivo porque puede afectar daño contra peds protegidos, no únicamente la cabeza. La V4 usa:

```xml
<LightlyArmouredDamageModifier value="1.000000" />
```

Esto evita reducción adicional sin multiplicar indiscriminadamente los bodyshots. El casco se trata mediante:

- `IgnoreHelmets`;
- `ArmourPenetrating`;
- `Penetration`;
- multiplicadores de cabeza;
- critical hits activos en runtime.

## Garantía matemática

El perfil recomendado calcula un daño base mínimo para superar:

```text
vida efectiva objetivo × margen de seguridad
```

La V4 usa por defecto:

- vida efectiva objetivo: `1000`;
- margen: `1.25`;
- contrato estimado: `1250` puntos en la ruta de red.

El piso se redondea **hacia arriba a seis decimales** para evitar que la serialización XML deje el daño unas milésimas por debajo del objetivo.

## Perfiles principales

| Perfil | Uso |
|---|---|
| `rebelion_real_onetap_v4.json` | Recomendado: cuerpo balanceado y cabeza letal. |
| `original_body_real_onetap_v4.json` | Conserva el daño corporal original del pack. |
| `headshot_focus_real_onetap_v4.json` | Cuerpo casi nulo y prioridad total a cabeza. |
| `rp_serious_onetap.json` | RP táctico, TTK corporal largo. |
| `pvp_competitive_onetap.json` | PvP equilibrado. |
| `pvp_hardcore_onetap.json` | PvP de TTK corto. |
| `no_body_or_head_damage.json` | Desactiva daño. |

Lista completa:

```powershell
python run_rebalance.py --list-profiles
```

## Auditorías META incluidas

- armas `WEAPON_*` duplicadas;
- definiciones repetidas dentro del mismo archivo;
- META no registrados en `fxmanifest.lua`;
- daño base o modificador de red en cero;
- distancia/falloff insuficientes;
- flags no letales incompatibles;
- `IgnoreHelmets` y `ArmourPenetrating` ausentes;
- daño estimado por debajo del contrato.

La auditoría META valida el XML generado. La auditoría runtime valida el código visible. Los recursos protegidos por escrow o binarios no se pueden inspeccionar completamente; en ese caso, el guard sirve para confirmar si el problema era `critical hits = false`.

## Comandos de calidad

```powershell
python run_rebalance.py --validate-profiles profiles
python -m unittest discover -s tests -v
python -m compileall -q .
```

La V5 incluye **28 pruebas automáticas**.
