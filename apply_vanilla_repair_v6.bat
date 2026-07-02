@echo off
setlocal
set "BASE=%~dp0"
set "TARGET=%~1"
set "GUARD=%~2"
if "%TARGET%"=="" set "TARGET=C:\TxData\rebelion\resources\[Streaming]\[PackArmas]"
if "%GUARD%"=="" set "GUARD=C:\TxData\rebelion\resources\[OscarDev]\os_weapon_damage_guard"
set "REFERENCE=%BASE%references\snags_original\metas"

if not exist "%REFERENCE%\weapons\weapons.meta" (
  powershell -NoProfile -ExecutionPolicy Bypass -File "%BASE%references\download_original_gtav_metas.ps1"
)

python "%BASE%run_rebalance.py" ^
  --root "%TARGET%" ^
  --profile "%BASE%profiles\vanilla_repair_custom_plus15_absolute_v6.json" ^
  --reference-root "%REFERENCE%" ^
  --write ^
  --report "%BASE%reports\apply_v6.json" ^
  --generate-damage-guard "%GUARD%" ^
  --force-install

if errorlevel 1 (
  echo [ERROR] No se pudo aplicar el perfil V6.
  pause
  exit /b 1
)

echo.
echo [IMPORTANTE] Agrega al FINAL de server.cfg:
echo ensure os_weapon_damage_guard
echo.
echo Comando de prueba dentro del juego: /osweaponstatus
pause
