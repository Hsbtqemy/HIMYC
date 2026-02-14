"""Tests unitaires ciblés pour l'onglet Personnages."""

from PySide6.QtCore import Qt

from howimetyourcorpus.app.models_qt import CharacterAssignmentsTableModel, CharacterNamesTableModel
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


def test_decode_run_selections_payload_filters_invalid_entries() -> None:
    raw = {
        "/tmp/proj1": {"S01E01": "run-1", "": "run-x", "S01E02": ""},
        "/tmp/proj2": {"S02E01": "run-2"},
        "": {"S99E99": "run-z"},
        "/tmp/proj3": ["bad"],
    }
    decoded = PersonnagesTabWidget._decode_run_selections_payload(raw)
    assert decoded == {
        "/tmp/proj1": {"S01E01": "run-1"},
        "/tmp/proj2": {"S02E01": "run-2"},
    }


def test_encode_decode_run_selections_payload_roundtrip() -> None:
    data = {
        "/tmp/projA": {"S01E01": "run-a1", "S01E02": "run-a2"},
        "/tmp/projB": {"S02E03": "run-b3"},
    }
    encoded = PersonnagesTabWidget._encode_run_selections_payload(data)
    decoded = PersonnagesTabWidget._decode_run_selections_payload(encoded)
    assert decoded == data


def test_character_names_table_model_edit_add_remove() -> None:
    model = CharacterNamesTableModel()
    model.set_characters(
        characters=[
            {"id": "ted", "canonical": "Ted", "names_by_lang": {"en": "Ted", "fr": "Ted"}},
        ],
        langs=["en", "fr"],
    )
    assert model.rowCount() == 1
    assert model.columnCount() == 4
    idx = model.index(0, 1)
    assert model.data(idx, Qt.ItemDataRole.DisplayRole) == "Ted"
    model.setData(idx, "Theodore", Qt.ItemDataRole.EditRole)
    assert model.data(idx, Qt.ItemDataRole.DisplayRole) == "Theodore"
    new_row = model.add_empty_row()
    assert new_row == 1
    assert model.rowCount() == 2
    assert model.remove_row(0) is True
    assert model.rowCount() == 1


def test_character_assignments_table_model_edit_character_id() -> None:
    model = CharacterAssignmentsTableModel()
    model.set_rows(
        rows_data=[("S01E01:sentence:1", "Hello there", "ted")],
        character_ids=["ted", "robin"],
    )
    assert model.rowCount() == 1
    assert model.columnCount() == 3
    idx_char = model.index(0, CharacterAssignmentsTableModel.COL_CHARACTER_ID)
    assert model.data(idx_char, Qt.ItemDataRole.DisplayRole) == "ted"
    assert model.setData(idx_char, "robin", Qt.ItemDataRole.EditRole) is True
    assert model.data(idx_char, Qt.ItemDataRole.DisplayRole) == "robin"
