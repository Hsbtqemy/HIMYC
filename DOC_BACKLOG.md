# Backlog — demandes à lancer plus tard

Ce fichier recense les idées / demandes discutées (brainstorming) pour les implémenter ultérieurement.

---

## 1. Onglet Corpus — cases à cocher pour la sélection

**Demande :** Pouvoir sélectionner les épisodes via des **cases à cocher** (au lieu ou en complément de la sélection par clic / Shift+Ctrl).

**Pistes :**
- Ajouter une colonne checkbox dans la table (ou une case « tout sélectionner » + cases par ligne).
- Décider : remplacer la sélection actuelle ou la compléter (ex. case « tout » + cases par épisode).
- Exposer les **actions de masse** sur la sélection (lancer pipeline, export, etc.) de façon cohérente.

**Fichiers concernés (à vérifier) :**  
`src/howimetyourcorpus/app/ui_mainwindow.py` (onglet Corpus), `models_qt.py` (EpisodesTableModel).

---

## 2. Onglet Inspecteur — redimensionnement et export

### 2.1 Redimensionner les box

**Demande :** Pouvoir **redimensionner** les zones (transcription, sous-titres, alignement, etc.) comme on souhaite.

**Piste :** Utiliser des **QSplitter** entre les zones avec poignées déplaçables ; optionnel : sauvegarder les proportions (settings).

**Fichiers concernés (à vérifier) :**  
`src/howimetyourcorpus/app/ui_mainwindow.py` — construction de l’onglet Inspecteur.

### 2.2 Exporter les textes segmentés depuis l’Inspecteur

**Demande :** Pouvoir **exporter les textes segmentés** depuis l’onglet Inspecteur (sans passer par l’onglet Corpus / Export).

**Pistes :**
- Format d’export : TXT (un segment par ligne), CSV/TSV (segment + timecodes + langue), SRT-like, etc.
- Périmètre : tout l’épisode affiché ou une sélection future dans l’Inspecteur.
- Un bouton « Exporter les segments » avec choix de format (boîte de dialogue ou menu).

**Fichiers concernés (à vérifier) :**  
`src/howimetyourcorpus/app/ui_mainwindow.py` (Inspecteur), éventuellement `core/export_utils.py` pour réutiliser des helpers.

---

## 3. Alignement sans timecodes

**Contexte :** Aujourd’hui, l’alignement **segment (transcript) ↔ cue EN** se fait par **similarité textuelle** (pas de timecodes). L’alignement **cue EN ↔ cue cible (IT, FR, etc.)** se fait par **recouvrement temporel** (`start_ms` / `end_ms` du SRT). Si on n’a **pas de timecodes** (fichiers “une phrase par ligne” ou SRT sans timings), la partie EN↔cible ne fonctionne plus.

**Pistes à mettre en œuvre :**

1. **Alignement par ordre**  
   Supposer que les deux fichiers sont parallèles (cue 1 EN ↔ cue 1 IT, cue 2 EN ↔ cue 2 IT, …) et créer des paires par indice. Option : activer ce mode si les cues n’ont pas de `start_ms` / `end_ms` (ou si tous à 0).

2. **Alignement EN↔cible par similarité textuelle**  
   Réutiliser la même logique que segment↔EN : comparer le texte de chaque cue EN au texte des cues cible (similarité lexicale / rapidfuzz). Utile quand les timecodes sont absents ou peu fiables.

3. **Format “sans timecodes”**  
   Accepter un format d’import type “une phrase par ligne” (sans timecodes) ; ne faire que segment↔cue EN (et éventuellement EN↔cible par ordre ou par similarité selon la piste choisie).

**Fichiers concernés (à vérifier) :**  
`src/howimetyourcorpus/core/align/aligner.py` (`align_cues_by_time` → fallback), `core/storage/db.py` / parsers SRT (gestion de cues sans `start_ms`/`end_ms`).

---

## Réalisé

- **Exemple utilisable (EN + IT, court)** — projet démo dans `example/` avec transcript, SRT EN/IT, README et corpus.db pré-initialisé. Voir `example/README.md` et section « Projet exemple » du `README.md` principal.
