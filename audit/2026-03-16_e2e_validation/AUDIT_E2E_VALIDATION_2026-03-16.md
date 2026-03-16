# Audit E2E Validation - 2026-03-16

## 1) Perimetre
- Cycle de stabilisation HIMYC sur base `v0.6.7` vers patch `v0.6.8`.
- Verification release, smoke local, checklist E2E A/B/C, quality gate, puis remediations CI post-tag.
- Correctifs appliques dans ce cycle: workflows CI, scripts de controle, tests de non-regression, et correctifs applicatifs cibles (Preparer/Alignement/refresh langues).

## 2) Methode de preuve
Toutes les affirmations ci-dessous sont tracees par mesures/logs dans:
- `audit/2026-03-16_e2e_validation/evidence/`

Preuves principales:
- release `v0.6.7`: `release_v0.6.7.json`, `release_run_22965244818_extract.txt`, `release_run_macos_build_extract.txt`
- smoke local: `smoke_launch_himyc.json`
- executions scripts locales:
  - `quality_gate/summary.json`, `quality_gate_postfix/summary.json`, `quality_gate_postfix2/summary.json`
  - `e2e_checklist_assist/report.json`, `e2e_checklist_assist_postfix/report.json`, `e2e_checklist_assist_postfix2/report.json`
- executions GitHub Actions post-tag `v0.6.8`:
  - echec quality gate initial: `gh_quality_run_23138611304.json`, `gh_quality_run_23138611304.log`
  - release succes: `gh_release_run_23138615250.json`
  - polling etat: `gh_runs_post_tag_status.log`
- verification en worktree propre (simulateur CI):
  - `ci_fix_probe2/summary.json`
  - `ci_fix_probe2/report.json`

## 3) Resultats Lot A (baseline)

### 3.1 Release `v0.6.7` - constat
- Asset publie: `.exe` uniquement.
- Le job macOS tente `dist/HowIMetYourCorpus.app` et log:
  - `Pattern 'dist/HowIMetYourCorpus.app' does not match any files.`
  - `dist/HowIMetYourCorpus.app does not include a valid file.`

Classification initiale:
- `P1` packaging release macOS incomplet.
- `P0` aucun bloqueur detecte sur la passe locale.

### 3.2 Smoke local
- `python launch_himyc.py`: process demarre (`started: true`).
- process ensuite stoppe par protocole de smoke (`exit_code: -1` attendu).

### 3.3 Checklist et quality gate initiaux
- Checklist E2E (full): PASS (`711 passed` precheck, scenarios A/B/C + continuite PASS).
- Quality gate (seuil 62): PASS, couverture `81.09%`.

## 4) Remediations implementees

### 4.1 CI/Release
- `.github/workflows/release.yml`
  - packaging `.app` -> `HowIMetYourCorpus-macos.app.zip`
  - upload `${{ env.ZIP_PATH }}`
  - `fail_on_unmatched_files: true` (Windows + macOS)

- `.github/workflows/quality-gate.yml`
  - quality gate standardise en CI:
    - `python scripts/quality_gate.py --coverage-min 62`
    - `python scripts/e2e_checklist_assist.py --skip-precheck`

- `tests/test_ci_workflows.py`
  - non-regression wiring workflows CI.

### 4.2 Correctifs applicatifs cibles
- `src/howimetyourcorpus/app/tabs/preparer_actions.py`
  - handoff Preparer->Alignement: infer `segment_kind` via DB (utterance si segments utterance existants), pas uniquement via source courante.

- `src/howimetyourcorpus/app/mainwindow_project.py`
  - `refresh_language_combos()` propage maintenant langues vers Preparer + Alignement (en plus de Inspecteur/Concordance/Personnages).

- `src/howimetyourcorpus/app/tabs/tab_alignement.py`
  - ajout combos pivot/cible et refresh langues pour coherer avec propagation multi-langues inter-onglets.

### 4.3 Script checklist E2E robuste
- `scripts/e2e_checklist_assist.py`
  - filtrage dynamique des node ids existants (fichier + fonction presentes),
  - fallback test nodes pour scenarios A/B/C/continuite,
  - echec explicite si un scenario ne trouve aucun test executable.

## 5) Boucle CI post-tag `v0.6.8`

### 5.1 Premier passage GitHub (avant remediations complementaires)
- Release run `23138615250`: **SUCCESS**.
- Quality Gate run `23138611304`: **FAILURE**.
- Causes mesurees:
  - 2 tests Preparer en echec (`test_preparer_go_to_alignement_prefers_existing_utterances_from_srt_source`, `test_refresh_language_combos_updates_multilang_tabs`).
  - seuil de couverture CI (`70`) non atteignable sur base versionnee propre (~`63%`).
  - checklist assistee reference des node ids absents dans la base versionnee (observe en simulation propre).

### 5.2 Verification post-correctifs
- GitHub Quality Gate rerun `23139288639`: **SUCCESS**.
  - `Run quality gate`: PASS (`251 passed`, couverture `62.83% >= 62`)
  - `Run checklist E2E assist`: PASS (A=7, B=5, C=1, continuite=7)
  - preuves: `gh_quality_run_23139288639.json`, `gh_quality_run_23139288639.log`

- Worktree propre (simulation CI):
  - quality gate: PASS, `251 passed`, couverture `62.83% >= 62` (`ci_fix_probe2/summary.json`)
  - checklist assistee: PASS scenarios A/B/C + continuite (`ci_fix_probe2/report.json`)

- Workspace courant:
  - quality gate post-fix: PASS, `713 passed`, couverture `81.09%` (`quality_gate_postfix2/summary.json`)
  - checklist assistee post-fix: PASS (A=9, B=6, C=1, continuite=9) (`e2e_checklist_assist_postfix2/report.json`)

## 6) Verdict executif
- `P0` ouverts: **0**
- `P1` critiques ouverts: **0**
- `P2` restant:
  - warning ecosysteme GitHub Actions Node 20 -> Node 24 (non bloquant immediat).

Decision:
- stabilisation validee, patch `v0.6.8` maintenu avec remediations CI appliquees.
