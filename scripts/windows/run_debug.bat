@echo off
setlocal
cd /d "%~dp0\..\.."
if not exist ".venv\Scripts\python.exe" (
    echo Lancez d'abord scripts\windows\install.bat
    exit /b 1
)
set PYTHONPATH=src
.venv\Scripts\python.exe -m howimetyourcorpus.app.main
exit /b 0
