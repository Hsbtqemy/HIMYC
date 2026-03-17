# Plan Action P0 / P1 / P2 - Vue Expert (issue audit 2026-03-17)

## Etat d avancement (2026-03-17)
- P0: termine (aucun item ouvert).
- P1.1: termine (check projet robuste + test non-regression).
- P1.2: termine (Context complete + tests mismatch/incomplet).
- P2.1: termine (toggle auto-refresh 2s + timer + test activation/desactivation).
- P2.2: termine (barre KPI avec infobulles + legende snapshot + spec UX courte).
- Evidences mises a jour:
  - `evidence/pytest_p2_expert.log`
  - `evidence/expert_runtime_snapshot_p2.txt`
  - `evidence/expert_runtime_snapshot_p2_metrics.json`
  - `SPEC_UX_P2_KPI_AUTORAFRAICHISSEMENT.md`

## P0 - Corriger
- Aucun item P0 ouvert.
- Justification: aucun controle present non branche et aucune regression test detectee.
- Preuves: `evidence/tab_expert_branching_metrics.json`, `evidence/pytest_global.log`

## P1 - Completer
1. Rendre `Project loaded` plus robuste
- Action: remplacer `bool(store and db)` par un check d etat projet explicite (ex: root/config/db accessible).
- Definition of done: un test non-regression qui couvre faux positif actuel.
- Preuve de besoin: `evidence/tab_expert_method_refs.txt` (ligne 219).

2. Distinguer coherence et completude du contexte
- Action: ajouter un indicateur `Context complete` (Inspecteur/Preparer/Alignement/Personnages tous renseignes) en plus de `Context consistent`.
- Definition of done: tests couvrant cas partiellement vides + cas mismatch.
- Preuve de besoin: `evidence/tab_expert_method_refs.txt` (ligne 210), `evidence/expert_runtime_snapshot_mismatch.txt`.

## P2 - Polish
1. Auto-refresh optionnel live
- Action: ajouter un toggle auto-refresh (intervalle court) pour vue Expert.
- DoD: pas de freeze UI + test d activation/desactivation.
- Preuves de contexte: `evidence/branchage_refs.txt`, `evidence/project_language_combo_refresh_excerpt.txt`.

2. Aide de lecture des KPI
- Action: infobulles/legende pour `Project loaded`, `Context consistent`, `Episode focus`.
- DoD: spec UX courte + verification manuelle sur snapshot.
- Preuve de besoin: `evidence/expert_runtime_snapshot.txt`.

## Ordonnancement recommande
1. P1.1
2. P1.2
3. P2.1
4. P2.2
