@echo off
setlocal
set "DEST=C:\TxData\rebelion\resources\[standalone]\os_headshot_guard"
cd /d "%~dp0"
python run_rebalance.py --install-headshot-guard "%DEST%"
if errorlevel 1 exit /b 1
echo.
echo Agrega esta linea DESPUES de recursos de combate/antitank:
echo ensure os_headshot_guard
pause
