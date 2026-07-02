# Changelog

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
