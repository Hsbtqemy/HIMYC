"""Tests des utilitaires du panneau Logs."""

from __future__ import annotations

from howimetyourcorpus.app.logs_utils import (
    build_logs_diagnostic_report,
    decode_custom_logs_presets,
    encode_custom_logs_presets,
    LogEntry,
    LOGS_BUILTIN_PRESETS,
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


def test_matches_log_filters_query_supports_and_expression() -> None:
    entry = LogEntry(
        level="ERROR",
        message="Indexing failed for S01E01",
        formatted_line="2026-02-14 [ERROR] failed to index",
    )
    assert matches_log_filters(entry, level_min="ALL", query="failed S01E01")
    assert not matches_log_filters(entry, level_min="ALL", query="failed S02E02")


def test_matches_log_filters_query_supports_exclusion_tokens() -> None:
    entry = LogEntry(
        level="INFO",
        message="fetch episode S01E01",
        formatted_line="2026 [INFO] fetch episode S01E01",
    )
    assert matches_log_filters(entry, level_min="ALL", query="fetch -error")
    assert not matches_log_filters(entry, level_min="ALL", query="fetch -S01E01")


def test_matches_log_filters_query_supports_or_tokens_and_quotes() -> None:
    entry = LogEntry(
        level="WARNING",
        message="align run failed for S01E02",
        formatted_line="2026 [WARNING] align run failed for S01E02",
    )
    assert matches_log_filters(entry, level_min="ALL", query="align|kwic")
    assert matches_log_filters(entry, level_min="ALL", query='"run failed" S01E02')
    assert not matches_log_filters(entry, level_min="ALL", query="kwic|concordance")


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


def test_build_logs_diagnostic_report_contains_core_fields() -> None:
    report = build_logs_diagnostic_report(
        selected_line="2026 [ERROR] Failed S01E02",
        episode_id="S01E02",
        preset_label="Erreurs (ERROR+)",
        level_filter="ERROR",
        query="index",
        recent_lines=[
            "2026 [INFO] start",
            "2026 [ERROR] Failed S01E02",
        ],
    )
    assert "HowIMetYourCorpus - Diagnostic logs" in report
    assert "Preset: Erreurs (ERROR+)" in report
    assert "Niveau min: ERROR" in report
    assert "Épisode détecté: S01E02" in report
    assert "- 2026 [ERROR] Failed S01E02" in report


def test_build_logs_diagnostic_report_handles_empty_recent_lines() -> None:
    report = build_logs_diagnostic_report(
        selected_line="line",
        episode_id=None,
        preset_label="Personnalisé",
        level_filter="ALL",
        query="",
        recent_lines=[],
    )
    assert "Épisode détecté: —" in report
    assert "Recherche: —" in report
    assert "Dernières lignes pertinentes:" in report
    assert "- —" in report


def test_decode_custom_logs_presets_filters_invalid_and_reserved_labels() -> None:
    payload = [
        {"label": " Mes erreurs ", "level": "error", "query": "failed"},
        {"label": "Tous", "level": "WARNING", "query": "ignored"},
        {"label": "", "level": "INFO", "query": "ignored"},
        {"label": "Mes erreurs", "level": "INFO", "query": "duplicate"},
        {"label": "Scope QA", "level": "TRACE", "query": "scope"},
        "bad-shape",
    ]
    presets = decode_custom_logs_presets(
        payload,
        reserved_labels=[label for label, _level, _query in LOGS_BUILTIN_PRESETS],
    )
    assert presets == [
        ("Mes erreurs", "ERROR", "failed"),
        ("Scope QA", "ALL", "scope"),
    ]


def test_decode_custom_logs_presets_accepts_json_string_payload() -> None:
    raw = '[{"label":"Build","level":"warning","query":"run failed"}]'
    assert decode_custom_logs_presets(raw) == [("Build", "WARNING", "run failed")]


def test_encode_custom_logs_presets_returns_deduplicated_json() -> None:
    encoded = encode_custom_logs_presets(
        [
            ("  QA ", "warning", "index"),
            ("QA", "ERROR", "duplicate"),
            ("Broken", "TRACE", "step"),
            ("", "INFO", "ignored"),
        ]
    )
    assert encoded == (
        '[{"label": "QA", "level": "WARNING", "query": "index"}, '
        '{"label": "Broken", "level": "ALL", "query": "step"}]'
    )
