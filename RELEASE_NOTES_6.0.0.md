# Weapon Rebalancer 6.0.0

## Resultado buscado

- Armas oficiales: valores absolutos del paquete original GTAV/DLC cuando está disponible.
- Armas custom: conservan su base válida y reciben `+15%` en daño y distancias.
- Custom rotas con `Damage=0`: se reparan desde el fallback de su grupo antes del `+15%`.
- Headshot: comportamiento normal/original; se reparan únicamente tags en cero o ausentes.
- Revólveres: daño de torso `350`, extremidades `0.25`, sin reducción adicional de armadura ligera.

## Por qué V5 podía no funcionar

V5 diferenciaba correctamente armas oficiales y custom, pero la base numérica seguía dependiendo del `.meta.bak` o del META actual. Un backup ya modificado, un tag ausente o `Damage=0` impedían recuperar el daño real. Además, un recurso runtime o un componente podía volver a cambiar el resultado.

## Solución V6

1. Descarga/lee un paquete original de META con `--reference-root`.
2. Restaura campos absolutos para armas oficiales.
3. Repara valores inválidos de custom mediante fallback por grupo.
4. Aplica el `×1.15` después de la reparación.
5. Audita `weaponcomponents.meta` y armas `PROJECTILE`.
6. Genera `os_weapon_damage_guard` con valores absolutos esperados.
7. Permite inspección dentro del juego mediante `/osweaponstatus`.

## Archivos rápidos

- `preview_vanilla_repair_v6.bat`
- `apply_vanilla_repair_v6.bat`
- `profiles/vanilla_repair_custom_plus15_absolute_v6.json`
- `references/download_original_gtav_metas.ps1`

## Validación

- 17 perfiles JSON válidos.
- 32 pruebas automáticas aprobadas.
- Smoke test CLI: oficial `999 → 26`; custom `0 → 31.05`; rango custom `0 → 138`; guard generado con ambos valores.
