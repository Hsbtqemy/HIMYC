# Revue de code — HowIMetYourCorpus

Revue globale du code (architecture, qualité, robustesse, tests). Date : 2025-02.

---

## 1. Vue d’ensemble

- **Stack** : Python 3.11+, PySide6, SQLite/FTS5, httpx, BeautifulSoup, pipeline modulaire (steps, runner, workers).
- **Structure** : `src/howimetyourcorpus/` — `app/` (main, UI, workers, models_qt), `core/` (models, pipeline, storage, align, normalize, segment, subtitles, adapters, utils).
- **Tests** : 50 tests pytest, tous verts (dont adapters, align, db/KWIC, export Phase 5, normalize, segment, subtitles).

**Points forts :**
- Séparation nette app / core, pipeline par étapes (Step/StepResult), workers en thread dédié avec signaux Qt.
- Modèles de données typés (dataclasses, EpisodeRef, ProjectConfig, etc.).
- Gestion des connexions SQLite (try/finally conn.close()) systématique dans `db.py`.
- Rétrocompatibilité TOML (tomllib 3.11+ / tomli) et écriture TOML manuelle sans dépendance lourde.

---

## 2. Architecture et design

| Zone | Constat | Recommandation |
|------|--------|----------------|
| **Pipeline** | Runner exécute les steps en ordre, callbacks progress/log/error, annulation via `_cancelled`. | OK. Éventuellement : résultat partiel (liste de StepResult) toujours retourné même en cas d’erreur, déjà le cas. |
| **Workers** | `JobRunner` + `_PipelineWorker`, `moveToThread`, signaux error/finished. | OK. Vérifier que `_on_job_finished` ne fait pas d’accès store/db depuis le worker (il est appelé dans le thread UI après finished.emit). |
| **UI** | `MainWindow` central, onglets Projet / Corpus (arbre Saison→Épisodes) / Inspecteur / Sous-titres / Alignement / Concordance / Logs / Personnages. | Corpus utilise déjà `EpisodesTreeModel` + colonnes SRT / Aligné (backlog §9 et §10.1 en partie couverts). |
| **Store vs DB** | `ProjectStore` = fichiers (config, series_index, episodes/*, subs). `CorpusDB` = SQLite (episodes, documents, FTS, segments, cues, align). | OK. Pas de duplication critique ; sync par rechargement après chaque job. |

---

## 3. Robustesse et erreurs

| Fichier / zone | Constat | Recommandation |
|----------------|--------|----------------|
| **project_store.load_series_index** | Utilise `e["episode_id"]`, `e["season"]`, etc. Si une clé manque dans le JSON → `KeyError`. | Utiliser `e.get("episode_id", "")`, `e.get("season", 0)`, etc., ou valider le schéma et logger un avertissement. |
| **project_store._episode_dir(episode_id)** | `root_dir / "episodes" / episode_id`. Si `episode_id` contient `".."` ou `/`, risque de path traversal. | Valider `episode_id` (ex. motif `S01E01` ou alphanumerics) avant de construire le chemin ; rejeter ou normaliser. |
| **project_store._write_toml** | Gère str, int, float, bool. Pas de listes ni dict imbriqués. | OK pour la config actuelle (plate). Si ajout de structures complexes, utiliser `tomli-w` ou équivalent pour l’écriture. |
| **UI _on_job_error** | Message d’erreur tronqué à 500 caractères + try/except sur `str(exc)`. | OK (évite plantage sur messages très longs). |
| **Exceptions dans slots UI** | Plusieurs `except Exception` avec `logger.exception` + message utilisateur. | OK. S’assurer de ne pas avaler d’exceptions sans log (déjà le cas). |

---

## 4. Sécurité

- **Entrées utilisateur** : Chemins projet et fichiers choisis via `QFileDialog` ; pas d’exécution de commandes basée sur des entrées brutes.
- **Path traversal** : Seul point à durcir : `episode_id` dans `_episode_dir` (voir ci-dessus).
- **SQL** : Requêtes paramétrées (`?`) partout dans `db.py` ; pas d’injection SQL.
- **Réseau** : `httpx` avec timeout et User-Agent configurable ; pas de stockage de secrets en clair dans le code.

---

## 5. Performance

- **DB** : Une connexion par opération (`_conn()` + close). Pour des batch lourds (ex. indexation de nombreux épisodes), envisager une connexion unique par batch ou pool si besoin.
- **FTS** : Requêtes FTS5 avec `MATCH` ; index présents sur documents, segments, cues.
- **UI** : Jobs longs dans un thread séparé ; pas de blocage du main thread. Rafraîchissements (episodes, subs, align) après chaque job — acceptable.

---

## 6. Tests

- **Couverture** : 50 tests, modules core bien couverts (align, db, export, normalize, segment, subtitles, adapters).
- **Warnings** : 3 DeprecationWarning (BeautifulSoup/lxml `strip_cdata`) — bénins, à traiter en amont (bs4/lxml).
- **Manques possibles** : Pas de tests d’intégration UI (main window) ; pas de tests de charge. Tests unitaires pipeline (runner + steps) partiels via les steps concrets.

**Recommandation** : Garder les tests à jour à chaque changement de contrat (store, db, steps) ; ajouter si possible 1–2 tests d’intégration sur un mini-projet (ex. example/) sans GUI.

---

## 7. Maintenabilité et doc

- **Docstrings** : Présentes sur les classes et méthodes publiques (store, db, pipeline, align, parsers). Par endroits, préciser les préconditions (ex. `episode_id` format attendu).
- **Typage** : Types Python utilisés (dataclasses, list, dict, Optional, etc.) ; cohérent dans core. UI : quelques `Any` ou types implicites.
- **Constantes** : Index d’onglets (TAB_*) centralisés ; noms de colonnes dans les modèles (COLUMNS, HEADERS). OK.

---

## 8. Cohérence avec le backlog

- **§9 (Arborescence saison → épisodes)** : Déjà en place — `EpisodesTreeModel` + `QTreeView` + filtre par saison + « Cocher la saison ».
- **§10.1 (Corpus = gestionnaire des docs)** : Déjà en place — colonnes SRT et Aligné dans `EpisodesTreeModel`, alimentées par `get_tracks_for_episode` et `get_align_runs_for_episode`.
- **§6.1 (Workflow SRT, import en masse)** : Partiellement en place (projet SRT only, ajout épisodes à la main, fusion découverte) ; import en masse non implémenté.
- **§7 (Profil modifiable)** : Profils personnalisés (profiles.json) + dialogue « Gérer les profils » présents ; choix du profil en batch (combo) présent.

---

## 9. Actions recommandées (priorité)

1. **Robustesse** *(appliqué)*  
   - `load_series_index` : utilisation de `.get()` pour les champs épisode (évite KeyError sur JSON dégradé) ; boucle avec `isinstance(e, dict)` pour ignorer entrées invalides.  
   - `_episode_dir` : sanitization de `episode_id` (remplacement de `\`, `/`, `..` par `_`, strip `._ `) pour éviter le path traversal.

2. **Tests**  
   - Corriger ou ignorer les 3 warnings pytest (bs4/lxml) si possible.  
   - Ajouter 1 test d’intégration (pipeline complet sur example/) optionnel.

3. **Doc**  
   - Mettre à jour le backlog pour marquer §9 et §10.1 comme réalisés (ou « partiellement réalisés ») si ce n’est pas déjà fait.

4. **Aucun changement bloquant**  
   - Aucun bug critique identifié ; le code est prêt pour une utilisation normale et des évolutions ciblées.
