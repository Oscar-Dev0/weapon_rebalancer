# Weapon Rebalancer 7.1

Herramienta para balancear las armas de un servidor FiveM editando sus `weapons.meta` de forma controlada, con **terminal interactiva**, **panel web**, cuatro perfiles principales con herencia, simulador y generador con respaldo y reversión. Terminal y panel usan el mismo motor, los mismos perfiles y el mismo historial.

Requiere **Python 3.10 o superior**. No necesita instalar paquetes.

## Inicio rápido

```bash
cd /fivem/pruebas/weapon_rebalancer
python3 wr.py            # terminal interactiva (flechas, números, / para buscar)
python3 wr.py serve      # panel web
```

El panel muestra un enlace con `?token=` que sirve una sola vez; `python3 wr.py token` da el vigente (desde tu PC: túnel SSH o reenvío de puertos de VS Code al `8765`). La documentación completa está en el panel → **Documentación**, en `docs/index.html` o en la terminal (`wr.py docs list`).

## Perfiles

| Perfil | Nivel | Para qué |
| --- | --- | --- |
| `balanced` — Balanced RP | Oficial (protegido) | Valores de GTA V; armas personalizadas llevadas a la referencia de su categoría |
| `realistic` — Realistic Combat | Oficial (protegido) | Daño moderado, recoil alto, cabeza one-tap |
| `competitive` — Competitive PvP | Oficial (protegido), hereda de `realistic` | TTK corto, recoil bajo, precisión alta |
| `flow_custom` — Flow Caribe Custom | Servidor (editable) | Balance actual de Flow Caribe; hereda de `competitive` y guarda solo sus diferencias |

Para modificar un oficial se crea un **perfil derivado** (`wr.py profile derive competitive mi_perfil`), que va a `profiles/user/`. Los 18 perfiles anteriores están intactos en `profiles/legacy/`; el informe de la migración está en `profiles/migrations/2026-10-12_v8/REPORT.md`.

## Qué incluye

| Módulo | Para qué |
| --- | --- |
| **Dashboard / estado** | Resumen del armamento, perfil activo frente al pack y problemas principales |
| **Armamento** | Todas las armas de ox_inventory cruzadas con los `weapons.meta`: original (`.bak`), actual, efectivo y de dónde sale cada valor |
| **Editor** | Ajustes por arma, categoría o global, con ayuda contextual y valores calculados por el motor real |
| **Perfiles** | Oficiales, servidor y usuario; derivar, importar, exportar, comparar, historial y restauración |
| **Constructor** | Perfil completo paso a paso sin editar JSON (panel) |
| **Simulador** | Daño por disparo, disparos para matar, TTK y DPS por distancia (teórico) |
| **Generador** | Vista previa, diff, aplicación como transacción reversible |
| **Diagnóstico / validación** | Bloqueantes, advertencias y recomendaciones; armas sin META, duplicadas, scripts que alteran el daño |

Todo lo que se muestra tiene un efecto real: un tag del META, una entrada de `qbx_recoils` o un native de un recurso generado. Lo que no se puede controlar se muestra como **No compatible**, y los datos que faltan como **N/D**.

## Terminal

```bash
python3 wr.py status                                # estado del servidor
python3 wr.py weapons -q glock -p competitive       # tabla de armas con un perfil
python3 wr.py weapon WEAPON_PISTOL                  # ficha con la procedencia de cada valor
python3 wr.py profiles                              # perfiles (--all incluye archivados)
python3 wr.py set mi_perfil GROUP_PISTOL damage=55  # cambia un valor (diff + confirmación)
python3 wr.py compare balanced competitive -w WEAPON_PISTOL
python3 wr.py validate flow_custom --preview
python3 wr.py generate -p flow_custom               # vista previa (--apply para escribir)
python3 -m unittest discover -s tests
```

`--json` en casi todos los comandos, `--no-color`/`NO_COLOR=1` y `--ascii` para consolas limitadas. Guía completa: `docs/pages/12-terminal.md`.

`python3 wr.py rebalance …` (o `run_rebalance.py`) mantiene todas sus opciones (`--profile` acepta un id o una ruta, `--write`, `--audit-runtime`, …).

## Seguridad

- El panel escucha en `127.0.0.1`. Sin sesión no entrega nada; se entra con un enlace de un solo uso que cambia cada 30 min (`python3 wr.py token`), la sesión caduca y los intentos fallidos bloquean.
- Solo escribe en los packs configurados, `qbx_recoils`, `profiles/` y `data/`. Los perfiles oficiales no se modifican.
- Guardar un perfil valida antes, respalda la versión anterior y rechaza ediciones simultáneas en lugar de pisarlas.
- Antes de escribir en el servidor copia cada archivo a `data/backups/`; escritura atómica y verificación.
- Nada se aplica sin escribir `APLICAR`.

## Estructura

```text
weapon_rebalancer/   engine/ meta/ runtime/ (motor) + core/ adapters/ catalog/ profile_store/ services/ api/ cli/
web/                 panel web (ES modules, sin compilación)
docs/                documentación (pages/*.md → js/docs-data.js); legacy/ = guías V4–V6
extras/              os_headshot_guard y descargador de META de referencia
profiles/            official/ server/ user/ legacy/ schemas/ migrations/
data/                workspace, historial, respaldos y logs (no se versiona)
tests/               pruebas automáticas
```

Arquitectura, API y cómo extenderla: `docs/pages/14-desarrollo.md`. Diagnóstico y migraciones: `docs/pages/15-auditoria.md`.

---

# Documentación histórica

Las secciones siguientes describen las versiones 6.x y anteriores. Los archivos `.bat` que mencionan no forman parte de este repositorio.

## Weapon Rebalancer META V6.1

Requiere **Python 3.10 o superior**.

## Perfil recomendado: vanilla normal + custom normalizada 15%

V6.1 corrige el exceso de daño de V6.0. Las armas custom ya **no toman su propio `Damage` y lo multiplican por 1.15**. Primero se normalizan contra una referencia equilibrada del mismo grupo y después reciben solamente el `+15%`.

Ejemplo real:

```text
Custom de pistola que llega con Damage=80
V6.0: 80 × 1.15 = 92       (demasiado fuerte)
V6.1: 27 × 1.15 = 31.05    (solo 15% sobre la referencia de pistola)
```

También se normalizan los modificadores ocultos que podían volver a inflar el resultado: daño de red, extremidades, armadura ligera, vehículo, falloff y headshot.

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

3. Agrega el guard al final del bloque de recursos de armas/combate:

```cfg
ensure os_weapon_damage_guard
```

4. Dentro del juego ejecuta:

```text
/osweaponstatus
```

## Valores normalizados para custom

| Grupo | Base vanilla equilibrada | Custom +15% |
|---|---:|---:|
| Pistola | 27.00 | 31.05 |
| SMG | 22.00 | 25.30 |
| Rifle | 30.00 | 34.50 |
| MG | 31.00 | 35.65 |
| Escopeta | 29.00 | 33.35 |
| Sniper | 101.00 | 116.15 |

El revólver mantiene su regla especial posterior: `350` al torso y `0.25` en extremidades.

## Orden de cálculo

```text
referencia META vanilla para armas oficiales
                    ↓
reparación de tags cero o ausentes
                    ↓
custom normalizada contra referencia de su grupo
                    ↓
+15% solamente sobre esa referencia normalizada
                    ↓
reglas especiales de familia (revólver)
                    ↓
validación, auditoría y guard runtime
```

V6.1 incluye **34 pruebas automáticas**.

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
