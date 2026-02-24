"""Tests UI ciblés pour l'onglet Alignement."""

from __future__ import annotations

import csv
import json
import os
from pathlib import Path
from typing import Any

import pytest
from PySide6.QtWidgets import QApplication, QMessageBox

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from howimetyourcorpus.app.tabs.tab_alignement import AlignmentTabWidget


class _FakeConnection:
    def __init__(self, links: list[dict[str, Any]]) -> None:
        self._links = links

    def __enter__(self) -> "_FakeConnection":
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:  # noqa: ANN001
        return False

    def execute(self, sql: str, params: tuple[Any, ...]) -> None:
        link_id = str(params[0]) if params else ""
        for link in self._links:
            if str(link.get("link_id")) != link_id:
                continue
            if "status = 'accepted'" in sql:
                link["status"] = "accepted"
            elif "status = 'rejected'" in sql:
                link["status"] = "rejected"

    def commit(self) -> None:
        return


class _FakeDB:
    def __init__(self, links: list[dict[str, Any]]):
        self.links = links
        self.deleted_runs: list[str] = []

    def connection(self) -> _FakeConnection:
        return _FakeConnection(self.links)

    def get_align_runs_for_episode(self, episode_id: str) -> list[dict[str, Any]]:  # noqa: ARG002
        return [{"align_run_id": "run1", "created_at": "2026-01-01T00:00:00", "params_json": "{}"}]

    def get_segments_for_episode(self, episode_id: str, kind: str | None = None) -> list[dict[str, Any]]:  # noqa: ARG002
        return [{"segment_id": "S01E01:sentence:0", "text": "Hello"}]

    def get_cues_for_episode_lang(self, episode_id: str, lang: str) -> list[dict[str, Any]]:  # noqa: ARG002
        return [{"cue_id": f"S01E01:{lang}:0", "text_clean": "Hello"}]

    def query_alignment_for_episode(  # noqa: ARG002
        self,
        episode_id: str,
        run_id: str | None = None,
        status_filter: str | None = None,
        min_confidence: float | None = None,
    ) -> list[dict[str, Any]]:
        rows = list(self.links)
        if status_filter:
            rows = [r for r in rows if (r.get("status") or "") == status_filter]
        if min_confidence is not None:
            rows = [r for r in rows if float(r.get("confidence") or 0.0) >= min_confidence]
        return rows

    def get_align_stats_for_run(  # noqa: ARG002
        self,
        episode_id: str,
        run_id: str,
        status_filter: str | None = None,
    ) -> dict[str, Any]:
        rows = self.query_alignment_for_episode(episode_id, run_id=run_id, status_filter=status_filter)
        return {"nb_links": len(rows), "nb_pivot": 0, "nb_target": 0, "avg_confidence": 0.5}

    def delete_align_run(self, run_id: str) -> None:
        self.deleted_runs.append(run_id)


class _FakeStore:
    pass


@pytest.fixture
def qapp() -> QApplication:
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def _build_tab(db: _FakeDB) -> AlignmentTabWidget:
    tab = AlignmentTabWidget(
        get_store=lambda: _FakeStore(),
        get_db=lambda: db,
        run_job=lambda _steps: None,
        undo_stack=None,
    )
    tab.align_episode_combo.blockSignals(True)
    tab.align_run_combo.blockSignals(True)
    tab.align_episode_combo.addItem("S01E01 - Pilot", "S01E01")
    tab.align_run_combo.addItem("run1", "run1")
    tab.align_episode_combo.setCurrentIndex(0)
    tab.align_run_combo.setCurrentIndex(0)
    tab.align_episode_combo.blockSignals(False)
    tab.align_run_combo.blockSignals(False)
    return tab


def test_bulk_accept_updates_only_candidates(
    qapp: QApplication,  # noqa: ARG001
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    db = _FakeDB(
        [
            {"link_id": "l1", "status": "auto", "confidence": 0.90},
            {"link_id": "l2", "status": "auto", "confidence": 0.50},
            {"link_id": "l3", "status": "accepted", "confidence": 0.99},
        ]
    )
    tab = _build_tab(db)
    infos: list[tuple[str, str]] = []
    monkeypatch.setattr("howimetyourcorpus.app.tabs.tab_alignement.confirm_action", lambda *_a, **_k: True)

    def _info(_parent, title: str, message: str):
        infos.append((title, message))
        return QMessageBox.StandardButton.Ok

    monkeypatch.setattr("howimetyourcorpus.app.tabs.tab_alignement.QMessageBox.information", _info)
    tab.bulk_threshold_spin.setValue(80)
    tab._bulk_accept()

    assert db.links[0]["status"] == "accepted"
    assert db.links[1]["status"] == "auto"
    assert db.links[2]["status"] == "accepted"
    assert infos == [("Actions bulk", "1 lien(s) accepté(s).")]


def test_bulk_reject_updates_only_candidates(
    qapp: QApplication,  # noqa: ARG001
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    db = _FakeDB(
        [
            {"link_id": "l1", "status": "auto", "confidence": 0.90},
            {"link_id": "l2", "status": "auto", "confidence": 0.50},
            {"link_id": "l3", "status": "accepted", "confidence": 0.10},
        ]
    )
    tab = _build_tab(db)
    infos: list[tuple[str, str]] = []
    monkeypatch.setattr("howimetyourcorpus.app.tabs.tab_alignement.confirm_action", lambda *_a, **_k: True)

    def _info(_parent, title: str, message: str):
        infos.append((title, message))
        return QMessageBox.StandardButton.Ok

    monkeypatch.setattr("howimetyourcorpus.app.tabs.tab_alignement.QMessageBox.information", _info)
    tab.bulk_threshold_spin.setValue(80)
    tab._bulk_reject()

    assert db.links[0]["status"] == "auto"
    assert db.links[1]["status"] == "rejected"
    assert db.links[2]["status"] == "accepted"
    assert infos == [("Actions bulk", "1 lien(s) rejeté(s).")]


def test_delete_current_run_calls_db_delete(
    qapp: QApplication,  # noqa: ARG001
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    db = _FakeDB(
        [
            {"link_id": "l1", "status": "auto", "confidence": 0.90},
            {"link_id": "l2", "status": "auto", "confidence": 0.50},
        ]
    )
    tab = _build_tab(db)
    monkeypatch.setattr("howimetyourcorpus.app.tabs.tab_alignement.confirm_action", lambda *_a, **_k: True)

    called = {"refresh": 0, "fill": 0}
    monkeypatch.setattr(tab, "refresh", lambda: called.__setitem__("refresh", called["refresh"] + 1))
    monkeypatch.setattr(tab, "_fill_links", lambda: called.__setitem__("fill", called["fill"] + 1))

    tab._delete_current_run()

    assert db.deleted_runs == ["run1"]
    assert called["refresh"] == 1
    assert called["fill"] == 1


def test_export_alignment_csv_writes_rows(
    qapp: QApplication,  # noqa: ARG001
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    db = _FakeDB(
        [
            {
                "link_id": "l1",
                "segment_id": "S01E01:sentence:0",
                "cue_id": "S01E01:en:0",
                "cue_id_target": "S01E01:fr:0",
                "lang": "fr",
                "role": "target",
                "confidence": 0.9,
                "status": "auto",
                "meta": {"k": "v"},
            }
        ]
    )
    tab = _build_tab(db)
    out = tmp_path / "align.csv"
    infos: list[tuple[str, str]] = []
    monkeypatch.setattr(
        "howimetyourcorpus.app.tabs.tab_alignement.QFileDialog.getSaveFileName",
        lambda *_args, **_kwargs: (str(out), "CSV (*.csv)"),
    )

    def _info(_parent, title: str, message: str):
        infos.append((title, message))
        return QMessageBox.StandardButton.Ok

    monkeypatch.setattr("howimetyourcorpus.app.tabs.tab_alignement.QMessageBox.information", _info)
    tab._export_alignment()

    assert out.exists()
    with out.open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.reader(handle))
    assert rows[0][:3] == ["link_id", "segment_id", "cue_id"]
    assert rows[1][0] == "l1"
    assert infos == [("Export", "Alignement exporté : 1 lien(s).")]


def test_export_alignment_jsonl_writes_rows(
    qapp: QApplication,  # noqa: ARG001
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    db = _FakeDB(
        [
            {
                "link_id": "l1",
                "segment_id": "S01E01:sentence:0",
                "cue_id": "S01E01:en:0",
                "cue_id_target": "S01E01:fr:0",
                "lang": "fr",
                "role": "target",
                "confidence": 0.9,
                "status": "auto",
                "meta": {"k": "v"},
            }
        ]
    )
    tab = _build_tab(db)
    out = tmp_path / "align.jsonl"
    monkeypatch.setattr(
        "howimetyourcorpus.app.tabs.tab_alignement.QFileDialog.getSaveFileName",
        lambda *_args, **_kwargs: (str(out), "JSONL (*.jsonl)"),
    )
    monkeypatch.setattr("howimetyourcorpus.app.tabs.tab_alignement.QMessageBox.information", lambda *_a, **_k: None)
    tab._export_alignment()

    assert out.exists()
    payload = [json.loads(line) for line in out.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert payload and payload[0]["link_id"] == "l1"
