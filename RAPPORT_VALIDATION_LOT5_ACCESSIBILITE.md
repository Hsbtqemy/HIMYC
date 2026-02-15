# Rapport validation Lot 5 - Accessibilite UI

Date: 2026-02-15  
Projet: HowIMetYourCorpus

## Perimetre

- Navigation clavier/focus sur onglets critiques.
- Raccourcis globaux recherche/logs.
- Contrat de non-regression accessibilite de base (sans dependances externes).

## Resultats

1. Raccourcis globaux: **OK**
- `Ctrl/Cmd+F` et `Ctrl/Cmd+L` declares dans `src/howimetyourcorpus/app/ui_mainwindow.py`.
- Routage de focus recherche deja couvre par `tests/test_ui_mainwindow_job_state.py`.

2. Contrat focus/tab-order: **OK**
- Methodes focus presentes sur widgets critiques:
  - `ProjectTabWidget`, `CorpusTabWidget`, `PilotageTabWidget`
  - `AlignmentTabWidget`, `PersonnagesTabWidget`, `ValidationAnnotationTabWidget`
  - `ConcordanceTabWidget`, `LogsTabWidget`
- Configuration explicite du tab-order verifiee (presence de `setTabOrder`) sur les vues critiques.

3. Validation automatisee ajoutee: **OK**
- Nouveau fichier: `tests/test_ui_accessibility_contract.py`
- Couvre:
  - declaration des raccourcis globaux,
  - presence des methodes de focus critiques,
  - presence des chaines de tab-order explicites.

## Execution de tests

- `pytest -q tests/test_ui_accessibility_contract.py`
- `pytest -q tests/test_ui_mainwindow_job_state.py`

## Conclusion Lot 5

Lot 5 est **clos cote code et contrat testable** (navigation clavier/focus/raccourcis).

## Note operationnelle

La verification HDPI Windows (125/150/200%) reste un protocole de recette de release sur poste cible, deja defini dans `CHECKLIST_ACCESSIBILITE_UI.md`.
