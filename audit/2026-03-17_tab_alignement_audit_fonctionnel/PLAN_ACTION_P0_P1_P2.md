# Plan d'Action - Audit Fonctionnel Alignement

## P0 - Corriger

- Aucun P0 identifie sur le branchement fonctionnel des controles Alignement.

## P1 - Completer

1. Renforcer les tests de `alignement_actions.py` (prioritaire)
- `delete_current_run` (fallback exception -> suppression directe)
- `run_align_episode` sur combinaisons de gardes supplementaires
- branches `undo_stack` vs mode sans undo

2. Renforcer les tests de `alignement_exporters.py`
- normalisation de chemin/extension selon filtre
- erreurs I/O et messages utilisateur

3. Ajouter un test UI explicite de non-regression sur les 2 controles indirects
- `align_by_similarity_cb` impacte `AlignEpisodeStep.use_similarity_for_cues`
- `bulk_threshold_spin` impacte selection des candidats bulk

## P2 - Polish

1. Clarifier le help text Alignement
- expliciter la difference segments mode vs cues-only mode
- expliciter l'effet du checkbox "Forcer alignement par similarite"

2. Ameliorer la telemetrie de debug (logs)
- journaliser decision path principal dans `run_align_episode`
- faciliter diagnostic utilisateur en cas de no-op

3. Eventuellement decomposer `AlignmentActionsController`
- extraire helpers exports et guards pour augmenter lisibilite/testabilite.
