@echo off
setlocal
set "ROOT=C:\TxData\rebelion\resources\[Streaming]\[PackArmas]"
cd /d "%~dp0"
echo Se modificaran los META y se crearan copias .bak.
set /p "CONFIRM=Escribe APLICAR para continuar: "
if /I not "%CONFIRM%"=="APLICAR" exit /b 0
python run_rebalance.py --root "%ROOT%" --profile "profiles\rebelion_server.json" --write --report "weapon_rebalance_report.json"
pause
