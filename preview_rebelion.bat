@echo off
setlocal
set "META_ROOT=C:\TxData\rebelion\resources\[Streaming]\[PackArmas]"
set "RUNTIME_ROOT=C:\TxData\rebelion\resources"
cd /d "%~dp0"
if not exist reports mkdir reports

python run_rebalance.py --validate-profiles profiles
if errorlevel 1 exit /b 1

python run_rebalance.py --root "%META_ROOT%" --profile "profiles\rebelion_real_onetap_v4.json" --report "reports\rebelion_v4_preview.json" --strict-onetap-audit
if errorlevel 1 exit /b 1

python run_rebalance.py --runtime-only --audit-runtime --runtime-root "%RUNTIME_ROOT%" --runtime-report "reports\rebelion_v4_runtime_preview.json"
pause
