"""Tâches concrètes du pipeline : FetchIndex, FetchEpisode, Normalize, BuildIndex."""

from __future__ import annotations

import datetime
import logging
import time
from pathlib import Path
from typing import Any, Callable

from corpusstudio.core.adapters.base import AdapterRegistry
from corpusstudio.core.models import EpisodeRef, EpisodeStatus, ProjectConfig, RunMeta, SeriesIndex, TransformStats
from corpusstudio.core.normalize.profiles import get_profile
from corpusstudio.core.pipeline.steps import Step, StepResult
from corpusstudio.core.storage.db import CorpusDB
from corpusstudio.core.storage.project_store import ProjectStore

logger = logging.getLogger(__name__)


class FetchSeriesIndexStep(Step):
    """Récupère la page série, parse, sauvegarde series_index.json."""

    name = "fetch_series_index"

    def __init__(self, series_url: str, user_agent: str | None = None):
        self.series_url = series_url
        self.user_agent = user_agent

    def run(
        self,
        context: dict[str, Any],
        *,
        force: bool = False,
        on_progress: Callable[[str, float, str], None] | None = None,
        on_log: Callable[[str, str], None] | None = None,
    ) -> StepResult:
        store: ProjectStore = context["store"]
        config: ProjectConfig = context["config"]
        adapter = AdapterRegistry.get(config.source_id)
        if not adapter:
            return StepResult(False, f"Adapter not found: {config.source_id}")

        def log(level: str, msg: str):
            if on_log:
                on_log(level, msg)
            getattr(logger, level.lower(), logger.info)(msg)

        if on_progress:
            on_progress(self.name, 0.0, "Discovering episodes...")
        try:
            index = adapter.discover_series(
                self.series_url or config.series_url,
                user_agent=self.user_agent or config.user_agent,
            )
        except Exception as e:
            log("error", str(e))
            return StepResult(False, str(e))
        store.save_series_index(index)
        for ref in index.episodes:
            context.get("db") and context["db"].upsert_episode(ref, EpisodeStatus.NEW.value)
        if on_progress:
            on_progress(self.name, 1.0, f"Found {len(index.episodes)} episodes")
        return StepResult(True, f"Index saved: {len(index.episodes)} episodes", {"series_index": index})


class FetchEpisodeStep(Step):
    """Télécharge une page épisode, extrait raw, sauvegarde (skip si déjà présent sauf force)."""

    name = "fetch_episode"

    def __init__(self, episode_id: str, episode_url: str):
        self.episode_id = episode_id
        self.episode_url = episode_url

    def run(
        self,
        context: dict[str, Any],
        *,
        force: bool = False,
        on_progress: Callable[[str, float, str], None] | None = None,
        on_log: Callable[[str, str], None] | None = None,
    ) -> StepResult:
        store: ProjectStore = context["store"]
        config: ProjectConfig = context["config"]
        db: CorpusDB | None = context.get("db")
        adapter = AdapterRegistry.get(config.source_id)
        if not adapter:
            return StepResult(False, f"Adapter not found: {config.source_id}")
        if not force and store.has_episode_raw(self.episode_id):
            if on_progress:
                on_progress(self.name, 1.0, f"Skip (already fetched): {self.episode_id}")
            if db:
                db.set_episode_status(self.episode_id, EpisodeStatus.FETCHED.value)
            return StepResult(True, f"Already fetched: {self.episode_id}")

        def log(level: str, msg: str):
            if on_log:
                on_log(level, msg)

        if on_progress:
            on_progress(self.name, 0.0, f"Fetching {self.episode_id}...")
        try:
            rate_limit = getattr(context.get("config"), "rate_limit_s", 2.0)
            time.sleep(rate_limit)
            html = adapter.fetch_episode_html(self.episode_url)
            store.save_episode_html(self.episode_id, html)
            raw_text, meta = adapter.parse_episode(html, self.episode_url)
            store.save_episode_raw(self.episode_id, raw_text, meta)
            if db:
                db.set_episode_status(self.episode_id, EpisodeStatus.FETCHED.value)
            if on_progress:
                on_progress(self.name, 1.0, f"Fetched: {self.episode_id}")
            return StepResult(True, f"Fetched: {self.episode_id}", {"meta": meta})
        except Exception as e:
            if db:
                db.set_episode_status(self.episode_id, EpisodeStatus.ERROR.value)
            logger.exception("Fetch episode failed")
            return StepResult(False, str(e))


class NormalizeEpisodeStep(Step):
    """Normalise un épisode (raw -> clean), sauvegarde (skip si clean existe sauf force)."""

    name = "normalize_episode"

    def __init__(self, episode_id: str, profile_id: str):
        self.episode_id = episode_id
        self.profile_id = profile_id

    def run(
        self,
        context: dict[str, Any],
        *,
        force: bool = False,
        on_progress: Callable[[str, float, str], None] | None = None,
        on_log: Callable[[str, str], None] | None = None,
    ) -> StepResult:
        store: ProjectStore = context["store"]
        db: CorpusDB | None = context.get("db")
        profile = get_profile(self.profile_id)
        if not profile:
            return StepResult(False, f"Profile not found: {self.profile_id}")
        if not force and store.has_episode_clean(self.episode_id):
            if on_progress:
                on_progress(self.name, 1.0, f"Skip (already normalized): {self.episode_id}")
            if db:
                db.set_episode_status(self.episode_id, EpisodeStatus.NORMALIZED.value)
            return StepResult(True, f"Already normalized: {self.episode_id}")
        raw = store.load_episode_text(self.episode_id, kind="raw")
        if not raw.strip():
            return StepResult(False, f"No raw text: {self.episode_id}")
        if on_progress:
            on_progress(self.name, 0.5, f"Normalizing {self.episode_id}...")
        clean_text, stats, debug = profile.apply(raw)
        store.save_episode_clean(self.episode_id, clean_text, stats, debug)
        if db:
            db.set_episode_status(self.episode_id, EpisodeStatus.NORMALIZED.value)
        if on_progress:
            on_progress(self.name, 1.0, f"Normalized: {self.episode_id}")
        return StepResult(True, f"Normalized: {self.episode_id}", {"stats": stats, "debug": debug})


class BuildDbIndexStep(Step):
    """Indexe les épisodes normalisés dans la DB (FTS). Skip si déjà indexé sauf force."""

    name = "build_db_index"

    def __init__(self, episode_ids: list[str] | None = None):
        """Si episode_ids is None, indexe tous les épisodes ayant clean.txt."""
        self.episode_ids = episode_ids

    def run(
        self,
        context: dict[str, Any],
        *,
        force: bool = False,
        on_progress: Callable[[str, float, str], None] | None = None,
        on_log: Callable[[str, str], None] | None = None,
    ) -> StepResult:
        store: ProjectStore = context["store"]
        db: CorpusDB = context["db"]
        if not db:
            return StepResult(False, "No DB in context")
        to_index: list[str] = []
        if self.episode_ids is not None:
            to_index = [eid for eid in self.episode_ids if store.has_episode_clean(eid)]
        else:
            index = store.load_series_index()
            if index:
                to_index = [e.episode_id for e in index.episodes if store.has_episode_clean(e.episode_id)]
            else:
                # Parcourir episodes/
                for d in (store.root_dir / "episodes").iterdir():
                    if d.is_dir() and (d / "clean.txt").exists():
                        to_index.append(d.name)
        n = len(to_index)
        for i, eid in enumerate(to_index):
            if not force and eid in db.get_episode_ids_indexed():
                continue
            clean = store.load_episode_text(eid, kind="clean")
            if clean:
                db.index_episode_text(eid, clean)
            if on_progress and n:
                on_progress(self.name, (i + 1) / n, f"Indexed {eid}")
        if on_progress:
            on_progress(self.name, 1.0, f"Indexed {len(to_index)} episodes")
        return StepResult(True, f"Indexed {len(to_index)} episodes")
