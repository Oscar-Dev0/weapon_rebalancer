@echo off
setlocal
set "ROOT=C:\TxData\rebelion\resources\[Streaming]\[PackArmas]"
cd /d "%~dp0"
python run_rebalance.py --root "%ROOT%" --profile "profiles\rebelion_server.json" --report "weapon_rebalance_report.json"
pause
