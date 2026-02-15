# Matrice Ownership UI - Workflow Refonte

Date: 2026-02-14

## RACI leger (definitions)

- Dev owner: implemente et garantit la qualite technique du lot.
- Reviewer tech: valide architecture, risques et regressions.
- Validateur UX/Produit: valide ergonomie, flux et acceptance.

## Matrice par lot

| Lot | Scope court | Dev owner | Reviewer tech | Validateur UX/Produit | Statut |
|---|---|---|---|---|---|
| Lot -1 | Refonte ergonomique Pilotage mac (2 colonnes, boxes droite, table corpus) | hsmy + codex | TBD | TBD | Fait |
| Lot 0 | Baseline KPI + gouvernance + rollback | hsmy + codex | TBD | TBD | Fait |
| Lot 1 | Fiabilite critique workflow (run explicite + etat global job) | hsmy + codex | TBD | TBD | Fait |
| Lot 2 | Concordance async + cancel + pagination stable | hsmy + codex | TBD | TBD | Fait |
| Lot 3 | Logs perf (debounce + incremental/tail + pin UX) | hsmy + codex | TBD | TBD | Fait |
| Lot 4 | Personnages model/view + parite I/O | hsmy + codex | TBD | TBD | Fait |
| Lot 5 | Accessibilite/HDPI/shortcuts + clarte visuelle | hsmy + codex | TBD | TBD | En cours |
| Lot 6 | Decouplage tab_corpus -> controller | hsmy + codex | TBD | TBD | En cours |

## Decision log minimal (a renseigner a chaque lot)

| Date | Lot | Decision | Impact | Owner |
|---|---|---|---|---|
| 2026-02-14 | Lot -1 | Pilotage passe en split 2 colonnes avec boxes adaptatives | Lisibilite + reduction frictions | hsmy + codex |
| 2026-02-14 | Lot 0 | Baseline perf scriptable ajoutee | Mesure avant/apres fiable | hsmy + codex |
| 2026-02-14 | Lot 1 | Etat global job normalise (`idle/running/cancelling/done/error`) + persistance run personnages | Feedback robuste + reprise fiable | hsmy + codex |
| 2026-02-14 | Lot 2 | Tri deterministe KWIC (episodes/segments/cues) pour pagination stable | Resultats "charger plus" coherents et reproductibles | hsmy + codex |
| 2026-02-14 | Lot 2 | Telemetrie KWIC (status/hits/duree) ajoutee dans la UI + logs | Visibilite perf/diagnostic continue | hsmy + codex |
| 2026-02-14 | Lot 3 | Refresh logs optimise (rendu bloc + ingestion incremental tail) | Filtrage plus fluide sur gros buffers | hsmy + codex |
| 2026-02-14 | Lot 3 | Baseline perf enrichie avec metrique `logs_render_10k_ms` | Suivi perf logs plus representatif | hsmy + codex |
| 2026-02-15 | Lot 4 | Validation propagation completee (priorite assignation cue + idempotence) via tests store | Cloture parite metier Personnages sans regression | hsmy + codex |
| 2026-02-15 | Lot 6 | Export corpus refactore dans `CorpusWorkflowController` (preconditions + dispatch format) | `tab_corpus` allege et logique export testee hors UI | hsmy + codex |
| 2026-02-15 | Lot 6 | Flux import local refactore dans `CorpusWorkflowController` (decouverte + merge + ajout manuel) | Moins de logique metier dans l'UI, preconditions unifiees et testees | hsmy + codex |
| 2026-02-15 | Lot 6 | Validation de selection d'episode erreur centralisee dans le controller | Suppression de duplication UI et messages precondition homogenes | hsmy + codex |
| 2026-02-15 | Lot 6 | Execution de plans composes + format message "episodes ignores" centralises dans le controller | Reduction de duplication `tab_corpus` et comportement warning/status unifie | hsmy + codex |
| 2026-02-15 | Lot 6 | Availability des actions scope centralisee (activations + raisons) dans le controller | UI plus declarative, logique metier testee hors widget | hsmy + codex |
