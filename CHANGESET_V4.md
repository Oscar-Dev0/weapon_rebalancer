# Changeset V4

## Problema corregido

El V3 validaba que el META tuviera daño suficiente, pero no podía detectar que otro recurso desactivara `critical hits` en ejecución. En ese estado, una gorra o cualquier ropa parecía tanquear porque el disparo de cabeza se procesaba como daño corporal.

## Archivos principales

- `weapon_rebalancer/runtime_audit.py`
- `extras/os_headshot_guard/*`
- `profiles/rebelion_real_onetap_v4.json`
- `profiles/original_body_real_onetap_v4.json`
- `profiles/headshot_focus_real_onetap_v4.json`
- `tests/test_v4_runtime_audit.py`
- `audit_rebelion_runtime.bat`
- `install_headshot_guard_rebelion.bat`
- `verify_rebelion_v4.bat`

## Migración

1. Ejecutar auditoría runtime sobre toda la carpeta `resources`.
2. Corregir las líneas `[X]` o instalar temporalmente `os_headshot_guard`.
3. Aplicar `rebelion_real_onetap_v4.json`.
4. Reiniciar recursos y reconectar el cliente de prueba.
