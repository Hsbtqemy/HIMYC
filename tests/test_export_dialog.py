"""Tests unitaires des helpers de résolution d'export UI."""

from pathlib import Path

from howimetyourcorpus.app.export_dialog import normalize_export_path, resolve_export_key


def test_normalize_export_path_keeps_known_suffix() -> None:
    path = normalize_export_path(
        Path("/tmp/resultats.tsv"),
        "CSV (*.csv)",
        allowed_suffixes=(".csv", ".tsv"),
        default_suffix=".csv",
        filter_to_suffix={"CSV": ".csv", "TSV": ".tsv"},
    )
    assert path.suffix == ".tsv"


def test_normalize_export_path_uses_filter_when_missing_suffix() -> None:
    path = normalize_export_path(
        Path("/tmp/resultats"),
        "Word (*.docx)",
        allowed_suffixes=(".csv", ".docx"),
        default_suffix=".csv",
        filter_to_suffix={"WORD": ".docx"},
    )
    assert path.suffix == ".docx"


def test_normalize_export_path_prefers_more_specific_filter_tokens() -> None:
    path = normalize_export_path(
        Path("/tmp/resultats"),
        "JSONL (*.jsonl)",
        allowed_suffixes=(".json", ".jsonl"),
        default_suffix=".json",
        filter_to_suffix={"JSON": ".json", "JSONL": ".jsonl"},
    )
    assert path.suffix == ".jsonl"


def test_normalize_export_path_uses_default_when_unknown() -> None:
    path = normalize_export_path(
        Path("/tmp/resultats.abc"),
        "",
        allowed_suffixes=(".csv", ".json"),
        default_suffix=".csv",
    )
    assert path.suffix == ".csv"


def test_resolve_export_key_prefers_suffix() -> None:
    key = resolve_export_key(
        Path("/tmp/resultats.json"),
        "CSV (*.csv)",
        suffix_to_key={".csv": "csv", ".json": "json"},
        filter_to_key={"CSV": "csv"},
        default_key="csv",
    )
    assert key == "json"


def test_resolve_export_key_uses_filter_then_default() -> None:
    key_from_filter = resolve_export_key(
        Path("/tmp/resultats.unknown"),
        "JSONL (*.jsonl)",
        suffix_to_key={".csv": "csv", ".jsonl": "jsonl"},
        filter_to_key={"JSONL": "jsonl"},
        default_key="csv",
    )
    key_default = resolve_export_key(
        Path("/tmp/resultats.unknown"),
        "",
        suffix_to_key={".csv": "csv", ".jsonl": "jsonl"},
        filter_to_key={"JSONL": "jsonl"},
        default_key="csv",
    )
    assert key_from_filter == "jsonl"
    assert key_default == "csv"
