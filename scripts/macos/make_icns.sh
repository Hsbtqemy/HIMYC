#!/usr/bin/env bash
# Génère icon.icns à partir de icon_512.png (nécessite macOS : sips, iconutil)
set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
ICONS_DIR="${REPO_ROOT}/resources/icons"
SRC="${ICONS_DIR}/icon_512.png"
ICONSET="${ICONS_DIR}/HowIMetYourCorpus.iconset"
OUT="${ICONS_DIR}/icon.icns"

if [[ ! -f "$SRC" ]]; then
  echo "Erreur: $SRC absent. Ajoutez une image 512x512 (PNG) dans resources/icons/."
  exit 1
fi

mkdir -p "$ICONSET"
for size in 16 32 64 128 256 512; do
  sips -z $size $size "$SRC" --out "$ICONSET/icon_${size}x${size}.png"
  size2=$((size * 2))
  sips -z $size2 $size2 "$SRC" --out "$ICONSET/icon_${size}x${size}@2x.png"
done
iconutil -c icns "$ICONSET" -o "$OUT"
rm -rf "$ICONSET"
echo "OK: $OUT"
