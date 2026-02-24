"""Non-régression UI: navigation Inspecteur → Préparer → Alignement."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QComboBox, QMessageBox, QStyleOptionViewItem, QTableWidgetItem

from howimetyourcorpus.app.ui_mainwindow import (
    MainWindow,
    TAB_ALIGNEMENT,
    TAB_INSPECTEUR,
    TAB_PREPARER,
)
from howimetyourcorpus.core.models import EpisodeRef, ProjectConfig, SeriesIndex, TransformStats
from howimetyourcorpus.core.segment import Segment
from howimetyourcorpus.core.storage.db import CorpusDB
from howimetyourcorpus.core.storage.project_store import ProjectStore
from howimetyourcorpus.core.subtitles import Cue


@pytest.fixture
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


@pytest.fixture
def main_window_with_project(tmp_path: Path, qapp: QApplication):
    root = tmp_path / "project"
    config = ProjectConfig(
        project_name="test_project",
        root_dir=root,
        source_id="subslikescript",
        series_url="https://example.invalid/series",
    )
    ProjectStore.init_project(config)
    store = ProjectStore(root)
    db = CorpusDB(store.get_db_path())
    db.init()
    store.save_series_index(
        SeriesIndex(
            series_title="Test",
            series_url="https://example.invalid/series",
            episodes=[
                EpisodeRef(
                    episode_id="S01E01",
                    season=1,
                    episode=1,
                    title="Pilot",
                    url="https://example.invalid/s01e01",
                )
            ],
        )
    )

    win = MainWindow()
    win._config = config
    win._store = store
    win._db = db
    win._refresh_inspecteur_episodes()
    win._refresh_preparer()
    win._refresh_align_runs()
    yield win
    win.close()


def test_preparer_tab_inserted_between_inspecteur_and_alignement(main_window_with_project: MainWindow) -> None:
    win = main_window_with_project
    assert win.tabs.tabText(TAB_INSPECTEUR) == "Inspecteur"
    assert win.tabs.tabText(TAB_PREPARER) == "Préparer"
    assert win.tabs.tabText(TAB_ALIGNEMENT) == "Alignement"


def test_navigation_handoff_episode_and_segment_kind(main_window_with_project: MainWindow) -> None:
    win = main_window_with_project
    win.tabs.setCurrentIndex(TAB_INSPECTEUR)

    win.open_preparer_for_episode("S01E01", source="transcript")
    assert win.tabs.currentIndex() == TAB_PREPARER
    assert win.preparer_tab.current_episode_id() == "S01E01"

    win.open_alignement_for_episode("S01E01", segment_kind="utterance")
    assert win.tabs.currentIndex() == TAB_ALIGNEMENT
    assert win.alignment_tab.align_episode_combo.currentData() == "S01E01"
    assert win.alignment_tab.align_segment_kind_combo.currentData() == "utterance"


def test_preparer_can_open_srt_source_when_track_exists(main_window_with_project: MainWindow) -> None:
    win = main_window_with_project
    db = win._db
    assert db is not None
    db.add_track("S01E01:en", "S01E01", "en", "srt")
    db.upsert_cues(
        "S01E01:en",
        "S01E01",
        "en",
        [
            Cue(
                episode_id="S01E01",
                lang="en",
                n=0,
                start_ms=1000,
                end_ms=1800,
                text_raw="Hi",
                text_clean="Hi",
            )
        ],
    )
    win._refresh_preparer()
    win.open_preparer_for_episode("S01E01", source="srt_en")

    assert win.tabs.currentIndex() == TAB_PREPARER
    assert win.preparer_tab.prep_source_combo.currentData() == "srt_en"
    assert win.preparer_tab.cue_table.rowCount() == 1


def test_preparer_srt_timecode_edit_persists_to_db(main_window_with_project: MainWindow) -> None:
    win = main_window_with_project
    db = win._db
    store = win._store
    assert db is not None
    assert store is not None
    db.add_track("S01E01:en", "S01E01", "en", "srt")
    db.upsert_cues(
        "S01E01:en",
        "S01E01",
        "en",
        [
            Cue(
                episode_id="S01E01",
                lang="en",
                n=0,
                start_ms=1000,
                end_ms=1800,
                text_raw="Hi",
                text_clean="Hi",
            )
        ],
    )
    win._refresh_preparer()
    win.open_preparer_for_episode("S01E01", source="srt_en")

    win.preparer_tab.prep_edit_timecodes_cb.setChecked(True)
    start_item = win.preparer_tab.cue_table.item(0, 1)
    end_item = win.preparer_tab.cue_table.item(0, 2)
    assert start_item is not None
    assert end_item is not None
    start_item.setText("00:00:01,500")
    end_item.setText("00:00:02,200")

    assert win.preparer_tab.save_current() is True
    cues = db.get_cues_for_episode_lang("S01E01", "en")
    assert cues[0]["start_ms"] == 1500
    assert cues[0]["end_ms"] == 2200
    content_fmt = store.load_episode_subtitle_content("S01E01", "en")
    assert content_fmt is not None
    content, fmt = content_fmt
    assert fmt == "srt"
    assert "00:00:01,500 --> 00:00:02,200" in content


def test_preparer_personnage_column_has_editable_combo_choices(main_window_with_project: MainWindow) -> None:
    win = main_window_with_project
    store = win._store
    db = win._db
    assert store is not None
    assert db is not None
    store.save_character_names(
        [
            {
                "id": "ted",
                "canonical": "Ted",
                "names_by_lang": {"en": "Ted", "fr": "Théodore"},
            }
        ]
    )
    db.upsert_segments(
        "S01E01",
        "utterance",
        [
            Segment(
                episode_id="S01E01",
                kind="utterance",
                n=0,
                start_char=0,
                end_char=2,
                text="Hi",
                speaker_explicit="Ted",
            )
        ],
    )
    db.add_track("S01E01:en", "S01E01", "en", "srt")
    db.upsert_cues(
        "S01E01:en",
        "S01E01",
        "en",
        [
            Cue(
                episode_id="S01E01",
                lang="en",
                n=0,
                start_ms=1000,
                end_ms=1800,
                text_raw="Hi",
                text_clean="Hi",
            )
        ],
    )

    win._refresh_preparer(force=True)
    win.open_preparer_for_episode("S01E01", source="transcript")
    utter_index = win.preparer_tab.utterance_table.model().index(0, 1)
    utter_delegate = win.preparer_tab.utterance_table.itemDelegateForColumn(1)
    utter_editor = utter_delegate.createEditor(
        win.preparer_tab.utterance_table,
        QStyleOptionViewItem(),
        utter_index,
    )
    assert isinstance(utter_editor, QComboBox)
    utter_values = {utter_editor.itemText(i) for i in range(utter_editor.count())}
    assert any(v in utter_values for v in ("ted", "Ted"))
    assert "Théodore" in utter_values

    win.open_preparer_for_episode("S01E01", source="srt_en")
    cue_index = win.preparer_tab.cue_table.model().index(0, 3)
    cue_delegate = win.preparer_tab.cue_table.itemDelegateForColumn(3)
    cue_editor = cue_delegate.createEditor(
        win.preparer_tab.cue_table,
        QStyleOptionViewItem(),
        cue_index,
    )
    assert isinstance(cue_editor, QComboBox)
    cue_values = {cue_editor.itemText(i) for i in range(cue_editor.count())}
    assert any(v in cue_values for v in ("ted", "Ted"))
    assert "Théodore" in cue_values


def test_preparer_srt_timecode_editability_restored_after_source_switch(
    main_window_with_project: MainWindow,
) -> None:
    win = main_window_with_project
    db = win._db
    assert db is not None
    db.add_track("S01E01:en", "S01E01", "en", "srt")
    db.upsert_cues(
        "S01E01:en",
        "S01E01",
        "en",
        [
            Cue(
                episode_id="S01E01",
                lang="en",
                n=0,
                start_ms=1000,
                end_ms=1800,
                text_raw="Hi",
                text_clean="Hi",
            )
        ],
    )

    win._refresh_preparer()
    win.open_preparer_for_episode("S01E01", source="srt_en")
    win.preparer_tab.prep_edit_timecodes_cb.setChecked(True)

    start_item = win.preparer_tab.cue_table.item(0, 1)
    assert start_item is not None
    assert bool(start_item.flags() & Qt.ItemFlag.ItemIsEditable)

    win.open_preparer_for_episode("S01E01", source="transcript")
    win.open_preparer_for_episode("S01E01", source="srt_en")
    start_item = win.preparer_tab.cue_table.item(0, 1)
    assert start_item is not None
    assert win.preparer_tab.prep_edit_timecodes_cb.isChecked()
    assert win.preparer_tab.prep_edit_timecodes_cb.isEnabled()
    assert bool(start_item.flags() & Qt.ItemFlag.ItemIsEditable)


def test_preparer_srt_timecode_strict_rejects_overlap(
    main_window_with_project: MainWindow,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    win = main_window_with_project
    db = win._db
    assert db is not None
    db.add_track("S01E01:en", "S01E01", "en", "srt")
    db.upsert_cues(
        "S01E01:en",
        "S01E01",
        "en",
        [
            Cue(
                episode_id="S01E01",
                lang="en",
                n=0,
                start_ms=1000,
                end_ms=1800,
                text_raw="Hi",
                text_clean="Hi",
            ),
            Cue(
                episode_id="S01E01",
                lang="en",
                n=1,
                start_ms=2000,
                end_ms=2600,
                text_raw="There",
                text_clean="There",
            ),
        ],
    )
    win._refresh_preparer()
    win.open_preparer_for_episode("S01E01", source="srt_en")

    warnings: list[str] = []

    def _fake_warning(*args, **kwargs):
        text = str(args[2]) if len(args) >= 3 else str(kwargs.get("text", ""))
        warnings.append(text)
        return QMessageBox.StandardButton.Ok

    monkeypatch.setattr("howimetyourcorpus.app.tabs.tab_preparer.QMessageBox.warning", _fake_warning)
    monkeypatch.setattr("howimetyourcorpus.app.tabs.tab_preparer.QMessageBox.critical", _fake_warning)

    win.preparer_tab.prep_edit_timecodes_cb.setChecked(True)
    win.preparer_tab.prep_strict_timecodes_cb.setChecked(True)
    end_item = win.preparer_tab.cue_table.item(0, 2)
    assert end_item is not None
    end_item.setText("00:00:02,300")  # Overlap avec la cue 2 (start=2000).

    assert win.preparer_tab.save_current() is False
    assert any("Chevauchement détecté" in w for w in warnings)
    cues = db.get_cues_for_episode_lang("S01E01", "en")
    assert cues[0]["end_ms"] == 1800
    assert cues[1]["start_ms"] == 2000
    win.preparer_tab._set_dirty(False)


def test_preparer_srt_timecode_overlap_allowed_when_strict_disabled(main_window_with_project: MainWindow) -> None:
    win = main_window_with_project
    db = win._db
    assert db is not None
    db.add_track("S01E01:en", "S01E01", "en", "srt")
    db.upsert_cues(
        "S01E01:en",
        "S01E01",
        "en",
        [
            Cue(
                episode_id="S01E01",
                lang="en",
                n=0,
                start_ms=1000,
                end_ms=1800,
                text_raw="Hi",
                text_clean="Hi",
            ),
            Cue(
                episode_id="S01E01",
                lang="en",
                n=1,
                start_ms=2000,
                end_ms=2600,
                text_raw="There",
                text_clean="There",
            ),
        ],
    )
    win._refresh_preparer()
    win.open_preparer_for_episode("S01E01", source="srt_en")
    win.preparer_tab.prep_edit_timecodes_cb.setChecked(True)
    win.preparer_tab.prep_strict_timecodes_cb.setChecked(False)

    end_item = win.preparer_tab.cue_table.item(0, 2)
    assert end_item is not None
    end_item.setText("00:00:02,300")

    assert win.preparer_tab.save_current() is True
    cues = db.get_cues_for_episode_lang("S01E01", "en")
    assert cues[0]["end_ms"] == 2300
    assert cues[1]["start_ms"] == 2000


def test_preparer_srt_timecode_rejects_invalid_range(
    main_window_with_project: MainWindow,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    win = main_window_with_project
    db = win._db
    assert db is not None
    db.add_track("S01E01:en", "S01E01", "en", "srt")
    db.upsert_cues(
        "S01E01:en",
        "S01E01",
        "en",
        [
            Cue(
                episode_id="S01E01",
                lang="en",
                n=0,
                start_ms=1000,
                end_ms=1800,
                text_raw="Hi",
                text_clean="Hi",
            )
        ],
    )
    win._refresh_preparer()
    win.open_preparer_for_episode("S01E01", source="srt_en")

    warnings: list[str] = []

    def _fake_warning(*args, **kwargs):
        text = str(args[2]) if len(args) >= 3 else str(kwargs.get("text", ""))
        warnings.append(text)
        return QMessageBox.StandardButton.Ok

    monkeypatch.setattr("howimetyourcorpus.app.tabs.tab_preparer.QMessageBox.warning", _fake_warning)
    monkeypatch.setattr("howimetyourcorpus.app.tabs.tab_preparer.QMessageBox.critical", _fake_warning)

    win.preparer_tab.prep_edit_timecodes_cb.setChecked(True)
    start_item = win.preparer_tab.cue_table.item(0, 1)
    end_item = win.preparer_tab.cue_table.item(0, 2)
    assert start_item is not None
    assert end_item is not None
    start_item.setText("00:00:02,500")
    end_item.setText("00:00:02,000")

    assert win.preparer_tab.save_current() is False
    assert any("timecodes invalides" in w for w in warnings)
    cues = db.get_cues_for_episode_lang("S01E01", "en")
    assert cues[0]["start_ms"] == 1000
    assert cues[0]["end_ms"] == 1800
    win.preparer_tab._set_dirty(False)


def test_preparer_save_transcript_rejects_unknown_character(
    main_window_with_project: MainWindow,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    win = main_window_with_project
    db = win._db
    assert db is not None
    db.upsert_segments(
        "S01E01",
        "utterance",
        [
            Segment(
                episode_id="S01E01",
                kind="utterance",
                n=0,
                start_char=0,
                end_char=2,
                text="Hi",
                speaker_explicit="TED",
            )
        ],
    )
    win._refresh_preparer()
    win.open_preparer_for_episode("S01E01", source="transcript")

    warnings: list[str] = []

    def _fake_warning(*args, **kwargs):
        text = str(args[2]) if len(args) >= 3 else str(kwargs.get("text", ""))
        warnings.append(text)
        return QMessageBox.StandardButton.Ok

    monkeypatch.setattr("howimetyourcorpus.app.tabs.preparer_save.QMessageBox.warning", _fake_warning)
    monkeypatch.setattr("howimetyourcorpus.app.tabs.tab_preparer.QMessageBox.critical", _fake_warning)

    assert win.preparer_tab.save_current() is False
    assert any("Personnage(s) inconnu(s)" in w for w in warnings)
    segs = db.get_segments_for_episode("S01E01", kind="utterance")
    assert segs[0]["speaker_explicit"] == "TED"
    win.preparer_tab._set_dirty(False)


def test_preparer_save_cue_rejects_unknown_character(
    main_window_with_project: MainWindow,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    win = main_window_with_project
    db = win._db
    assert db is not None
    db.add_track("S01E01:en", "S01E01", "en", "srt")
    db.upsert_cues(
        "S01E01:en",
        "S01E01",
        "en",
        [
            Cue(
                episode_id="S01E01",
                lang="en",
                n=0,
                start_ms=1000,
                end_ms=1800,
                text_raw="Hi",
                text_clean="Hi",
            )
        ],
    )
    win._refresh_preparer()
    win.open_preparer_for_episode("S01E01", source="srt_en")

    speaker_item = win.preparer_tab.cue_table.item(0, 3)
    assert speaker_item is not None
    speaker_item.setText("Ted")

    warnings: list[str] = []

    def _fake_warning(*args, **kwargs):
        text = str(args[2]) if len(args) >= 3 else str(kwargs.get("text", ""))
        warnings.append(text)
        return QMessageBox.StandardButton.Ok

    monkeypatch.setattr("howimetyourcorpus.app.tabs.preparer_save.QMessageBox.warning", _fake_warning)
    monkeypatch.setattr("howimetyourcorpus.app.tabs.tab_preparer.QMessageBox.critical", _fake_warning)

    assert win.preparer_tab.save_current() is False
    assert any("Personnage(s) inconnu(s)" in w for w in warnings)
    cues = db.get_cues_for_episode_lang("S01E01", "en")
    assert cues[0]["text_clean"] == "Hi"
    win.preparer_tab._set_dirty(False)


def test_preparer_utterance_cell_edit_undo_redo(main_window_with_project: MainWindow) -> None:
    win = main_window_with_project
    db = win._db
    assert db is not None
    db.upsert_segments(
        "S01E01",
        "utterance",
        [
            Segment(
                episode_id="S01E01",
                kind="utterance",
                n=0,
                start_char=0,
                end_char=2,
                text="Hi",
                speaker_explicit="TED",
            )
        ],
    )
    win._refresh_preparer()
    win.open_preparer_for_episode("S01E01", source="transcript")
    table = win.preparer_tab.utterance_table
    assert table.rowCount() == 1
    text_item = table.item(0, 2)
    assert text_item is not None
    assert text_item.text() == "Hi"

    count_before = win.undo_stack.count()
    text_item.setText("Hello")
    assert table.item(0, 2).text() == "Hello"
    assert win.undo_stack.count() == count_before + 1

    win.undo_stack.undo()
    assert table.item(0, 2).text() == "Hi"
    win.undo_stack.redo()
    assert table.item(0, 2).text() == "Hello"
    win.preparer_tab._set_dirty(False)


def test_preparer_segment_draft_undo_restores_previous_view(main_window_with_project: MainWindow) -> None:
    win = main_window_with_project
    win.open_preparer_for_episode("S01E01", source="transcript")
    assert win.preparer_tab.stack.currentWidget() == win.preparer_tab.text_editor
    win.preparer_tab.text_editor.setPlainText("TED: Hi\nMARSHALL: Yo")

    count_before = win.undo_stack.count()
    win.preparer_tab._segment_to_utterances()
    assert win.preparer_tab.stack.currentWidget() == win.preparer_tab.utterance_table
    assert win.preparer_tab.utterance_table.rowCount() == 2
    assert win.undo_stack.count() == count_before + 1

    win.undo_stack.undo()
    assert win.preparer_tab.stack.currentWidget() == win.preparer_tab.text_editor
    win.preparer_tab._set_dirty(False)


def test_preparer_status_combo_persists_and_is_undoable(main_window_with_project: MainWindow) -> None:
    win = main_window_with_project
    store = win._store
    assert store is not None
    win.open_preparer_for_episode("S01E01", source="transcript")
    assert win.preparer_tab.prep_status_combo.currentData() == "raw"

    idx_verified = win.preparer_tab.prep_status_combo.findData("verified")
    assert idx_verified >= 0
    win.preparer_tab.prep_status_combo.setCurrentIndex(idx_verified)
    assert store.get_episode_prep_status("S01E01", "transcript") == "verified"

    win.undo_stack.undo()
    assert store.get_episode_prep_status("S01E01", "transcript") == "raw"
    win.undo_stack.redo()
    assert store.get_episode_prep_status("S01E01", "transcript") == "verified"


def test_preparer_default_status_transcript_clean_is_normalized(main_window_with_project: MainWindow) -> None:
    win = main_window_with_project
    store = win._store
    assert store is not None
    store.save_episode_clean(
        "S01E01",
        "Clean content",
        TransformStats(raw_lines=1, clean_lines=1, merges=0, kept_breaks=0, duration_ms=0),
        {"source": "test"},
    )

    win._refresh_preparer()
    win.open_preparer_for_episode("S01E01", source="transcript")
    assert win.preparer_tab.prep_status_combo.currentData() == "normalized"


def test_preparer_default_status_srt_text_clean_diff_is_normalized(main_window_with_project: MainWindow) -> None:
    win = main_window_with_project
    db = win._db
    assert db is not None
    db.add_track("S01E01:en", "S01E01", "en", "srt")
    db.upsert_cues(
        "S01E01:en",
        "S01E01",
        "en",
        [
            Cue(
                episode_id="S01E01",
                lang="en",
                n=0,
                start_ms=1000,
                end_ms=1800,
                text_raw="Hi",
                text_clean="Ted: Hi",
            )
        ],
    )

    win._refresh_preparer()
    win.open_preparer_for_episode("S01E01", source="srt_en")
    assert win.preparer_tab.prep_status_combo.currentData() == "normalized"


def test_preparer_save_transcript_rows_undo_restores_db(main_window_with_project: MainWindow) -> None:
    win = main_window_with_project
    db = win._db
    store = win._store
    assert db is not None
    assert store is not None
    store.save_character_names(
        [
            {
                "id": "ted",
                "canonical": "TED",
                "names_by_lang": {"en": "Ted"},
            }
        ]
    )
    db.upsert_segments(
        "S01E01",
        "utterance",
        [
            Segment(
                episode_id="S01E01",
                kind="utterance",
                n=0,
                start_char=0,
                end_char=2,
                text="Hi",
                speaker_explicit="TED",
            )
        ],
    )
    win._refresh_preparer()
    win.open_preparer_for_episode("S01E01", source="transcript")
    win.undo_stack.clear()

    table = win.preparer_tab.utterance_table
    win.preparer_tab._apply_table_cell_value(table, 0, 2, "Hello there")
    assert win.preparer_tab.save_current() is True
    segs = db.get_segments_for_episode("S01E01", kind="utterance")
    assert segs[0]["text"] == "Hello there"
    assert store.get_episode_prep_status("S01E01", "transcript") == "edited"

    # Changement hors scope transcript, à préserver lors du undo.
    store.set_episode_prep_status("S01E01", "srt_en", "verified")
    assignments = store.load_character_assignments()
    assignments.append(
        {
            "episode_id": "S01E01",
            "source_type": "cue",
            "source_id": "S01E01:en:999",
            "character_id": "someone_else",
        }
    )
    store.save_character_assignments(assignments)

    win.undo_stack.undo()
    segs = db.get_segments_for_episode("S01E01", kind="utterance")
    assert segs[0]["text"] == "Hi"
    assert store.get_episode_prep_status("S01E01", "transcript") == "raw"
    assert store.get_episode_prep_status("S01E01", "srt_en") == "verified"
    assert any(
        a.get("source_type") == "cue"
        and a.get("source_id") == "S01E01:en:999"
        for a in store.load_character_assignments()
    )
    win.undo_stack.redo()
    segs = db.get_segments_for_episode("S01E01", kind="utterance")
    assert segs[0]["text"] == "Hello there"
    assert store.get_episode_prep_status("S01E01", "transcript") == "edited"
    assert store.get_episode_prep_status("S01E01", "srt_en") == "verified"
    assert any(
        a.get("source_type") == "cue"
        and a.get("source_id") == "S01E01:en:999"
        for a in store.load_character_assignments()
    )
    win.preparer_tab._set_dirty(False)


def test_preparer_save_srt_undo_restores_db_and_file(main_window_with_project: MainWindow) -> None:
    win = main_window_with_project
    db = win._db
    store = win._store
    assert db is not None
    assert store is not None
    db.add_track("S01E01:en", "S01E01", "en", "srt")
    db.upsert_cues(
        "S01E01:en",
        "S01E01",
        "en",
        [
            Cue(
                episode_id="S01E01",
                lang="en",
                n=0,
                start_ms=1000,
                end_ms=1800,
                text_raw="Hi",
                text_clean="Hi",
            )
        ],
    )
    store.save_episode_subtitle_content(
        "S01E01",
        "en",
        "1\n00:00:01,000 --> 00:00:01,800\nHi\n",
        "srt",
    )
    win._refresh_preparer()
    win.open_preparer_for_episode("S01E01", source="srt_en")
    win.undo_stack.clear()

    table = win.preparer_tab.cue_table
    win.preparer_tab._apply_table_cell_value(table, 0, 4, "Ted: Hi")
    assert win.preparer_tab.save_current() is True
    cues = db.get_cues_for_episode_lang("S01E01", "en")
    assert cues[0]["text_clean"] == "Ted: Hi"
    assert store.get_episode_prep_status("S01E01", "srt_en") == "edited"
    content_fmt = store.load_episode_subtitle_content("S01E01", "en")
    assert content_fmt is not None
    assert "Ted: Hi" in content_fmt[0]

    # Changement hors scope srt_en, à préserver lors du undo.
    store.set_episode_prep_status("S01E01", "transcript", "verified")
    assignments = store.load_character_assignments()
    assignments.append(
        {
            "episode_id": "S01E01",
            "source_type": "segment",
            "source_id": "S01E01:utterance:999",
            "character_id": "ted",
        }
    )
    store.save_character_assignments(assignments)

    win.undo_stack.undo()
    cues = db.get_cues_for_episode_lang("S01E01", "en")
    assert cues[0]["text_clean"] == "Hi"
    assert store.get_episode_prep_status("S01E01", "srt_en") == "raw"
    assert store.get_episode_prep_status("S01E01", "transcript") == "verified"
    assert any(
        a.get("source_type") == "segment"
        and a.get("source_id") == "S01E01:utterance:999"
        for a in store.load_character_assignments()
    )
    content_fmt = store.load_episode_subtitle_content("S01E01", "en")
    assert content_fmt is not None
    assert "Ted: Hi" not in content_fmt[0]
    win.undo_stack.redo()
    cues = db.get_cues_for_episode_lang("S01E01", "en")
    assert cues[0]["text_clean"] == "Ted: Hi"
    assert store.get_episode_prep_status("S01E01", "srt_en") == "edited"
    assert store.get_episode_prep_status("S01E01", "transcript") == "verified"
    assert any(
        a.get("source_type") == "segment"
        and a.get("source_id") == "S01E01:utterance:999"
        for a in store.load_character_assignments()
    )
    win.preparer_tab._set_dirty(False)


def test_preparer_save_clean_file_undo_restores_previous_file_state(main_window_with_project: MainWindow) -> None:
    win = main_window_with_project
    store = win._store
    assert store is not None
    win.open_preparer_for_episode("S01E01", source="transcript")
    win.undo_stack.clear()
    if store.has_episode_clean("S01E01"):
        # Garantir un état initial sans clean pour ce test.
        ep_dir = store.root_dir / "episodes" / "S01E01"
        clean_path = ep_dir / "clean.txt"
        if clean_path.exists():
            clean_path.unlink()

    win.preparer_tab.stack.setCurrentWidget(win.preparer_tab.text_editor)
    win.preparer_tab._apply_plain_text_value("Fresh clean text.")
    assert win.preparer_tab.save_current() is True
    assert store.has_episode_clean("S01E01")
    assert store.load_episode_text("S01E01", kind="clean") == "Fresh clean text."
    assert store.get_episode_prep_status("S01E01", "transcript") == "edited"

    win.undo_stack.undo()
    assert not store.has_episode_clean("S01E01")
    assert store.get_episode_prep_status("S01E01", "transcript") == "raw"
    win.undo_stack.redo()
    assert store.has_episode_clean("S01E01")
    assert store.load_episode_text("S01E01", kind="clean") == "Fresh clean text."
    assert store.get_episode_prep_status("S01E01", "transcript") == "edited"
    win.preparer_tab._set_dirty(False)


def test_refresh_tabs_after_job_preserves_preparer_dirty_draft(main_window_with_project: MainWindow) -> None:
    win = main_window_with_project
    store = win._store
    assert store is not None
    store.save_episode_clean(
        "S01E01",
        "Saved text",
        TransformStats(raw_lines=1, clean_lines=1, merges=0, kept_breaks=0, duration_ms=0),
        {"source": "test"},
    )

    win._refresh_preparer(force=True)
    win.open_preparer_for_episode("S01E01", source="transcript")
    win.preparer_tab.text_editor.setPlainText("UNSAVED EDIT")
    assert win.preparer_tab.has_unsaved_changes()
    assert win.preparer_tab.text_editor.toPlainText() == "UNSAVED EDIT"

    win._refresh_tabs_after_job()
    assert win.preparer_tab.has_unsaved_changes()
    assert win.preparer_tab.text_editor.toPlainText() == "UNSAVED EDIT"
    win.preparer_tab._set_dirty(False)


def test_personnages_save_assignments_cues_scoped_by_lang(main_window_with_project: MainWindow) -> None:
    win = main_window_with_project
    store = win._store
    assert store is not None

    store.save_character_assignments(
        [
            {
                "episode_id": "S01E01",
                "source_type": "cue",
                "source_id": "S01E01:en:1",
                "character_id": "ted",
            },
            {
                "episode_id": "S01E01",
                "source_type": "cue",
                "source_id": "S01E01:fr:1",
                "character_id": "barney",
            },
        ]
    )

    win.personnages_tab.refresh()
    idx = win.personnages_tab.personnages_source_combo.findData("cues_fr")
    assert idx >= 0
    win.personnages_tab.personnages_source_combo.setCurrentIndex(idx)

    # Sauvegarde sans lignes modifiées: ne doit purger que le scope FR.
    win.personnages_tab._save_assignments()
    assignments = store.load_character_assignments()
    assert any(a.get("source_id") == "S01E01:en:1" for a in assignments)
    assert not any(a.get("source_id") == "S01E01:fr:1" for a in assignments)


def test_personnages_save_warns_on_character_alias_collision(
    main_window_with_project: MainWindow,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    win = main_window_with_project
    store = win._store
    assert store is not None

    win.personnages_tab.refresh()
    table = win.personnages_tab.personnages_table
    table.setRowCount(2)
    table.setItem(0, 0, QTableWidgetItem("ted"))
    table.setItem(0, 1, QTableWidgetItem("Ted"))
    table.setItem(0, 2, QTableWidgetItem("Ted"))
    table.setItem(0, 3, QTableWidgetItem("Ted"))

    table.setItem(1, 0, QTableWidgetItem("theodore"))
    table.setItem(1, 1, QTableWidgetItem("Theodore"))
    table.setItem(1, 2, QTableWidgetItem("Ted"))  # Collision alias EN
    table.setItem(1, 3, QTableWidgetItem("Théodore"))

    warnings: list[str] = []

    def _fake_warning(*args, **kwargs):
        text = str(args[2]) if len(args) >= 3 else str(kwargs.get("text", ""))
        warnings.append(text)
        return QMessageBox.StandardButton.Ok

    monkeypatch.setattr("howimetyourcorpus.app.tabs.tab_personnages.QMessageBox.warning", _fake_warning)

    win.personnages_tab._save()
    assert any("Catalogue personnages invalide" in w for w in warnings)
    assert store.load_character_names() == []
