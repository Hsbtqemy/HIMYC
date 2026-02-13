# Exemple de projet HowIMetYourCorpus (EN + FR)

Petit projet démo fourni dans le dépôt pour comprendre la mécanique : **transcript propre** → **segmentation** → **sous-titres SRT** (EN + FR) → **alignement** → Inspecteur / Concordancier.

## Contenu

- **config.toml** — configuration du projet
- **series_index.json** — un épisode : S01E01 "Demo"
- **episodes/S01E01/** — `raw.txt` uniquement (transcript brut) ; pas de `clean.txt` pour pouvoir tester l’étape « Normaliser »
- **s01e01_en.srt** — sous-titres anglais (à importer)
- **s01e01_fr.srt** — sous-titres français (à importer)
- **corpus.db** — base pré-initialisée avec l’épisode S01E01 (si absente, lancer `create_demo_db.py`)

## Important

**Ne pas utiliser le bouton « Télécharger »** pour ce projet : le transcript brut est déjà dans `episodes/S01E01/raw.txt`. « Télécharger » sert à récupérer des épisodes depuis une source en ligne (ex. subslikescript.com) ; l’URL de l’exemple n’existe pas (404).

## Étapes pour un nouvel utilisateur

1. **Ouvrir le projet**  
   Lancer l’application, puis *Fichier → Ouvrir un projet* et choisir le dossier **example** (celui qui contient ce README).

2. **Normaliser**  
   Onglet *Corpus* : sélectionner S01E01, cliquer sur **Normaliser sélection** pour produire `clean.txt` à partir de `raw.txt` (test de l’étape raw → clean).

3. **Indexer le texte**  
   Onglet *Corpus* : lancer **Indexer DB** pour indexer `clean.txt` dans la base.

4. **Segmenter**  
   Lancer l’étape **Segment** pour S01E01 (découpage en phrases / tours de parole).

5. **Importer les sous-titres**  
   Onglet *Sous-titres* : épisode S01E01, *Importer un fichier* — importer **s01e01_en.srt** (langue EN), puis **s01e01_fr.srt** (langue FR).

6. **Aligner**  
   Onglet *Alignement* : épisode S01E01, lancer **Align** (pivot EN, langue cible FR).

7. **Explorer**  
   - **Inspecteur** : choisir S01E01 pour voir segments, cues et liens d’alignement.
   - **Concordancier** : rechercher un mot (ex. *Legendary*) et consulter le rapport parallèle EN / FR.

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
