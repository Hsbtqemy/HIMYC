# Build macOS (.app)

## Prérequis

- macOS
- Python 3.11+
- PyInstaller (`pip install pyinstaller`)

## Icône

L’icône de l’app est générée depuis `resources/icons/icon_512.png` (512×512 px).

- Générer le fichier `.icns` (nécessaire pour le Dock/Finder) :
  ```bash
  ./scripts/macos/make_icns.sh
  ```
  Produit : `resources/icons/icon.icns`

- **Windows** : le .exe utilise `resources/icons/icon.ico`. Régénérer avec `python scripts/make_ico.py` (Pillow requis).

- Si `icon.icns` est absent au moment du build, PyInstaller utilisera l’icône par défaut.

## Build de l’application

À la racine du projet :

```bash
./scripts/macos/build_app.sh
```

Ou manuellement :

```bash
# optionnel si icon.icns manquant
./scripts/macos/make_icns.sh

pip install -e ".[align]" pyinstaller
pyinstaller --noconfirm HowIMetYourCorpus.spec
```

Résultat : `dist/HowIMetYourCorpus.app` (double-clic pour lancer).

## CI

Lors d’un push de tag `v*`, le workflow Release build aussi le .app sur `macos-latest` et l’attache à la release GitHub avec le .exe Windows.
