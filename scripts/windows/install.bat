@echo off
setlocal
cd /d "%~dp0\..\.."
echo HowIMetYourCorpus - Installation Windows
echo.

if not exist ".venv" (
    echo Creation de l'environnement virtuel .venv...
    python -m venv .venv
    if errorlevel 1 (
        echo Erreur: impossible de creer le venv. Verifiez que Python 3.11+ est installe.
        exit /b 1
    )
)

echo Activation du venv et installation des dependances...
call .venv\Scripts\activate.bat
.venv\Scripts\python.exe -m pip install --upgrade pip -q
pip install -r requirements.txt -q
pip install -e . -q
if errorlevel 1 (
    echo Installation editable a echoue. Utilisez PYTHONPATH=src pour lancer.
)

echo.
echo Installation terminee. Lancez l'application avec: scripts\windows\run.bat
exit /b 0
