# Resume Executif - Audit Alignement

## Resultat global

- Perimetre audite: onglet Alignement + controleur d'actions.
- Verdict: **aucun controle interactif non branche** sur la matrice effective cross-file.

## Chiffres cles

- Controles interactifs: `18`
- Branches directs: `13`
- Branches indirects: `5`
- Non branches: `0`
- Delegations UI->controleur verifiees en runtime: `10/10`
- Tests executes pour cet audit: `52`, tous verts

## Points importants

1. Les controles apparemment "inactifs" localement (`align_by_similarity_cb`, `bulk_threshold_spin`) sont en realite utilises dans `AlignmentActionsController`.
2. La logique `run_align_episode` est fonctionnelle avec gardes:
- bloque pivot==cible,
- bloque no-segment/no-target,
- autorise le mode cues-only.
3. L'onglet Alignement est bien integre top-level dans MainWindow.

## Ecart prioritaire

- Couverture faible sur la couche controleur/export:
  - `alignement_actions.py` a `33.84%`
  - `alignement_exporters.py` a `53.66%`

## Preuves principales

- `evidence/tab_alignement_branching_matrix_effective.json`
- `evidence/tab_alignement_runtime_delegation_probe.json`
- `evidence/alignement_actions_runtime_probe.json`
- `evidence/pytest_alignement_focus.log`
- `evidence/pytest_alignement_exporters.log`
- `evidence/tab_alignement_coverage_from_quality_gate.json`
