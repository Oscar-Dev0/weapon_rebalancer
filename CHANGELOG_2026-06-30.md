# Corrección one tap contra cascos — 2026-06-30

## Corregido

- Se agregó `headshot.bypass_helmets` configurable desde JSON.
- Se agregó `headshot.helmet_multiplier` para `LightlyArmouredDamageModifier`.
- Se agregó soporte para `Penetration` en `CWeaponInfo`.
- Los tags de casco/penetración se insertan si faltan en metas custom.
- `LightlyArmouredDamageModifier` ya no se recorta silenciosamente a `2.0`.
- El daño explícito de perfiles externos ya no se recorta a `85.0`.
- La política de cascos se aplica después de módulos y overrides, evitando que otro perfil la sobrescriba.
- `WEAPON_SNOWBALL` y `WEAPON_BALL` siguen forzadas a daño y penetración cero.
- `Settings.from_config()` ahora clona la configuración mutable de headshot.
- Corregida la sangría al insertar tags antes de `</Item>`.

## Añadido

- CLI: `--onetap-through-helmets`.
- CLI: `--no-onetap-through-helmets`.
- CLI: `--helmet-multiplier`.
- CLI: `--helmet-penetration`.
- Cuatro pruebas automáticas en `tests/test_helmet_onetap.py`.
