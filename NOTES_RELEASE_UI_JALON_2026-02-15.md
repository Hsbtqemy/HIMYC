# Notes de release - Jalon UI (2026-02-15)

Date: 2026-02-15  
Branche cible: `refonte/workflow-ux-20260214`

## 1) Scope du jalon

Ce jalon couvre:
- lots ergonomie Pilotage mac (-1),
- lots fiabilite/perf/accessibilite (0..5),
- cloture Lot 6 (decouplage `tab_corpus` -> `CorpusWorkflowController`),
- consolidation QA initiale (smoke CI UI/workflow).

References:
- `DOC_PLAN_PRIORISATION_UI_REVIEW.md`
- `RAPPORT_CLOTURE_LOT6_DECOUPLAGE.md`
- `RAPPORT_VALIDATION_LOT5_ACCESSIBILITE.md`

## 2) Gate de validation

### 2.1 CI smoke

Workflow ajoute: `.github/workflows/ui-smoke.yml`

Suite smoke:
- `tests/test_ui_accessibility_contract.py`
- `tests/test_corpus_controller.py`
- `tests/test_corpus_scope.py`
- `tests/test_workflow_ui.py`
- `tests/test_ui_mainwindow_job_state.py`
- `tests/test_project_store_propagation.py`

### 2.2 QA manuelle minimale (mac)

Parcours cible:
1. Ouvrir/creer projet.
2. Decouvrir episodes.
3. Telecharger scope selectionne.
4. Normaliser puis Segmenter/Indexer.
5. Simuler une reprise erreurs (selectionnee + bulk).
6. Ouvrir Inspecteur/Logs depuis panneau erreurs.
7. Rechercher en Concordance.

## 3) Tag propose

Tag recommande:

```bash
git tag v0.5.2-ui-jalon-20260215
git push origin v0.5.2-ui-jalon-20260215
```

Note: le workflow release (`.github/workflows/release.yml`) se declenche sur `v*`.

## 4) Rollback cible (non destructif)

### 4.1 Rollback Lot 6 (fonctionnel)

Anchor pre-Lot6: commit `3216dcc` (cloture Lot 5).

Pour revert la serie Lot 6:

```bash
git revert --no-edit e60922f^..b2c4a8d
```

### 4.2 Rollback QA smoke CI uniquement

```bash
git revert --no-edit 2d8e783
```

## 5) Etat

Statut jalon: **Pret a tagger** apres validation manuelle mac.
