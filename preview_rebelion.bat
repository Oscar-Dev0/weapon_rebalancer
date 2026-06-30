@echo off
setlocal
set "ROOT=C:\TxData\rebelion\resources\[Streaming]\[PackArmas]"
cd /d "%~dp0"
if not exist reports mkdir reports
python run_rebalance.py --validate-profiles profiles
if errorlevel 1 exit /b 1
python run_rebalance.py --root "%ROOT%" --profile "profiles\rebelion_balanced_v3.json" --report "reports\rebelion_preview.json" --strict-onetap-audit
pause
