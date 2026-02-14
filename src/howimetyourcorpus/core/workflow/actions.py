"""Declarative workflow action catalog."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Mapping

from howimetyourcorpus.core.pipeline.context import PipelineContext
from howimetyourcorpus.core.pipeline.steps import Step
from howimetyourcorpus.core.pipeline.tasks import (
    BuildDbIndexStep,
    FetchEpisodeStep,
    NormalizeEpisodeStep,
    SegmentEpisodeStep,
)
from howimetyourcorpus.core.workflow.contracts import WorkflowActionId, WorkflowOptionError

BuildStepsFn = Callable[[PipelineContext, list[str], Mapping[str, Any]], list[Step]]


@dataclass(frozen=True)
class WorkflowActionSpec:
    """Specification for one workflow action."""

    action_id: WorkflowActionId
    label: str
    build_steps: BuildStepsFn


def _build_fetch_steps(
    context: PipelineContext,
    episode_ids: list[str],
    options: Mapping[str, Any],
) -> list[Step]:
    if not episode_ids:
        return []
    raw_map = options.get("episode_url_by_id")
    if not isinstance(raw_map, Mapping):
        raise WorkflowOptionError("fetch_episodes requires `episode_url_by_id` mapping")
    steps: list[Step] = []
    for eid in episode_ids:
        url = raw_map.get(eid)
        if isinstance(url, str) and url.strip():
            steps.append(FetchEpisodeStep(eid, url.strip()))
    return steps


def _build_normalize_steps(
    context: PipelineContext,
    episode_ids: list[str],
    options: Mapping[str, Any],
) -> list[Step]:
    if not episode_ids:
        return []
    default_profile = str(options.get("default_profile_id") or "default_en_v1")
    profile_by_episode = options.get("profile_by_episode")
    if profile_by_episode is None:
        profile_by_episode = {}
    if not isinstance(profile_by_episode, Mapping):
        raise WorkflowOptionError("normalize_episodes `profile_by_episode` must be a mapping")

    steps: list[Step] = []
    for eid in episode_ids:
        profile = profile_by_episode.get(eid)
        if not isinstance(profile, str) or not profile.strip():
            profile = default_profile
        steps.append(NormalizeEpisodeStep(eid, profile.strip()))
    return steps


def _build_segment_steps(
    context: PipelineContext,
    episode_ids: list[str],
    options: Mapping[str, Any],
) -> list[Step]:
    if not episode_ids:
        return []
    lang_hint = str(options.get("lang_hint") or "en")
    return [SegmentEpisodeStep(eid, lang_hint=lang_hint) for eid in episode_ids]


def _build_index_steps(
    context: PipelineContext,
    episode_ids: list[str],
    options: Mapping[str, Any],
) -> list[Step]:
    if episode_ids:
        return [BuildDbIndexStep(episode_ids=episode_ids)]
    # Fallback global indexation: keeps historical behavior when no series index
    # is available but clean.txt files exist in episodes/.
    if bool(options.get("allow_all_with_clean")):
        return [BuildDbIndexStep()]
    return []


ACTION_CATALOG: dict[WorkflowActionId, WorkflowActionSpec] = {
    WorkflowActionId.FETCH_EPISODES: WorkflowActionSpec(
        action_id=WorkflowActionId.FETCH_EPISODES,
        label="Télécharger épisodes",
        build_steps=_build_fetch_steps,
    ),
    WorkflowActionId.NORMALIZE_EPISODES: WorkflowActionSpec(
        action_id=WorkflowActionId.NORMALIZE_EPISODES,
        label="Normaliser épisodes",
        build_steps=_build_normalize_steps,
    ),
    WorkflowActionId.SEGMENT_EPISODES: WorkflowActionSpec(
        action_id=WorkflowActionId.SEGMENT_EPISODES,
        label="Segmenter épisodes",
        build_steps=_build_segment_steps,
    ),
    WorkflowActionId.BUILD_DB_INDEX: WorkflowActionSpec(
        action_id=WorkflowActionId.BUILD_DB_INDEX,
        label="Indexer épisodes",
        build_steps=_build_index_steps,
    ),
}
