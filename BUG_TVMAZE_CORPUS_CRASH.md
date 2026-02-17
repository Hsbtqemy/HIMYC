# BUG CONNU : Crash avec adapter TVMaze

## Symptômes
- La découverte d'épisodes via TVMaze fonctionne ✅
- Les 62 épisodes sont correctement récupérés et sauvegardés ✅
- **MAIS** : Cliquer sur l'onglet Corpus après découverte fait crasher l'application ❌
- Aucun message d'erreur Python (crash au niveau Qt C++)

## Cause probable
Le modèle Qt `EpisodesTreeModel` crash lors du rendu de 62 épisodes TVMaze.
Hypothèses :
1. Crash dans `_refresh_season_filter_combo()` avec le proxy
2. Crash dans `QTreeView.expand()` avec trop d'épisodes
3. Problème d'accès DB pour des épisodes sans fichiers raw/clean

## Fichiers affectés
- `src/howimetyourcorpus/app/tabs/tab_corpus.py` : refresh()
- `src/howimetyourcorpus/app/models_qt.py` : EpisodesTreeModel

## Protections ajoutées (mais insuffisantes)
✅ Try/catch dans `corpus_tab.refresh()`
✅ Try/catch dans `EpisodesTreeModel._refresh_status()`
✅ Try/catch dans `ui_mainwindow._on_job_finished()`
❌ Le crash est au niveau C++ Qt, pas Python

## Workaround temporaire
**Ne pas cliquer sur l'onglet Corpus après découverte TVMaze !**

À la place :
1. Découvrir les épisodes via TVMaze (fonctionne)
2. Rester sur l'onglet Projet ou Logs
3. Télécharger les transcripts depuis subslikescript (via les boutons Projet)
4. OU importer des SRT via l'onglet Inspecteur
5. Une fois qu'il y a du contenu, l'onglet Corpus devrait fonctionner

## Solution à implémenter
1. **Option A** : Désactiver l'expand automatique pour TVMaze
2. **Option B** : Utiliser QTableView au lieu de QTreeView pour TVMaze
3. **Option C** : Lazy loading des épisodes (pagination)
4. **Option D** : Débugger avec gdb/Qt Creator pour trouver le crash C++

## Tests effectués
- ✅ Import de toutes les classes fonctionne
- ✅ Modèle Qt simple avec 62 épisodes fonctionne
- ✅ Données JSON TVMaze sont valides
- ❌ Modèle complexe EpisodesTreeModel crashe avec épisodes TVMaze

## Date
2026-02-17
