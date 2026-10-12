---
slug: auditoria
title: Auditoría y migración (v7)
group: Desarrollo
description: Diagnóstico del proyecto antes de la modernización y plan de migración aplicado.
---
# Auditoría y migración (v7)

Diagnóstico realizado el 2026-10-12 sobre `weapon_rebalancer` 6.12.0 y el servidor de pruebas, antes de modernizarlo.

## Estado inicial

- Motor Python sólido (~5.000 líneas) con 38 pruebas en verde: edita los META en su sitio, entiende bloques anidados y tiene auditorías de headshot y de scripts.
- Solo línea de comandos. Sin interfaz, caché, historial de perfiles ni integración con ox_inventory.
- 18 perfiles con `schema_version` 3, 4, 5 y 7 usado como número de generación, no de formato.

## Problemas encontrados en el código

| # | Problema | Impacto | Corrección |
| --- | --- | --- | --- |
| 1 | Ruta del pack fija en `engine/config.py` | No portable | Workspace en `data/workspace.json` con detección |
| 2 | El tokenizador XML se repetía en cada lectura de campo (11.289 veces por ejecución) | 4,1 s por pasada | Caché por bloque: 0,47 s, salida idéntica |
| 3 | El resumen contaba anotaciones del motor como cambios | `flow_caribe` decía “130 archivos cambiados” cuando cambiaba 0 | `content_changed` real |
| 4 | Un perfil vacío heredaba `pvp_lethal`, one-tap ×1500 y presets de cuerpo a cuerpo | Un perfil “en blanco” no era neutral | `engine_defaults: false` |
| 5 | `modules.headshot` activo sin `headshot.mode` hereda one-tap ×1500 | Riesgo silencioso | Aviso `headshot_mode_inherited` y el panel siempre declara el modo |
| 6 | Escritura no atómica y lectura con `errors='ignore'` | Posible archivo a medias o pérdida de bytes no UTF-8 | Escritura atómica, verificación y bloqueo UTF-8 en el generador |
| 7 | El guard de daño generado reaplicaba natives en cada frame | CPU en cliente | 250 ms por defecto |
| 8 | `docs/legacy/PROFILE_REFERENCE.md` documentaba el preset antes de `defaults` | El orden real es el inverso | Documentado según el código |
| 9 | `release_manifest.json` y el README citan `.bat` y notas de versión que no existen | Confusión | Se actualizaron README y manifiesto |
| 10 | La auditoría de registro marcaba archetypes/components como META sin `WEAPONINFO_FILE` | 6 falsos positivos (MarkoMods) | Solo se revisan archivos con `CWeaponInfo` |
| 11 | 18 módulos del motor sueltos en la raíz del paquete | Difícil de navegar | Subpaquetes `engine/`, `meta/`, `runtime/`; CLI en `cli.py` |

## Problemas encontrados en los perfiles

- `validation.require_runtime_critical_hits` aparece en 6 perfiles y **ningún código lo lee**.
- En `head_only`, `headshot_focus_*` y los `pvp_*`, los valores de recoil y precisión por categoría **los pisa el preset del módulo** (`modules.recoil/accuracy`): nunca llegan al META.
- `flow_caribe`: 18 valores por arma los ajusta otra regla (multiplicador ×7 de la Gadget Pistol, recoil tiro a tiro). Es intencional; el panel lo muestra como informativo.
- Los 18 perfiles son repetibles (aplicarlos dos veces da el mismo resultado).

## Estado del servidor de pruebas

- El pack **coincide exactamente** con `flow_caribe`: aplicarlo hoy no cambia ningún archivo.
- 199 `.meta`, 288 definiciones, 430 armas de jugador (113 oficiales, 317 personalizadas).
- **ox_inventory**: 422 armas; **204 no tienen `weapons.meta` en `[PackArmas]`**. De ellas, 203 no aparecen en ningún recurso del servidor (por ejemplo `WEAPON_AK47`, `WEAPON_FAMAS`, `WEAPON_DRACO`); `WEAPON_STUNGRENADE` está en `[scripting]/[Small]/stungrenade` (se puede agregar como pack en Configuración). Claves repetidas: `WEAPON_FNX45`, `WEAPON_GLOCK22`, `WEAPON_GLOCK41`, `WEAPON_TEC9S` (y 90 componentes).
- **Definiciones duplicadas**: `WEAPON_APPISTOL`, `WEAPON_ASSAULTRIFLE`, `WEAPON_COMBATPISTOL`, `WEAPON_MICROSMG`, `WEAPON_PISTOL`, `WEAPON_PISTOL50`.
- **Caída invertida**: `WEAPON_APPISTOL`, `WEAPON_GLIZZYG26SWITCH`.
- **One-tap a la cabeza**: 35 armas, todas en la lista permitida de `flow_caribe` (intencional).
- **qbx_recoils**: 67 entradas activas (66 de armas existentes). Casi ninguna arma personalizada tiene recoil vertical por script.
- **Scripts**: `qbx_ignore` apaga los critical hits solo si `config.disable.headshots` está activo (hoy `false`); arenas y minijuegos cancelan o restauran daño a propósito.

> [!NOTE]
> Estos datos no se corrigieron automáticamente: son decisiones del servidor. El panel los muestra en Diagnóstico con su arreglo sugerido.

## Arquitectura elegida

Se conservó el motor (probado y con conocimiento acumulado) y se construyeron capas alrededor, en lugar de reescribirlo. Ver [Desarrollo](14-desarrollo.md).

- Sin dependencias externas: el servidor no tiene pip ni Node, así que el panel usa solo la librería estándar de Python y JavaScript sin compilación.
- Un único camino de cálculo: la vista previa, el simulador “propuesto”, la comparación de perfiles y el generador ejecutan el motor real.

## Plan de migración aplicado

1. **Identificar el esquema**: sin bloque `profile` = legacy (v3–v7).
2. **Respaldar**: cada migración guarda el archivo anterior en `data/history/<id>/`.
3. **Migración versionada** a v8: `name`/`description` → `profile`, `engine_defaults: true` para conservar el comportamiento.
4. **Validar**: una prueba automática comprueba que los 18 perfiles producen la misma configuración del motor antes y después, y que la vuelta atrás también.
5. **Registrar**: notas de migración en el historial.
6. **Revertir**: *Revertir migración* restaura el archivo original byte a byte.

Los archivos no se migran solos: pasan a v8 al guardarlos o al ejecutar `python3 wr.py migrate --write`.

## Reorganización de perfiles 7.1 {#migracion-perfiles}

### Inventario

Había 18 perfiles en `profiles/`. Muchos eran copias exactas con otro nombre (por ejemplo `pvp_no_tank` = `pvp_competitive_onetap`, `rebelion_server` = `rebelion_balanced_v3`), dos eran plantillas de ejemplo y casi todos los PvP tenían 60 valores por categoría que el motor descartaba siempre (los pisaba un preset de módulo o la política de cabeza one-tap).

### Resultado

| Antes | Después |
| --- | --- |
| 18 perfiles sueltos en una carpeta | 4 principales: 3 oficiales protegidos + `flow_custom` del servidor |
| Copias con pequeñas variaciones | Herencia: `competitive` hereda de `realistic`; `flow_custom` de `competitive` y guarda solo sus diferencias |
| Cualquier perfil se podía sobrescribir | Oficiales de solo lectura; cambios mediante perfiles derivados en `profiles/user/` |
| Lógica de perfiles en el panel | Un solo motor de perfiles para panel y terminal (`profile_store/edit.py`) |

### Garantías

- **Nada se perdió.** Los 18 originales están intactos en `profiles/legacy/` y respaldados en `data/backups/profiles_pre_v8_*`. Las 6 configuraciones únicas que no corresponden a un principal están en `profiles/migrations/2026-10-12_v8/pending/` como deltas que reproducen exactamente el perfil original.
- **Verificado con el motor sobre el pack real**: `flow_custom` produce la misma configuración que `flow_caribe` y `competitive` el mismo resultado que `pvp_competitive_onetap`. `realistic` y `balanced` solo difieren en los cambios de diseño documentados.
- **Sin valores inventados.** Los datos que faltan se muestran como N/D. Las cifras de los perfiles oficiales vienen de los perfiles anteriores.

### Cambios de diseño (decisiones a revisar por el servidor)

- **balanced**: se quitó el +15 % que tenían las armas personalizadas y la regla de revólver a 350 de daño (venía de otro servidor).
- **realistic**: recoil `normal` → `high`.
- Desequilibrios detectados y no corregidos: ver [Perfiles oficiales → Desequilibrios](06-perfiles-oficiales.md#desequilibrios).

El informe con el destino de cada perfil y todas las verificaciones está en `profiles/migrations/2026-10-12_v8/REPORT.md`.
