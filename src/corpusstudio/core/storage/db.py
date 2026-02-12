"""SQLite + FTS5 + requêtes KWIC."""

from __future__ import annotations

import datetime
import re
import sqlite3
from dataclasses import dataclass
from pathlib import Path

from corpusstudio.core.models import EpisodeRef, EpisodeStatus

# Schéma DDL
SCHEMA_SQL = (Path(__file__).parent / "schema.sql").read_text(encoding="utf-8")


@dataclass
class KwicHit:
    """Un résultat KWIC (contexte gauche, match, contexte droit)."""

    episode_id: str
    title: str
    left: str
    match: str
    right: str
    position: int  # position approximative dans le document (caractère)
    score: float = 1.0


class CorpusDB:
    """Accès à la base corpus (épisodes, documents, FTS, KWIC)."""

    def __init__(self, db_path: Path | str):
        self.db_path = Path(db_path)

    def _conn(self) -> sqlite3.Connection:
        return sqlite3.connect(self.db_path)

    def init(self) -> None:
        """Crée les tables et FTS si nécessaire."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = self._conn()
        try:
            conn.executescript(SCHEMA_SQL)
            conn.commit()
        finally:
            conn.close()

    def upsert_episode(self, ref: EpisodeRef, status: str = "new") -> None:
        """Insère ou met à jour une entrée épisode."""
        conn = self._conn()
        try:
            conn.execute(
                """
                INSERT INTO episodes (episode_id, season, episode, title, url, status)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(episode_id) DO UPDATE SET
                  season=excluded.season, episode=excluded.episode,
                  title=excluded.title, url=excluded.url, status=excluded.status
                """,
                (ref.episode_id, ref.season, ref.episode, ref.title, ref.url, status),
            )
            conn.commit()
        finally:
            conn.close()

    def set_episode_status(
        self, episode_id: str, status: str, timestamp: str | None = None
    ) -> None:
        """Met à jour le statut d'un épisode (et fetched_at / normalized_at si fourni)."""
        ts = timestamp or datetime.datetime.utcnow().isoformat() + "Z"
        conn = self._conn()
        try:
            if status == EpisodeStatus.FETCHED.value:
                conn.execute(
                    "UPDATE episodes SET status=?, fetched_at=? WHERE episode_id=?",
                    (status, ts, episode_id),
                )
            elif status == EpisodeStatus.NORMALIZED.value:
                conn.execute(
                    "UPDATE episodes SET status=?, normalized_at=? WHERE episode_id=?",
                    (status, ts, episode_id),
                )
            else:
                conn.execute(
                    "UPDATE episodes SET status=? WHERE episode_id=?",
                    (status, episode_id),
                )
            conn.commit()
        finally:
            conn.close()

    def index_episode_text(self, episode_id: str, clean_text: str) -> None:
        """Indexe le texte normalisé d'un épisode (documents + FTS)."""
        conn = self._conn()
        try:
            conn.execute(
                "INSERT OR REPLACE INTO documents (episode_id, clean_text) VALUES (?, ?)",
                (episode_id, clean_text),
            )
            conn.execute(
                "UPDATE episodes SET status=? WHERE episode_id=?",
                (EpisodeStatus.INDEXED.value, episode_id),
            )
            conn.commit()
        finally:
            conn.close()

    def _fts5_match_query(self, term: str) -> str:
        """Échappe le terme pour FTS5 MATCH (phrase entre guillemets)."""
        escaped = term.replace('"', '""')
        return f'"{escaped}"'

    def query_kwic(
        self,
        term: str,
        season: int | None = None,
        episode: int | None = None,
        window: int = 45,
        limit: int = 200,
    ) -> list[KwicHit]:
        """
        Recherche KWIC : utilise FTS5 pour filtrer les documents, puis construit
        (left, match, right) en Python avec window caractères de contexte.
        """
        conn = self._conn()
        conn.row_factory = sqlite3.Row
        try:
            fts_query = self._fts5_match_query(term)
            if season is not None and episode is not None:
                rows = conn.execute(
                    """
                    SELECT d.episode_id, d.clean_text, e.title
                    FROM documents_fts
                    JOIN documents d ON d.rowid = documents_fts.rowid
                    JOIN episodes e ON e.episode_id = d.episode_id
                    WHERE documents_fts MATCH ? AND e.season = ? AND e.episode = ?
                    """,
                    (fts_query, season, episode),
                ).fetchall()
            elif season is not None:
                rows = conn.execute(
                    """
                    SELECT d.episode_id, d.clean_text, e.title
                    FROM documents_fts
                    JOIN documents d ON d.rowid = documents_fts.rowid
                    JOIN episodes e ON e.episode_id = d.episode_id
                    WHERE documents_fts MATCH ? AND e.season = ?
                    """,
                    (fts_query, season),
                ).fetchall()
            else:
                rows = conn.execute(
                    """
                    SELECT d.episode_id, d.clean_text, e.title
                    FROM documents_fts
                    JOIN documents d ON d.rowid = documents_fts.rowid
                    JOIN episodes e ON e.episode_id = d.episode_id
                    WHERE documents_fts MATCH ?
                    """,
                    (fts_query,),
                ).fetchall()

            hits: list[KwicHit] = []
            pattern = re.compile(re.escape(term), re.IGNORECASE)
            for row in rows:
                episode_id = row["episode_id"]
                title = row["title"] or ""
                text = row["clean_text"] or ""
                for m in pattern.finditer(text):
                    start, end = m.start(), m.end()
                    left = text[max(0, start - window) : start]
                    match = text[start:end]
                    right = text[end : end + window]
                    if len(left) < start - max(0, start - window):
                        left = "..." + left
                    if len(right) < min(window, len(text) - end):
                        right = right + "..."
                    hits.append(
                        KwicHit(
                            episode_id=episode_id,
                            title=title,
                            left=left,
                            match=match,
                            right=right,
                            position=start,
                            score=1.0,
                        )
                    )
                    if len(hits) >= limit:
                        return hits
            return hits
        finally:
            conn.close()

    def get_episode_ids_indexed(self) -> list[str]:
        """Liste des episode_id ayant du texte indexé."""
        conn = self._conn()
        try:
            rows = conn.execute(
                "SELECT episode_id FROM documents"
            ).fetchall()
            return [r[0] for r in rows]
        finally:
            conn.close()
