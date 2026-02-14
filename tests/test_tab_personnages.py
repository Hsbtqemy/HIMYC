"""Tests unitaires ciblés pour l'onglet Personnages."""

from howimetyourcorpus.app.tabs.tab_personnages import PersonnagesTabWidget


def test_format_run_label_includes_created_at_and_target_langs() -> None:
    run = {
        "align_run_id": "S01E01:align:20260214T101112Z",
        "created_at": "2026-02-14T10:11:12Z",
        "params_json": '{"target_langs": ["fr", "it"]}',
    }
    label = PersonnagesTabWidget._format_run_label(run)
    assert "2026-02-14 10:11:12 UTC" in label
    assert "Cible FR/IT" in label
    assert "S01E01:align:20260214T101112Z" in label


def test_format_run_label_handles_invalid_json() -> None:
    run = {
        "align_run_id": "run-42",
        "created_at": "",
        "params_json": "{invalid}",
    }
    label = PersonnagesTabWidget._format_run_label(run)
    assert label == "run-42"
