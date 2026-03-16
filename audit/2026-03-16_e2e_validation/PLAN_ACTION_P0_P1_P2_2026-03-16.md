# Plan d'action P0 / P1 / P2 - Stabilisation 2026-03-16

## P0 - Corriger immediatement
Etat: **aucun P0 ouvert**.

Preuves:
- `audit/2026-03-16_e2e_validation/evidence/e2e_checklist_assist_postfix/report.json`
- `audit/2026-03-16_e2e_validation/evidence/quality_gate_postfix/summary.json`

## P1 - Completer / fiabiliser

### P1.1 Packaging release macOS (clos)
Constat initial:
- Upload release pointe `dist/HowIMetYourCorpus.app` et ne trouve pas de fichier valide.
- Preuve: `audit/2026-03-16_e2e_validation/evidence/release_run_macos_build_extract.txt`

Action realisee:
- `.github/workflows/release.yml`:
  - packaging `.app` en `HowIMetYourCorpus-macos.app.zip`
  - upload sur `${{ env.ZIP_PATH }}`
  - `fail_on_unmatched_files: true`

Validation:
- `tests/test_ci_workflows.py` -> `2 passed`
- Preuve: `audit/2026-03-16_e2e_validation/evidence/pytest_ci_workflows_postfix.log`

### P1.2 Gate CI minimal workflow (clos)
Action realisee:
- Ajout `.github/workflows/quality-gate.yml` pour executer:
  - `scripts/quality_gate.py` (seuil 70)
  - `scripts/e2e_checklist_assist.py --skip-precheck`

Validation:
- Quality gate post-correctifs: PASS, `713 passed`, couverture `81.09%`.
- Checklist E2E post-correctifs: PASS A/B/C + continuite.
- Preuves:
  - `audit/2026-03-16_e2e_validation/evidence/quality_gate_postfix/summary.json`
  - `audit/2026-03-16_e2e_validation/evidence/e2e_checklist_assist_postfix/report.json`

## P2 - Polish / maintenance

### P2.1 Anticiper la transition Node 24 sur GitHub Actions
Constat:
- Warning de deprecation Node 20 visible dans logs release.
- Preuve: `audit/2026-03-16_e2e_validation/evidence/release_run_macos_build_extract.txt`

Proposition:
- Verifier et, si necessaire, mettre a jour versions d'actions avant la date de bascule runner.

## Decision de sortie de cycle
- Conditions de sortie stabilisation respectees sur ce perimetre.
- Patch release `v0.6.8` recommandee.
