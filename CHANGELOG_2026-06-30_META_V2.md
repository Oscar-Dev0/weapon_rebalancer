# Changelog — META V2 — 2026-06-30

## One-tap y cascos

- Añadida aplicación incremental de `IgnoreHelmets`.
- Añadida aplicación incremental de `ArmourPenetrating`.
- Se preservan todas las `WeaponFlags` originales.
- Las flags solo se fuerzan cuando el one-tap está activo para esa arma.
- Las armas inofensivas no reciben flags ofensivas.
- Continúan forzándose `LightlyArmouredDamageModifier` y `Penetration`.

## Cobertura META

- Catálogo ampliado de 38 a 133 campos de `CWeaponInfo`.
- Añadidos campos de red, fuerzas, proyectil, pellets, cámara, FOV, rumble, HUD, IA, recarga, spin, bullet bending y animación.
- Añadido catálogo de 146 `WeaponFlags` conocidas.
- Añadida sección `meta` para tags XML custom/desconocidos.
- Añadido soporte de atributos múltiples (`x`, `y`, `z`, etc.).
- Añadidos scopes global, por grupo y por arma.

## Exportación y auditoría

- Nuevo `--export-meta`: inventario de todos los `.meta` y todas sus hojas XML.
- Nuevo `--export-full-profile`: genera un perfil reutilizable desde los META reales.
- Nuevo `--list-fields` ampliado y agrupado.
- Nuevo `--list-flags`.
- Detección/documentación de armas duplicadas.
- Registro de errores XML sin abortar toda la exportación.

## Seguridad

- Los tags dinámicos no se crean por defecto.
- Solo los campos estándar marcados como seguros pueden insertarse automáticamente.
- Validación estricta opcional para detectar typos en `fields`.
- Los arrays/estructuras complejas se inventarían de forma insegura, por lo que se exportan completos pero no se reconstruyen a ciegas.

## Pruebas

- 8 pruebas automáticas superadas.
- Cobertura de casco, flags, tags custom, vectores, exportación, armas inofensivas y límites numéricos.
