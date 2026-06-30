@echo off
setlocal
set "ROOT=C:\TxData\rebelion\resources\[Streaming]\[PackArmas]"
cd /d "%~dp0"
if not exist reports mkdir reports
python run_rebalance.py --validate-profiles profiles
if errorlevel 1 exit /b 1
python -m unittest discover -s tests -q
if errorlevel 1 exit /b 1
echo Se modificaran los META y se crearan copias .bak.
set /p "CONFIRM=Escribe APLICAR para continuar: "
if /I not "%CONFIRM%"=="APLICAR" exit /b 0
python run_rebalance.py --root "%ROOT%" --profile "profiles\rebelion_balanced_v3.json" --write --report "reports\rebelion_apply.json" --strict-onetap-audit
pause
