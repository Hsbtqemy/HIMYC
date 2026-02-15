"""Tests du contrat d'état global job (idle/running/cancelling/done/error)."""

import pytest

pytest.importorskip("PySide6.QtWidgets", reason="Runtime Qt non disponible")

from howimetyourcorpus.app import ui_mainwindow as mw


def test_job_state_transition_contract() -> None:
    is_valid = mw.MainWindow._is_valid_job_state_transition
    assert is_valid(mw._JOB_STATE_IDLE, mw._JOB_STATE_RUNNING)
    assert is_valid(mw._JOB_STATE_RUNNING, mw._JOB_STATE_CANCELLING)
    assert is_valid(mw._JOB_STATE_RUNNING, mw._JOB_STATE_DONE)
    assert is_valid(mw._JOB_STATE_RUNNING, mw._JOB_STATE_ERROR)
    assert is_valid(mw._JOB_STATE_CANCELLING, mw._JOB_STATE_DONE)
    assert is_valid(mw._JOB_STATE_CANCELLING, mw._JOB_STATE_ERROR)
    assert is_valid(mw._JOB_STATE_DONE, mw._JOB_STATE_IDLE)
    assert is_valid(mw._JOB_STATE_ERROR, mw._JOB_STATE_IDLE)
    assert not is_valid(mw._JOB_STATE_IDLE, mw._JOB_STATE_DONE)
    assert not is_valid(mw._JOB_STATE_IDLE, mw._JOB_STATE_ERROR)
    assert not is_valid(mw._JOB_STATE_IDLE, mw._JOB_STATE_CANCELLING)


def test_normalize_job_state_fallbacks_to_idle() -> None:
    normalize = mw.MainWindow._normalize_job_state
    assert normalize("RUNNING") == mw._JOB_STATE_RUNNING
    assert normalize(" cancelling ") == mw._JOB_STATE_CANCELLING
    assert normalize("unknown-state") == mw._JOB_STATE_IDLE
    assert normalize("") == mw._JOB_STATE_IDLE


def test_resolve_search_focus_tab_prefers_logs_only_when_active() -> None:
    resolve = mw.MainWindow._resolve_search_focus_tab
    assert resolve(mw.TAB_LOGS) == mw.TAB_LOGS
    assert resolve(mw.TAB_CONCORDANCE) == mw.TAB_CONCORDANCE
    assert resolve(mw.TAB_PILOTAGE) == mw.TAB_CONCORDANCE
