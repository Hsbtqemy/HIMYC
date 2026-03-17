# Audit Fonctionnel - Onglet Sous-titres

## Perimetre

- Date: 2026-03-16
- Cible: `src/howimetyourcorpus/app/tabs/tab_sous_titres.py` + integration MainWindow/Inspecteur combine.
- Objectif: verifier les controles interactifs, leur branchement reel, et classifier les ecarts.

## Methode

- Inventaire statique AST des widgets, signaux, slots et gardes.
- Probe runtime headless (etat des boutons avant/apres chargement/selection).
- Verification d'integration du tab dans l'onglet combine Inspecteur+Sous-titres.
- Verification des tests existants et des preuves de couverture disponibles.

## Verdict Executif

- Controles interactifs recenses: **14**
- Branches directs (signal -> slot): **9**
- Branches indirects (pas de signal, mais utilises par logique metier): **5**
- Controles interactifs non branches detectes: **0**

Conclusion:
- Sur ce perimetre, **aucun controle present mais non branche** n'a ete detecte dans `SubtitleTabWidget`.
- Le composant Sous-titres n'est pas un onglet autonome top-level: il est **branche via l'onglet combine** Inspecteur (design intentionnel).

## Inventaire Et Branchement

- Voir:
  - `evidence/tab_sous_titres_ast_inventory.json`
  - `evidence/tab_sous_titres_branching_matrix.json`
  - `evidence/tab_sous_titres_branching_matrix.csv`
  - `evidence/tab_sous_titres_control_usage_matrix.json`

Resume fonctionnel des actions principales:

- `Importer SRT/VTT...` -> `_import_file` -> `ImportSubtitlesStep` (pipeline async).
- `Importer SRT en masse...` -> `_import_batch` -> `SubtitleBatchImportDialog` -> `ImportSubtitlesStep[]`.
- `Telecharger depuis OpenSubtitles...` -> `_import_opensubtitles` -> `DownloadOpenSubtitlesStep[]`.
- `Supprimer la piste selectionnee` -> `_delete_selected_track` -> `DeleteSubtitleTrackCommand` (Undo/Redo) ou suppression directe DB+fichier.
- `Normaliser la piste` -> `_normalize_track` -> `store.normalize_subtitle_track(...)`.
- `Exporter SRT final...` -> `_export_srt_final` -> `db.get_cues_for_episode_lang` + `cues_to_srt`.
- `Sauvegarder et re-importer` -> `_save_content` -> `save_episode_subtitle_content` + `ImportSubtitlesStep`.

## Present Vs Reellement Branche

### Elements correctement branches

- 9 controles avec connexion explicite signal->slot.
- 5 controles utilises sans connexion directe (combos/checkbox utilises comme sources de parametres dans les slots).
- Tous les slots d'action ont une implementation non vide et des appels metier observables (store/db/pipeline/fichier).

### Element present mais non top-level (a clarifier)

- `SubtitleTabWidget` existe, mais n'est pas ajoute comme onglet dedie dans MainWindow.
- Il est instancie dans `InspecteurEtSousTitresTabWidget` puis expose sous l'onglet "Inspecteur".
- Ce point est un **choix d'architecture**, pas un defaut de branchement.

Preuve:
- `evidence/tab_sous_titres_embedding_refs.txt`

## Probes Runtime

- Probe widget Sous-titres:
  - boutons critiques desactives par defaut
  - activation apres selection d'une piste
  - chargement contenu + metadata piste (`editing_lang`, `editing_fmt`)
- Probe onglet combine:
  - selecteur episode interne Sous-titres masque (pilotage par selecteur commun)
  - changement episode commun propage sur Sous-titres

Preuves:
- `evidence/tab_sous_titres_runtime_probe.json`
- `evidence/combined_inspector_subtitles_probe.json`

## Tests Et Couverture

- Tests executes pour preuves:
  - `tests/test_subtitle_batch_parse.py`
  - `tests/test_ui_guards.py::test_subtitles_opensubtitles_warns_without_project`
  - `tests/test_undo_commands.py::test_delete_subtitle_track_command_redo_undo_restores_db_files_and_alignment`
  - `tests/test_ui_mainwindow_core.py::test_refresh_tabs_after_job_skips_duplicate_subs_refresh_when_inspector_is_combined`
  - `tests/test_ui_mainwindow_core.py::test_refresh_tabs_after_project_open_skips_duplicate_subs_refresh_when_inspector_is_combined`

Preuves:
- `evidence/pytest_subtitles_focus.log`
- `evidence/pytest_subtitles_refresh_integration.log`
- `evidence/tests_references_subtitles.txt`

Couverture (derivee du quality gate du 2026-03-16):
- Fichier `tab_sous_titres.py`: **48%**
- Preuve:
  - `evidence/tab_sous_titres_coverage_from_quality_gate.json`

## Risques Fonctionnels Restants

- Aucun risque P0 detecte sur le branchement des controles.
- Risque principal: couverture de non-regression du tab Sous-titres encore partielle (48%), notamment sur les flux UI de bout en bout des actions d'import/export/edition.
