#!/usr/bin/env python3
"""Baseline UI/perf reproductible pour Lot 0 (KWIC + Logs + workflow export)."""

from __future__ import annotations

import argparse
import json
import math
import platform
import random
import statistics
import sys
import tempfile
import time
from dataclasses import asdict, dataclass
from datetime import datetime, UTC
from pathlib import Path
from typing import Callable, Any


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from howimetyourcorpus.app.logs_utils import LogEntry, matches_log_filters
from howimetyourcorpus.app.tabs.tab_logs import LogsTabWidget
from howimetyourcorpus.core.export_utils import export_kwic_csv
from howimetyourcorpus.core.models import EpisodeRef
from howimetyourcorpus.core.segment.segmenters import segmenter_sentences
from howimetyourcorpus.core.storage.db import CorpusDB
from howimetyourcorpus.core.subtitles import Cue


@dataclass
class MetricStats:
    count: int
    min_ms: float
    max_ms: float
    mean_ms: float
    p50_ms: float
    p95_ms: float


def _percentile(values: list[float], p: float) -> float:
    if not values:
        return 0.0
    if p <= 0:
        return min(values)
    if p >= 100:
        return max(values)
    ordered = sorted(values)
    pos = (len(ordered) - 1) * (p / 100.0)
    lo = math.floor(pos)
    hi = math.ceil(pos)
    if lo == hi:
        return ordered[lo]
    frac = pos - lo
    return ordered[lo] + (ordered[hi] - ordered[lo]) * frac


def _summarize(samples_ms: list[float]) -> MetricStats:
    return MetricStats(
        count=len(samples_ms),
        min_ms=min(samples_ms) if samples_ms else 0.0,
        max_ms=max(samples_ms) if samples_ms else 0.0,
        mean_ms=statistics.fmean(samples_ms) if samples_ms else 0.0,
        p50_ms=_percentile(samples_ms, 50),
        p95_ms=_percentile(samples_ms, 95),
    )


def _measure(
    fn: Callable[[], Any],
    *,
    repeat: int,
    warmup: int = 2,
) -> tuple[MetricStats, list[float], Any]:
    for _ in range(max(0, warmup)):
        fn()
    samples_ms: list[float] = []
    last_value: Any = None
    for _ in range(max(1, repeat)):
        t0 = time.perf_counter()
        last_value = fn()
        dt_ms = (time.perf_counter() - t0) * 1000.0
        samples_ms.append(dt_ms)
    return _summarize(samples_ms), samples_ms, last_value


def _episode_id(i: int) -> str:
    season = (i // 24) + 1
    episode = (i % 24) + 1
    return f"S{season:02d}E{episode:02d}"


def _build_episode_text(ep_index: int, *, lines_per_episode: int, rng: random.Random) -> str:
    speakers = ("TED", "ROBIN", "MARSHALL", "LILY", "BARNEY")
    actions = (
        "walks into the bar and says this is going to be legendary tonight",
        "argues about sandwiches and then laughs loudly with the group",
        "explains a weird theory while everyone rolls their eyes",
        "checks a message and immediately changes the plan",
        "starts a toast and repeats that the night is legendary for sure",
        "opens the notebook and reads a short dramatic line",
        "asks a direct question and waits in silence",
    )
    lines: list[str] = []
    for line_idx in range(lines_per_episode):
        speaker = speakers[(ep_index + line_idx) % len(speakers)]
        action = actions[(line_idx + ep_index) % len(actions)]
        maybe = " legendary" if (line_idx % 6 == 0 or rng.random() < 0.12) else ""
        line = f"{speaker}: {action}{maybe}."
        lines.append(line)
    return "\n".join(lines)


def _build_log_entries(n: int) -> list[LogEntry]:
    levels = ("DEBUG", "INFO", "WARNING", "ERROR")
    phases = ("fetch", "normalize", "segment", "index", "align", "kwic")
    entries: list[LogEntry] = []
    for i in range(n):
        level = levels[i % len(levels)]
        phase = phases[i % len(phases)]
        eid = _episode_id(i % 120)
        msg = f"{phase} step for {eid}"
        if i % 19 == 0:
            msg += " run failed retry scheduled"
        if i % 13 == 0:
            msg += " debug trace"
        formatted = f"2026-02-14 20:{(i // 60) % 60:02d}:{i % 60:02d},000 [{level}] {msg}"
        entries.append(LogEntry(level=level, message=msg, formatted_line=formatted))
    return entries


def run_baseline(
    *,
    episodes: int,
    lines_per_episode: int,
    cues_per_episode: int,
    log_lines: int,
    repeat: int,
    seed: int,
) -> dict[str, Any]:
    rng = random.Random(seed)
    started = datetime.now(UTC)

    with tempfile.TemporaryDirectory(prefix="himyc_ui_baseline_") as tmp_str:
        tmp = Path(tmp_str)
        db_path = tmp / "corpus.db"
        csv_path = tmp / "kwic_export.csv"
        big_log_path = tmp / "application.log"

        db = CorpusDB(db_path)
        t0_init = time.perf_counter()
        db.init()

        entries_for_index: list[tuple[str, str]] = []
        total_segments = 0
        total_cues = 0

        for i in range(episodes):
            episode_id = _episode_id(i)
            season = (i // 24) + 1
            episode = (i % 24) + 1
            db.upsert_episode(
                EpisodeRef(
                    episode_id=episode_id,
                    season=season,
                    episode=episode,
                    title=f"Episode {episode_id}",
                    url=f"https://example.org/{episode_id}",
                    source_id="subslikescript",
                )
            )

            text = _build_episode_text(i, lines_per_episode=lines_per_episode, rng=rng)
            entries_for_index.append((episode_id, text))

            sentence_segments = segmenter_sentences(text)
            for n, seg in enumerate(sentence_segments):
                seg.episode_id = episode_id
                seg.n = n
            db.upsert_segments(episode_id, "sentence", sentence_segments)
            total_segments += len(sentence_segments)

            track_id = f"{episode_id}:en"
            db.add_track(track_id, episode_id, "en", "srt", source_path=None)
            cues: list[Cue] = []
            for n in range(cues_per_episode):
                start_ms = n * 2100
                end_ms = start_ms + 1700
                text_raw = (
                    f"{episode_id} cue {n} says legendary line"
                    if n % 5 == 0
                    else f"{episode_id} cue {n} neutral dialog"
                )
                cues.append(
                    Cue(
                        episode_id=episode_id,
                        lang="en",
                        n=n,
                        start_ms=start_ms,
                        end_ms=end_ms,
                        text_raw=text_raw,
                        text_clean=text_raw,
                    )
                )
            db.upsert_cues(track_id, episode_id, "en", cues)
            total_cues += len(cues)

        db.index_episodes_text(entries_for_index)
        setup_ms = (time.perf_counter() - t0_init) * 1000.0

        kwic_term = "legendary"
        kwic_limit = 250

        def _kwic_episode() -> int:
            return len(db.query_kwic(kwic_term, limit=kwic_limit, offset=0))

        def _kwic_episode_two_pages() -> int:
            p1 = db.query_kwic(kwic_term, limit=kwic_limit, offset=0)
            p2 = db.query_kwic(kwic_term, limit=kwic_limit, offset=kwic_limit)
            return len(p1) + len(p2)

        def _kwic_segments() -> int:
            return len(db.query_kwic_segments(kwic_term, kind="sentence", limit=kwic_limit, offset=0))

        def _kwic_cues() -> int:
            return len(db.query_kwic_cues(kwic_term, lang="en", limit=kwic_limit, offset=0))

        def _open_project_to_export_kwic() -> int:
            reloaded = CorpusDB(db_path)
            reloaded.ensure_migrated()
            hits = reloaded.query_kwic(kwic_term, limit=kwic_limit, offset=0)
            export_kwic_csv(hits, csv_path)
            return len(hits)

        kwic_episode_stats, _, kwic_episode_hits = _measure(_kwic_episode, repeat=repeat)
        kwic_episode_2p_stats, _, kwic_episode_2p_hits = _measure(_kwic_episode_two_pages, repeat=repeat)
        kwic_segments_stats, _, kwic_segments_hits = _measure(_kwic_segments, repeat=repeat)
        kwic_cues_stats, _, kwic_cues_hits = _measure(_kwic_cues, repeat=repeat)
        workflow_export_stats, _, workflow_export_hits = _measure(_open_project_to_export_kwic, repeat=repeat)

        logs_5k = _build_log_entries(5000)
        logs_10k = _build_log_entries(10000)
        level_min = "INFO"
        query = 'kwic|align -debug "run failed"'

        def _logs_filter_5k() -> int:
            return sum(
                1
                for entry in logs_5k
                if matches_log_filters(entry, level_min=level_min, query=query)
            )

        def _logs_filter_10k() -> int:
            return sum(
                1
                for entry in logs_10k
                if matches_log_filters(entry, level_min=level_min, query=query)
            )

        def _logs_render_10k() -> int:
            text, _count = LogsTabWidget._build_filtered_view_text(
                logs_10k,
                level_min=level_min,
                query=query,
            )
            return len(text)

        logs_filter_5k_stats, _, logs_5k_visible = _measure(_logs_filter_5k, repeat=repeat)
        logs_filter_10k_stats, _, logs_10k_visible = _measure(_logs_filter_10k, repeat=repeat)
        logs_render_10k_stats, _, logs_render_10k_chars = _measure(_logs_render_10k, repeat=repeat)

        big_log_lines = max(log_lines, 50000)
        with big_log_path.open("w", encoding="utf-8") as handle:
            for i in range(big_log_lines):
                level = ("INFO" if i % 10 else "ERROR")
                handle.write(
                    f"2026-02-14 21:{(i // 60) % 60:02d}:{i % 60:02d},000 "
                    f"[{level}] kwic step for {_episode_id(i % 120)}\n"
                )

        def _tail_500() -> int:
            return len(LogsTabWidget._read_tail_lines(big_log_path, 500))

        tail_stats, _, tail_lines = _measure(_tail_500, repeat=repeat)

        finished = datetime.now(UTC)
        return {
            "generated_at_utc": finished.isoformat().replace("+00:00", "Z"),
            "duration_total_ms": round((finished - started).total_seconds() * 1000.0, 3),
            "env": {
                "python": platform.python_version(),
                "platform": platform.platform(),
                "machine": platform.machine(),
            },
            "dataset": {
                "episodes": episodes,
                "lines_per_episode": lines_per_episode,
                "cues_per_episode": cues_per_episode,
                "total_segments_sentence": total_segments,
                "total_cues": total_cues,
                "logs_tail_file_lines": big_log_lines,
                "setup_db_and_index_ms": round(setup_ms, 3),
            },
            "kpis": {
                "kwic_episode_page_ms": asdict(kwic_episode_stats),
                "kwic_episode_two_pages_ms": asdict(kwic_episode_2p_stats),
                "kwic_segments_page_ms": asdict(kwic_segments_stats),
                "kwic_cues_page_ms": asdict(kwic_cues_stats),
                "workflow_open_project_to_export_kwic_ms": asdict(workflow_export_stats),
                "logs_filter_5k_ms": asdict(logs_filter_5k_stats),
                "logs_filter_10k_ms": asdict(logs_filter_10k_stats),
                "logs_render_10k_ms": asdict(logs_render_10k_stats),
                "logs_tail_read_500_ms": asdict(tail_stats),
            },
            "sanity": {
                "kwic_episode_hits_page": kwic_episode_hits,
                "kwic_episode_hits_two_pages": kwic_episode_2p_hits,
                "kwic_segments_hits_page": kwic_segments_hits,
                "kwic_cues_hits_page": kwic_cues_hits,
                "workflow_export_hits": workflow_export_hits,
                "logs_visible_5k": logs_5k_visible,
                "logs_visible_10k": logs_10k_visible,
                "logs_render_10k_chars": logs_render_10k_chars,
                "tail_lines_read": tail_lines,
            },
        }


def _format_line(name: str, stats: dict[str, Any]) -> str:
    return (
        f"- {name}: p50={stats['p50_ms']:.2f} ms, "
        f"p95={stats['p95_ms']:.2f} ms, "
        f"mean={stats['mean_ms']:.2f} ms"
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Mesure baseline UI/perf (KWIC, Logs, workflow export).",
    )
    parser.add_argument("--episodes", type=int, default=96)
    parser.add_argument("--lines-per-episode", type=int, default=180)
    parser.add_argument("--cues-per-episode", type=int, default=120)
    parser.add_argument("--log-lines", type=int, default=80000)
    parser.add_argument("--repeat", type=int, default=15)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument(
        "--output-json",
        type=Path,
        default=Path("artifacts/ui_baseline/baseline_ui_perf.json"),
    )
    args = parser.parse_args()

    result = run_baseline(
        episodes=max(1, args.episodes),
        lines_per_episode=max(10, args.lines_per_episode),
        cues_per_episode=max(10, args.cues_per_episode),
        log_lines=max(1000, args.log_lines),
        repeat=max(3, args.repeat),
        seed=args.seed,
    )

    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"Baseline ecrite: {args.output_json}")
    print(f"Env: {result['env']['platform']} | Python {result['env']['python']}")
    print(f"Dataset: {result['dataset']}")
    print(_format_line("KWIC episodes page", result["kpis"]["kwic_episode_page_ms"]))
    print(_format_line("KWIC episodes 2 pages", result["kpis"]["kwic_episode_two_pages_ms"]))
    print(_format_line("KWIC segments page", result["kpis"]["kwic_segments_page_ms"]))
    print(_format_line("KWIC cues page", result["kpis"]["kwic_cues_page_ms"]))
    print(_format_line("Workflow open->export", result["kpis"]["workflow_open_project_to_export_kwic_ms"]))
    print(_format_line("Logs filter 5k", result["kpis"]["logs_filter_5k_ms"]))
    print(_format_line("Logs filter 10k", result["kpis"]["logs_filter_10k_ms"]))
    print(_format_line("Logs render 10k", result["kpis"]["logs_render_10k_ms"]))
    print(_format_line("Logs tail 500", result["kpis"]["logs_tail_read_500_ms"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
