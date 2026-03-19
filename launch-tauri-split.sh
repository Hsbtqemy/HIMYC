#!/usr/bin/env bash
# =============================================================================
# launch-tauri-split.sh — MX-018 : Lancement HIMYC en deux fenêtres Terminal
# =============================================================================
#
# Variante de launch-tauri.sh qui ouvre deux panneaux Terminal.app séparés
# via osascript, pour suivre les logs du backend et du frontend indépendamment.
#
# Usage :
#   ./launch-tauri-split.sh
#
# Dépôt officiel du shell Tauri :
#   https://github.com/Hsbtqemy/HIMYC_Tauri.git
# Chemin : HIMYC_TAURI_DIR ou défaut /Users/hsmy/Dev/HIMYC_Tauri
#
# Prérequis :
#   chmod +x /Users/hsmy/Dev/HIMYC/launch-tauri-split.sh
#
# Architecture des fenêtres ouvertes :
#   Fenêtre 1 (Terminal A) : Backend Python — uvicorn, port 8765
#   Fenêtre 2 (Terminal B) : Frontend Tauri — npm run tauri dev, port Vite 1421
#
# Note Windows : osascript est spécifique à macOS. Sur Windows, remplacer par
#   deux appels : start cmd /k "..."
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
# Chemins et ports
# ---------------------------------------------------------------------------
BACKEND_DIR="/Users/hsmy/Dev/HIMYC"
FRONTEND_DIR="${HIMYC_TAURI_DIR:-/Users/hsmy/Dev/HIMYC_Tauri}"
BACKEND_PORT=8765
VITE_PORT=1421

# ---------------------------------------------------------------------------
# Bandeau de démarrage
# ---------------------------------------------------------------------------
echo ""
echo -e "${CYAN}${BOLD}╔══════════════════════════════════════════════════════════════════╗${RESET}"
echo -e "${CYAN}${BOLD}║     HIMYC — MODE TAURI SPLIT  (deux fenêtres Terminal)          ║${RESET}"
echo -e "${CYAN}${BOLD}╠══════════════════════════════════════════════════════════════════╣${RESET}"
echo -e "${CYAN}${BOLD}║  ▸ Terminal A : Backend  FastAPI/uvicorn → port ${BACKEND_PORT}          ║${RESET}"
echo -e "${CYAN}${BOLD}║  ▸ Terminal B : Frontend Vite + Tauri    → port ${VITE_PORT}           ║${RESET}"
echo -e "${CYAN}${BOLD}║                                                                  ║${RESET}"
echo -e "${CYAN}${BOLD}║  Ce script ≠ HIMYC PyQt (launch_himyc.py)                       ║${RESET}"
echo -e "${CYAN}${BOLD}╚══════════════════════════════════════════════════════════════════╝${RESET}"
echo ""

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
check_cmd osascript "osascript est requis (macOS uniquement)"

if [[ ! -d "$FRONTEND_DIR" ]]; then
  echo -e "${RED}ERREUR : répertoire frontend introuvable : ${FRONTEND_DIR}${RESET}"
  echo -e "${YELLOW}  git clone https://github.com/Hsbtqemy/HIMYC_Tauri.git${RESET}"
  echo -e "${YELLOW}  Ou : export HIMYC_TAURI_DIR=/chemin/vers/votre/clone${RESET}"
  exit 1
fi
echo -e "  ${GREEN}✓${RESET} HIMYC_Tauri trouvé (${FRONTEND_DIR})"
echo ""

# ---------------------------------------------------------------------------
# 2. Vérification du port backend (8765)
# ---------------------------------------------------------------------------
echo -e "${BOLD}[2/4] Vérification du port ${BACKEND_PORT} (backend)...${RESET}"

BACKEND_ALREADY_RUNNING=false
if lsof -ti:"$BACKEND_PORT" &>/dev/null; then
  echo -e "${YELLOW}AVERTISSEMENT : Le port ${BACKEND_PORT} est déjà utilisé.${RESET}"
  echo -e "${YELLOW}  Le backend tourne peut-être déjà. Continuons sans le relancer.${RESET}"
  echo -e "${YELLOW}  Pour forcer : lsof -ti:${BACKEND_PORT} | xargs kill -9${RESET}"
  BACKEND_ALREADY_RUNNING=true
else
  echo -e "  ${GREEN}✓${RESET} Port ${BACKEND_PORT} libre"
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
# 4. Ouverture des deux fenêtres Terminal via osascript
# ---------------------------------------------------------------------------
echo -e "${BOLD}[4/4] Ouverture des fenêtres Terminal...${RESET}"

# --- Fenêtre A : Backend Python ---
if [[ "$BACKEND_ALREADY_RUNNING" == false ]]; then
  echo -e "  Ouverture Terminal A (backend)..."
  osascript <<EOF
tell application "Terminal"
  activate
  -- Ouvrir une nouvelle fenêtre pour le backend
  set winA to do script "printf '\\\\033[0;36m\\\\033[1m[HIMYC BACKEND — port ${BACKEND_PORT}]\\\\033[0m\\\\n' && cd '${BACKEND_DIR}' && uvicorn howimetyourcorpus.api.server:app --host 127.0.0.1 --port ${BACKEND_PORT} --reload"
  set custom title of winA to "HIMYC Backend :${BACKEND_PORT}"
end tell
EOF
  echo -e "  ${GREEN}✓${RESET} Terminal A ouvert (backend uvicorn)"
  echo -e "  ${CYAN}Attente 2s pour laisser le backend démarrer...${RESET}"
  sleep 2
else
  echo -e "  ${YELLOW}Terminal A ignoré (backend déjà actif sur le port ${BACKEND_PORT})${RESET}"
fi

# --- Fenêtre B : Frontend Tauri ---
echo -e "  Ouverture Terminal B (frontend Tauri)..."
osascript <<EOF
tell application "Terminal"
  activate
  -- Ouvrir une nouvelle fenêtre pour le frontend
  set winB to do script "printf '\\\\033[0;36m\\\\033[1m[HIMYC FRONTEND — Vite port ${VITE_PORT}]\\\\033[0m\\\\n' && cd '${FRONTEND_DIR}' && npm run tauri dev"
  set custom title of winB to "HIMYC Frontend Tauri"
end tell
EOF
echo -e "  ${GREEN}✓${RESET} Terminal B ouvert (frontend npm run tauri dev)"

# ---------------------------------------------------------------------------
# 5. Message de fin dans ce terminal (script principal)
# ---------------------------------------------------------------------------
echo ""
echo -e "${GREEN}${BOLD}Les deux fenêtres Terminal sont ouvertes.${RESET}"
echo ""
echo -e "  ${BOLD}Terminal A :${RESET} Backend  → http://127.0.0.1:${BACKEND_PORT}"
echo -e "  ${BOLD}Terminal B :${RESET} Frontend → http://localhost:${VITE_PORT}"
echo ""
echo -e "${YELLOW}Pour arrêter :${RESET}"
echo -e "  • Fermez les fenêtres Terminal A et B, ou Ctrl+C dans chacune"
echo -e "  • Backend  : lsof -ti:${BACKEND_PORT} | xargs kill -9"
echo -e "  • Frontend : lsof -ti:${VITE_PORT} | xargs kill -9"
echo ""
