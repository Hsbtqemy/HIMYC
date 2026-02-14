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
| Lot 0 | Baseline KPI + gouvernance + rollback | hsmy + codex | TBD | TBD | En cours |
| Lot 1 | Fiabilite critique workflow (run explicite + etat global job) | hsmy + codex | TBD | TBD | En cours |
| Lot 2 | Concordance async + cancel + pagination stable | TBD | TBD | TBD | A faire |
| Lot 3 | Logs perf (debounce + incremental/tail + pin UX) | TBD | TBD | TBD | A faire |
| Lot 4 | Personnages model/view + parite I/O | TBD | TBD | TBD | A faire |
| Lot 5 | Accessibilite/HDPI/shortcuts + clarte visuelle | TBD | TBD | TBD | A faire |
| Lot 6 | Decouplage tab_corpus -> controller | TBD | TBD | TBD | A faire |

## Decision log minimal (a renseigner a chaque lot)

| Date | Lot | Decision | Impact | Owner |
|---|---|---|---|---|
| 2026-02-14 | Lot -1 | Pilotage passe en split 2 colonnes avec boxes adaptatives | Lisibilite + reduction frictions | hsmy + codex |
| 2026-02-14 | Lot 0 | Baseline perf scriptable ajoutee | Mesure avant/apres fiable | hsmy + codex |
| 2026-02-14 | Lot 1 | Etat global job normalise (`idle/running/cancelling/done/error`) + persistance run personnages | Feedback robuste + reprise fiable | hsmy + codex |
