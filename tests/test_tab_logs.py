"""Tests ciblés pour l'onglet Logs."""

from pathlib import Path

from howimetyourcorpus.app.tabs.tab_logs import LogsTabWidget


def test_read_tail_lines_returns_last_n_lines(tmp_path: Path) -> None:
    log_path = tmp_path / "app.log"
    log_path.write_text("\n".join(f"line-{i}" for i in range(1, 51)) + "\n", encoding="utf-8")

    tail = LogsTabWidget._read_tail_lines(log_path, 5)

    assert tail == ["line-46", "line-47", "line-48", "line-49", "line-50"]


def test_read_tail_lines_handles_zero_or_missing_file(tmp_path: Path) -> None:
    missing = tmp_path / "missing.log"
    assert LogsTabWidget._read_tail_lines(missing, 10) == []
    assert LogsTabWidget._read_tail_lines(missing, 0) == []
