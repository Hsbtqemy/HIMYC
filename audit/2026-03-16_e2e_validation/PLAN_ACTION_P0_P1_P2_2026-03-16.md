# Plan d'action P0 / P1 / P2 - Stabilisation 2026-03-16

## P0 - Corriger immediatement
Etat courant: **0 P0 ouvert**.

Validation:
- `audit/2026-03-16_e2e_validation/evidence/quality_gate_postfix2/summary.json`
- `audit/2026-03-16_e2e_validation/evidence/e2e_checklist_assist_postfix2/report.json`

## P1 - Completer / fiabiliser

### P1.1 Packaging release macOS (clos)
Constat initial:
- upload `dist/HowIMetYourCorpus.app` invalide sur `v0.6.7`.
- preuve: `release_run_macos_build_extract.txt`

Action:
- release workflow bascule vers zip `.app` + `fail_on_unmatched_files: true`.

Validation:
- run release `23138615250` success (`gh_release_run_23138615250.json`).

### P1.2 Gate CI pragmatique base versionnee (clos)
Constat:
- premier run quality gate `23138611304` en echec (tests Preparer + seuil couverture inadapté + node ids checklist manquants).
- preuve: `gh_quality_run_23138611304.log`

Actions:
- Correctifs Preparer/Alignement/langues:
  - `src/howimetyourcorpus/app/tabs/preparer_actions.py`
  - `src/howimetyourcorpus/app/mainwindow_project.py`
  - `src/howimetyourcorpus/app/tabs/tab_alignement.py`
- durcissement scripts/gate:
  - `scripts/e2e_checklist_assist.py` (filtrage node ids + fallback)
  - `.github/workflows/quality-gate.yml` seuil couverture `62`

Validation:
- simulation CI worktree propre:
  - quality gate PASS `251 passed`, couverture `62.83%` (`ci_fix_probe2/summary.json`)
  - checklist E2E PASS (`ci_fix_probe2/report.json`)
- GitHub rerun quality gate PASS:
  - run `23139288639` success (`gh_quality_run_23139288639.json`)
  - log detail (`gh_quality_run_23139288639.log`)
- workspace courant:
  - quality gate PASS (`quality_gate_postfix2/summary.json`)
  - checklist E2E PASS (`e2e_checklist_assist_postfix2/report.json`)

## P2 - Polish

### P2.1 Node 24 readiness GitHub Actions
Constat:
- warning deprecation Node 20 dans logs de run.
- preuve: `gh_quality_run_23138611304.log` et `release_run_macos_build_extract.txt`.

Action recommandee:
- planifier une passe dediee MAJ actions pour avant bascule Node 24.

## Decision de sortie
- Criteria de stabilisation satisfaits sur perimetre controle.
- `v0.6.8` maintenu avec remediations CI appliquees.
