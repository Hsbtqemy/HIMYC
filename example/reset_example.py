"""
Remet l'exemple à zéro : base vide (uniquement épisode S01E01), plus de pistes SRT ni de runs d'alignement.
À lancer depuis la racine du projet :
  PYTHONPATH=src python example/reset_example.py
"""
from pathlib import Path

EXAMPLE_DIR = Path(__file__).resolve().parent


def main() -> None:
    # 1) Recréer corpus.db (épisode S01E01 uniquement)
    db_path = EXAMPLE_DIR / "corpus.db"
    if db_path.exists():
        db_path.unlink()
    from howimetyourcorpus.core.models import EpisodeRef
    from howimetyourcorpus.core.storage.db import CorpusDB

    db = CorpusDB(db_path)
    db.init()
    ref = EpisodeRef(
        episode_id="S01E01",
        season=1,
        episode=1,
        title="Demo",
        url="https://example.com/demo/s01e01",
    )
    db.upsert_episode(ref, status="new")
    print(f"Recréé {db_path} avec épisode S01E01.")

    # 2) Supprimer sous-titres et runs d'alignement sur disque (fichiers)
    episodes_dir = EXAMPLE_DIR / "episodes"
    if episodes_dir.exists():
        for ep_dir in episodes_dir.iterdir():
            if not ep_dir.is_dir():
                continue
            subs = ep_dir / "subs"
            if subs.exists():
                for f in subs.iterdir():
                    f.unlink(missing_ok=True)
                print(f"  Vidé {subs}")
            align_dir = ep_dir / "align"
            if align_dir.exists():
                for f in align_dir.iterdir():
                    f.unlink(missing_ok=True)
                print(f"  Vidé {align_dir}")
            segments_file = ep_dir / "segments.jsonl"
            if segments_file.exists():
                segments_file.unlink()
                print(f"  Supprimé {segments_file}")

    print("Exemple remis à zéro. Vous pouvez rouvrir le projet et ré-importer SRT / segmenter / aligner.")


if __name__ == "__main__":
    main()
