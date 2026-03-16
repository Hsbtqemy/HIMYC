# Smoke Report - Release v0.6.10 (.exe)

## Scope

- Date: 2026-03-16
- Target: GitHub release asset `HowIMetYourCorpus.exe` for tag `v0.6.10`
- Goal:
  - confirm release asset integrity
  - confirm executable starts and opens main window
  - prepare evidence for follow-up manual UI smoke

## Automated checks executed

1. Download release asset:
- Source: `https://github.com/Hsbtqemy/HIMYC/releases/tag/v0.6.10`
- File: `HowIMetYourCorpus.exe`

2. Integrity check:
- Local SHA256 computed
- Compared with release digest published by GitHub release API
- Result: match

3. Executable launch probe:
- Started `HowIMetYourCorpus.exe`
- Waited 10 seconds
- Observed running process and visible window title `HowIMetYourCorpus`
- Stopped probe processes cleanly after observation

4. Proxy workflow tests (source-level guards related to requested flow):
- `tests/test_ui_corpus_sources.py`
- `tests/test_ui_mainwindow_core.py::test_on_job_finished_success_clears_failed_episode_ids`
- `tests/test_ui_mainwindow_core.py::test_tab_change_stays_on_preparer_when_prompt_cancelled`
- Result: `6 passed`

## Evidence files

- `evidence/exe_metadata.json`
- `evidence/exe_integrity_check.json`
- `evidence/exe_launch_probe.json`
- `evidence/proxy_workflow_tests.log`

## Verdict

- Release `.exe` integrity: PASS
- `.exe` startup and main window availability: PASS
- Full interactive flow (`open project -> import batch SRT`) directly on packaged `.exe`: not fully automated in this run.

## Manual follow-up checklist (5 min)

1. Launch `HowIMetYourCorpus.exe`.
2. Open an existing project.
3. Go to Corpus tab and run batch SRT import from a test folder.
4. Confirm import jobs start and episodes refresh.
5. Save project state and relaunch app to verify persistence.
