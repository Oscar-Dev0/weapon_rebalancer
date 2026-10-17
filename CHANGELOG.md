# 7.2.0 — Registro, cambios a mano y paso a principal

- **Sello de integridad** (`services/integrity.py`): SHA-256 de los `.meta`, `fxmanifest.lua` y qbx_recoils; se actualiza solo tras aplicar, revertir o pasar. `wr.py integrity [--server principal]` lista lo cambiado **fuera de la herramienta** y lo deja en el registro (una vez por cambio). `wr.py integrity seal --reason …` acepta el estado actual (motivo obligatorio).
- **`wr.py sync principal`** (`services/sync.py`): pasa las armas a otro servidor como transacción reversible (`wr.py rollback`), con respaldo, verificación, sin borrar nada del destino y sin pisar cambios hechos a mano allí salvo `--force`. Destinos en `sync_targets` (`wr.py settings set sync_targets.principal=/fivem/principal`).
- **`wr.py registro`**: aplicaciones, reversiones, pasos, sellos, cambios a mano y escrituras de la CLI antigua.
- `wr.py status` muestra **Cambios a mano**; `wr.py generate` avisa antes de aplicar encima de cambios a mano.
- La CLI antigua (`wr.py rebalance --write`, `run_rebalance.py --write`) ahora registra y sella los archivos que cambia.
- Documentación: página «Registro, cambios a mano y paso a principal». Pruebas nuevas en `tests/test_v9_integrity.py` (111 en total).

# 7.1.1 — Acceso al panel endurecido

- **Sin sesión no se entrega nada**: página, JS, CSS, documentación y API responden *Acceso denegado* (antes los archivos estáticos se servían sin token).
- **Enlace de un solo uso** (`/?token=`): se canjea por una sesión, queda gastado y redirige a `/` para no dejar el token en el historial. **Cambia solo** cada 30 min; `python3 wr.py token` muestra el vigente (guardado en `data/panel_access_<puerto>.json`, permisos 600).
- **Sesión con caducidad**: cookie HttpOnly atada a la IP; caduca tras 30 min sin uso o 8 h. Cookie y clave de la API rotan cada 10 min (`X-WR-Token-Next`, 2 min de gracia). **Cerrar sesión** en Configuración. Al caducar, la página se vacía.
- **Bloqueo**: 8 credenciales incorrectas en 10 min bloquean nuevas entradas desde esa IP durante 10 min y cambian el enlace.
- Tiempos configurables en `data/workspace.json` (`server.*`) o con `wr.py serve --rotate/--idle`.
- Pruebas nuevas en `tests/test_v8_auth.py` (105 en total).

# 7.1.0 — Cuatro perfiles principales y terminal profesional

## Perfiles
- **18 → 4 perfiles principales**: `balanced` (Balanced RP), `realistic` (Realistic Combat), `competitive` (Competitive PvP, hereda de `realistic`) y `flow_custom` (Flow Caribe Custom, hereda de `competitive` y guarda solo sus diferencias).
- **Niveles**: `profiles/official/` (protegidos), `server/` (editable, se puede bloquear con `server_profiles_editable`), `user/` (derivados e importados), `legacy/` (los 18 originales, solo lectura). `schemas/profile.schema.json` (JSON Schema 2020-12) y `$schema` en cada perfil.
- **Herencia con JSON Merge Patch (RFC 7386)**: `null` quita lo heredado; resolución determinista con detección de ciclos y bases inexistentes; caché invalidada por cambios en cualquier archivo de la cadena.
- **Procedencia** de cada valor efectivo: del perfil, heredado (de qué perfil y ámbito), sobrescrito, regla del motor, original o sin efecto.
- **Contradicciones** detectadas: listas y excepciones en conflicto, armas ignoradas con valores, flags que se agregan y quitan, reglas de cadencia inalcanzables o repetidas, políticas de cabeza sin efecto, `null` sin perfil base. Niveles Bloqueante / Advertencia / Recomendación.
- Metadatos nuevos: nombre corto, objetivo, público, características y advertencias.
- `qbx_recoils`: `false` quita la entrada del arma.
- Edición segura: bloqueo entre procesos, detección de conflictos (`sha`), validación antes de guardar e historial.

## Migración (`profiles/migrations/2026-10-12_v8/`)
- `flow_caribe` → `flow_custom`: configuración del motor idéntica (verificado).
- `pvp_competitive_onetap` → `competitive`: resultado idéntico sobre el pack real.
- `rp_serious_onetap` → `realistic`: recoil `normal` → `high`.
- `vanilla_repair_custom_plus15_absolute_v6` → `balanced`: sin el +15 % para armas personalizadas ni la regla de revólver a 350.
- 6 configuraciones únicas quedan como pendientes importables (deltas exactos); 8 archivados (copias exactas y plantillas). Respaldo en `data/backups/profiles_pre_v8_*`.

## Terminal
- `python3 wr.py` abre un estudio interactivo: banner, estado del servidor, menú 0–9, navegación con flechas, números, búsqueda con `/` y Esc.
- Comandos directos: `status`, `weapons`, `weapon`, `profiles`, `profile …` (show, activate, validate, affected, create, derive, duplicate, rename, delete, export, import, history, restore), `set`, `headshot`, `compare`, `simulate`, `validate`, `generate`, `transactions`, `rollback`, `params`, `docs`, `settings`.
- Colores ANSI 256 con la paleta del panel, `--no-color`/`NO_COLOR`, `--ascii`, Windows (VT/msvcrt) y SSH; `--json`; códigos de salida 0/1/2/130.
- Terminal y panel comparten el motor de edición (`profile_store/edit.py`, `POST /api/profiles/ops`).

## Panel
- Perfiles por nivel con insignias, *Mostrar archivados*, *Crear perfil derivado*, *Armas afectadas*; comparador contra original/actual con flechas y procedencia.
- Armamento: columna de estado del perfil y procedencia en el detalle del arma.
- Editor: aviso de solo lectura en oficiales, valores heredados y botón **No heredar**.
- Configuración: *Permitir editar perfiles del servidor*.

## Documentación
- Páginas nuevas: **Perfiles oficiales** (con TTK medidos y desequilibrios detectados) y **Terminal** (con salidas reales). Actualizadas: Perfiles, Primeros pasos, Instalación, Editor, Desarrollo, Auditoría y Solución de problemas.

## Pruebas
- `test_v8_profiles.py` y `test_v8_cli.py` (95 pruebas en total): equivalencias de la migración, pendientes exactos, terminal ↔ panel, protección, modo sin color/ASCII y bloqueo entre procesos.

# 7.0.0 — Panel web, perfiles v8 y generador transaccional

Modernización completa sobre el motor 6.12 (que se conserva). Diagnóstico y plan de migración en `docs/pages/13-auditoria.md`.

## Nuevo
- **Panel web local** (`python3 wr.py serve`): Dashboard, Armamento, Editor, Perfiles, Constructor, Simulador, Generador, Diagnóstico, Documentación y Configuración. Solo librería estándar; JS sin compilación.
- **Integración con ox_inventory** (solo lectura): armas, etiquetas, hash, munición, componentes y claves repetidas; cruce con los `weapons.meta` (sin META, sin ítem, municiones inexistentes).
- **qbx_recoils**: recoil vertical de cámara por arma, leído y editable vía `resources.qbx_recoils` del perfil.
- **Registro de parámetros** con método real (META / Native / Recurso / Solo lectura / No compatible), límites del motor y textos; la referencia de la documentación se genera desde él.
- **Perfiles v8**: bloque `profile` (id, nombre, herencia `extends`, etiquetas, revisión), historial de versiones con restauración byte a byte, papelera, importar/exportar (normal, resuelto, legacy), comparación por efecto real, migración reversible.
- **Vista previa con el motor real** en memoria: valores propuestos por arma, valores sin efecto (módulo en original, preset que los pisa, recortes) y comprobación de repetibilidad.
- **Simulador**: daño por zona y distancia, disparos para matar, TTK con recargas, DPS y DPS sostenido, comparación de hasta 8 series.
- **Generador transaccional**: plan atado al hash de cada archivo, respaldo previo, escritura atómica, verificación, bloqueo de archivos no UTF-8 o XML roto, registro de cambios y reversión.
- **Diagnóstico** unificado (rutas, inventario, packs, perfiles, perfil activo frente al pack y auditoría de scripts con la condición `if` detectada).
- **Documentación web** (`docs/index.html`) con buscador, tabla de contenidos y validación de enlaces en el build.
- 36 pruebas nuevas (74 en total).

## Cambios en el motor
- Rendimiento: caché de la tokenización XML y de los regex (4,1 s → 0,47 s por pasada, salida idéntica).
- `RebalanceEngine(capture=…, overlay=…)` para vista previa sin escribir.
- `FileChange.content_changed`: el resumen ya no cuenta anotaciones como cambios (antes `flow_caribe` mostraba 130 archivos “cambiados” cuando cambiaba 0).
- `engine_defaults: false` y `base_preset: none`: perfiles neutros que no heredan de `config.py`.
- La ruta del pack sale de `data/workspace.json` (antes fija).
- Paquete ordenado: `engine/`, `meta/`, `runtime/`, CLI en `weapon_rebalancer/cli.py` (`run_rebalance.py` queda como lanzador). `profiles.py` → `engine/presets.py`; `runtime_audit/guard` → `runtime/audit|guard`. `references/` → `extras/references/`, guías antiguas → `docs/legacy/`.
- Guard de daño generado: reaplica cada 250 ms por defecto (antes cada frame).

## Compatibilidad
- Los perfiles v3–v7 siguen funcionando con la CLI y el panel; se migran a v8 al guardarlos o con `wr.py migrate --write`. Una prueba garantiza que los 18 perfiles incluidos producen la misma configuración del motor antes y después.

# 6.12.0

- `WEAPON_REVOLVER_MK2` now receives the same exact damage multiplier as `WEAPON_REVOLVER`: base pistol damage 10 × 6 = **60**.
- `WEAPON_REVOLVER_MK2` is explicitly added to Flow Caribe's fixed one-tap allowlist, so its single-shot recoil behavior matches the standard Revolver.
- Exact matching remains strict: names such as `WEAPON_REVOLVER_MK2_TEST` do not inherit the ×6 multiplier or fixed allowlist behavior.

# 6.11.0

- Added exact `weapon_field_multipliers` profile support. Multipliers match the full weapon name instead of substring families.
- `WEAPON_REVOLVER`: base pistol damage 10 × 6 = **60**.
- `WEAPON_GADGETPISTOL`: heavy PISTOL50-style base damage 30 × 7 = **210**.
- Multipliers run after base/cadence resolution and before family rules, while explicit base damage keeps these two special weapons deterministic.

# Changelog

## 6.9.0 - Flow Caribe heavy Gadget + revolver one-tap recoil
- `WEAPON_GADGETPISTOL` now mirrors the complete `WEAPON_PISTOL50` heavy profile: 30 body damage, 220 range, 165-220 falloff window and the same accuracy/range tuning.
- `WEAPON_GADGETPISTOL` remains fixed one-tap and, when truly single-shot, receives the visible pistol one-tap recoil profile.
- `WEAPON_REVOLVER` is added to the fixed one-tap allowlist.
- `WEAPON_REVOLVER` keeps the normal pistol body-damage scale but receives visible recoil when it is truly tiro-a-tiro.
- Automatic/burst versions of either weapon still keep near-zero recoil; only mechanical single-shot behavior receives the special recoil.
- Added regression coverage for Gadget=.50 parity and Revolver one-tap recoil.

## 6.8.0 - Flow Caribe one-tap single-shot recoil
- One-tap weapons that truly fire one shot per trigger now receive visible recoil.
- Fixed one-tap pistols: recoil 0.30 / shake 0.28 with faster recovery.
- GROUP_SNIPER one-tap: heavier recoil 0.75 / shake 0.65.
- Automatic, burst, multi-bullet and rapid-tuning one-tap weapons keep the near-zero recoil profile.
- Cadence alone does not remove recoil from a semi-auto one-tap weapon; tiro-a-tiro remains recoil-enabled even at fast TBS.
- Added regression tests for semi-auto, automatic allowlist, fast semi-auto and sniper recoil behavior.

## 6.7.0 - Flow Caribe normal-max damage scale
- Pistols: normal 10; rapid tiers 9/8/7/6.
- SMGs: normal 14; rapid tiers 13/12/11/10.
- Rifles: normal 15; rapid tiers 14/13/12/11.
- MGs: normal 14; rapid tiers 13/12/11/10.
- Snipers: normal 40; faster custom snipers 37/34/30/25.
- PISTOL50: 30 body damage (3x normal pistol).
- Automatic/Burst detection now enforces at least a one-tier body-damage reduction even when authored cadence looks slow.
- Fixed-pistol and sniper one-tap policy and near-zero recoil remain enabled.

## 6.6.0 - Flow Caribe 10-15 damage scale
- Pistolas adaptativas: 10/11/12/13 por cadencia; pistola normal 15.
- SMG adaptativas: 10-14, con 14 como daño base.
- Rifles/largas: hasta 15; cadencias extremas bajan a 12-14.
- MG: hasta 14.
- Escopetas y snipers: 15 de daño base.
- WEAPON_PISTOL50: 45 de daño (3x la pistola normal de 15).
- Se conserva one-tap dinámico solo para las 25 pistolas fijadas y GROUP_SNIPER.
- Recoil casi nulo permanece sin cambios.

## 6.5.0 - 2026-08-11

- Flow Caribe vuelve a one-tap **solo** para las 25 pistolas fijadas y `GROUP_SNIPER`.
- La allowlist es autoritativa: una pistola fijada conserva one-tap incluso si el META la marca `Automatic` o su cadencia es rápida; la cadencia sigue reduciendo únicamente el daño corporal.
- Cualquier arma fuera de la allowlist queda limitada a headshot normal de **1.5x**, incluso si un override intenta forzar `mode=onetap`.
- Nuevo one-tap dinámico: calcula el multiplicador mínimo necesario desde el daño corporal final y el falloff, evitando valores fijos 300x/1500x.
- Ejemplo real: `WEAPON_RUSOGLOCK` no fijada => 5.5 cuerpo / 1.5x cabeza; el mismo META renombrado a `WEAPON_GLIZZYG17` fijada => 5.5 cuerpo / ~25.25x, suficiente para one-tap en el peor falloff configurado.
- Overrides externos no pueden quitar one-tap a una arma fijada ni otorgárselo a una no fijada.
- Recoil casi nulo y clasificador robusto de cadencia se conservan.
- 40 pruebas automáticas aprobadas.

## 6.4.0 - 2026-08-11

- Flow Caribe cambia de multiplicadores de headshot 4x/1500x a un límite duro de **1.5x**.
- Ejemplo contractual: daño corporal 10 => daño de cabeza 15; 6 => 9; 18 => 27.
- Nuevo `fire_rate_classifier.force_bounded_headshot` para aplicar la protección después de overrides de paquete/grupo/arma.
- Nuevo `fire_rate_classifier.max_headshot_multiplier` para impedir que configuraciones externas restauren multiplicadores exagerados.
- Un override `mode=onetap, multiplier=1500` se degrada a `normal` y queda limitado a 1.5x.
- Se desactivan en Flow Caribe los ajustes one-tap de casco/penetración que podían alterar el daño efectivo.
- Se conserva detección robusta de cadencia y recoil casi nulo.
- 40 pruebas automáticas aprobadas.

## 6.3.0 - 2026-08-11

- Flow Caribe ahora usa una allowlist estricta: one-tap solo en las 25 pistolas declaradas y `GROUP_SNIPER`.
- Las 25 pistolas son solo elegibles: si el META indica `Automatic`, burst, cadencia rápida o señales de machine-pistol, pierden one-tap.
- Scanner `CWeaponInfo` corregido: extracción balanceada de `<Item>` para no truncar armas con `OverrideForces`/`AttachPoints` anidados.
- Lectura y escritura de campos al nivel directo de `CWeaponInfo`, ignorando duplicados anidados que antes podían ocultar `WeaponFlags` reales.
- Duplicados directos de campos se normalizan todos; un segundo `NetworkHeadShotPlayerDamageModifier` ya no puede dejar un multiplicador viejo.
- Clasificador fail-safe: usa el menor `TimeBetweenShots`, mayor `AnimFireRateModifier`, cualquier flag `Automatic`, patrones burst/full-auto y señales secundarias `APPISTOL`/SMG.
- `unknown_cadence_forces_non_normal` activado en Flow Caribe: si una pistola elegible no declara cadencia, pierde one-tap por seguridad.
- Regresión añadida con estructura META realista anidada y override externo intentando forzar one-tap.
- 38 pruebas automáticas aprobadas.

## 6.2.0 - 2026-08-11

- Nuevo perfil `profiles/flow_caribe.json` para PvP Flow Caribe.
- 25 pistolas declaradas explícitamente con one-tap de cabeza.
- Nueva regla `fire_rate_damage_rules`: reduce daño según la cadencia original sin alterar `TimeBetweenShots`.
- `WEAPON_PISTOL50` reforzada con daño y alcance propios, con prioridad sobre la regla de cadencia.
- Rifles, SMG, MG, escopetas y sniper reajustados; recoil casi nulo conservando algo de feedback.
- Headshot one-tap sin forzar `DamageFallOffModifier=1.0`, preservando el falloff corporal.
- 35 pruebas automáticas aprobadas.

## 6.1.0 - 2026-07-02

- Custom normalizadas contra una referencia vanilla por grupo antes del +15%.
- Ya no se multiplica el daño inflado incluido por el pack custom.
- Normalización de modificadores de red, extremidades, armadura, vehículo, falloff y headshot.
- 34 pruebas automáticas.

## 6.0.0 - 2026-07-02

- Reparación absoluta basada en paquete META de referencia.
- Custom +15% sin multiplicar valores cero.
- Guard runtime de daño y auditoría de componentes.
- 32 pruebas automáticas.

## 5.0.0 — 2026-07-02

### Vanilla y custom automáticos

- Restauración desde el `.meta.bak` original antes de calcular cambios.
- Catálogo oficial Cfx.re integrado para distinguir armas default de armas custom.
- Armas oficiales sin alteraciones; armas custom de fuego con `+15%` de daño y distancia.
- Headshots originales conservados.
- Revólveres oficiales y custom con un disparo letal al torso y daño reducido en extremidades.

### Motor y calidad

- Multiplicadores por clasificación y reglas por familia.
- Advertencias cuando falta el backup.
- 28 pruebas automáticas aprobadas.

## 4.0.0 — 2026-06-30

### Corrección del fallo real

- Auditoría runtime para `SetPedSuffersCriticalHits(false)`.
- Detección de cancelación de `weaponDamageEvent`.
- Detección de restauración de vida/armadura dentro de eventos de daño.
- Reporte con archivo, línea y fragmento exacto.

### META

- `LightlyArmouredDamageModifier` deja de forzarse a `100.0`; el perfil recomendado usa `1.0` para no multiplicar bodyshots.
- Vida efectiva objetivo elevada a `1000` con margen `1.25`.
- Redondeo hacia arriba a seis decimales del piso de daño.
- Nuevos perfiles V4 para Rebelion, daño corporal original y headshot focus.

### Compatibilidad

- Recurso opcional `os_headshot_guard`.
- El guard no escribe vida, armadura ni daño y no cancela eventos.
- Instalador `--install-headshot-guard`.

### Calidad

- 23 pruebas automáticas.
- Smoke tests de auditoría e instalación.
- Scripts BAT para verificar, auditar e instalar.

## 3.0.0 — 2026-06-30

### One-tap

- Política global, por grupo y por arma.
- Distancias independientes para pistola, SMG, rifle, MG, escopeta y sniper.
- Piso matemático de daño base para perfiles con cuerpo cero.
- Reparación de `NetworkPlayerDamageModifier=0`.
- Bypass de casco mediante campos y flags META.
- Eliminación opcional de flags no letales contradictorias.
- Auditoría del XML final generado.

### Auditoría del pack

- Detección de armas duplicadas, incluso repetidas en el mismo archivo.
- Detección de META sin `WEAPONINFO_FILE` visible.
- Reporte de métricas de daño y distancia.
- Modo `--strict-onetap-audit`.

### Perfiles

- Rebelion balanceado.
- RP serio.
- PvP competitivo.
- PvP hardcore.
- Headshot focus.
- Daño corporal original + one-tap.

### Configuración

- Nuevo modo `configured` para aplicar exactamente los valores del JSON.
- Validación formal de módulos y opciones de headshot.
- Catálogo de perfiles y comandos `--list-profiles` / `--validate-profiles`.

### Calidad

- 16 pruebas automáticas.
- Exportadores actualizados al formato V3.
- Documentación y guía de commits.
