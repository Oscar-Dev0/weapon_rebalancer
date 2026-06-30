@echo off
setlocal
cd /d "%~dp0"
python run_rebalance.py --validate-profiles profiles
if errorlevel 1 goto error
python -m unittest discover -s tests -v
if errorlevel 1 goto error
python -m compileall -q .
if errorlevel 1 goto error
echo.
echo Validacion completa: OK
pause
exit /b 0
:error
echo.
echo Validacion completa: ERROR
pause
exit /b 1
