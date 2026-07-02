# V6.0.0 — Reparación absoluta de daño

## Problema corregido

V5 dependía demasiado de `.meta.bak`. Si el backup estaba alterado, faltaba o tenía `Damage=0`, el multiplicador custom producía resultados incorrectos. Además, el perfil normal activaba accidentalmente la sincronización de distancia del modo one-tap.

## Cambios

- Nuevo perfil `vanilla_repair_custom_plus15_absolute_v6.json`.
- Soporte para `--reference-root` con paquetes META originales.
- Descargador de la referencia original GTAV/DLC de Snag.
- Reparación previa de `Damage`, modificadores de red, alcance, falloff y headshot.
- Fallback por grupo cuando una custom viene en cero o sin tags.
- `+15%` aplicado después de reparar la base.
- Núcleo vanilla con daños absolutos conocidos como segunda protección.
- Headshot normal/original; eliminado el multiplicador global 1500 de este perfil.
- Revólver: 350 al torso, extremidades reducidas.
- Auditoría de modificadores de daño en `weaponcomponents.meta`.
- Generador de `os_weapon_damage_guard` con `/osweaponstatus`.
- 32 pruebas automáticas.
