#!/usr/bin/env bash
# =============================================================================
# launch-tauri.sh — MX-018 : Script de lancement unifié HIMYC (mode Tauri)
# =============================================================================
#
# Usage :
#   ./launch-tauri.sh
#
# Ce script lance :
#   - Le backend Python (FastAPI/uvicorn, port 8765) dans un nouveau Terminal.app
#   - Le frontend Tauri (npm run tauri dev, port Vite 1421) dans ce terminal
#
# Dépôt officiel du shell Tauri :
#   https://github.com/Hsbtqemy/HIMYC_Tauri.git
#   (clone typique → dossier HIMYC_Tauri à côté de ce repo)
#
# Chemin du frontend : variable d'environnement HIMYC_TAURI_DIR (prioritaire),
# sinon défaut macOS ci-dessous.
#
# Prérequis :
#   chmod +x /Users/hsmy/Dev/HIMYC/launch-tauri.sh
#
# Note Windows : sur Windows, remplacer l'appel `open -a Terminal` par
#   start cmd /k "cd /d %BACKEND_DIR% && uvicorn ..."
# et adapter les chemins en conséquence.
# =============================================================================

set -euo pipefail

# ---------------------------------------------------------------------------
# Couleurs ANSI
# ---------------------------------------------------------------------------
RED='\033[0;31m'
YELLOW='\033[1;33m'
GREEN='\033[0;32m'
CYAN='\033[0;36m'
BOLD='\033[1m'
RESET='\033[0m'

# ---------------------------------------------------------------------------
# Chemins
# ---------------------------------------------------------------------------
BACKEND_DIR="/Users/hsmy/Dev/HIMYC"
FRONTEND_DIR="${HIMYC_TAURI_DIR:-/Users/hsmy/Dev/HIMYC_Tauri}"
BACKEND_PORT=8765
VITE_PORT=1421

# ---------------------------------------------------------------------------
# Bandeau de démarrage — lever l'ambiguïté Tauri vs PyQt
# ---------------------------------------------------------------------------
echo ""
echo -e "${CYAN}${BOLD}╔══════════════════════════════════════════════════════════════════╗${RESET}"
echo -e "${CYAN}${BOLD}║          HIMYC — MODE TAURI  (frontend TypeScript + Rust)        ║${RESET}"
echo -e "${CYAN}${BOLD}╠══════════════════════════════════════════════════════════════════╣${RESET}"
echo -e "${CYAN}${BOLD}║  ▸ Backend  : FastAPI/uvicorn  → http://127.0.0.1:${BACKEND_PORT}          ║${RESET}"
echo -e "${CYAN}${BOLD}║  ▸ Frontend : Vite + Tauri    → http://localhost:${VITE_PORT}           ║${RESET}"
echo -e "${CYAN}${BOLD}║                                                                  ║${RESET}"
echo -e "${CYAN}${BOLD}║  Ce script ≠ HIMYC PyQt (launch_himyc.py)                       ║${RESET}"
echo -e "${CYAN}${BOLD}╚══════════════════════════════════════════════════════════════════╝${RESET}"
echo ""

# ---------------------------------------------------------------------------
# Trap SIGINT — message de nettoyage propre
# ---------------------------------------------------------------------------
cleanup() {
  echo ""
  echo -e "${YELLOW}${BOLD}[HIMYC Tauri] Interruption reçue. Arrêt du frontend.${RESET}"
  echo -e "${YELLOW}Le backend Python (Terminal.app séparé) doit être arrêté manuellement.${RESET}"
  echo -e "${YELLOW}  → Fermez la fenêtre Terminal ouverte pour le backend, ou :${RESET}"
  echo -e "${YELLOW}  → lsof -ti:${BACKEND_PORT} | xargs kill -9${RESET}"
  echo ""
}
trap cleanup INT

# ---------------------------------------------------------------------------
# 1. Vérification des prérequis
# ---------------------------------------------------------------------------
echo -e "${BOLD}[1/4] Vérification des prérequis...${RESET}"

check_cmd() {
  local cmd="$1"
  local hint="$2"
  if ! command -v "$cmd" &>/dev/null; then
    echo -e "${RED}ERREUR : '$cmd' introuvable. ${hint}${RESET}"
    exit 1
  fi
  echo -e "  ${GREEN}✓${RESET} $cmd"
}

check_cmd uvicorn   "Installer les dépendances Python : pip install -r requirements.txt"
check_cmd npm       "Installer Node.js >= 18 : https://nodejs.org"
check_cmd cargo     "Installer Rust via rustup : https://rustup.rs"

if [[ ! -d "$FRONTEND_DIR" ]]; then
  echo -e "${RED}ERREUR : répertoire frontend introuvable : ${FRONTEND_DIR}${RESET}"
  echo -e "${YELLOW}  Clonez le shell Tauri : git clone https://github.com/Hsbtqemy/HIMYC_Tauri.git${RESET}"
  echo -e "${YELLOW}  Ou définissez HIMYC_TAURI_DIR vers votre clone existant.${RESET}"
  exit 1
fi
echo -e "  ${GREEN}✓${RESET} HIMYC_Tauri trouvé (${FRONTEND_DIR})"
echo ""

# ---------------------------------------------------------------------------
# 2. Vérification du port backend (8765)
# ---------------------------------------------------------------------------
echo -e "${BOLD}[2/4] Vérification du port ${BACKEND_PORT} (backend)...${RESET}"

if lsof -ti:"$BACKEND_PORT" &>/dev/null; then
  echo -e "${YELLOW}AVERTISSEMENT : Le port ${BACKEND_PORT} est déjà utilisé.${RESET}"
  echo -e "${YELLOW}  Le backend tourne peut-être déjà. Continuons sans le relancer.${RESET}"
  echo -e "${YELLOW}  Pour forcer le redémarrage : lsof -ti:${BACKEND_PORT} | xargs kill -9${RESET}"
  BACKEND_ALREADY_RUNNING=true
else
  echo -e "  ${GREEN}✓${RESET} Port ${BACKEND_PORT} libre"
  BACKEND_ALREADY_RUNNING=false
fi
echo ""

# ---------------------------------------------------------------------------
# 3. Vérification du port Vite (1421) — kill automatique si occupé
# ---------------------------------------------------------------------------
echo -e "${BOLD}[3/4] Vérification du port ${VITE_PORT} (Vite/frontend)...${RESET}"

if lsof -ti:"$VITE_PORT" &>/dev/null; then
  echo -e "${YELLOW}Port ${VITE_PORT} occupé. Arrêt du process en conflit...${RESET}"
  lsof -ti:"$VITE_PORT" | xargs kill -9 2>/dev/null || true
  sleep 1
  if lsof -ti:"$VITE_PORT" &>/dev/null; then
    echo -e "${RED}ERREUR : Impossible de libérer le port ${VITE_PORT}.${RESET}"
    exit 1
  fi
  echo -e "  ${GREEN}✓${RESET} Port ${VITE_PORT} libéré"
else
  echo -e "  ${GREEN}✓${RESET} Port ${VITE_PORT} libre"
fi
echo ""

# ---------------------------------------------------------------------------
# 4. Lancement du backend dans un nouveau Terminal.app
# ---------------------------------------------------------------------------
echo -e "${BOLD}[4/4] Lancement des services...${RESET}"

if [[ "$BACKEND_ALREADY_RUNNING" == false ]]; then
  echo -e "  Ouverture d'un nouveau Terminal.app pour le backend..."
  # Ouvre un nouveau Terminal.app avec la commande uvicorn dans le bon répertoire
  open -a Terminal "$BACKEND_DIR"
  sleep 0.5
  osascript <<EOF
tell application "Terminal"
  -- Cibler la dernière fenêtre ouverte (celle qu'on vient d'ouvrir)
  set w to front window
  do script "cd '${BACKEND_DIR}' && uvicorn howimetyourcorpus.api.server:app --host 127.0.0.1 --port ${BACKEND_PORT} --reload" in w
end tell
EOF
  echo -e "  ${GREEN}✓${RESET} Backend lancé dans Terminal.app (port ${BACKEND_PORT})"
  echo -e "  ${CYAN}Attente 2s pour laisser le backend démarrer...${RESET}"
  sleep 2
else
  echo -e "  ${YELLOW}Backend ignoré (déjà actif sur le port ${BACKEND_PORT})${RESET}"
fi

echo ""
echo -e "${GREEN}${BOLD}Lancement du frontend Tauri dans ce terminal...${RESET}"
echo -e "${CYAN}(Ctrl+C pour arrêter le frontend)${RESET}"
echo ""

# ---------------------------------------------------------------------------
# 5. Frontend en foreground dans ce terminal
# ---------------------------------------------------------------------------
cd "$FRONTEND_DIR"
exec npm run tauri dev
