"""Point d'entrée pour PyInstaller : assure que le package est sur sys.path puis lance l'app."""
import sys
import os

if getattr(sys, "frozen", False):
    # Exécutable PyInstaller : le bundle est extrait dans _MEIPASS
    sys.path.insert(0, sys._MEIPASS)
else:
    # Développement : ajouter src pour résoudre howimetyourcorpus
    _root = os.path.dirname(os.path.abspath(__file__))
    _src = os.path.join(_root, "src")
    if _src not in sys.path:
        sys.path.insert(0, _src)

from howimetyourcorpus.app.main import main

if __name__ == "__main__":
    sys.exit(main())
