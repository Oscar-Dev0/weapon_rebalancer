@echo off
setlocal
set "BASE=%~dp0"
set "TARGET=%~1"
if "%TARGET%"=="" set "TARGET=C:\TxData\rebelion\resources\[Streaming]\[PackArmas]"
set "REFERENCE=%BASE%references\snags_original\metas"

if not exist "%REFERENCE%\weapons\weapons.meta" (
  powershell -NoProfile -ExecutionPolicy Bypass -File "%BASE%references\download_original_gtav_metas.ps1"
)

python "%BASE%run_rebalance.py" ^
  --root "%TARGET%" ^
  --profile "%BASE%profiles\vanilla_repair_custom_plus15_absolute_v6.json" ^
  --reference-root "%REFERENCE%" ^
  --report "%BASE%reports\preview_v6.json"

pause
