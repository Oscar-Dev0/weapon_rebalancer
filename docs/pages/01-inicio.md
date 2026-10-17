---
slug: inicio
title: Introducción
group: Primeros pasos
description: Qué hace Weapon Rebalancer, qué controla de verdad y cómo está organizado.
---
# Introducción

Weapon Rebalancer es una herramienta en Python para **balancear las armas de un servidor FiveM** editando sus `weapons.meta` de forma controlada. Incluye un panel web local y una terminal interactiva (`wr.py`) para configurar cada arma, crear perfiles de balanceo, comparar resultados, simularlos y aplicarlos con respaldo. Panel y terminal usan el mismo motor y los mismos perfiles.

> [!SUCCESS]
> Todo lo que aparece en el panel corresponde a un mecanismo real: un tag del META, una entrada de `qbx_recoils` o un native de un recurso generado. Lo que no se puede controlar se muestra como **No compatible** con su explicación.

![Flujo de datos](img/flujo.svg)

## Qué puedes hacer

- **Ver todo el armamento** del servidor: las armas de `ox_inventory` cruzadas con los `weapons.meta` de los packs, con su valor original (`.bak`), actual y propuesto.
- **Editar cada arma** por secciones (daño, cabeza, alcance, cadencia, recoil, precisión, munición, proyectil, flags) o aplicar valores a una categoría completa.
- **Partir de cuatro perfiles principales** ([Balanced, Realistic, Competitive y Flow Custom](06-perfiles-oficiales.md)) y **crear los tuyos** heredando de ellos, con historial de versiones y restauración.
- **Validar** que cada valor declarado tenga efecto real: el panel ejecuta el motor en memoria y avisa si un valor lo pisa un preset, un módulo en `original` o un límite del motor.
- **Simular** daño por disparo, disparos para matar, TTK y DPS a distintas distancias.
- **Generar y aplicar** los cambios al servidor como una transacción reversible.
- **Diagnosticar** armas sin META, duplicadas, municiones inexistentes y scripts que alteran el daño en ejecución.

## Qué controla y qué no

| Mecanismo | Ejemplos | Cómo se aplica |
| --- | --- | --- |
| **META** (`weapons.meta`) | Daño, multiplicadores, alcance, caída, cadencia, recoil, precisión, cargador, recarga, flags | El generador edita el tag; efecto al reiniciar el recurso del arma |
| **Recurso** | Recoil vertical de cámara (`qbx_recoils`), datos de `ox_inventory` | `qbx_recoils` lo edita el generador; `ox_inventory` es solo lectura |
| **Native** | Critical hits, guard de daño | Recursos Lua (`os_headshot_guard`, guard generado opcional) |
| **No compatible** | Recoil horizontal, ráfaga del jugador, daño por material | Se documenta; no hay control ficticio |

Más detalle en [FiveM: qué controla cada cosa](10-fivem.md).

## Estructura del proyecto

| Carpeta | Contenido |
| --- | --- |
| `weapon_rebalancer/` | `engine/` y `meta/` (motor y edición de META), `runtime/`, `core/`, `adapters/`, `catalog/`, `profile_store/`, `services/`, `api/` y `cli/` (terminal) |
| `web/` | Panel web (HTML, CSS y módulos JS sin compilación) |
| `docs/` | Esta documentación |
| `profiles/` | Perfiles JSON por nivel: `official/`, `server/` (`flow_caribe`), `user/` y `schemas/` |
| `data/` | Configuración del workspace, historial, respaldos y logs (no se versiona) |
| `tests/` | Pruebas automáticas |

## Ruta recomendada

1. [Instalación](02-instalacion.md): arrancar el panel o la terminal y revisar las rutas.
2. [Primeros pasos](03-primeros-pasos.md): de cero a un perfil aplicado.
3. [Perfiles oficiales](06-perfiles-oficiales.md): qué hace cada uno de los cuatro.
4. [Editor de armas](04-editor.md) y [Referencia de parámetros](#parametros).
5. [Perfiles](07-perfiles.md) y [Constructor](08-constructor.md).
6. [Balanceo y simulador](09-balanceo.md).
7. [Terminal](12-terminal.md), [Generador](11-generador.md) y [Solución de problemas](13-solucion-problemas.md).
