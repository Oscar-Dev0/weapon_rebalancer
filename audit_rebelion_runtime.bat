@echo off
setlocal
set "RUNTIME_ROOT=C:\TxData\rebelion\resources"
cd /d "%~dp0"
if not exist reports mkdir reports
python run_rebalance.py --runtime-only --audit-runtime --runtime-root "%RUNTIME_ROOT%" --runtime-report "reports\rebelion_runtime_audit.json"
echo.
echo Revisa primero las lineas [X]. Son bloqueos que el weapons.meta no puede superar.
pause
