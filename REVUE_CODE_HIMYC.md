# Revue de code — HowIMetYourCorpus (HIMYC)

**Dernière mise à jour** : revue complète (état actuel)  
**Périmètre** : `src/howimetyourcorpus/`, `tests/`  
**Tests** : **203 passés**, 0 warning.

---

## 1. Structure du projet

### 1.1 Packages et points d’entrée

- **Point d’entrée CLI** : `howimetyourcorpus.app.main:main` (`pyproject.toml`). Fichier `app/main.py` : `setup_logging`, `QApplication`, `MainWindow`, boucle d’événements.
- **`app/`** : UI Qt (fenêtre, onglets, dialogs, workers, models_qt, undo_commands).
- **`core/`** : storage, pipeline, preparer, align, export, normalisation, adapters, segment, subtitles, opensubtitles, utils.

### 1.2 Câblage onglets et dialogs

- **MainWindow** (`ui_mainwindow.py`) : constantes `TAB_*`, construction via `_build_tab_*` ; injection par lambdas (`get_store`, `get_db`, `run_job`, `show_status`, `undo_stack`).
- **Dialogs** : `ProfilesDialog`, `OpenSubtitlesDownloadDialog`, `NormalizeOptionsDialog`, `SegmentationOptionsDialog`, `SubtitleBatchImportDialog` (export depuis `app/dialogs/__init__.py`).

---

## 2. Core

### 2.1 ProjectStore (`core/storage/project_store.py`)

- Layout projet (config, series_index, episodes RAW/CLEAN, SRT, profils, personnages, prep status, langues). Méthodes load/save nombreuses.
- Gestion d’erreurs : `load_custom_profiles` et validation personnages lèvent `ValueError` ; pas de `except: pass`.

### 2.2 CorpusDB (`core/storage/db.py`)

- Façade SQLite, délégation vers `db_align`, `db_segments`, `db_subtitles`, `db_kwic`. Context managers `connection()` / `transaction()`, PRAGMA WAL. Migrations via `migrations/*.sql`.
- API batch : `get_tracks_for_episodes()`, `get_align_runs_for_episodes()`, `get_episode_text_presence()` (évitent N+1).

### 2.3 Pipeline (tasks, runner, context)

- **Context** : TypedDict `config`, `store`, `db`, `custom_profiles`, `is_cancelled`.
- **Runner** : boucle sur les steps, callbacks progress/log/error/cancelled.
- **Tasks** : `BuildIndexStep`, `FetchEpisodeStep`, `NormalizeEpisodeStep`, etc. **Corrigé** : N+1 dans `BuildIndexStep` — un seul appel à `get_episode_ids_indexed()` avant la boucle (`indexed = set(db.get_episode_ids_indexed())` si `not force`).

### 2.4 Preparer, align, export

- **Preparer** : `service.py`, `segmentation.py`, `persistence.py`, `status.py`, `snapshots.py`, `timecodes.py`.
- **Align** : `aligner.py`, `similarity.py`.
- **Export** : `export_utils.py` (corpus, segments, KWIC).

---

## 3. App / UI

### 3.1 MainWindow (`ui_mainwindow.py`)

- Construction onglets, menu (Undo/Redo, Aide), gestion projet, JobRunner (run, progress, log, error, finished, cancel), handoffs (Préparer → Alignement, Concordance → Inspecteur), fermeture (save state, prompt Préparer dirty).
- `_sync_config_from_project_tab()`, `_build_job_summary_message()`, `_refresh_tabs_after_job()` déjà factorisés.

### 3.2 Onglets

- **Projet** : formulaire, validation, callbacks vers MainWindow.
- **Corpus** (~1080 lignes) : arbre épisodes, filtres saison, actions (découvrir, fetch, normaliser, indexer). Grosse classe.
- **Inspecteur** + **Sous-titres** : conteneur fusionné `InspecteurEtSousTitresTabWidget`.
- **Préparer** (~954 lignes) + `preparer_context.py`, `preparer_edit.py`, `preparer_save.py`, `preparer_state.py`, `preparer_views.py`.
- **Alignement** (~822 lignes) : runs, liens, tableau, undo.
- **Concordance** : KWIC, filtres, export, graphique fréquence (matplotlib).
- **Personnages** : grille, assignations, propagation.
- **Logs** : affichage log projet.

### 3.3 Workers, models_qt, undo_commands

- **JobRunner** : pipeline dans un `QThread`, signaux progress/log/error/finished/cancelled, option `QProgressDialog`.
- **models_qt** : `EpisodesTreeModel`, `EpisodesTableModel`, `KwicTableModel`, `AlignLinksTableModel` ; `_compute_episode_text_presence` en batch + fallback.
- **undo_commands** : commandes QUndoCommand pour alignement et sous-titres.

---

## 4. Correctifs déjà appliqués

| Sujet | Statut |
|-------|--------|
| Synchro config Projet dupliquée | `_sync_config_from_project_tab()` factorisé |
| `cues_audit` dupliqué pipeline | Helper `cues_to_audit_rows()` |
| Refresh statuts épisodes coûteux | `get_episode_text_presence()` batch |
| `_on_job_finished` trop long | `_build_job_summary_message()` + `_refresh_tabs_after_job()` |
| Undo Préparer trop global | Snapshots ciblés |
| Rollback sauvegarde cues SRT | `PreparerService.save_cue_edits()` rollback compensatoire |
| Préparer refacto | Contrôleurs `preparer_context`, `preparer_save`, `preparer_edit`, `preparer_state`, `preparer_views` |
| N+1 BuildIndexStep | Un seul appel `get_episode_ids_indexed()` avant la boucle |
| Logs ProjectStore | `logger.warning` sur JSON corrompu dans plusieurs `load_*` |
| Exceptions silencieuses Personnages | `logger.debug` sur parsing `summary_json` / `params_json` |
| Exceptions silencieuses UI/Core ciblées | `logger.debug` ajouté (Alignement, Corpus, Inspecteur/Sous-titres, `db_align`, `models_qt`, `http`) |
| Vérification « projet ouvert » | Uniformisée sur actions principales de `tab_corpus` via décorateurs |
| Métadonnées run alignement | Parsing/fallback factorisés dans `core/align/run_metadata.py` |
| Dépréciation Qt | `invalidateFilter()` remplacé par `invalidate()` |
| Couverture tests | Ajouts sur MainWindow, workers, metadata alignement, regroupement aligné |
| Refacto `ProjectStore` (propagation) | Logique déplacée vers `core/storage/character_propagation.py` (délégation depuis `project_store.py`) |
| Refacto `ProjectStore` (grouping aligné) | Logique déplacée vers `core/storage/align_grouping.py` (délégation depuis `project_store.py`) |
| Couverture UI/dialogs P2 | Tests ajoutés sur Inspecteur + dialog Profils (`tests/test_ui_inspecteur_profiles.py`) |
| Refacto `tab_alignement` | Exports + dialogue d’édition déplacés vers `app/tabs/alignement_exporters.py` et `app/dialogs/edit_align_link.py` |
| Refacto `models_qt` | Modèles séparés en modules dédiés (`models_qt_episodes.py`, `models_qt_kwic.py`, `models_qt_align.py`, `models_qt_common.py`) avec façade compatibilité `models_qt.py` |
| Refacto `tab_preparer` | Actions UI extraites vers `app/tabs/preparer_actions.py` + dialogue déplacé vers `app/dialogs/search_replace.py` |
| Refacto `tab_corpus` | Actions sources + import/export extraites vers `app/tabs/corpus_sources.py` et `app/tabs/corpus_export.py` |
| Refacto `tab_preparer` (persistence) | Orchestration save/snapshots extraite vers `app/tabs/preparer_persistence.py` |

---

## 5. Qualité — points à améliorer

### 5.1 Observabilité

- Aucun `except ...: pass` résiduel détecté dans le périmètre ciblé de la revue.
- Les chemins de fallback JSON/Qt réseau concernés tracent maintenant en `logger.debug`.

### 5.2 Duplication

- Le formatage de `segment_kind` des runs d’alignement est centralisé (`core/align/run_metadata.py`).
- Les checks « projet ouvert / DB » sont désormais majoritairement uniformisés via décorateurs UI (`require_project`, `require_project_and_db`, `require_db`).

### 5.3 Fichiers volumineux (> 500 lignes)

- **project_store.py** ~990 — allégé via `character_propagation.py` et `align_grouping.py`, reste à découper (ex. « characters », « prep_status », « config »).
- **tab_corpus.py** ~843 — allégé via `corpus_sources.py`/`corpus_export.py`, reste à découper (workflow batch / normalisation).
- **tab_preparer.py** ~595 — allégé via `preparer_actions.py` + `preparer_persistence.py`.
- **tab_alignement.py** ~697 — allégé via extraction des exports/dialogue, reste à découper (actions run/bulk/table).
- **models_qt.py** ~21 — façade de compatibilité ; logique déplacée dans des modules dédiés (~545 épisodes, ~115 align, ~62 kwic).
- **ui_mainwindow.py** ~702 — extraire construction onglets / gestion job.
- **tasks.py** ~695, **db.py** ~620, **profiles.py** (dialogs) ~737 — à surveiller.

### 5.4 Types et docstrings

- Core en général bien typé. Certaines méthodes d’onglets sans type de retour ; docstrings inégales dans l’UI. Viser au moins les signatures publiques.

---

## 6. Performance

- **N+1** : corrigé dans `BuildIndexStep`. Corpus refresh utilise déjà `get_tracks_for_episodes`, `get_align_runs_for_episodes`, `get_episode_text_presence` en batch.
- **I/O** : fetch / indexation par épisode séquentiels (volontaire avec rate limit). Pour très gros corpus, envisager batch ou parallélisme contrôlé.
- **UI** : JobRunner dans un thread ; refresh onglet Corpus synchrone — pour 100+ épisodes, envisager chargement asynchrone ou différé.

---

## 7. Tests

- **Structure** : `tests/` à plat, `conftest.py` (fixtures_dir). **203 tests passés**, 0 warning.
- **Couverture** : unit (segment, subtitles, align, normalize, preparer, db_*, export), intégration pipeline, UI (Corpus, Préparer, MainWindow, Concordance, Logs, Inspecteur, dialogs), workers, undo, project_store.
- **Manques** : couverture UI encore partielle sur certains scénarios dialogs complexes (édition avancée des règles regex du ProfileEditor, flows multi-onglets très longs).

---

## 8. Priorités recommandées

| Priorité | Action |
|----------|--------|
| **P1** | ✅ Uniformisation des checks « projet ouvert » et « DB ouverte » sur les actions UI principales (Corpus, Préparer, Alignement, Projet, Concordance, Personnages). |
| **P1** | ✅ Nettoyage des artefacts runtime sous `tests/` via script dédié (`scripts/clean_test_artifacts.sh`) et `.gitignore`. |
| **P2** | 🟡 Découper les plus gros fichiers (project_store/models_qt allégés ; tab_preparer fortement réduit ; poursuivre sur tab_corpus/tab_alignement). |
| **P2** | 🟡 Étendre les tests UI/dialogs (Inspecteur/Concordance/Logs couverts; poursuivre sur flows dialogs avancés). |
| **P3** | Chargement asynchrone du refresh Corpus pour très gros corpus. |

---

## 9. Conclusion

Architecture claire (app / core), correctifs majeurs déjà en place (sync config, batch statuts, N+1 BuildIndexStep, refacto Préparer, undo ciblé, observabilité, factorisation alignement, dépréciation Qt résolue). Le risque résiduel est surtout **structurel** (fichiers longs) et **couverture UI partielle** sur quelques zones.
