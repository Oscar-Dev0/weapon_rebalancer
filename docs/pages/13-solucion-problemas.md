---
slug: solucion-problemas
title: Solución de problemas
group: Servidor
description: Errores frecuentes, qué significa cada aviso del Diagnóstico y cómo corregirlo.
---
# Solución de problemas

## El panel no abre

| Síntoma | Causa | Solución |
| --- | --- | --- |
| *Acceso denegado* | Sin sesión: el enlace ya se usó, caducó o el panel se reinició | Pide un enlace nuevo con `python3 wr.py token` |
| *Sesión caducada* / la página se vació | 30 min sin uso, 8 h abierta o cerraste sesión | `python3 wr.py token` y abre el enlace nuevo |
| *Acceso bloqueado temporalmente* | Demasiados enlaces viejos o incorrectos seguidos | Espera los minutos indicados o reinicia `wr.py serve` |
| *Host no permitido* | Entraste con un nombre de host distinto | Usa `127.0.0.1` o `localhost` con el mismo puerto |
| No carga nada | El túnel o el reenvío de puerto no está activo | Revisa [Abrirlo desde tu PC](02-instalacion.md#acceso-remoto) |
| *No hay conexión con el servidor local* | Se detuvo `wr.py serve` | Vuelve a arrancarlo y abre el enlace nuevo |

## Cambié un valor y en el juego no cambia nada

1. **¿Guardaste y aplicaste?** El editor solo cambia el borrador. Hay que guardar el perfil y aplicarlo en el Generador.
2. **¿Reiniciaste el recurso del arma?** Ver [qué reiniciar](10-fivem.md#que-reiniciar-despues-de-aplicar).
3. **¿El valor tiene efecto?** En la revisión del perfil, busca `module_original`, `module_preset_overrides` o `clamped`.
4. **¿Hay otra definición del arma?** Con `duplicate_definition`, gana la que carga última.
5. **¿El META está registrado?** `meta_unregistered` = falta en `data_file 'WEAPONINFO_FILE'`.
6. **¿Un script cambia el daño en ejecución?** Diagnóstico → Auditar scripts (`runtime_damage_modifier`).

## El disparo a la cabeza no mata

- Revisa la **política de cabeza** (Editor → Cabeza). Con `modules.headshot = original`, no se toca.
- El objetivo necesita **critical hits** activos. Busca `critical_hits_disabled` en la auditoría de scripts; si la llamada está dentro de un `if`, revisa esa opción de configuración.
- Comprueba la **distancia máxima de cabeza** y el blindaje en el [Simulador](09-balanceo.md).

## Avisos del Diagnóstico

| Código | Significado | Qué hacer |
| --- | --- | --- |
| `ox_without_meta` | Ítem de ox_inventory sin `weapons.meta` en los packs | Si el arma está en otro recurso, agrégalo como pack; si no, el ítem no tiene modelo |
| `meta_without_ox` | Arma con META que no es ítem | Agrégala a ox_inventory si debe obtenerse |
| `duplicate_definition` | Varias definiciones `CWeaponInfo` | Deja una o mantenlas iguales (el generador las iguala) |
| `ox_duplicate_key` | Clave repetida en weapons.lua | Deja una sola entrada |
| `ammo_unknown` | La munición no existe en `Ammo` | Usa una munición existente |
| `meta_unregistered` | META sin `WEAPONINFO_FILE` | Agrégalo al `fxmanifest.lua` |
| `repeated_tags` | Tag directo repetido en un bloque | Informativo: el generador iguala las copias |
| `headshot_onetap` | Un tiro a la cabeza hace ≥ 100 sin blindaje | Correcto si es intencional; si no, baja el multiplicador |
| `falloff_inverted` | La caída empieza después de terminar | Corrige inicio/final de caída |
| `zero_network_modifier` | No hace daño a jugadores | Multiplicador contra jugadores en 1.0 |
| `projectile` | El daño depende del AmmoInfo/explosión | Informativo |
| `no_backup` | Sin `.bak`: el original es el actual | Se crea al escribir por primera vez |
| `pack_differs` | El pack no coincide con el perfil activo | Aplica el perfil o actualízalo con los cambios manuales |
| `not_idempotent` | Aplicarlo dos veces da otro resultado | Ver [Resultado repetible](07-perfiles.md#repetible) |

### Scripts en ejecución

| Código | Significado |
| --- | --- |
| `critical_hits_disabled` | `SetPedSuffersCriticalHits(..., false)`: la cabeza deja de multiplicar |
| `weapon_damage_event_cancelled` | Se cancela `weaponDamageEvent`: el daño no llega (esperado en minijuegos y arenas) |
| `damage_event_health_or_armour_restore` | El archivo procesa daño y reescribe vida/armadura (esperado en arenas) |
| `runtime_damage_modifier` | Otro recurso cambia el daño en ejecución |
| `ped_armour_write` / `ped_health_write` | Escritura de armadura/vida: normal en chalecos y curas |

> [!NOTE]
> La auditoría es estática: no puede leer recursos cifrados (escrow) y no evalúa configuraciones. Por eso muestra la condición `if … then` cuando la llamada está dentro de una.

## El Generador no deja aplicar

| Mensaje | Causa |
| --- | --- |
| *No es UTF-8 válido* | El archivo tiene bytes que se perderían al reescribirlo. Guárdalo como UTF-8 primero |
| *Dejaría de ser XML válido* | El cambio rompería el archivo. Revisa los tags exactos (`meta`) del perfil |
| *Algunos archivos cambiaron después de la vista previa* | Alguien editó el archivo. Genera de nuevo la vista previa |
| *El perfil tiene errores* | Corrige los errores marcados en la revisión |

## Revertir no funciona

Si un archivo cambió después de aplicar, revertir lo pisaría, así que no se revierte nada. Las copias siguen en `data/backups/<transacción>/files/` y su `manifest.json` indica a qué ruta corresponde cada una.

## Los perfiles archivados muestran avisos

Es normal: algunos perfiles antiguos (los legacy, borrados en la 7.3.0) traían claves sin efecto (`validation.require_runtime_critical_hits`) o valores por categoría que pisa un preset de módulo. Son de solo lectura y se conservan como estaban; los avisos indican qué parte del perfil no hace nada.

## No me deja guardar un perfil

- **“Es un perfil oficial protegido”**: `balanced`, `realistic` y `competitive` no se modifican. Crea un derivado (**Crear perfil derivado** o `wr.py profile derive competitive mi_perfil`).
- **`flow_caribe` no se puede editar**: revisa **Configuración → Permitir editar perfiles del servidor** (`wr.py settings set server_profiles_editable=true`).
- **Conflicto (409)**: otra pestaña o la terminal guardó el mismo perfil mientras lo editabas. Recarga el perfil y repite el cambio; nada se pisó.
- **Error bloqueante**: corrige lo que indica la validación (por ejemplo un ciclo de herencia o un perfil base que no existe).

## Me falta un perfil antiguo

Se borraron del repo en la 7.3.0 porque ya no se usaban. Están en `/fivem/backups/weapon_rebalancer_limpieza_2026-10-17/` (`legacy/` y `migrations/…/pending/`). Para recuperar uno:

```bash
python3 wr.py profile import /fivem/backups/weapon_rebalancer_limpieza_2026-10-17/migrations/2026-10-12_v8/pending/head_only.json --id head_only
```

## La terminal se ve mal

- **Caracteres raros en los bordes**: la consola no usa UTF-8. Usa `--ascii` o `WR_ASCII=1`.
- **Códigos como `\x1b[38;5;…m`**: la consola no interpreta colores ANSI (CMD antiguo). Usa `--no-color` o `NO_COLOR=1`.
- **Las flechas no responden**: algunas sesiones SSH sin terminal asignada (`ssh host comando`) no son interactivas. Conéctate con `ssh -t` o usa los números de cada opción y los comandos directos.
- **Sin menú, solo ayuda**: la salida no es una terminal (tubería o script). Es intencional; usa los comandos directos.
