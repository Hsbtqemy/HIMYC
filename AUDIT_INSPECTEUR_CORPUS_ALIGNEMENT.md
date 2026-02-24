# Audit des onglets Inspecteur, Corpus et Alignement

**Date** : 2026-02-23  
**Périmètre** : `tab_inspecteur.py`, `tab_inspecteur_sous_titres.py`, `tab_corpus.py`, `tab_alignement.py`  
**Référentiel** : `.cursor/rules/analyse-himyc.mdc` (analyse approfondie HIMYC)

---

## 1. Onglet Inspecteur

**Fichiers** : `tab_inspecteur.py`, `tab_inspecteur_sous_titres.py`  
**Classe principale** : `InspectorTabWidget`, `InspecteurEtSousTitresTabWidget`

### 1.1 Points positifs

- **Responsabilités** : L’Inspecteur gère clairement épisode, RAW/CLEAN, segments, profils, notes. Le widget fusionné délègue bien à `InspectorTabWidget` et `SubtitleTabWidget`.
- **Décorateurs** : `@require_project` / `@require_project_and_db` centralisent la vérification projet/DB.
- **Tooltips** : Présents sur les combos (Vue, Kind, Profil, Aller à) et les boutons.
- **Sauvegarde d’état** : Splitters et notes sauvegardés dans `QSettings` et à la fermeture.
- **Navigation** : « Aller à #N » pour le segment, vue Segments avec filtre Kind.

### 1.2 Problèmes et recommandations

| # | Problème | Localisation | Recommandation |
|---|----------|--------------|----------------|
| 1 | **Pas de `@require_project` sur `_run_normalize` / `_set_episode_preferred_profile`** | `tab_inspecteur.py` L366, L377 | Vérification manuelle `if not eid or not store`. Cohérent avec le décorateur sur `_run_segment` / `_export_segments`. Soit uniformiser avec `@require_project` pour éviter les messages génériques, soit garder le message « Sélectionnez un épisode et ouvrez un projet » (actuel). |
| 2 | **Export segments : erreur générique** | L329-331 | `except Exception as e: QMessageBox.critical(..., str(e))`. Enrichir : `f"Erreur lors de l'export : {e}\n\nVérifiez les droits d'écriture et que le fichier n'est pas ouvert ailleurs."` |
| 3 | **`_fill_segments` appelé même en vue « Épisode »** | L281-283 | Quand `currentData() != "segments"` on clear et return. Pas de problème fonctionnel, mais on pourrait éviter l’appel depuis `_load_episode` si la vue n’est pas segments (micro-optimisation). |
| 4 | **`hasattr(self, 'inspect_kind_combo')` inutile** | L334 | Toujours vrai dans cette classe. Remplacer par `self.inspect_kind_combo.currentData()`. |
| 5 | **Pas de chargement asynchrone** | `_load_episode` | Pour des épisodes très longs (500+ segments), le chargement reste synchrone. Si l’UI bloque, prévoir un worker + barre de progression (comme indiqué dans la règle § Inspecteur). |
| 6 | **Widget fusionné : pas de sauvegarde du splitter** | `tab_inspecteur_sous_titres.py` | `save_state` enregistre bien le splitter fusionné + délégation à l’Inspecteur. Rien à changer. |

### 1.3 UX / Accessibilité

- **Raccourci clavier** : « Aller à » réagit à Entrée ; pas de raccourci global (ex. Ctrl+G) pour « Aller au segment ».
- **Indicateur de modification** : Les notes sont sauvegardées à la fermeture et au changement d’épisode ; pas d’indicateur visuel « non sauvegardé ».
- **Sync transcript ↔ sous-titres** : Dans le widget fusionné, pas de scroll synchronisé entre transcript et SRT (mentionné dans la règle comme « à vérifier »).

---

## 2. Onglet Corpus

**Fichier** : `tab_corpus.py`  
**Classe** : `CorpusTabWidget`

### 2.1 Points positifs

- **Structure** : Bloc 1 (SOURCES : Transcripts + SRT), Bloc 2 (Normalisation / segmentation), barre de progression et statuts clairs.
- **Feedback** : Labels « Status : X/Y téléchargés », « X/Y importés » avec style (orange si manquants, vert si OK). Workflow global affiché.
- **Boutons activés/désactivés** : Selon `n_fetched`, `n_norm`, `n_total` (L356-360).
- **Reprise échecs** : `store_failed_episodes` + bouton « Reprendre les échecs » avec explication.
- **Double-clic** : Ouvre l’Inspecteur sur l’épisode (si `_on_open_inspector` fourni).

### 2.2 Doublons et redondances (priorité haute)

| # | Problème | Localisation | Recommandation |
|---|----------|--------------|----------------|
| 1 | **Récupération « ids sélection ou cochés » répétée 7 fois** | L419-425, 439-445, 537-543, 676-684, 841-849, 875-883, 916-924, 956-964, 1012-1020 | **Factoriser** en une méthode du widget, ex. `def _get_selected_or_checked_episode_ids(self) -> list[str]`, qui fait : `ids = get_checked_episode_ids()` puis si vide `ids = get_episode_ids_selection(proxy→source)`. Appeler cette méthode partout à la place du bloc répété. |
| 2 | **Validation « Ouvrez un projet / Découvrez les épisodes »** | `_fetch_episodes`, `_normalize_episodes`, `_segment_episodes`, `_run_all_for_selection`, `_discover_episodes`, `_discover_merge` | Plusieurs méthodes refont `context.get("config")`, `store`, `index.episodes`. On peut extraire une méthode `_get_checked_context_and_index()` ou au moins `_ensure_project_and_episodes()` qui retourne `(store, index)` ou None et affiche le message d’erreur une fois. |
| 3 | **Refresh sans projet : deux blocs quasi identiques** | L319-328 et L330-341 | Même séquence clear combo, setText status, setEnabled False. Factoriser en une méthode `_set_no_project_state()` appelée dans les deux branches. |

### 2.3 Autres points

| # | Problème | Localisation | Recommandation |
|---|----------|--------------|----------------|
| 4 | **`refresh_profile_combo` après dialogue Profils** | L406-410 | Utilise `self.norm_batch_profile_combo.model().stringList()` qui peut ne pas exister (modèle par défaut). Mieux : passer les `profile_ids` depuis le dialogue ou depuis `get_all_profile_ids()` après fermeture. |
| 5 | **Import batch SRT : TODO** | L498-506 | Message indique « import automatique complet sera ajouté prochainement ». Les épisodes sont créés, mais l’import SRT en base n’est pas fait. Documenter clairement ou implémenter l’appel au pipeline d’import. |
| 6 | **`_on_season_filter_changed` et QTreeView** | L410-418 | Code `isinstance(self.episodes_tree, QTreeView)` et expand. Avec `_use_table = True` la vue est toujours QTableView, ce bloc est mort. Supprimer ou garder pour évolution future en commentant « Si on repasse en TreeView ». |
| 7 | **Erreur refresh** | L364-366 | `QMessageBox.critical` avec type(e) et message : bien. Suggérer d’ajouter un lien « Ouvrir l’onglet Logs » si possible. |

### 2.4 Performance

- **Refresh** : `refresh()` fait un passage synchrone sur tous les épisodes (`n_fetched`, `n_norm`, `tracks_by_ep`, `runs_by_ep`). Pour 100+ épisodes c’est acceptable ; au-delà, envisager un calcul différé ou en arrière-plan.
- **Modèle** : Utilisation de `EpisodesTableModel` (TableView) partout ; pas de N+1 évident car les statuts sont chargés en batch dans `_refresh_status`.

---

## 3. Onglet Alignement

**Fichier** : `tab_alignement.py`  
**Classes** : `AlignmentTabWidget`, `EditAlignLinkDialog`

### 3.1 Points positifs

- **Undo/Redo** : Commandes `SetAlignStatusCommand`, `BulkAcceptLinksCommand`, `BulkRejectLinksCommand`, `DeleteAlignRunCommand`, `EditAlignLinkCommand` bien branchées.
- **Panneau Stats** : `AlignStatsWidget` mis à jour à chaque changement de run/liens (Phase 7 HP4).
- **Actions bulk** : Accepter/Rejeter par seuil de confiance avec confirmation.
- **Tooltips** : Sur les boutons, le seuil, la case « Liens acceptés uniquement », et le texte d’aide.
- **Export** : Plusieurs formats (CSV, TSV, JSONL, HTML, DOCX, TXT) pour alignement et concordancier.

### 3.2 Problèmes et recommandations

| # | Problème | Localisation | Recommandation |
|---|----------|--------------|----------------|
| 1 | **Clé `target_id` vs `cue_id_target` (bug)** | L391 (tab_alignement), undo_commands.py L63-73 | Le schéma DB et le reste du code utilisent `cue_id_target`. Dans `tab_alignement.py` utiliser `link.get("cue_id_target")` pour `old_target_id`. Dans `EditAlignLinkCommand` (undo_commands.py) le SQL utilise `target_id` alors que la colonne s’appelle `cue_id_target` : corriger les deux `UPDATE align_links SET target_id` en `cue_id_target`. |
| 2 | **Export alignement : erreur générique** | L424-426 | Comme Inspecteur : `except Exception: QMessageBox.critical(..., str(e))`. Enrichir le message (fichier, droits, encodage). |
| 3 | **Pas de sauvegarde du splitter** | `main_splitter` (table | stats) | Les proportions table/stats ne sont pas sauvegardées dans `QSettings`. Ajouter dans un `save_state()` si la fenêtre principale appelle `save_state` sur les onglets, et `_restore_splitter` au `refresh` ou dans `__init__`. |
| 4 | **Confirmation suppression run** | L311-319 | Le texte dit « irréversible (même avec Undo/Redo) » puis « Undo/Redo peut restaurer ». Contradiction. Corriger le libellé selon le comportement réel (si Undo restaure, ne pas dire « irréversible »). |

### 3.3 UX / Paramétrage

- **Lancer alignement** : Langues pivot/cible en dur (`pivot_lang="en"`, `target_langs=["fr"]`). Si le projet est multilingue, envisager des combos ou la config projet.
- **Recherche dans la table** : Pas de filtre texte sur les liens (recherche par segment/cue). Pour de gros runs, un champ « Filtrer » pourrait aider.

---

## 4. Synthèse transversale

### 4.1 Doublons entre onglets

- **Message « Ouvrez un projet d'abord »** : Déjà centralisé via `@require_project` / `@require_project_and_db` (titres adaptés selon le nom de la méthode). Corpus utilise parfois un contexte `context.get("config")` en plus ; alignement et inspecteur s’appuient surtout sur store/db.
- **Combo épisodes** : Remplissage identique (index.episodes → addItem avec episode_id, title) dans Inspecteur, Corpus (via modèle), Alignement, Inspecteur+Sous-titres. Une fonction utilitaire `fill_episode_combo(combo, index)` réduirait la duplication.

### 4.2 Checklist règle analyse-himyc

| Critère | Inspecteur | Corpus | Alignement |
|---------|------------|--------|------------|
| Responsabilité unique | Oui | Oui (mais fichier très long) | Oui |
| Tooltips | Oui | Oui | Oui |
| Feedback progression | Non (pas de job long dans l’onglet) | Oui (progress bar) | Non (job lancé ailleurs) |
| Erreurs contextualisées | Partiel (export) | Bon (refresh) | Partiel (export) |
| Gestion annulation | N/A | Oui (Annuler job) | N/A |
| Sauvegarde état UI | Oui (splitters, notes) | N/A | Partiel (splitter non sauvegardé) |

### 4.3 Actions recommandées par priorité

**P0 (rapide, fort impact)**  
1. **Corpus** : Introduire `_get_selected_or_checked_episode_ids()` et remplacer les 7 blocs dupliqués.  
2. **Alignement** : Utiliser `link.get("cue_id_target")` dans tab_alignement.py (ligne ~391) ; corriger `EditAlignLinkCommand` dans undo_commands.py : remplacer `target_id` par `cue_id_target` dans les requêtes SQL. Corriger le texte de confirmation suppression run (irréversible vs Undo).

**P1 (maintenabilité)**  
3. **Corpus** : Factoriser `_set_no_project_state()` et, si possible, une méthode de type `_ensure_project_and_episodes()` pour réduire la duplication de validation.  
4. **Inspecteur** : Supprimer le `hasattr(self, 'inspect_kind_combo')` inutile.  
5. **Alignement** : Sauvegarder/restaurer les proportions du splitter table/stats.

**P2 (UX / robustesse)**  
6. Enrichir les messages d’erreur d’export (Inspecteur, Alignement).  
7. **Corpus** : Corriger ou documenter `refresh_profile_combo` après dialogue Profils ; clarifier le TODO import batch SRT.

---

*Audit réalisé selon la méthodologie définie dans `.cursor/rules/analyse-himyc.mdc`.*
