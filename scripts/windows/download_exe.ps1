# Télécharge HowIMetYourCorpus.exe depuis la dernière release GitHub.
# Place le .exe dans le dossier courant (pas dans un zip).
# Usage: .\download_exe.ps1   ou   powershell -ExecutionPolicy Bypass -File download_exe.ps1

$ErrorActionPreference = "Stop"
$Repo = "Hsbtqemy/HIMYC"
$ExeName = "HowIMetYourCorpus.exe"
$Url = "https://github.com/$Repo/releases/latest/download/$ExeName"

$Dest = Join-Path -Path (Get-Location) -ChildPath $ExeName
Write-Host "Téléchargement de $ExeName depuis GitHub (dernière release)..."
Write-Host "URL: $Url"
Write-Host "Destination: $Dest"
Write-Host ""

try {
    Invoke-WebRequest -Uri $Url -OutFile $Dest -UseBasicParsing
    Write-Host "OK: $ExeName enregistré dans le dossier courant."
    Write-Host "Lancement: .\$ExeName"
} catch {
    Write-Host "Erreur: $_"
    Write-Host "Vérifiez que le dépôt $Repo existe et qu'une release avec l'asset $ExeName est publiée."
    exit 1
}
