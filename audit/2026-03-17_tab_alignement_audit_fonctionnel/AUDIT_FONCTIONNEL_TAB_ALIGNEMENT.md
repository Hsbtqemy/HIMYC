# Audit Fonctionnel - Onglet Alignement

## Perimetre

- Date: 2026-03-17
- Cible:
  - `src/howimetyourcorpus/app/tabs/tab_alignement.py`
  - `src/howimetyourcorpus/app/tabs/alignement_actions.py`
  - `src/howimetyourcorpus/app/tabs/alignement_exporters.py`
  - integration MainWindow (`mainwindow_tabs.py`, `ui_mainwindow.py`)
- Objectif: verifier controles interactifs, branchements reels, delegation UI->controleur, et gardes metier d'alignement.

## Methode

- Inventaire AST des widgets/signaux/slots de `tab_alignement.py`.
- Matrice de branchement locale puis matrice effective cross-file (avec usages `tab.<control>` dans `alignement_actions.py`).
- Probe runtime delegation: clic boutons -> methodes controleur attendues.
- Probe runtime metier `run_align_episode` (cas nominal + gardes).
- Execution tests cibles + preuve couverture existante.

## Verdict Executif

- Controles interactifs recenses: **18**
- Branches directs: **13**
- Branches indirects: **5**
- Non branches (matrice effective cross-file): **0**

Conclusion:
- Aucun controle interactif detecte comme "present mais non reellement branche" sur le perimetre audite.
- Les actions de l'onglet Alignement sont bien branchees soit en direct, soit via delegation vers `AlignmentActionsController`.

## Inventaire Et Branchement

Preuves:
- `evidence/tab_alignement_ast_inventory.json`
- `evidence/tab_alignement_control_usage_matrix.json`
- `evidence/tab_alignement_branching_matrix.json`
- `evidence/tab_alignement_branching_matrix_effective.json`
- `evidence/tab_alignement_crossfile_control_usage.json`
- `evidence/tab_alignement_slot_callmap.json`

Important (present vs reellement branche):

- La matrice locale (fichier `tab_alignement.py` seul) marquait 2 controles `NON_BRANCHE`:
  - `align_by_similarity_cb`
  - `bulk_threshold_spin`
- En matrice effective cross-file, ces controles sont utilises dans `alignement_actions.py`:
  - `align_by_similarity_cb` lu par `run_align_episode`
  - `bulk_threshold_spin` lu par `bulk_accept` et `bulk_reject`
- Verdict final: ces 2 controles sont **BRANCHE_INDIRECT**, donc pas des faux boutons.

## Delegation UI -> Controleur

Constat:
- 10 slots de `AlignmentTabWidget` deleguent vers `AlignmentActionsController`.
- Probe runtime: `10/10` appels de delegation observes apres clics (aucun manquant).

Preuves:
- `evidence/tab_alignement_controller_delegations.json`
- `evidence/tab_alignement_runtime_delegation_probe.json`
- `evidence/tab_alignement_delegation_refs.txt`
- `evidence/alignement_actions_callmap.json`

## Logique Metier Aligner (preuves runtime)

Probe `run_align_episode` (controller reel):

1. Cas nominal segments + cible:
- creation d'un `AlignEpisodeStep`
- `segment_kind` propage (`utterance`)
- `pivot_lang='en'`, `target_langs=['fr']`

2. Cas pivot==cible:
- warning utilisateur
- aucun step lance

3. Cas sans segments et sans cible:
- warning utilisateur
- aucun step lance

4. Cas cues-only (sans segments, cible renseignee):
- autorise
- `AlignEpisodeStep` lance

Preuves:
- `evidence/alignement_actions_runtime_probe.json`
- `evidence/alignement_logic_excerpts.txt`

## Integration MainWindow

- `AlignmentTabWidget` est instancie et ajoute comme onglet top-level "Alignement".

Preuve:
- `evidence/tab_alignement_embedding_refs.txt`

## Tests Et Couverture

Tests executes:

- `tests/test_ui_alignement.py` (36 tests)
- `tests/test_align_grouping.py` (1 test)
- `tests/test_align_run_metadata.py` (7 tests)
- `tests/test_export_phase5.py` (7 tests)
- `tests/test_ui_preparer_navigation.py::test_navigation_handoff_episode_and_segment_kind` (1 test)

Total execute pour cet audit: **52 tests**, tous verts.

Preuves:
- `evidence/pytest_alignement_focus.log`
- `evidence/pytest_alignement_exporters.log`
- `evidence/pytest_alignement_handoff.log`
- `evidence/tests_references_alignement.txt`

Couverture issue quality gate (2026-03-16):

- `tab_alignement.py`: **92.78%**
- `alignement_actions.py`: **33.84%**
- `alignement_exporters.py`: **53.66%**

Preuve:
- `evidence/tab_alignement_coverage_from_quality_gate.json`

## Risques Fonctionnels Restants

- Aucun risque P0 de branchement UI detecte.
- Risque principal: couverture faible sur `alignement_actions.py` et partielle sur `alignement_exporters.py`, alors que ces couches portent des gardes metier et I/O d'export.
