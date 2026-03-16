# Validation Steps 1-2 - Corpus Batch + Quality Gate

## Scope

- Date: 2026-03-16
- Branch: `master`
- Commit under validation: `f45337e`
- Goal:
  - Step 1: functional validation of Corpus batch SRT import.
  - Step 2: run full quality gate (`pytest`, coverage, assisted E2E checklist).

## Step 1 - Functional validation (Corpus batch SRT)

### Automated targeted checks

- Command:
  - `python -m pytest -q tests/test_ui_corpus_sources.py tests/test_ui_corpus_tab.py tests/test_ui_dialogs.py`
- Result:
  - PASS, `28 passed`.
- Evidence:
  - `evidence/pytest_targeted_batch.log`

### UI smoke launch

- Command:
  - `python -c "... MainWindow ..."`
- Result:
  - PASS, `SMOKE_MAINWINDOW_OK`.
- Evidence:
  - `evidence/mainwindow_smoke.log`

## Step 2 - Full quality gate

### Global test suite

- Command:
  - `python -m pytest -q`
- Result:
  - PASS, `309 passed`.

### Coverage gate script

- Command:
  - `python scripts/quality_gate.py`
- Result:
  - PASS.
  - Coverage: `65.07%` (threshold: `62.00%`).
- Evidence:
  - `evidence/pytest_cov.log`
  - `evidence/coverage.json`
  - `evidence/summary.json`

### Assisted E2E checklist

- Command:
  - `python scripts/e2e_checklist_assist.py`
- Result:
  - PASS global.
  - PASS `precheck`, `scenario_a`, `scenario_b`, `scenario_c`, `continuite`.
- Evidence:
  - `evidence/report.md`
  - `evidence/report.json`

## Verdict

- Step 1: PASS
- Step 2: PASS
- Blocking issue detected: none

## Suggested next move

- Proceed with release preparation (tag + build artifact) if no additional hotspot is requested.
