---
slug: editor
title: Editor de armas
group: Editor de armas
description: Cómo ajustar un arma, una categoría o todo el perfil, y qué significa cada columna.
---
# Editor de armas

El Editor modifica el **borrador** del perfil abierto. Nada se escribe en el servidor hasta que lo generes y apliques en el [Generador](11-generador.md).

## Elegir arma, perfil y ámbito

- **Perfil en edición** (arriba a la izquierda): el perfil que modificas. El activo lleva ★.
- Si el perfil es **oficial** (o archivado), el editor lo muestra en solo lectura con el aviso *Crear derivado*: un perfil de usuario que hereda todo y guarda solo tus cambios. Ver [Perfiles → Niveles](07-perfiles.md#niveles).
- **Lista de armas**: solo armas con `weapons.meta`. El número morado indica cuántos valores propios tiene esa arma en el perfil.
- **Aplicar cambios a**:
  - **Esta arma** → `weapons.WEAPON_X`.
  - **Categoría** → `groups.GROUP_X` (todas las armas del mismo `<Group>`).
  - **Global** → `defaults` (todas las armas que procese el perfil).

El valor por arma gana sobre el de la categoría y este sobre el global. El orden completo está en [Perfiles → Precedencia](07-perfiles.md#precedencia).

## Columnas de cada parámetro

| Columna | De dónde sale |
| --- | --- |
| **Original** | El `.bak` del archivo (el estado antes de la primera escritura de la herramienta) |
| **Actual** | El `weapons.meta` tal como está ahora |
| **Propuesto** | El resultado de ejecutar el motor real con el borrador (incluye presets, reglas y límites) |

En ámbito Categoría o Global, las columnas usan el arma seleccionada como referencia.

Cada parámetro muestra su **método** (META, Recurso, Native, Solo lectura) y su tag XML. El botón **?** explica qué controla y sus límites.

En un perfil derivado cada fila indica además su estado:

| Marca | Significado | Acción |
| --- | --- | --- |
| *en el perfil* | Valor propio | ↶ lo quita y vuelve a heredar |
| *heredado: N* | Viene del perfil base | **No heredar** escribe `null`: deja de aplicarse el valor del base |
| *no hereda* | Tiene `null` | ↶ vuelve a heredar |

La procedencia completa (regla del motor, preset, original…) está en **Armamento → detalle del arma**. Ver [Perfiles → Procedencia](07-perfiles.md#procedencia).

> [!NOTE]
> Si un valor queda fuera de los límites del motor, la fila lo avisa: el motor lo recortará al escribir. Si existe un multiplicador exacto para ese campo, también se indica.

## Módulos y valores sin efecto

Cada sección (daño, alcance, cadencia, recoil, precisión, recarga) tiene un **módulo** en el perfil. Si está en `original`, el motor **descarta** los valores de esa sección. Al editar un campo así, el panel cambia el módulo a `configured`. Si eso además activaría valores ya escritos en otras categorías, primero te los muestra y pide confirmación.

Los módulos de recoil y precisión con un preset (`low`, `normal`, `high`…) **recalculan** sus campos después de tus valores; el editor lo avisa.

## Pestañas

### Daño, Alcance, Cadencia, Recoil, Precisión, Munición, Proyectil

Parámetros del META agrupados. Los menos usados están en *Avanzados* dentro de cada sección. La ficha de cada uno está en la [Referencia de parámetros](#parametros).

- **Cadencia**: las RPM se calculan como `60 / TimeBetweenShots` (dividido por `AnimFireRateModifier` si es mayor que 1). En armas semiautomáticas es el máximo si se hace clic muy rápido.
- **Recoil**: en el META el recoil es error de puntería acumulado y sacudida de cámara. El retroceso vertical de cámara lo aplica `qbx_recoils` (pestaña Recursos).

### Cabeza

Los multiplicadores y distancias de cabeza los escribe la **política de cabeza**:

- **Modo**: heredar, sin multiplicador, normal u one-tap.
- **Multiplicador**, **distancia máxima** y **vida objetivo** (one-tap).
- **Multiplicador calculado desde el daño** (one-tap): calcula el multiplicador justo para matar con el daño final, en vez de usar un valor fijo alto.

> [!WARNING]
> El multiplicador de cabeza contra jugadores solo funciona si el objetivo tiene *critical hits* activos. Revisa **Diagnóstico → Auditar scripts**.

### Flags

Agrega o quita `WeaponFlags` concretas; el resto se conserva. Las flags que cambian el gatillo (`Automatic`, `OnlyFireOneShotPerTriggerPress`) conviene probarlas en el juego.

### Recursos

- **qbx_recoils**: recoil vertical de cámara por arma. Vacío = no cambiar; *Quitar la entrada* = sin recoil por script. Ver [FiveM → qbx_recoils](10-fivem.md#qbx-recoils).
- **ox_inventory**: peso, desgaste y munición, solo lectura.
- **Mecanismos no disponibles**: lo que no se puede controlar y por qué.

## Excepciones

En ámbito *Esta arma*:

- **No tocar esta arma** → `ignore_weapons`: el motor la omite aunque tenga valores.
- **Inofensiva** → `harmless_weapons`: daño y multiplicadores a 0, por encima de cualquier regla.

## Guardar

La barra *Cambios sin guardar* aparece en todas las páginas. **Guardar** escribe el perfil en su carpeta (`profiles/user/` o `profiles/server/`), valida antes y deja la versión anterior en el historial. Si alguien guardó el mismo perfil mientras lo editabas (otra pestaña o la terminal), el guardado se rechaza con un aviso de conflicto en vez de pisarlo. **Descartar** vuelve a la versión guardada.
