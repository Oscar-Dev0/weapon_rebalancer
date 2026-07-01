@echo off
setlocal
set "META_ROOT=C:\TxData\rebelion\resources\[Streaming]\[PackArmas]"
set "RUNTIME_ROOT=C:\TxData\rebelion\resources"
cd /d "%~dp0"
if not exist reports mkdir reports

python run_rebalance.py --validate-profiles profiles
if errorlevel 1 exit /b 1

python -m unittest discover -s tests -q
if errorlevel 1 exit /b 1

python run_rebalance.py --runtime-only --audit-runtime --runtime-root "%RUNTIME_ROOT%" --runtime-report "reports\rebelion_runtime_before_apply.json"
if errorlevel 1 exit /b 1

echo.
echo Revisa cualquier linea [X]. El META no puede vencer esos bloqueos runtime por si solo.
echo Se modificaran los META y se crearan copias .bak.
set /p "CONFIRM=Escribe APLICAR para continuar: "
if /I not "%CONFIRM%"=="APLICAR" exit /b 0

python run_rebalance.py --root "%META_ROOT%" --profile "profiles\rebelion_real_onetap_v4.json" --write --report "reports\rebelion_v4_apply.json" --strict-onetap-audit
pause
