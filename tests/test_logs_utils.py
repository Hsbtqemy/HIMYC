"""Tests des utilitaires du panneau Logs."""

from __future__ import annotations

from howimetyourcorpus.app.logs_utils import (
    LogEntry,
    extract_episode_id,
    matches_log_filters,
    parse_formatted_log_line,
)


def test_extract_episode_id_returns_canonical_uppercase() -> None:
    assert extract_episode_id("failure on s01e09 while indexing") == "S01E09"


def test_extract_episode_id_returns_none_when_absent() -> None:
    assert extract_episode_id("no episode in this line") is None


def test_matches_log_filters_level_threshold() -> None:
    entry = LogEntry(level="INFO", message="ready", formatted_line="2026 [INFO] ready")
    assert matches_log_filters(entry, level_min="ALL", query="")
    assert matches_log_filters(entry, level_min="INFO", query="")
    assert not matches_log_filters(entry, level_min="WARNING", query="")


def test_matches_log_filters_query_matches_formatted_line_or_message() -> None:
    entry = LogEntry(
        level="ERROR",
        message="Indexing failed for S01E01",
        formatted_line="2026-02-14 [ERROR] failed to index",
    )
    assert matches_log_filters(entry, level_min="ALL", query="S01E01")
    assert matches_log_filters(entry, level_min="ALL", query="failed to index")
    assert not matches_log_filters(entry, level_min="ALL", query="S02E03")


def test_parse_formatted_log_line_extracts_level_and_tail_message() -> None:
    line = "2026-02-14 10:00:00 [WARNING] Indexing failed for S01E01"
    entry = parse_formatted_log_line(line)
    assert entry.level == "WARNING"
    assert entry.message == "Indexing failed for S01E01"
    assert entry.formatted_line == line


def test_parse_formatted_log_line_falls_back_to_info_when_level_missing() -> None:
    line = "custom trace without bracket level"
    entry = parse_formatted_log_line(line)
    assert entry.level == "INFO"
    assert entry.message == line
