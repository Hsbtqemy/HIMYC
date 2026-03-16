# Rapport Checklist E2E assistee

- Date UTC: 2026-03-16T10:29:31.385861+00:00
- Statut global: PASS
- Verifications executees: 4

## PASS - Scenario A: Transcript -> Preparer -> Alignement -> Personnages

- Cle: `scenario_a`
- Checklist: A.4 Preparer transcript (edition + invalidation runs), A.5 Alignement phrases/tours + export, A.6 Personnages propagation, A.7 Concordance / exports
- Commande: `C:\Program Files\Python312\python.exe -m pytest -q tests/test_ui_preparer_navigation.py::test_preparer_save_transcript_structural_edits_replace_segments tests/test_ui_preparer_navigation.py::test_preparer_save_structural_warns_and_can_cancel_run_invalidation tests/test_ui_preparer_navigation.py::test_preparer_save_transcript_non_structural_keeps_align_runs tests/test_ui_alignement.py::test_run_align_episode_uses_selected_languages tests/test_ui_alignement.py::test_export_alignment_csv_writes_rows tests/test_ui_personnages.py::test_propagate_runs_with_utterance_assignments_when_run_is_utterance tests/test_ui_personnages.py::test_propagate_runs_and_reports_success tests/test_export_phase5.py::test_export_parallel_concordance_csv tests/test_export_phase5.py::test_export_align_report_html`
- Duree: 1.88s
- Resume: `============================== 9 passed in 1.04s ==============================`

## PASS - Scenario B: Sous-titres only

- Cle: `scenario_b`
- Checklist: B.3 Preparer source SRT + validation stricte, B.4 Alignement SRT-only
- Commande: `C:\Program Files\Python312\python.exe -m pytest -q tests/test_ui_preparer_navigation.py::test_preparer_can_open_srt_source_when_track_exists tests/test_ui_preparer_navigation.py::test_preparer_srt_timecode_strict_rejects_overlap tests/test_ui_preparer_navigation.py::test_preparer_srt_timecode_overlap_allowed_when_strict_disabled tests/test_tasks_align_episode.py::test_align_episode_supports_cues_only_without_segments tests/test_ui_preparer_navigation.py::test_preparer_go_to_alignement_prefers_existing_utterances_from_srt_source tests/test_ui_alignement.py::test_export_alignment_jsonl_writes_rows`
- Duree: 2.09s
- Resume: `============================== 6 passed in 1.06s ==============================`

## PASS - Scenario C: Continuite multi-langues projet

- Cle: `scenario_c`
- Checklist: C.2 Langues coherentes entre onglets
- Commande: `C:\Program Files\Python312\python.exe -m pytest -q tests/test_ui_preparer_navigation.py::test_refresh_language_combos_updates_multilang_tabs`
- Duree: 1.68s
- Resume: `============================== 1 passed in 0.79s ==============================`

## PASS - Continuite inter-onglets

- Cle: `continuite`
- Checklist: I.1 Preparer dirty + Ignorer recharge l'etat persistant, I.2 Fin de job pipeline -> refresh onglets, I.3 Handoff explicite vers Alignement
- Commande: `C:\Program Files\Python312\python.exe -m pytest -q tests/test_ui_preparer_navigation.py::test_preparer_discard_reloads_persisted_context tests/test_ui_mainwindow_core.py::test_refresh_tabs_after_job_calls_concordance_refresh_speakers tests/test_ui_preparer_navigation.py::test_refresh_tabs_after_job_updates_personnages_runs tests/test_ui_mainwindow_core.py::test_refresh_tabs_after_job_skips_duplicate_subs_refresh_when_inspector_is_combined tests/test_ui_mainwindow_core.py::test_refresh_tabs_after_project_open_skips_duplicate_subs_refresh_when_inspector_is_combined tests/test_ui_mainwindow_core.py::test_tab_change_stays_on_preparer_when_prompt_cancelled tests/test_ui_mainwindow_core.py::test_open_preparer_for_episode_aborts_when_unsaved_cancelled tests/test_ui_preparer_navigation.py::test_preparer_go_to_alignement_uses_utterance_when_transcript_rows_present tests/test_ui_preparer_navigation.py::test_preparer_go_to_alignement_prefers_existing_utterances_from_srt_source`
- Duree: 2.38s
- Resume: `============================== 9 passed in 1.51s ==============================`

