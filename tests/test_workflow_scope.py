"""Tests for workflow scope resolution."""

from __future__ import annotations

import pytest

from howimetyourcorpus.core.models import EpisodeRef
from howimetyourcorpus.core.workflow.contracts import WorkflowScope, WorkflowScopeError
from howimetyourcorpus.core.workflow.scope import ScopeResolver


@pytest.fixture
def episode_refs() -> list[EpisodeRef]:
    return [
        EpisodeRef("S01E01", season=1, episode=1, title="Pilot", url="u1"),
        EpisodeRef("S01E02", season=1, episode=2, title="Purple", url="u2"),
        EpisodeRef("S02E01", season=2, episode=1, title="New", url="u3"),
    ]


def test_scope_all_keeps_order(episode_refs: list[EpisodeRef]) -> None:
    ids = ScopeResolver.resolve_episode_ids(WorkflowScope.all(), episode_refs)
    assert ids == ["S01E01", "S01E02", "S02E01"]


def test_scope_selection_deduplicates_and_filters_unknown(episode_refs: list[EpisodeRef]) -> None:
    scope = WorkflowScope.selection(["S01E02", "S01E02", "S99E99", "S01E01"])
    ids = ScopeResolver.resolve_episode_ids(scope, episode_refs)
    assert ids == ["S01E02", "S01E01"]


def test_scope_season_filters_refs(episode_refs: list[EpisodeRef]) -> None:
    ids = ScopeResolver.resolve_episode_ids(WorkflowScope.season_scope(2), episode_refs)
    assert ids == ["S02E01"]


def test_scope_current_requires_known_episode(episode_refs: list[EpisodeRef]) -> None:
    with pytest.raises(WorkflowScopeError):
        ScopeResolver.resolve_episode_ids(WorkflowScope.current("S09E09"), episode_refs)
