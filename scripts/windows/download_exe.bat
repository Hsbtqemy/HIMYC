@echo off
:: Télécharge HowIMetYourCorpus.exe depuis la dernière release GitHub.
:: Place le .exe dans le dossier courant (pas dans un zip).
powershell -ExecutionPolicy Bypass -File "%~dp0download_exe.ps1"
pause
