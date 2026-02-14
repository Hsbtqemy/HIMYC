"""Tests de décision de prochaine action workflow (Pilotage)."""

from howimetyourcorpus.app.workflow_advice import (
    WorkflowStatusCounts,
    build_workflow_advice,
)


def _counts(**kwargs) -> WorkflowStatusCounts:
    defaults = dict(
        n_total=10,
        n_fetched=0,
        n_norm=0,
        n_segmented=0,
        n_indexed=0,
        n_error=0,
        n_with_srt=0,
        n_aligned=0,
    )
    defaults.update(kwargs)
    return WorkflowStatusCounts(**defaults)


def test_advice_prioritizes_errors_first() -> None:
    advice = build_workflow_advice(_counts(n_error=2, n_fetched=5, n_with_srt=3))
    assert advice.action_id == "retry_errors"


def test_advice_detects_srt_first_mode() -> None:
    advice = build_workflow_advice(_counts(n_total=4, n_with_srt=4))
    assert advice.action_id == "open_concordance_cues"


def test_advice_fetch_all_when_missing_fetch() -> None:
    advice = build_workflow_advice(_counts(n_total=10, n_fetched=8))
    assert advice.action_id == "fetch_all"


def test_advice_normalize_all_when_missing_norm() -> None:
    advice = build_workflow_advice(_counts(n_total=10, n_fetched=10, n_norm=7))
    assert advice.action_id == "normalize_all"


def test_advice_segment_and_index_when_missing_segments() -> None:
    advice = build_workflow_advice(_counts(n_total=10, n_fetched=10, n_norm=10, n_segmented=6, n_indexed=6))
    assert advice.action_id == "segment_and_index"


def test_advice_index_all_when_missing_index() -> None:
    advice = build_workflow_advice(_counts(n_total=10, n_fetched=10, n_norm=10, n_segmented=10, n_indexed=8))
    assert advice.action_id == "index_all"


def test_advice_import_srt_when_no_tracks() -> None:
    advice = build_workflow_advice(_counts(n_total=10, n_fetched=10, n_norm=10, n_segmented=10, n_indexed=10))
    assert advice.action_id == "open_inspector_srt"


def test_advice_open_validation_when_not_aligned() -> None:
    advice = build_workflow_advice(
        _counts(n_total=10, n_fetched=10, n_norm=10, n_segmented=10, n_indexed=10, n_with_srt=10, n_aligned=7)
    )
    assert advice.action_id == "open_validation_alignment"


def test_advice_done_when_all_ready() -> None:
    advice = build_workflow_advice(
        _counts(n_total=10, n_fetched=10, n_norm=10, n_segmented=10, n_indexed=10, n_with_srt=10, n_aligned=10)
    )
    assert advice.action_id == "done"
