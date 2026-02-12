"""Tests CorpusDB : init, index, requête KWIC."""

import pytest
from pathlib import Path
import tempfile

from corpusstudio.core.storage.db import CorpusDB, KwicHit
from corpusstudio.core.models import EpisodeRef, EpisodeStatus


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
