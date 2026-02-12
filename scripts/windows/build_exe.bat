@echo off
setlocal
cd /d "%~dp0\..\.."
echo HowIMetYourCorpus - Build .exe (PyInstaller)
echo.

if not exist ".venv\Scripts\python.exe" (
    echo Erreur: environnement virtuel .venv absent. Lancez scripts\windows\install.bat
    exit /b 1
)

.venv\Scripts\python.exe -m pip install pyinstaller -q
.venv\Scripts\pyinstaller.exe --noconfirm HowIMetYourCorpus.spec

if errorlevel 1 (
    echo Build echoue.
    exit /b 1
)

if exist "dist\HowIMetYourCorpus.exe" (
    echo.
    echo OK: dist\HowIMetYourCorpus.exe
    echo L'exe se trouve dans le dossier dist\ a la racine du projet.
) else (
    echo Erreur: dist\HowIMetYourCorpus.exe non cree.
    exit /b 1
)
exit /b 0
