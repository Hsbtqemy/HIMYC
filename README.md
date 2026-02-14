# HowIMetYourCorpus

Application desktop Windows pour construire, normaliser, indexer et explorer des transcriptions (et sous-titres) depuis des sources web. Interface PySide6, architecture modulaire et extensible.

## Prérequis

- **Windows 10/11**
- Connexion internet (pour le scraping des sources configurées)
- Pour l’installation depuis les sources : **Python 3.11+**

---

## Installation

### Option A — Exécutable .exe (sans Python)

1. **Télécharger le .exe** depuis la dernière [release GitHub](https://github.com/Hsbtqemy/HIMYC/releases/latest) : l’asset **HowIMetYourCorpus.exe** est un fichier unique (pas de zip).
2. Ou exécuter le script de téléchargement (place le .exe dans le dossier courant) :
   ```bat
   scripts\windows\download_exe.bat
   ```
   Ou en PowerShell :
   ```powershell
   .\scripts\windows\download_exe.ps1
   ```
3. Lancer l’application en double-cliquant sur **HowIMetYourCorpus.exe** ou depuis un terminal : `.\HowIMetYourCorpus.exe`.

Le .exe est placé dans le dossier où vous avez lancé le script (ou où vous l’avez téléchargé) ; il n’est pas extrait d’une archive.

### Option B — Depuis les sources (Python)

1. Ouvrir un terminal dans le dossier du projet.
2. Exécuter le script d’installation :
   ```bat
   scripts\windows\install.bat
   ```
3. Ce script crée un environnement virtuel `.venv`, installe les dépendances et le package en mode éditable.

**Alignement (Phase 4) :** pour une meilleure similarité textuelle segment↔cues, l’installation optionnelle de `rapidfuzz` est recommandée : `pip install rapidfuzz` (ou `pip install -e ".[align]"`). Sans rapidfuzz, le code utilise un fallback Jaccard sur tokens.

---

## Lancement

### Avec l’exécutable .exe

- Double-clic sur **HowIMetYourCorpus.exe**, ou en ligne de commande : `.\HowIMetYourCorpus.exe`.

### Avec Python (sources)

- **Sans console** (recommandé pour l’usage) :
  ```bat
  scripts\windows\run.bat
  ```
- **Avec console** (débogage) :
  - **Windows (cmd)** :
    ```bat
    .venv\Scripts\activate
    set PYTHONPATH=src
    python -m howimetyourcorpus.app.main
    ```
  - **macOS / Linux (bash, zsh)** :
    ```bash
    source .venv/bin/activate
    export PYTHONPATH=src
    python -m howimetyourcorpus.app.main
    ```
  (Si le package n'est pas installé en éditable, `PYTHONPATH=src` est nécessaire.)

## Projet exemple (EN + FR)

Un **projet démo** est fourni dans le dépôt pour comprendre la mécanique sans scraper :

- **Dossier** : `example/` à la racine du projet.
- **Contenu** : un épisode S01E01 (transcript court EN), sous-titres SRT EN et FR à importer.
- **Étapes** : ouvrir le projet `example` → Normaliser sélection (raw → clean) → Indexer DB → Segmenter → importer `s01e01_en.srt` et `s01e01_fr.srt` → Aligner → Inspecteur / Concordancier.

Voir **example/README.md** pour les instructions détaillées.

---

## Utilisation rapide

1. **Créer ou ouvrir un projet** (onglet Pilotage, section Projet)  
   - Choisir un dossier pour le projet (ou en ouvrir un existant).  
   - Renseigner la source (ex. `subslikescript`) et l’URL de la page série.  
   - Valider et initialiser.

2. **Construire le corpus** (onglet Pilotage, section Corpus)  
   - « Découvrir épisodes » : récupère la liste des épisodes depuis la source.  
   - **Filtre Saison** : choisir « Toutes les saisons » ou « Saison 1 », « Saison 2 », etc. pour afficher uniquement les épisodes d’une saison ; **« Cocher la saison »** coche tous les épisodes de la saison affichée (ou tout si « Toutes les saisons »).  
   - **« Périmètre action »** : choisir `Épisode courant`, `Sélection`, `Saison filtrée` ou `Tout le corpus`.  
   - « Télécharger » : récupère les pages HTML et extrait le texte brut selon le périmètre choisi.  
   - « Normaliser » : applique le profil de normalisation (RAW → CLEAN) selon le périmètre choisi.  
   - « Segmenter » / « Indexer DB » : segmente et indexe selon le périmètre choisi.  
   - « Tout faire » : enchaîne Télécharger → Normaliser → Segmenter → Indexer DB sur le périmètre choisi.  
   - **« Forcer re-traitement »** : rejoue les étapes idempotentes (normalisation/segmentation/indexation) même si des artefacts existent déjà.
   - **« Exporter corpus »** : exporte les épisodes normalisés en **TXT**, **CSV**, **JSON**, **Word (.docx)**, ou en **segmenté** : **JSONL** / **CSV** par **utterances** (tours de parole) ou par **phrases**.
   - Pendant un job (Télécharger / Normaliser / Segmenter / Indexer / Tout faire), les actions Pilotage sont temporairement verrouillées pour éviter les doubles lancements ; utilisez **« Annuler »** si nécessaire.
   - Le haut de l’onglet Pilotage rappelle la politique de profils (acquisition vs normalisation vs export) et propose des raccourcis vers **Inspecteur**, **Validation & Annotation** et **Concordance**.

   **Workflow recommandé (batch par saison)**  
   - **Option A — Saison par saison** : pour chaque saison, sélectionner « Saison N » + `Périmètre action = Saison filtrée` → « Télécharger » → « Normaliser » → « Indexer DB » (ou segmenter / importer SRT / aligner selon vos besoins), puis passer à la saison suivante.  
   - **Option B — Tout normaliser puis traiter par saison** : `Périmètre action = Tout le corpus` + « Télécharger » puis « Normaliser » ; ensuite utiliser le filtre saison + `Périmètre action = Saison filtrée` pour segmenter, importer les sous-titres et aligner saison par saison.
   - **Mode SRT-first** : si vous importez d’abord des sous-titres (sans transcripts), le Pilotage propose une bascule directe vers **Concordance** (scope **Cues**) pour commencer l’exploration ; l’alignement segment↔cues reste disponible après `Télécharger → Normaliser → Segmenter`.

3. **Inspecter** (onglet Inspecteur)  
   - Choisir un épisode et comparer RAW vs CLEAN, stats et exemples de fusions.  
   - **Vue Segments** (Phase 2) : basculer sur « Segments » pour afficher la liste des phrases/tours de parole ; cliquer sur un segment pour le surligner dans le texte CLEAN.  
   - **« Segmente l'épisode »** : produit les segments (phrases + tours) et les indexe en DB (écrit `episodes/<id>/segments.jsonl`).
   - **« Forcer re-traitement »** (Inspecteur) : relance normalisation/segmentation de l’épisode courant sans skip.
   - Depuis l’Inspecteur, un accès direct vers **Validation & Annotation** est disponible pour enchaîner sur l’alignement puis l’annotation personnages.

4. **Sous-titres** (dans l’onglet Inspecteur, panneau Sous-titres, Phase 3)  
   - Choisir un épisode et une langue (en/fr/it), puis **« Importer SRT/VTT... »** pour importer un fichier .srt ou .vtt.  
   - **« Importer SRT en masse... »** : scan d’un dossier, mapping fichier → épisode/langue, import en lot.  
   - **« Télécharger depuis OpenSubtitles… »** : téléchargement de sous-titres depuis l’API OpenSubtitles (clé API gratuite sur opensubtitles.com ; IMDb ID de la série requis).  
   - La liste des pistes pour l’épisode affiche langues, format et nombre de cues.

5. **Alignement et annotation** (onglet Validation & Annotation, section Alignement, Phase 4–5)  
   - Choisir un épisode et un run d’alignement (ou **« Lancer alignement »** pour en créer un).  
   - L’alignement associe les segments (phrases) au transcript aux cues EN, puis les cues EN à la langue cible choisie par recouvrement temporel/similarité.  
   - Table des liens (segment, cue, cue target, confiance, statut) ; menu contextuel **Accepter / Rejeter** ; **« Exporter aligné »** en CSV ou JSONL.  
   - **Phase 5** : **« Exporter concordancier parallèle »** (CSV / TSV / JSONL : segment + EN + langue cible) ; **« Rapport HTML »** (stats + échantillon) ; **« Stats »** (nb liens, pivot/target, confiance moyenne, par statut).
   - La section Personnages du même onglet permet l’assignation et la propagation.

6. **Concordance** (onglet Concordance)  
   - Saisir un terme, filtrer par saison/épisode, afficher les résultats KWIC.  
   - **Scope** : « Épisodes (texte) », « Segments » ou **« Cues (sous-titres) »** ; **Kind** : phrases/tours (si scope Segments) ; **Langue** : en/fr/it (si scope Cues).  
   - **« Exporter résultats »** : exporte en **CSV**, **TSV**, **JSON** ou **JSONL** (segments : `segment_id`, `kind` ; cues : `cue_id`, `lang`).  
   - Double-clic : ouvre l’Inspecteur sur l’épisode concerné.

7. **Logs** (menu **Outils → Journaux → Journal d’exécution (live)**)  
   - Ouvrir le journal live et/ou le fichier de log du projet.

## Configuration et profils

- Chaque projet contient un `config.toml` à la racine du projet.
- Un preset exemple est fourni : `preset_himym.toml` (How I Met Your Mother sur subslikescript).  
  Le code reste **générique** : toute URL de série valide pour la source configurée fonctionne.

## Notes légales et limites

- **Usage local uniquement** : les données sont stockées sur votre machine ; aucune redistribution intégrée des contenus.
- **Scraping** : respectez les conditions d’utilisation des sites sources et un rythme de requêtes raisonnable (rate limit configurable).  
  L’outil est fourni à des fins de recherche et d’analyse personnelle ; vous êtes responsable du respect du droit applicable.

## Ajouter un nouvel adapteur (phase future)

1. Créer `src/howimetyourcorpus/core/adapters/<nom_source>.py`.
2. Implémenter l’interface `SourceAdapter` (discover_series, fetch_episode_html, parse_episode, normalize_episode_id).
3. Enregistrer l’adapteur dans le registre : `AdapterRegistry.register(MonAdapter())`.
4. Ajouter le `source_id` dans la config projet si besoin.

## Construire le .exe (développeurs, Phase 6)

Pour générer **HowIMetYourCorpus.exe** en local (dossier **dist/** à la racine du projet) :

1. Avoir installé le projet (Option B ci-dessus).
2. *(Optionnel)* Pour un .exe avec meilleure similarité textuelle (Phase 4, alignement) : `pip install -e ".[align]"` avant le build, afin d’embarquer **rapidfuzz** ; sinon le .exe utilise le fallback Jaccard.
3. Lancer le build :
   ```bat
   scripts\windows\build_exe.bat
   ```
4. L’exécutable est produit dans **dist\HowIMetYourCorpus.exe**.

Le build utilise **HowIMetYourCorpus.spec** (PyInstaller) qui inclut le schéma SQL et les migrations en données embarquées. Le menu **Aide → À propos** affiche la version ; **Aide → Vérifier les mises à jour** ouvre la page des releases GitHub.

**Publier une release** : créer un tag (ex. `v0.3.0`) et le pousser. Le workflow [.github/workflows/release.yml](.github/workflows/release.yml) build le .exe et l’attache à la release. **Garder `__version__`** (dans `src/howimetyourcorpus/__init__.py`) **et le tag synchronisés** (ex. tag `v0.3.0` ↔ `__version__ = "0.3.0"`) avant de pousser le tag.

---

## Tests

```bat
set PYTHONPATH=src
python -m pytest tests\ -v
```

## Structure du projet

```
src/howimetyourcorpus/
  app/          # Bootstrap UI, MainWindow, widgets, workers
  core/         # Modèles, pipeline, adapters, normalisation, stockage
tests/          # Tests (adapters, normalisation, DB KWIC)
scripts/windows/# install.bat, run.bat, build_exe.bat, download_exe.ps1
.github/workflows/# release.yml (build .exe et release GitHub)
HowIMetYourCorpus.spec  # Spec PyInstaller (Phase 6, datas schema + migrations)
dist/           # Généré par build_exe : HowIMetYourCorpus.exe (ignoré par git)
```

## Documentation projet

- **RECAP.md** — Structure, commandes, layout, phases.
- **DOC_BACKLOG.md** — Demandes et idées (réalisé / à faire).
- **DOC_PLAN_ACTION.md** — Plan priorisé et checklist (P0/P1/P2).
- **DOC_NETTOYAGE.md** — Rituel de nettoyage des doc. Les revues de phase historiques sont dans `doc/archive/`.

## Licence

MIT.
