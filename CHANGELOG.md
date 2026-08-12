# Changelog

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
