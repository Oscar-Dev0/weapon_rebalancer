---
slug: perfiles-oficiales
title: Perfiles oficiales
group: Perfiles
description: Los cuatro perfiles principales (Balanced, Realistic, Competitive y Flow Custom), qué hace cada uno, sus números medidos y cómo derivar uno propio.
---
# Perfiles oficiales

Desde la versión 7.1 la herramienta trae **cuatro perfiles principales**. Reemplazan a los 18 perfiles anteriores, que se conservan intactos en `profiles/legacy/` (ver [Migración](06-perfiles-oficiales.md#migracion)).

```text
Catálogo original (.bak + META)
        │
        ├── balanced      Balanced RP          (oficial, protegido)
        ├── realistic     Realistic Combat     (oficial, protegido)
        │     └── competitive  Competitive PvP (oficial, protegido, hereda de realistic)
        │           └── flow_custom  Flow Caribe Custom (servidor, editable)
        └── tus perfiles  profiles/user/       (usuario, editables)
```

| Identificador | Nombre | Nivel | Hereda de | Editable |
| --- | --- | --- | --- | --- |
| `balanced` | Balanced RP | Oficial | — | No (protegido) |
| `realistic` | Realistic Combat | Oficial | — | No (protegido) |
| `competitive` | Competitive PvP | Oficial | `realistic` | No (protegido) |
| `flow_custom` | Flow Caribe Custom | Servidor | `competitive` | Sí, con historial |

> [!NOTE]
> Los perfiles **oficiales** no se modifican. Si quieres cambiar uno, crea un **perfil derivado**: hereda todo del oficial y guarda solo tus cambios. El panel y la terminal lo ofrecen automáticamente cuando intentas editar un oficial.

## Balanced RP {#balanced}

**Objetivo:** combate consistente y reconocible, sin armas personalizadas más fuertes que las del juego base.
**Para:** servidores de roleplay general que quieren un punto de partida neutro.

- Armas oficiales de GTA V: valores del `.bak` (antes de cualquier modificación) y tabla de referencia vanilla incluida.
- Armas personalizadas: daño, alcance y caída normalizados a la referencia de su categoría (×1.0).
- Repara daño, modificadores de red y alcances en 0 o ausentes.
- No toca recoil, precisión ni cadencia: cada arma conserva los suyos.

> [!WARNING]
> Necesita los `.bak` del pack: parte siempre de ellos (`restore.from_backup`). Las armas personalizadas pierden los valores que trae su META; es intencional.

## Realistic Combat {#realistic}

**Objetivo:** que el control del arma y la colocación del disparo pesen más que la cadencia.
**Para:** servidores de roleplay serio o táctico.

- Daño corporal por categoría: pistola 34, SMG 25, rifle 30, escopeta 24 por perdigón, MG 28, francotirador 80.
- Cabeza **one-tap** dentro de 300 m, también con blindaje y casco nativo.
- Recoil preset `high` en todas las armas procesadas.
- Cadencia fija por categoría.

> [!WARNING]
> Es una aproximación de diseño, no una simulación física verificada. El one-tap requiere *critical hits* activos (ver [FiveM](10-fivem.md)). Hereda de `config.py` los presets de cuerpo a cuerpo y el alcance ×1.5 de revólveres (`engine_defaults`).

## Competitive PvP {#competitive}

**Objetivo:** enfrentamientos rápidos y predecibles donde gana quien acierta primero.
**Para:** servidores o modos PvP, arenas y eventos competitivos.

- Hereda de Realistic las distancias, caídas y la política de cabeza.
- Daño corporal por categoría: pistola 67, SMG 40, rifle 50, escopeta 36 por perdigón, MG 45, francotirador 100.
- Recoil preset `low` y precisión preset `high`.
- Cadencia fija por categoría.

> [!WARNING]
> Los daños se diseñaron para **200 de vida**. Con la muerte en 100 (este servidor) el TTK real es la mitad: ver la tabla de abajo.

## Flow Caribe Custom {#flow-custom}

**Objetivo:** mantener exactamente el balance actual del servidor, editable por categoría y por arma.
**Para:** administradores de Flow Caribe.

- Es el perfil `flow_caribe` (v6.12) migrado **sin cambios de comportamiento**: la configuración del motor resultante es idéntica (lo comprueban las pruebas).
- Daño adaptativo por cadencia, cabeza ×1.5 general, one-tap dinámico solo en la lista de pistolas fijadas, revólver y francotiradores, .50 reforzada y recoil casi nulo salvo en armas one-tap tiro a tiro.
- Reglas por arma: 26 armas configuradas, multiplicadores exactos (revólver ×6, Gadget ×7).
- Es el único perfil de nivel **servidor**: se puede editar directamente y cada guardado deja la versión anterior en el historial.

### Cómo funciona la herencia de flow_custom

`flow_custom` declara `"extends": "competitive"` y guarda **solo lo que difiere** de Competitive. El motor primero resuelve `realistic → competitive` y después aplica las diferencias de `flow_custom`. Lo que Flow Custom no declara se toma de Competitive, y donde Flow Custom quiere *quitar* un valor heredado escribe `null` (ver [Perfiles → Herencia](07-perfiles.md#herencia)).

Se eligió Competitive porque es la base con la que el delta queda más pequeño. Aun así el ahorro es modesto (20 454 frente a 21 139 bytes) porque la configuración de Flow es realmente propia: reglas por arma, clasificador de cadencia y multiplicadores exactos que ningún oficial tiene.

### Cambiar el perfil base

En **Constructor → General → Hereda de** elige otro perfil, revisa y guarda.

> [!DANGER]
> El delta se calculó contra Competitive. Si cambias la base, todo lo que Flow Custom **no** declara pasará a salir del nuevo perfil y el resultado cambiará. Revisa **Comparar** (`wr.py compare flow_custom competitive`) y la vista previa del Generador antes de aplicar. Siempre puedes volver atrás con **Historial → Restaurar**.

## Números medidos {#ttk}

Resultado del simulador con el motor real sobre el pack del servidor: **jugador, torso, 15 m, sin blindaje, 100 de vida**. Formato: *disparos para matar · TTK*.

| Arma | Original (.bak) | Balanced | Realistic | Competitive | Flow Custom |
| --- | --- | --- | --- | --- | --- |
| Pistola | 4 · 1.11 s | 4 · 1.11 s | 3 · 0.36 s | 2 · 0.18 s | 10 · 3.33 s |
| Pistola .50 | 2 · 0.52 s | 2 · 0.52 s | 3 · 0.36 s | 2 · 0.18 s | 4 · 1.56 s |
| SMG | 5 · 0.47 s | 5 · 0.47 s | 4 · 0.32 s | 3 · 0.21 s | 9 · 0.94 s |
| Carabina | 4 · 0.41 s | 4 · 0.41 s | 4 · 0.38 s | 2 · 0.12 s | 8 · 0.95 s |
| Escopeta (Pump) | 1 · 0 s | 1 · 0 s | 1 · 0 s | 1 · 0 s | 2 · 0.80 s |
| MG | 3 · 0.27 s | 4 · 0.41 s | 4 · 0.35 s | 3 · 0.23 s | 8 · 0.96 s |
| Francotirador | 1 · 0 s | 1 · 0 s | 2 · 1.25 s | 1 · 0 s | 3 · 3.13 s |

**Cabeza:** Realistic y Competitive matan de un disparo con todas las armas. Flow Custom hace one-tap con pistolas fijadas y francotiradores; SMG necesita 6 disparos, rifle 5 y MG 6. Balanced se comporta como el juego base.

Puedes repetir cualquier fila:

```bash
python3 wr.py simulate WEAPON_PISTOL:original WEAPON_PISTOL:proposed -p competitive
python3 wr.py simulate WEAPON_CARBINERIFLE:proposed -p flow_custom --zone head
```

> [!WARNING]
> Son cálculos teóricos a partir del META. La prueba definitiva es en el juego.

## Desequilibrios detectados {#desequilibrios}

La herramienta **no los corrige sola**: cambiarlos es una decisión de diseño del servidor. Quedan documentados:

1. **Competitive para 200 de vida.** Con 100 de vida, pistolas y rifles matan en 2 disparos (≤ 0.23 s). Si se quiere el TTK de diseño, deriva el perfil y baja el daño por categoría a la mitad, o ajusta la vida.
2. **Realistic y Competitive aplanan cada categoría.** La pistola y la pistola pesada tienen el mismo daño y la misma cadencia: se pierde la identidad de cada arma dentro de su categoría.
3. **Flow Custom tiene TTK de torso largos** (pistola 10 disparos, rifle 8), compensados con cabeza ×1.5 y one-tap selectivo. Es el balance actual del servidor; se mantuvo tal cual.
4. **Realistic es una aproximación.** No hay datos balísticos verificados detrás de sus valores; el nombre describe la intención, no una medición.

## Crear tu propio perfil

La forma recomendada es **derivar** de un oficial:

```bash
python3 wr.py profile derive competitive mi_pvp --name "Mi PvP"
python3 wr.py set mi_pvp GROUP_PISTOL damage=45
python3 wr.py validate mi_pvp --preview
```

O en el panel: **Perfiles → (clic en el perfil) → Crear perfil derivado**. El nuevo perfil va a `profiles/user/`, hereda todo y solo guarda lo que cambies. Ver [Terminal](12-terminal.md) y [Perfiles](07-perfiles.md).

## Migración de los perfiles anteriores {#migracion}

| Perfil anterior | Destino |
| --- | --- |
| `vanilla_repair_custom_plus15_absolute_v6` | **balanced** (sin el +15 % a armas personalizadas ni la regla de revólver a 350) |
| `rp_serious_onetap` | **realistic** (recoil `normal` → `high`) |
| `pvp_competitive_onetap` | **competitive** (resultado idéntico) |
| `flow_caribe` | **flow_custom** (configuración idéntica) |
| `head_only`, `no_body_or_head_damage`, `original_body_real_onetap`, `pvp_hardcore_onetap`, `rebelion_balanced_v3`, `vanilla_normal_custom_plus15_revolver_onetap` | **Pendientes**: deltas listos para importar en `profiles/migrations/2026-10-12_v8/pending/` |
| `pvp_no_tank`, `headshot_focus_*`, `original_body_real_onetap_v4`, `rebelion_real_onetap_v4`, `rebelion_server` | Archivados: equivalentes exactos de otro perfil |
| `profile_template`, `full_meta_template` | Archivados: plantillas de ejemplo |

Para recuperar un pendiente como perfil de usuario:

```bash
python3 wr.py profile import profiles/migrations/2026-10-12_v8/pending/pvp_hardcore_onetap.json --id hardcore
```

El informe completo, con las verificaciones del motor, está en `profiles/migrations/2026-10-12_v8/REPORT.md`. Ver también [Auditoría](15-auditoria.md#migracion-perfiles).
