#!/usr/bin/env bash
# Build HowIMetYourCorpus.app (macOS) — PyInstaller + icône
set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
cd "$REPO_ROOT"

echo "HowIMetYourCorpus - Build .app (macOS)"
echo ""

# Icône : générer .icns si nécessaire
if [[ ! -f "resources/icons/icon.icns" ]]; then
  if [[ -f "resources/icons/icon_512.png" ]]; then
    echo "Génération de l'icône .icns..."
    "$SCRIPT_DIR/make_icns.sh"
  else
    echo "Attention: resources/icons/icon_512.png absent — l'app utilisera l'icône par défaut."
  fi
fi

# Environnement virtuel optionnel
if [[ -d ".venv/bin" ]]; then
  PYTHON=".venv/bin/python"
  PIP=".venv/bin/pip"
else
  PYTHON="python3"
  PIP="pip3"
fi

$PIP install -e ".[align]" -q
$PIP install pyinstaller -q

echo "Lancement de PyInstaller..."
$PYTHON -m PyInstaller --noconfirm HowIMetYourCorpus.spec

if [[ -d "dist/HowIMetYourCorpus.app" ]]; then
  echo ""
  echo "OK: dist/HowIMetYourCorpus.app"
  echo "L'app se trouve dans dist/ à la racine du projet."
else
  echo "Erreur: dist/HowIMetYourCorpus.app non créé."
  exit 1
fi
