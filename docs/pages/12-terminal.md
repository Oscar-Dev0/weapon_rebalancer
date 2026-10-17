---
slug: terminal
title: Terminal (CMD)
group: Servidor
description: Menú interactivo, atajos de teclado y todos los comandos de wr.py con salidas reales.
---
# Terminal (CMD)

`wr.py` es la herramienta de terminal. Usa **el mismo motor, los mismos validadores, el mismo almacenamiento y el mismo historial** que el panel web: un cambio hecho en la terminal se ve en el panel y al revés. Las pruebas comprueban que ambos producen el mismo JSON y el mismo plan de generación.

Funciona en Linux, Windows (CMD, PowerShell, Windows Terminal) y por SSH. Solo necesita Python 3.10+, sin paquetes adicionales.

## Menú interactivo

Sin argumentos (y en una terminal real) abre el estudio:

```bash
python3 wr.py
```

```text
  ╭────────────────────────────────────────────────────────────────╮
  │                                                                │
  │   WEAPON REBALANCER                                            │
  │   FiveM Weapon Configuration Studio                            │
  │                                                                │
  │   Versión 7.1.0  •  OscarDev                                   │
  │                                                                │
  ╰────────────────────────────────────────────────────────────────╯

  ESTADO DEL SERVIDOR
  ────────────────────────────────────────────────────────────────
  Inventario         ox_inventory (422 ítems de arma)
  Armas              430 detectadas · 317 personalizadas · 199 META
  Perfil activo      Flow Caribe (flow_caribe)
  Validación         ✔ Correcta
  Cambios pendientes ✔ Ninguno: el pack coincide

  MENÚ PRINCIPAL
  ❯ [1]  Explorador de armas  buscar, filtrar y ver procedencia
    [2]  Editor de armas  cambiar parámetros por arma, categoría o global
    [3]  Perfiles  oficiales, servidor, usuario, historial
    [4]  Comparar perfiles  también contra original/actual
    [5]  Simulador de balance  daño, TTK, DPS
    [6]  Validar configuración  errores, advertencias y recomendaciones
    [7]  Generar recurso FiveM  vista previa, diff y aplicar
    [8]  Documentación
    [9]  Configuración  rutas, perfil activo, permisos
    [0]  Salir

  ↑↓ o número · Enter elegir · Esc salir
```

### Teclas {#teclas}

| Tecla | Acción |
| --- | --- |
| ↑ ↓ | Moverse por la lista |
| Número | Elegir esa opción directamente |
| Enter | Abrir / confirmar |
| `/` | Buscar dentro de la lista (admite espacios); Enter acepta |
| RePág / AvPág, Inicio / Fin | Saltar por listas largas |
| Esc, `q`, ← o Retroceso | Volver a la pantalla anterior |
| Ctrl+C | Salir sin escribir nada pendiente |

En las listas de selección múltiple (por ejemplo el simulador) Enter marca o desmarca y **Listo** termina. En la documentación, espacio o AvPág avanza, `q` sale.

### Pantallas

1. **Explorador de armas**: búsqueda, filtro por categoría, cambiar de perfil. Cada fila abre la ficha del arma con la procedencia de cada valor; desde ahí puedes editarla, compararla con el original o simularla.
2. **Editor de armas**: elige perfil, arma o categoría y ámbito (*Esta arma*, *Categoría*, *Global*), y edita por secciones (Daño, Cabeza, Alcance, Cadencia, Recoil, Precisión, Munición, Proyectil, Avanzados). Los cambios se acumulan en un borrador; **Revisar y guardar** muestra el diff, valida y pide confirmación. Si el perfil es oficial, ofrece crear un derivado.
3. **Perfiles**: oficiales, servidor, usuario (y archivados). Por perfil: activar, validar, armas afectadas, comparar, derivar, duplicar, exportar, historial/restaurar; en los editables también editar armas, editar nombre y descripción, y en los de usuario renombrar y borrar.
4. **Comparar perfiles**: dos perfiles, o un perfil contra *Valores originales (.bak)* o *META actual*.
5. **Simulador**: hasta 3 series (original, actual, propuesto), zona, distancia, blindaje y vida.
6. **Validar**: un perfil o todos, con vista previa sobre el pack.
7. **Generar**: vista previa, diff por archivo y aplicar (pide escribir `APLICAR`); historial y reversión.
8. **Documentación**: estas mismas páginas en la terminal.
9. **Configuración**: rutas, perfil activo y permiso de edición de los perfiles de servidor.

## Comandos {#comandos}

Todos los comandos funcionan sin menú, para scripts o para usar por SSH. Casi todos aceptan `--json`.

### Estado y armas

```bash
python3 wr.py status
```

```text
  ESTADO DEL SERVIDOR
  ────────────────────────────────────────────────────────────────
  Inventario         ox_inventory (422 ítems de arma)
  Armas              430 detectadas · 317 personalizadas · 199 META
  Perfil activo      Flow Caribe (flow_caribe)
  Validación         ✔ Correcta
  Cambios pendientes ✔ Ninguno: el pack coincide
```

```bash
python3 wr.py weapons -c pistol --limit 6
```

```text
  ARMAMENTO  perfil flow_caribe · 64 armas
  ────────────────────────────────────────────────────────────────
  Identificador              Nombre                 Categoría  Daño orig.  Daño perfil    RPM  Perfil  Estado
  ────────────────────────────────────────────────────────────────────────────────────────────────
  WEAPON_APPISTOL            AP Pistol              Pistolas           25           12    600  al día  ▲ aviso
  WEAPON_BLUEGLOCKS          BLUE GLOCK SWITCH      Pistolas           10            9    333  al día  ✔ ok
  WEAPON_CERAMICPISTOL       Ceramic Pistol         Pistolas           10           10    333  al día  ✔ ok
  WEAPON_COMBATPISTOL        Combat Pistol          Pistolas           27           10    162  al día  ▲ aviso
  …
```

Opciones: `-q TEXTO` busca, `-c` categoría (`pistol`, `smg`, `rifle`, `sniper`, `shotgun`, `mg`, `melee`…), `-p` perfil, `--changed` solo las que el perfil cambia, `--all` incluye armas sin `weapons.meta`, `--limit 0` sin límite.

La columna **Perfil** dice qué haría el perfil con esa arma: *cambia N* (campos pendientes de aplicar), *al día*, *omitida* (en `ignore_weapons`), *no la toca* o *sin META*. Un dato que no existe se muestra como **N/D**: la herramienta nunca rellena valores inventados.

```bash
python3 wr.py weapon WEAPON_PISTOL -p competitive
```

```text
  PISTOL  WEAPON_PISTOL · Pistolas · oficial
  ────────────────────────────────────────────────────────────────
  Hash               453432689 (453432689)
  ox_inventory       Pistol · munición ammo-9
  Recoil por script  0.3
  Perfil             competitive (cadena: realistic → competitive)

  Parámetro                        Original    Actual  Efectivo  Unidad       Procedencia
  ──────────────────────────────────────────────────────────────────────────────────────
  Tamaño del cargador                    12        12        12  balas   [O]  META actual (sin cambio)
  Daño base                              26        10        67  pts     [S]  competitive · categoría (sobres…
  Multiplicador de extremidades         0.5      0.68       0.6  x       [H]  realistic · categoría (heredado)
  …
```

**Procedencia** de cada valor efectivo:

| Marca | Significado |
| --- | --- |
| `[P]` | Lo declara el propio perfil |
| `[H]` | Heredado de un perfil base (se indica cuál) |
| `[S]` | El perfil sobrescribe un valor que heredaba |
| `[R]` | Lo fija una regla del motor (preset, regla por cadencia, multiplicador exacto, política de cabeza…) |
| `[O]` | Original: el META actual, sin cambios |
| `[X]` | Declarado pero sin efecto (módulo en `original`, arma omitida…) |

`--all` muestra todos los parámetros, no solo los principales.

### Perfiles

```bash
python3 wr.py profiles          # --all incluye los archivados (legacy)
```

```text
  PERFILES  ★ = activo · usa --all para ver los archivados
  ────────────────────────────────────────────────────────────────
  Nivel     Identificador  Nombre              Hereda de    Editable   Rev.
  ─────────────────────────────────────────────────────────────────────────
  Oficial   balanced       Balanced RP         N/D          protegido     1
  Oficial   competitive    Competitive PvP     realistic    protegido     1
  Oficial   realistic      Realistic Combat    N/D          protegido     1
  Servidor  flow_caribe ★  Flow Caribe  competitive  sí            1
```

| Comando | Qué hace |
| --- | --- |
| `profile show ID` | Detalle: metadatos, cadena de herencia, validación |
| `profile activate ID` | Marca el perfil activo (lo valida antes) |
| `profile validate ID` | Valida estructura, herencia y contradicciones |
| `profile affected ID` | Armas que el perfil cambiaría |
| `profile create NUEVO [--extends BASE] [--name …] [--description …]` | Perfil de usuario vacío o derivado |
| `profile derive BASE NUEVO [--name …]` | Derivado: hereda todo y guarda solo diferencias |
| `profile duplicate ID NUEVO [--name …]` | Copia completa e independiente (sin herencia) |
| `profile rename ID [NUEVO] [--name …]` | Solo perfiles de usuario |
| `profile delete ID [--yes]` | Solo usuario; va a `data/trash/` |
| `profile export ID [-o archivo] [--resolved \| --legacy]` | JSON tal cual, con la herencia aplicada o para la CLI antigua |
| `profile import ARCHIVO [--id NUEVO] [--yes]` | Importa como perfil de usuario (valida y migra v3–v8) |
| `profile history ID` | Versiones guardadas |
| `profile restore ID ARCHIVO [--yes]` | Restaura una versión del historial byte a byte |

```bash
python3 wr.py profile derive competitive mi_pvp --name "Mi PvP"
```

```text
  ✔ Perfil de usuario “mi_pvp” creado en profiles/user/.
```

### Editar valores

```bash
python3 wr.py set PERFIL OBJETIVO campo=valor [campo=valor …] [--yes]
python3 wr.py headshot PERFIL OBJETIVO mode=onetap multiplier=1.5 distance=150 [--yes]
```

- `OBJETIVO`: `WEAPON_X`, `GROUP_X` o `global`.
- `campo=inherit` escribe `null`: deja de usar el valor heredado del perfil base.
- `campo=unset` quita el valor del perfil: vuelve a heredar.
- Los nombres de campo están en la [Referencia de parámetros](#parametros) (`python3 wr.py params damage`).

Antes de guardar muestra el diff y valida; pide confirmación salvo con `--yes`. Sin terminal interactiva **exige** `--yes`.

```text
  CAMBIOS EN MI_PVP
  ────────────────────────────────────────────────────────────────
  groups.GROUP_PISTOL.fields.damage  — › 45
  ✔ Validación correcta.
  ✔ Guardado. La versión anterior está en el historial de mi_pvp.
```

Un perfil oficial no se modifica:

```text
$ python3 wr.py set competitive GROUP_PISTOL damage=45 --yes
  ✖ “competitive” es un perfil oficial protegido: no se puede modificar.
     › Crea un perfil derivado: hereda todo de “competitive” y guarda solo tus cambios.
```

> [!NOTE]
> Si el cambio activa un módulo que estaba en `original` y eso despierta valores ya escritos en otras categorías, la terminal los lista y pide confirmación aparte, igual que el panel.

### Comparar

```bash
python3 wr.py compare balanced competitive -w WEAPON_CARBINERIFLE \
  -k damage,time_between_shots,weapon_range,recoil_shake_amplitude,network_headshot
```

```text
  BALANCED  VS  COMPETITIVE  1 arma(s) con resultado distinto · 309 diferencias en el JSON
  ────────────────────────────────────────────────────────────────

  WEAPON_CARBINERIFLE
    Parámetro                               balanced  competitive
    ───────────────────────────────────────────────────────────────────
    Daño base                             [R]        30  [S]         50  ↑ sube
    Multiplicador de cabeza contra juga…  [R]       1.7  [R]       1500  ↑ sube
    Sacudida de cámara                    [R]     0.333  [R]        0.1  ↓ baja
    Tiempo entre disparos                 [O]     0.135  [H]      0.125  ↓ baja
    Alcance máximo                        [R]       120  [H]        320  ↑ sube
```

`original` y `current` se pueden usar en lugar de un perfil: `wr.py compare original flow_caribe -w WEAPON_PISTOL`. En color, ↑ sale en verde, ↓ en rojo y sin cambio en gris.

### Simular

```bash
python3 wr.py simulate WEAPON_CARBINERIFLE:original WEAPON_CARBINERIFLE:proposed -p competitive
```

```text
  SIMULADOR (TEÓRICO)  player · torso · 15 m · vida 100 · blindaje 0
  ────────────────────────────────────────────────────────────────
  Serie                           Daño/disparo  Disparos            TTK   RPM   DPS  Nota
  ───────────────────────────────────────────────────────────────────────────────────────
  WEAPON_CARBINERIFLE (original)            32         4         0.41 s   444   237
  WEAPON_CARBINERIFLE (proposed)     50 (+56%)         2  0.12 s (-69%)   480   400
  Cálculo teórico a partir del META. No sustituye una prueba de daño en el servidor.
```

Opciones: `--zone torso|head|limbs`, `--distance`, `--armour`, `--health`, `--target player|npc`.

### Validar

```bash
python3 wr.py validate                   # todos
python3 wr.py validate flow_caribe --preview
```

```text
  ✔ flow_caribe   ✖ 0 bloqueantes  ▲ 0 advertencias  ● 18 recomendaciones
     Aplicarlo cambiaría 0 archivos / 0 armas · repetible: sí · generador: compatible
  ● Recomendación  WEAPON_GADGETPISTOL.damage: declaraste 30.0 y el resultado es 210.0 (multiplicador exacto ×7 en weapon_field_multipliers).
     › Es correcto si esa regla es intencional; si no, ajusta o quita la regla indicada.
  …
```

Tres niveles: **Bloqueante** (impide guardar o aplicar), **Advertencia** (se puede guardar, conviene revisar) y **Recomendación** (informativo). `check` es un alias de `validate`. Ver [Perfiles → Validaciones](07-perfiles.md#validaciones).

### Generar y revertir

```bash
python3 wr.py generate -p flow_caribe
```

```text
  GENERADOR · FLOW_CUSTOM  plan a2b48d2104f9
  ────────────────────────────────────────────────────────────────
  Archivos a escribir  0
  Armas que cambian    0
  One-tap              39/39
  Repetible            sí
  ✔ Sin avisos de efecto.
  Vista previa: no se escribió nada. Usa --apply para aplicar (pide escribir APLICAR).
```

| Comando | Qué hace |
| --- | --- |
| `generate -p ID --diff RUTA` | Diff exacto de un archivo del plan |
| `generate -p ID --apply` | Aplica; en terminal pide escribir `APLICAR` |
| `generate -p ID --apply --confirm APLICAR` | Aplica sin preguntar (scripts) |
| `transactions` | Historial de aplicaciones |
| `rollback ID --confirm APLICAR` | Revierte una aplicación byte a byte |

Cada archivo se respalda en `data/backups/` antes de escribirse.

### Otros

| Comando | Qué hace |
| --- | --- |
| `params [sección] [--all]` | Referencia de parámetros en la terminal |
| `docs list` / `docs show SLUG` / `docs build` | Esta documentación |
| `settings show` / `settings set clave=valor` | Configuración del workspace (`active_profile`, `server_profiles_editable`, rutas…) |
| `serve [--port 8765] [--rotate MIN] [--idle MIN]` | Panel web (ver [Acceso y sesión](02-instalacion.md#acceso)) |
| `token` | Enlace de acceso vigente del panel (sirve una vez) |
| `scan` | Reescanea ox_inventory y los packs |
| `migrate [--write]` | Migra a v8 perfiles de usuario en formato antiguo |
| `rebalance …` | CLI original del motor (igual que `run_rebalance.py`) |

## Salida para scripts {#scripts}

- `--json` devuelve los mismos datos que la API del panel.
- Sin terminal interactiva no hay colores, ni menús, ni preguntas: los comandos que escriben exigen `--yes` o `--confirm APLICAR`.
- Si cortas la salida (`wr.py weapons | head`) termina en silencio.

Códigos de salida:

| Código | Significado |
| --- | --- |
| `0` | Correcto |
| `1` | Validación fallida o cancelado por el usuario |
| `2` | Error de uso o de la aplicación (perfil protegido, conflicto, ruta inválida…) |
| `130` | Interrumpido con Ctrl+C |

## Colores, Windows y SSH {#compatibilidad}

- Colores ANSI de 256 con la paleta del panel. Se desactivan con `--no-color`, `NO_COLOR=1`, `TERM=dumb` o cuando la salida no es una terminal; `FORCE_COLOR=1` los fuerza.
- `--ascii` (o `WR_ASCII=1`) usa bordes y símbolos ASCII para consolas sin UTF-8.
- **Windows**: activa el modo VT automáticamente; en consolas antiguas usa `--ascii`. Las teclas se leen con `msvcrt`.
- **SSH**: funciona igual; si los bordes salen rotos, revisa que la sesión use UTF-8 o usa `--ascii`.
- Las tablas se adaptan al ancho de la terminal y truncan con `…`.

> [!TIP]
> Si dos personas editan el mismo perfil a la vez (terminal y panel), el segundo guardado se rechaza con un aviso de conflicto en vez de pisar el primero. Vuelve a abrir el perfil y repite el cambio.
