@echo off
setlocal
set "ROOT=C:\TxData\rebelion\resources\[Streaming]\[PackArmas]"
cd /d "%~dp0"
python run_rebalance.py --root "%ROOT%" --export-meta "meta_inventory.json" --export-full-profile "perfil_pack_completo.json" --export-only
if errorlevel 1 (
  echo.
  echo ERROR: no se pudo exportar la informacion META.
  pause
  exit /b 1
)
echo.
echo Exportacion completada:
echo   meta_inventory.json
echo   perfil_pack_completo.json
pause
