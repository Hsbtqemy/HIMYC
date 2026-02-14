"""Tests CorpusDB : init, index, requête KWIC."""

import pytest
from pathlib import Path
import tempfile

from howimetyourcorpus.core.storage.db import CorpusDB, KwicHit
from howimetyourcorpus.core.models import EpisodeRef, EpisodeStatus


@pytest.fixture
def db_path():
    with tempfile.TemporaryDirectory() as d:
        yield Path(d) / "corpus.db"


@pytest.fixture
def db(db_path):
    c = CorpusDB(db_path)
    c.init()
    return c


def test_db_init(db_path):
    db = CorpusDB(db_path)
    db.init()
    assert db_path.exists()


def test_upsert_episode_and_index(db):
    ref = EpisodeRef(
        episode_id="S01E01",
        season=1,
        episode=1,
        title="Pilot",
        url="https://example.com/s01e01",
    )
    db.upsert_episode(ref, EpisodeStatus.FETCHED.value)
    db.index_episode_text(
        "S01E01",
        "Ted: So this is the story of how I met your mother. Marshall: Legendary.",
    )
    ids = db.get_episode_ids_indexed()
    assert "S01E01" in ids


def test_get_episode_statuses_returns_db_status_map(db):
    ref = EpisodeRef(
        episode_id="S09E09",
        season=9,
        episode=9,
        title="Finale",
        url="https://example.com/s09e09",
    )
    db.upsert_episode(ref, status=EpisodeStatus.ERROR.value)
    statuses = db.get_episode_statuses(["S09E09", "S99E99"])
    assert statuses.get("S09E09") == EpisodeStatus.ERROR.value
    assert "S99E99" not in statuses


def test_db_kwic(db):
    """Indexer un texte, requêter KWIC, vérifier left/match/right."""
    ref = EpisodeRef(
        episode_id="S01E02",
        season=1,
        episode=2,
        title="Purple Giraffe",
        url="https://example.com/s01e02",
    )
    db.upsert_episode(ref)
    text = (
        "Barney said the word legendary many times. "
        "Legendary is his favorite word. So legendary."
    )
    db.index_episode_text("S01E02", text)
    hits = db.query_kwic("legendary", window=20, limit=10)
    assert len(hits) >= 2
    for h in hits:
        assert isinstance(h, KwicHit)
        assert h.episode_id == "S01E02"
        assert h.match.lower() == "legendary"
        assert "legendary" in (h.left + h.match + h.right).lower()
        assert h.title == "Purple Giraffe"


def test_upsert_segments_and_query_kwic_segments(db):
    """Phase 2 : upsert segments, query_kwic_segments, segment_id/kind présents."""
    ref = EpisodeRef(
        episode_id="S01E03",
        season=1,
        episode=3,
        title="Sweet Taste of Liberty",
        url="https://example.com/s01e03",
    )
    db.upsert_episode(ref)
    from howimetyourcorpus.core.segment import segmenter_sentences

    text = "Barney says legendary. Marshall says okay."
    segments = segmenter_sentences(text, "en")
    for s in segments:
        s.episode_id = "S01E03"
    db.upsert_segments("S01E03", "sentence", segments)
    hits = db.query_kwic_segments("legendary", kind="sentence", limit=10)
    assert len(hits) >= 1
    for h in hits:
        assert h.episode_id == "S01E03"
        assert h.segment_id is not None
        assert h.kind == "sentence"
        assert h.match.lower() == "legendary"


def test_get_episode_ids_with_segments(db):
    """Retourne les épisodes réellement segmentés (filtrables par kind)."""
    from howimetyourcorpus.core.segment import Segment

    ref1 = EpisodeRef(
        episode_id="S01E03A",
        season=1,
        episode=30,
        title="Seg A",
        url="https://example.com/s01e03a",
    )
    ref2 = EpisodeRef(
        episode_id="S01E03B",
        season=1,
        episode=31,
        title="Seg B",
        url="https://example.com/s01e03b",
    )
    db.upsert_episode(ref1)
    db.upsert_episode(ref2)

    db.upsert_segments(
        "S01E03A",
        "sentence",
        [Segment(episode_id="S01E03A", kind="sentence", n=0, start_char=0, end_char=5, text="Hello")],
    )
    db.upsert_segments(
        "S01E03A",
        "utterance",
        [Segment(episode_id="S01E03A", kind="utterance", n=0, start_char=0, end_char=5, text="Hello")],
    )
    db.upsert_segments(
        "S01E03B",
        "utterance",
        [Segment(episode_id="S01E03B", kind="utterance", n=0, start_char=0, end_char=7, text="General")],
    )

    assert db.get_episode_ids_with_segments(kind="sentence") == ["S01E03A"]
    assert db.get_episode_ids_with_segments(kind="utterance") == ["S01E03A", "S01E03B"]
    assert db.get_episode_ids_with_segments() == ["S01E03A", "S01E03B"]


def test_upsert_cues_and_query_kwic_cues(db):
    """Phase 3 : add_track, upsert_cues, query_kwic_cues (cue_id, lang)."""
    ref = EpisodeRef(
        episode_id="S01E05",
        season=1,
        episode=5,
        title="Okay Awesome",
        url="https://example.com/s01e05",
    )
    db.upsert_episode(ref)
    from howimetyourcorpus.core.subtitles import Cue, parse_srt

    content = """1
00:00:01,000 --> 00:00:03,000
Legendary word.
"""
    cues = parse_srt(content)
    for c in cues:
        c.episode_id = "S01E05"
        c.lang = "en"
    db.add_track("S01E05:en", "S01E05", "en", "srt", None, None, None)
    db.upsert_cues("S01E05:en", "S01E05", "en", cues)
    hits = db.query_kwic_cues("Legendary", lang="en", limit=10)
    assert len(hits) >= 1
    assert hits[0].episode_id == "S01E05"
    assert hits[0].cue_id is not None
    assert hits[0].lang == "en"


def test_align_run_and_links(db):
    """Phase 4 : create_align_run, upsert_align_links, query_alignment_for_episode."""
    ref = EpisodeRef(
        episode_id="S01E06",
        season=1,
        episode=6,
        title="Slutty Pumpkin",
        url="https://example.com/s01e06",
    )
    db.upsert_episode(ref)
    run_id = "S01E06:align:20250212T120000Z"
    db.create_align_run(run_id, "S01E06", "en", None, "2025-02-12T12:00:00Z", "{}")
    links = [
        {"segment_id": "S01E06:sentence:0", "cue_id": "S01E06:en:0", "lang": "en", "role": "pivot", "confidence": 0.85, "status": "auto", "meta": {}},
    ]
    db.upsert_align_links(run_id, "S01E06", links)
    runs = db.get_align_runs_for_episode("S01E06")
    assert len(runs) == 1
    assert runs[0]["align_run_id"] == run_id
    result = db.query_alignment_for_episode("S01E06", run_id=run_id)
    assert len(result) == 1
    assert result[0]["segment_id"] == "S01E06:sentence:0"
    assert result[0]["confidence"] == 0.85
    db.set_align_status(result[0]["link_id"], "accepted")
    result2 = db.query_alignment_for_episode("S01E06", run_id=run_id, status_filter="accepted")
    assert len(result2) == 1


def test_align_stats_and_parallel_concordance(db):
    """Phase 5 : get_align_stats_for_run, get_parallel_concordance."""
    from howimetyourcorpus.core.segment import Segment
    from howimetyourcorpus.core.subtitles import Cue

    ref = EpisodeRef(
        episode_id="S01E07",
        season=1,
        episode=7,
        title="Matchmaker",
        url="https://example.com/s01e07",
    )
    db.upsert_episode(ref)
    run_id = "S01E07:align:20250212T130000Z"
    db.create_align_run(run_id, "S01E07", "en", None, "2025-02-12T13:00:00Z", "{}")

    seg = Segment(episode_id="S01E07", kind="sentence", n=0, start_char=0, end_char=11, text="Hello world")
    db.upsert_segments("S01E07", "sentence", [seg])

    db.add_track("S01E07:en", "S01E07", "en", "srt")
    db.add_track("S01E07:fr", "S01E07", "fr", "srt")
    cue_en = Cue(episode_id="S01E07", lang="en", n=0, start_ms=0, end_ms=2000, text_raw="Hello world", text_clean="Hello world")
    cue_fr = Cue(episode_id="S01E07", lang="fr", n=0, start_ms=0, end_ms=2000, text_raw="Bonjour le monde", text_clean="Bonjour le monde")
    db.upsert_cues("S01E07:en", "S01E07", "en", [cue_en])
    db.upsert_cues("S01E07:fr", "S01E07", "fr", [cue_fr])

    links = [
        {"segment_id": "S01E07:sentence:0", "cue_id": "S01E07:en:0", "lang": "en", "role": "pivot", "confidence": 0.9, "status": "auto", "meta": {}},
        {"cue_id": "S01E07:en:0", "cue_id_target": "S01E07:fr:0", "lang": "fr", "role": "target", "confidence": 1.0, "status": "auto", "meta": {}},
    ]
    db.upsert_align_links(run_id, "S01E07", links)

    stats = db.get_align_stats_for_run("S01E07", run_id)
    assert stats["nb_links"] == 2
    assert stats["nb_pivot"] == 1
    assert stats["nb_target"] == 1
    assert stats["avg_confidence"] is not None

    rows = db.get_parallel_concordance("S01E07", run_id)
    assert len(rows) == 1
    assert rows[0]["segment_id"] == "S01E07:sentence:0"
    assert rows[0]["text_segment"] == "Hello world"
    assert rows[0]["text_en"] == "Hello world"
    assert rows[0]["text_fr"] == "Bonjour le monde"
    assert rows[0]["confidence_pivot"] == 0.9
    assert rows[0]["confidence_fr"] == 1.0


def test_parallel_concordance_uses_actual_target_lang(db):
    """Le concordancier parallèle expose les colonnes de la langue cible réellement alignée."""
    from howimetyourcorpus.core.segment import Segment
    from howimetyourcorpus.core.subtitles import Cue

    ref = EpisodeRef(
        episode_id="S01E08",
        season=1,
        episode=8,
        title="The Duel",
        url="https://example.com/s01e08",
    )
    db.upsert_episode(ref)
    run_id = "S01E08:align:20250212T131500Z"
    db.create_align_run(run_id, "S01E08", "en", None, "2025-02-12T13:15:00Z", "{}")

    seg = Segment(episode_id="S01E08", kind="sentence", n=0, start_char=0, end_char=7, text="Hi all")
    db.upsert_segments("S01E08", "sentence", [seg])

    db.add_track("S01E08:en", "S01E08", "en", "srt")
    db.add_track("S01E08:it", "S01E08", "it", "srt")
    cue_en = Cue(episode_id="S01E08", lang="en", n=0, start_ms=0, end_ms=2000, text_raw="Hi all", text_clean="Hi all")
    cue_it = Cue(episode_id="S01E08", lang="it", n=0, start_ms=0, end_ms=2000, text_raw="Ciao a tutti", text_clean="Ciao a tutti")
    db.upsert_cues("S01E08:en", "S01E08", "en", [cue_en])
    db.upsert_cues("S01E08:it", "S01E08", "it", [cue_it])

    links = [
        {"segment_id": "S01E08:sentence:0", "cue_id": "S01E08:en:0", "lang": "en", "role": "pivot", "confidence": 0.8, "status": "auto", "meta": {}},
        {"cue_id": "S01E08:en:0", "cue_id_target": "S01E08:it:0", "lang": "it", "role": "target", "confidence": 0.95, "status": "auto", "meta": {}},
    ]
    db.upsert_align_links(run_id, "S01E08", links)

    rows = db.get_parallel_concordance("S01E08", run_id)
    assert len(rows) == 1
    assert rows[0]["text_it"] == "Ciao a tutti"
    assert rows[0]["confidence_it"] == 0.95
    assert rows[0].get("text_fr", "") == ""


def test_align_stats_avg_confidence_aggregates_per_row(db):
    """Moyenne de confiance exacte même quand plusieurs liens partagent role+status."""
    ref = EpisodeRef(
        episode_id="S01E10",
        season=1,
        episode=10,
        title="Pineapple Incident",
        url="https://example.com/s01e10",
    )
    db.upsert_episode(ref)
    run_id = "S01E10:align:20250212T150000Z"
    db.create_align_run(run_id, "S01E10", "en", None, "2025-02-12T15:00:00Z", "{}")
    links = [
        {"segment_id": "S01E10:sentence:0", "cue_id": "S01E10:en:0", "lang": "en", "role": "pivot", "confidence": 0.1, "status": "auto"},
        {"segment_id": "S01E10:sentence:1", "cue_id": "S01E10:en:1", "lang": "en", "role": "pivot", "confidence": 0.9, "status": "auto"},
        {"cue_id": "S01E10:en:1", "cue_id_target": "S01E10:fr:1", "lang": "fr", "role": "target", "confidence": 1.0, "status": "auto"},
    ]
    db.upsert_align_links(run_id, "S01E10", links)
    stats = db.get_align_stats_for_run("S01E10", run_id)
    # (0.1 + 0.9 + 1.0) / 3 = 0.666666...
    assert stats["avg_confidence"] == pytest.approx(0.6667, abs=1e-4)


def test_kwic_episode_non_regression(db):
    """Non-régression : query_kwic (épisodes) continue de marcher après migration segments."""
    ref = EpisodeRef(
        episode_id="S01E04",
        season=1,
        episode=4,
        title="Return of the Shirt",
        url="https://example.com/s01e04",
    )
    db.upsert_episode(ref)
    db.index_episode_text("S01E04", "The return of the shirt. Legendary shirt.")
    hits_ep = db.query_kwic("shirt", limit=10)
    assert len(hits_ep) >= 2
    assert all(h.episode_id == "S01E04" for h in hits_ep)
    assert all(getattr(h, "segment_id", None) is None for h in hits_ep)


def test_normalize_subtitle_track_s11(db):
    """§11 — normalize_subtitle_track applique le profil aux cues (text_clean mis à jour)."""
    from howimetyourcorpus.core.storage.project_store import ProjectStore
    from howimetyourcorpus.core.models import ProjectConfig
    from howimetyourcorpus.core.subtitles import Cue

    ref = EpisodeRef(episode_id="S01E08", season=1, episode=8, title="Norms", url="https://ex.com/s01e08")
    db.upsert_episode(ref)
    db.add_track("S01E08:en", "S01E08", "en", "srt")
    cue_raw = Cue(
        episode_id="S01E08", lang="en", n=0,
        start_ms=0, end_ms=2000,
        text_raw="Line one\nbreaks here.",
        text_clean="Line one\nbreaks here.",
    )
    db.upsert_cues("S01E08:en", "S01E08", "en", [cue_raw])

    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        ProjectStore.init_project(ProjectConfig(project_name="t", root_dir=root, source_id="x", series_url=""))
        store = ProjectStore(root)
        nb = store.normalize_subtitle_track(db, "S01E08", "en", "default_en_v1", rewrite_srt=False)
    assert nb == 1
    cues = db.get_cues_for_episode_lang("S01E08", "en")
    assert len(cues) == 1
    clean = (cues[0].get("text_clean") or "").strip()
    assert "Line one" in clean and "breaks here" in clean
    assert "\n" not in clean or clean.count("\n") < 2
