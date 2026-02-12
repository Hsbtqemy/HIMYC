@echo off
setlocal
cd /d "%~dp0\..\.."
if not exist ".venv\Scripts\pythonw.exe" (
    echo Lancez d'abord scripts\windows\install.bat
    exit /b 1
)
set PYTHONPATH=src
.venv\Scripts\pythonw.exe -m corpusstudio.app.main
exit /b 0
