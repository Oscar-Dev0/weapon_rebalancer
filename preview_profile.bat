@echo off
setlocal
set "ROOT=%~1"
set "PROFILE=%~2"
if "%ROOT%"=="" set "ROOT=C:\TxData\rebelion\resources\[Streaming]\[PackArmas]"
if "%PROFILE%"=="" set "PROFILE=profiles\rebelion_real_onetap_v4.json"
cd /d "%~dp0"
if not exist reports mkdir reports
python run_rebalance.py --root "%ROOT%" --profile "%PROFILE%" --report "reports\profile_preview.json" --strict-onetap-audit
pause
