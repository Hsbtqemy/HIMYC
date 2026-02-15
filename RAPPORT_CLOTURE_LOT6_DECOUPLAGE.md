# Rapport de cloture - Lot 6 (Decouplage `tab_corpus` -> controller)

Date: 2026-02-15  
Branche: `refonte/workflow-ux-20260214`

## 1) Objectif du lot

Sortir la logique workflow metier de `tab_corpus` vers `CorpusWorkflowController` afin de:
- reduire le couplage UI/metier,
- homogeniser les preconditions/warnings,
- augmenter la testabilite hors widget Qt.

## 2) Resultat

Statut: **Fait**.

Le flux workflow de l'onglet Corpus est desormais majoritairement orchestre par `CorpusWorkflowController`:
- preparation des scopes/actions (fetch/normalize/segment/index/run-all/segment+index),
- preconditions globales et disponibilite des actions scope,
- reprise d'erreurs (selectionnee et bulk),
- callbacks d'ouverture depuis le panneau erreurs (inspecteur/logs),
- formatage des messages de statut workflow et "episodes ignores".

`tab_corpus.py` est recentre sur:
- la collecte du contexte UI (selection/scope),
- la liaison boutons/signaux,
- l'affichage des retours utilisateur.

## 3) Commits de cloture Lot 6

- `e60922f` `refactor(corpus): centralize scope action ui-state preconditions`
- `647aff5` `refactor(corpus): move run-all scope plan prep to controller`
- `16ad50a` `refactor(corpus): centralize normalize and clean-scope prep`
- `e8fa31f` `refactor(corpus): centralize fetch scope preparation`
- `c341c6f` `refactor(corpus): factor selection-scope action orchestration`
- `a35f4f9` `refactor(corpus): centralize segment+index scope plan prep`
- `5553f47` `refactor(corpus): centralize composed workflow execution`
- `d30c9da` `refactor(corpus): centralize scope action execution flows`
- `7c7f82b` `refactor(corpus): centralize error retry orchestration`
- `7b34311` `refactor(corpus): simplify run-all handler in tab_corpus`
- `b2c4a8d` `refactor(corpus): factor error panel open callbacks`
- `c1cc6f7` `docs(ui): close lot6 decoupling and update next steps`

## 4) Validation executee

Suites lancees et passees:
- `pytest -q tests/test_corpus_controller.py`
- `pytest -q tests/test_corpus_scope.py tests/test_workflow_ui.py tests/test_ui_mainwindow_job_state.py tests/test_tab_personnages.py tests/test_project_store_propagation.py`

Resultat: toutes vertes.

## 5) Risques residuels

- Validation visuelle/manual QA encore necessaire sur mac (13" + ecran large) pour confirmer l'ergonomie finale du flux pilotage.
- Pas de test widget specifique "interaction utilisateur" dedie au bloc reprise erreurs (comportement deja couvre via controller).

## 6) Suite recommandee

1. Ouvrir un lot de consolidation QA (parcours utilisateur complet + checklist de non-regression visuelle).
2. Figer un jalon de release UI avec notes de rollback.
