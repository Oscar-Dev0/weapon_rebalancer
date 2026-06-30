@echo off
setlocal
set "ROOT=%~1"
set "PROFILE=%~2"
if "%ROOT%"=="" set "ROOT=C:\TxData\rebelion\resources\[Streaming]\[PackArmas]"
if "%PROFILE%"=="" set "PROFILE=profiles\rebelion_balanced_v3.json"
cd /d "%~dp0"
if not exist reports mkdir reports
echo ROOT: %ROOT%
echo PROFILE: %PROFILE%
set /p "CONFIRM=Escribe APLICAR para continuar: "
if /I not "%CONFIRM%"=="APLICAR" exit /b 0
python run_rebalance.py --root "%ROOT%" --profile "%PROFILE%" --write --report "reports\profile_apply.json" --strict-onetap-audit
pause
