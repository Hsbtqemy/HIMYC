# Revue de code — Phase 6 (HowIMetYourCorpus)  
**Packaging Windows (PyInstaller) et mise à jour optionnelle**

*Date : février 2025 — 1ʳᵉ révision (correctifs appliqués)*

---

## 1. Contexte

La Phase 6 ajoute le **packaging Windows** via PyInstaller (exécutable unique `.exe`) et une **mise à jour optionnelle** : le menu Aide permet d’afficher la version et d’ouvrir la page des releases GitHub pour télécharger une nouvelle version. Ce document résume la revue du code Phase 6 et liste les corrections ou évolutions à prévoir.

---

## 2. Ce qui va bien

- **Spec PyInstaller** : `HowIMetYourCorpus.spec` — point d’entrée `main.py`, `pathex=['src']`, **datas** : `schema.sql` et dossier `migrations/` inclus dans `howimetyourcorpus/core/storage` ; `hiddenimports` pour `db` et `project_store` ; exe en onefile, `console=False`, `upx=True`.
- **Résolution des chemins** : `db.py` utilise `STORAGE_DIR = Path(__file__).parent` puis `SCHEMA_SQL = (STORAGE_DIR / "schema.sql").read_text(...)` et `MIGRATIONS_DIR = STORAGE_DIR / "migrations"`. En mode frozen, PyInstaller place les datas au même chemin relatif que le module ; `__file__` pointe vers l’extraction temporaire, donc schéma et migrations sont trouvés sans adaptation.
- **Build local** : `scripts/windows/build_exe.bat` — vérifie `.venv`, installe PyInstaller si besoin, lance `pyinstaller --noconfirm HowIMetYourCorpus.spec`, vérifie la présence de `dist/HowIMetYourCorpus.exe`.
- **CI/CD** : `.github/workflows/release.yml` — déclenché sur push de tag `v*` ; Windows, Python 3.12, `pip install -e .` + `pyinstaller` ; build du .exe puis `softprops/action-gh-release@v2` avec `files: dist/HowIMetYourCorpus.exe` ; pas de zip, asset unique.
- **UI** : Menu **Aide** — « À propos » (version depuis `howimetyourcorpus.__version__`, texte explicatif + rappel « Vérifier les mises à jour ») ; « Vérifier les mises à jour » ouvre `https://github.com/Hsbtqemy/HIMYC/releases` via `QDesktopServices.openUrl`.
- **Téléchargement utilisateur** : `download_exe.ps1` (URL latest release, `Invoke-WebRequest`, message d’erreur si pas de release) ; `download_exe.bat` appelle le script PowerShell.
- **Documentation** : README section « Construire le .exe (Phase 6) » ; RECAP Phase 6 ; `.gitignore` commenté pour le .spec (versionné).

---

## 3. Points à traiter

### 3.1 Priorité basse

#### A. Dépendance optionnelle `rapidfuzz` (Phase 4) non incluse dans le .exe

**Fichiers :** `pyproject.toml`, `HowIMetYourCorpus.spec`

**Constat :** L’alignement (Phase 4) utilise `rapidfuzz` si disponible, sinon Jaccard. Le build PyInstaller n’installe que les dépendances du projet (`pip install -e .`) ; `rapidfuzz` est en extra `[align]`. Si l’utilisateur n’a pas installé `.[align]` avant le build, le .exe n’embarquera pas rapidfuzz et l’alignement utilisera le fallback Jaccard.

**À faire :** Documenter dans le README / RECAP que pour un .exe avec meilleure similarité (Phase 4), lancer le build après `pip install -e ".[align]"`. Optionnel : ajouter dans le workflow release une étape qui installe `.[align]` avant `pyinstaller` si on souhaite que les releases officielles incluent rapidfuzz.

---

#### B. Version affichée dans « À propos » vs tag de release

**Fichiers :** `src/howimetyourcorpus/__init__.py` (`__version__`), workflow release (tag `v*`)

**Constat :** La version affichée dans l’app vient de `__version__` (ex. `0.3.0`). Les releases GitHub sont créées à partir du tag (ex. `v0.2.0`). Si le tag et `__version__` ne sont pas synchronisés, l’utilisateur peut voir une version différente de celle de la release.

**À faire :** Rappel process : avant de pousser un tag `vX.Y.Z`, mettre à jour `__version__` dans `__init__.py` à `X.Y.Z` pour cohérence. Optionnel : script ou CI check qui vérifie que le tag et `__version__` correspondent.

---

#### C. Tests du build frozen (optionnel)

**Constat :** Aucun test automatisé ne vérifie que l’exe démarre ou que le schéma/migrations sont bien chargés en mode frozen. Les tests actuels s’exécutent en environnement Python normal.

**À faire :** Optionnel : étape CI qui lance brièvement l’exe (ex. `dist/HowIMetYourCorpus.exe` avec un argument « headless » ou timeout) pour détecter une régression de packaging ; ou au moins documenter une vérification manuelle (lancer l’exe, ouvrir un projet, créer la DB).

---

## 4. Bilan des correctifs appliqués

| Réf   | Sujet | Statut |
|-------|--------|--------|
| § 3.1 A | Build .exe avec rapidfuzz | ✅ README et RECAP : `pip install -e ".[align]"` avant build ; workflow release.yml installe `.[align]` pour embarquer rapidfuzz dans le .exe. |
| § 3.1 B | __version__ et tag synchronisés | ✅ README : note « Garder __version__ (__init__.py) et le tag synchronisés avant de pousser le tag ». |
| § 3.1 C | Test build frozen (optionnel) | ⏸ Non fait (optionnel). |

---

## 5. Synthèse pour le dev (référence)

| Priorité | Réf   | Sujet |
|----------|-------|--------|
| Basse    | § 3.1 A | Documenter build .exe avec rapidfuzz (pip install -e ".[align]") ; optionnel : inclure [align] dans le workflow release. |
| Basse    | § 3.1 B | Garder __version__ et tag de release synchronisés ; optionnel : check CI. |
| Basse    | § 3.1 C | Optionnel : test ou vérification manuelle que l’exe démarre et charge schema/migrations. |

---

## 6. Fichiers Phase 6 concernés

| Fichier | Rôle Phase 6 |
|---------|----------------|
| `HowIMetYourCorpus.spec` | Spec PyInstaller : entry point, datas schema.sql + migrations, hiddenimports, onefile, console=False. |
| `scripts/windows/build_exe.bat` | Build local du .exe (venv, pyinstaller, vérification dist/). |
| `.github/workflows/release.yml` | Build .exe sur tag v*, upload asset sur la release GitHub. |
| `src/howimetyourcorpus/app/ui_mainwindow.py` | Menu Aide : À propos (__version__), Vérifier les mises à jour (URL releases). |
| `src/howimetyourcorpus/__init__.py` | __version__ (affichée dans À propos). |
| `scripts/windows/download_exe.ps1` | Téléchargement du .exe depuis la dernière release. |
| `scripts/windows/download_exe.bat` | Lance download_exe.ps1. |
| `README.md` | Section « Construire le .exe (Phase 6) ». |
| `RECAP.md` | Phase 6 décrite. |
| `.gitignore` | dist/, build/ ; .spec versionné. |

---

*Document généré à partir de la revue de code Phase 6 du projet HowIMetYourCorpus. Correctifs § 3.1 A–B appliqués.*
