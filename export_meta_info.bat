@echo off
setlocal
set "ROOT=C:\TxData\rebelion\resources\[Streaming]\[PackArmas]"
cd /d "%~dp0"
if not exist exports mkdir exports
python run_rebalance.py --root "%ROOT%" --export-meta "exports\meta_inventory.json" --export-full-profile "exports\perfil_pack_completo.json" --export-only
if errorlevel 1 (
  echo.
  echo ERROR: no se pudo exportar la informacion META.
  pause
  exit /b 1
)
echo.
echo Exportacion completada en exports\
pause
