# Audit Fonctionnel - Vues Transverses d'Expertise

## Perimetre

- Date: 2026-03-17
- Cible: flux transverses entre `Inspecteur`, `Preparer`, `Alignement`, `Personnages`, orchestration MainWindow, et undo/redo global.
- Objectif: verifier que les vues/fonctions transverses d'expertise sont reellement branchees et coherentes (contexte, handoff, propagation, refresh, undo/redo).

## Methode

- Releve statique des points de branchement cross-tab et orchestration MainWindow.
- Releve statique des points undo/redo et propagation personnages.
- Execution d'un lot de tests transverses cibles (handoff, persistance, propagation, refresh, segment_kind).
- Construction d'une matrice de vues expertes (EV1..EV6) avec preuves code + tests.

## Metrics Observees

Preuve:
- `evidence/vues_transverses_metrics.json`

Valeurs:
- references cross-tab: `33`
- references undo/redo: `120`
- references propagation: `44`
- references persistance contexte: `85`
- tests transverses executes: `23/23` verts

## Inventaire Des Vues Transverses

Preuve:
- `evidence/vues_expertise_matrix.json`
- `evidence/vues_expertise_verdicts.csv`

Verdict par vue:

1. `EV1` Handoff episode/segment_kind inter-onglets: **OPERATIONNEL**
2. `EV2` Persistance contexte local (episode/source/splitter/notes): **OPERATIONNEL**
3. `EV3` Tracabilite segment_kind (run alignement -> vues expertes): **OPERATIONNEL**
4. `EV4` Propagation assignations segment/cue vers DB+fichiers: **OPERATIONNEL**
5. `EV5` Undo/Redo transversal (sous-titres, preparer, alignement): **OPERATIONNEL**
6. `EV6` Orchestration refresh transverse (post-job, post-open projet): **OPERATIONNEL**

## Preuves Principales

- Handoff / orchestration:
  - `evidence/cross_tab_handoff_refs.txt`
- Persistance contexte:
  - `evidence/context_persistence_refs.txt`
- Undo/Redo:
  - `evidence/undo_redo_refs.txt`
- Propagation personnages / segment_kind:
  - `evidence/propagation_refs.txt`
- Tests transverses:
  - `evidence/pytest_vues_transverses_focus.log`
  - `evidence/pytest_vues_transverses_segment_kind.log`

## Present Vs Reellement Branche (transverse)

### Reellement branches

- Les handoffs episode/segment_kind vers Alignement sont relies a des methodes explicites MainWindow -> tabs (`open_alignement_for_episode`, `set_episode_and_segment_kind`).
- La propagation personnages est reliee aux runs d'alignement et a `segment_kind` (lecture metadata run + verification source_type).
- Undo/redo est transversalement cable via un `undo_stack` global propage aux tabs metier.

### Point de structure a noter (pas une panne)

- Il n'existe pas d'onglet unique "expert transverse" dedie.
- Les vues transverses sont distribuees sur plusieurs onglets (Inspecteur/Preparer/Alignement/Personnages).

Preuve:
- `evidence/main_tabs_inventory_refs.txt`
- `evidence/expert_view_keyword_scan.txt` (aucun module/onglet "expert" explicite detecte)

## Resultat Global

- Aucun bug P0 detecte sur les branchements transverses verifies.
- Les 6 vues transverses cibles sont operationnelles sur le perimetre audite.
- Le principal manque n'est pas un branchement casse, mais l'absence d'une vue unifiee de pilotage expert.
