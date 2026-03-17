# Audit Fonctionnel - Onglet Inspecteur

## Perimetre

- Date: 2026-03-16
- Cible:
  - `src/howimetyourcorpus/app/tabs/tab_inspecteur.py`
  - `src/howimetyourcorpus/app/tabs/tab_inspecteur_sous_titres.py`
  - Integration MainWindow (`mainwindow_tabs.py`, `ui_mainwindow.py`)
- Objectif: verifier les controles interactifs, les branchements reels, les gardes, et la logique de segmentation.

## Methode

- Inventaire statique AST des widgets/signaux/slots.
- Matrice de branchement `BRANCHE_DIRECT / BRANCHE_INDIRECT / NON_BRANCHE`.
- Probe runtime headless (clics boutons, guardrails, export).
- Probe integration du widget combine (episode partage Inspecteur+Sous-titres).
- Tests cibles executes et journalises.
- Evidence de couverture derivee du quality gate existant.

## Verdict Executif

- Controles interactifs recenses: **17**
- Branches directs (signal -> slot): **12**
- Branches indirects (utilises sans signal direct): **5**
- Controles interactifs non branches detectes: **0**

Conclusion:
- Sur ce perimetre, **aucun controle present mais non branche** n'a ete detecte.
- Les 6 boutons d'action principaux de l'Inspecteur sont valides par probe runtime (`6/6`).

## Inventaire Et Branchement

Preuves:
- `evidence/tab_inspecteur_ast_inventory.json`
- `evidence/tab_inspecteur_control_usage_matrix.json`
- `evidence/tab_inspecteur_branching_matrix.json`
- `evidence/tab_inspecteur_branching_matrix.csv`
- `evidence/tab_inspecteur_slot_callmap.json`

Synthese des actions principales (boutons):

- `->` (goto) -> `_goto_segment`
- `Segmente l'episode` -> `_run_segment` -> `SegmentEpisodeStep`
- `Exporter les segments` -> `_export_segments` -> export TXT/CSV/TSV/SRT-like/DOCX
- `Normaliser cet episode` -> `_run_normalize` -> `NormalizeEpisodeStep`
- `Definir comme prefere...` -> `_set_episode_preferred_profile`
- `Gerer les profils...` -> `_open_profiles_dialog`

Preuve runtime boutons:
- `evidence/tab_inspecteur_buttons_probe_matrix.json`

## Present Vs Reellement Branche

### Elements correctement branches

- 12 controles avec connexion signal->slot explicite.
- 5 controles sans signal direct mais utilises par la logique metier (editeurs/combos en source ou cible d'etat).
- 0 controle `NON_BRANCHE`.

### Points d'architecture (pas des defauts)

- L'Inspecteur top-level est le widget combine `InspecteurEtSousTitresTabWidget`.
- Le selecteur episode interne de chaque sous-widget est masque et pilote par un selecteur commun.

Preuves:
- `evidence/tab_inspecteur_embedding_refs.txt`
- `evidence/tab_inspecteur_combined_widget_refs.txt`
- `evidence/combined_inspector_probe.json`

## Logique De Segmentation (preuve)

Observation code + runtime:

1. Le clic `Segmente l'episode` appelle `_run_segment` dans `tab_inspecteur.py`.
2. `_run_segment` declenche `SegmentEpisodeStep(eid, lang_hint="en")`.
3. Dans `SegmentEpisodeStep.run`, la segmentation calcule **deux jeux**:
- `segmenter_sentences(clean, lang_hint)`
- `segmenter_utterances(clean)`
4. Les deux types sont ecrits et upsertes en DB (`sentence` et `utterance`).

Implication fonctionnelle:
- Le combo `Kind` de l'Inspecteur filtre l'affichage des segments; il ne choisit pas un mode exclusif de segmentation a l'execution.

Preuves:
- `evidence/segmentation_logic_excerpts.txt`
- `evidence/segment_episode_step_callmap.json`
- `evidence/tab_inspecteur_runtime_probe.json`

## Probes Runtime

Resultats principaux:

- Conservation episode apres `refresh`: `true`.
- Passage en vue `segments` applique bien la bascule (`isHidden == false` pour liste + filtre kind).
- Filtre kind:
  - all: 2
  - utterance: 1
  - sentence: 1
- Navigation goto `#2`: selection effective du segment `n=2`.
- Boutons verifies:
  - normalize -> job `NormalizeEpisodeStep`
  - segment -> job `SegmentEpisodeStep`
  - segment guard sans clean -> warning utilisateur
  - export -> fichier ecrit + message info
  - profil prefere -> persistence store
  - gerer profils -> dialogue execute

Preuves:
- `evidence/tab_inspecteur_runtime_probe.json`
- `evidence/tab_inspecteur_buttons_probe_matrix.json`

## Tests Et Couverture

Tests executes:

- `tests/test_ui_inspecteur_profiles.py`
- `tests/test_ui_guards.py::test_inspector_normalize_warns_without_project`
- `tests/test_ui_mainwindow_core.py::test_refresh_tabs_after_job_skips_duplicate_subs_refresh_when_inspector_is_combined`
- `tests/test_ui_mainwindow_core.py::test_refresh_tabs_after_project_open_skips_duplicate_subs_refresh_when_inspector_is_combined`

Preuves:
- `evidence/pytest_inspecteur_focus.log`
- `evidence/pytest_inspecteur_integration.log`
- `evidence/tests_references_inspecteur.txt`

Couverture (quality gate 2026-03-16):

- `tab_inspecteur.py`: **73.18%**
- `tab_inspecteur_sous_titres.py`: **89.80%**

Preuve:
- `evidence/tab_inspecteur_coverage_from_quality_gate.json`

## Risques Fonctionnels Restants

- Aucun risque P0 de branchement detecte sur l'onglet Inspecteur.
- Risques restants surtout en clarte UX et robustesse non-regression sur:
  - mapping des formats d'export
  - comprehension utilisateur du `Kind` (filtre vs mode de segmentation)
  - scenarios UI multi-etapes autour des profils.
