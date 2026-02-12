# Exemple de projet HowIMetYourCorpus (EN + IT)

Petit projet démo fourni dans le dépôt pour comprendre la mécanique : **transcript propre** → **segmentation** → **sous-titres SRT** (EN + IT) → **alignement** → Inspecteur / Concordancier.

## Contenu

- **config.toml** — configuration du projet
- **series_index.json** — un épisode : S01E01 "Demo"
- **episodes/S01E01/** — `raw.txt` et `clean.txt` (transcript court en anglais)
- **s01e01_en.srt** — sous-titres anglais (à importer)
- **s01e01_it.srt** — sous-titres italien (à importer)
- **corpus.db** — base pré-initialisée avec l’épisode S01E01 (si absente, lancer `create_demo_db.py`)

## Étapes pour un nouvel utilisateur

1. **Ouvrir le projet**  
   Lancer l’application, puis *Fichier → Ouvrir un projet* et choisir le dossier **example** (celui qui contient ce README).

2. **Indexer le texte**  
   Onglet *Corpus* : sélectionner S01E01, lancer le pipeline ou l’étape **Build DB index** pour indexer `clean.txt` dans la base.

3. **Segmenter**  
   Lancer l’étape **Segment** pour S01E01 (découpage en phrases / tours de parole).

4. **Importer les sous-titres**  
   Onglet *Sous-titres* : épisode S01E01, *Importer un fichier* — importer **s01e01_en.srt** (langue EN), puis **s01e01_it.srt** (langue IT).

5. **Aligner**  
   Onglet *Alignement* : épisode S01E01, lancer **Align** (pivot EN, langue cible IT).

6. **Explorer**  
   - **Inspecteur** : choisir S01E01 pour voir segments, cues et liens d’alignement.
   - **Concordancier** : rechercher un mot (ex. *Legendary*) et consulter le rapport parallèle EN / IT.

## Recréer corpus.db

Si le fichier **corpus.db** est absent (par exemple après un clone), exécuter une fois depuis la racine du projet :

```bash
PYTHONPATH=src python example/create_demo_db.py
```

Sous Windows (PowerShell) :

```powershell
$env:PYTHONPATH = "src"; python example/create_demo_db.py
```

Puis rouvrir le projet **example** dans l’application.
