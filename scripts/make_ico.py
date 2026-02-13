#!/usr/bin/env python3
"""Génère resources/icons/icon.ico à partir de icon_512.png (pour Windows .exe). Nécessite Pillow."""
from pathlib import Path

try:
    from PIL import Image
except ImportError:
    raise SystemExit("Pillow requis : pip install Pillow")

REPO_ROOT = Path(__file__).resolve().parent.parent
SRC = REPO_ROOT / "resources" / "icons" / "icon_512.png"
OUT = REPO_ROOT / "resources" / "icons" / "icon.ico"

SIZES = [(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]


def main():
    if not SRC.exists():
        raise SystemExit(f"Source absente : {SRC}")
    img = Image.open(SRC)
    if img.mode != "RGBA":
        img = img.convert("RGBA")
    img.save(OUT, format="ICO", sizes=SIZES)
    print(f"OK : {OUT}")


if __name__ == "__main__":
    main()
