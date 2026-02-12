"""
Script à lancer une fois pour créer example/corpus.db avec l'épisode S01E01.
Depuis la racine du projet :
  PYTHONPATH=src python example/create_demo_db.py
"""
from pathlib import Path

from howimetyourcorpus.core.models import EpisodeRef
from howimetyourcorpus.core.storage.db import CorpusDB

EXAMPLE_DIR = Path(__file__).resolve().parent
DB_PATH = EXAMPLE_DIR / "corpus.db"

def main():
    db = CorpusDB(DB_PATH)
    db.init()
    ref = EpisodeRef(
        episode_id="S01E01",
        season=1,
        episode=1,
        title="Demo",
        url="https://example.com/demo/s01e01",
    )
    db.upsert_episode(ref, status="new")
    print(f"Created {DB_PATH} with episode S01E01.")

if __name__ == "__main__":
    main()
