"""SQLite + FTS5 + requêtes KWIC."""

from __future__ import annotations

import datetime
import sqlite3
from pathlib import Path

import json

from howimetyourcorpus.core.models import EpisodeRef, EpisodeStatus

from howimetyourcorpus.core.storage import db_align
from howimetyourcorpus.core.storage import db_segments
from howimetyourcorpus.core.storage import db_subtitles
from howimetyourcorpus.core.storage.db_kwic import (
    KwicHit,
    query_kwic as _query_kwic,
    query_kwic_cues as _query_kwic_cues,
    query_kwic_segments as _query_kwic_segments,
)

# Schéma DDL
STORAGE_DIR = Path(__file__).parent
SCHEMA_SQL = (STORAGE_DIR / "schema.sql").read_text(encoding="utf-8")
MIGRATIONS_DIR = STORAGE_DIR / "migrations"

# Réexport pour compatibilité (KwicHit défini dans db_kwic)
__all__ = ["CorpusDB", "KwicHit"]


class CorpusDB:
    """Accès à la base corpus (épisodes, documents, FTS, KWIC)."""

    def __init__(self, db_path: Path | str):
        self.db_path = Path(db_path)

    def _conn(self) -> sqlite3.Connection:
        return sqlite3.connect(self.db_path)

    def _migrate(self, conn: sqlite3.Connection) -> None:
        """Exécute les migrations en attente (schema_version)."""
        if not self._table_exists(conn, "schema_version"):
            conn.execute(
                "CREATE TABLE IF NOT EXISTS schema_version (version INTEGER PRIMARY KEY)"
            )
            conn.execute("INSERT INTO schema_version (version) VALUES (1)")
            conn.commit()
        cur = conn.execute(
            "SELECT version FROM schema_version ORDER BY version DESC LIMIT 1"
        )
        row = cur.fetchone()
        current = int(row[0]) if row else 0
        if not MIGRATIONS_DIR.exists():
            return
        migration_files = sorted(MIGRATIONS_DIR.glob("*.sql"))
        for path in migration_files:
            # 002_segments.sql -> 2
            try:
                version = int(path.stem.split("_")[0])
            except ValueError:
                continue
            if version <= current:
                continue
            sql = path.read_text(encoding="utf-8")
            conn.executescript(sql)
            conn.commit()

    def init(self) -> None:
        """Crée les tables et FTS si nécessaire, puis exécute les migrations."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = self._conn()
        try:
            conn.executescript(SCHEMA_SQL)
            conn.commit()
            self._migrate(conn)
        finally:
            conn.close()

    def _table_exists(self, conn: sqlite3.Connection, table_name: str) -> bool:
        """Retourne True si la table existe."""
        row = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
            (table_name,),
        ).fetchone()
        return row is not None

    def get_schema_version(self) -> int:
        """Retourne la version du schéma (table schema_version). 0 si la table n'existe pas ou est vide."""
        if not self.db_path.exists():
            return 0
        conn = self._conn()
        try:
            if not self._table_exists(conn, "schema_version"):
                return 0
            row = conn.execute(
                "SELECT version FROM schema_version ORDER BY version DESC LIMIT 1"
            ).fetchone()
            return int(row[0]) if row else 0
        finally:
            conn.close()

    def ensure_migrated(self) -> None:
        """Exécute les migrations en attente (à appeler à l'ouverture d'un projet existant).
        Si des tables Phase 3+ sont manquantes (schema_version incohérent), exécute les scripts concernés.
        """
        if not self.db_path.exists():
            return
        conn = self._conn()
        try:
            self._migrate(conn)
            if not self._table_exists(conn, "subtitle_tracks"):
                for name in ("003_subtitles", "004_align"):
                    path = MIGRATIONS_DIR / f"{name}.sql"
                    if path.exists():
                        conn.executescript(path.read_text(encoding="utf-8"))
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
        ts = timestamp or datetime.datetime.now(datetime.UTC).isoformat().replace("+00:00", "Z")
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

    def query_kwic(
        self,
        term: str,
        season: int | None = None,
        episode: int | None = None,
        window: int = 45,
        limit: int = 200,
    ) -> list[KwicHit]:
        """Recherche KWIC sur documents (FTS5). Délègue à db_kwic."""
        conn = self._conn()
        try:
            return _query_kwic(conn, term, season=season, episode=episode, window=window, limit=limit)
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

    def get_episode_statuses(self, episode_ids: list[str]) -> dict[str, str]:
        """Retourne les statuts épisodes depuis la DB (episode_id -> status)."""
        if not episode_ids:
            return {}
        conn = self._conn()
        try:
            placeholders = ",".join("?" * len(episode_ids))
            rows = conn.execute(
                f"SELECT episode_id, status FROM episodes WHERE episode_id IN ({placeholders})",
                episode_ids,
            ).fetchall()
            return {str(r[0]): str(r[1]) for r in rows if r and r[0] is not None and r[1] is not None}
        finally:
            conn.close()

    # ----- Phase 2: segments (délègue à db_segments) -----

    def upsert_segments(
        self,
        episode_id: str,
        kind: str,
        segments: list,
    ) -> None:
        """Insère ou met à jour les segments d'un épisode (sentence ou utterance)."""
        conn = self._conn()
        try:
            db_segments.upsert_segments(conn, episode_id, kind, segments)
            conn.commit()
        finally:
            conn.close()

    def query_kwic_segments(
        self,
        term: str,
        kind: str | None = None,
        season: int | None = None,
        episode: int | None = None,
        window: int = 45,
        limit: int = 200,
    ) -> list[KwicHit]:
        """Recherche KWIC au niveau segments (FTS segments_fts). Délègue à db_kwic."""
        conn = self._conn()
        try:
            return _query_kwic_segments(
                conn, term, kind=kind, season=season, episode=episode, window=window, limit=limit
            )
        finally:
            conn.close()

    def get_segments_for_episode(
        self,
        episode_id: str,
        kind: str | None = None,
    ) -> list[dict]:
        """Retourne les segments d'un épisode (pour l'Inspecteur). kind = 'sentence' | 'utterance' | None (tous)."""
        conn = self._conn()
        try:
            return db_segments.get_segments_for_episode(conn, episode_id, kind)
        finally:
            conn.close()

    def update_segment_speaker(self, segment_id: str, speaker_explicit: str | None) -> None:
        """Met à jour le champ speaker_explicit d'un segment (propagation §8)."""
        conn = self._conn()
        try:
            db_segments.update_segment_speaker(conn, segment_id, speaker_explicit)
            conn.commit()
        finally:
            conn.close()

    def get_distinct_speaker_explicit(self, episode_ids: list[str]) -> list[str]:
        """Retourne la liste des noms de locuteurs (speaker_explicit) présents dans les segments des épisodes donnés, triés."""
        conn = self._conn()
        try:
            return db_segments.get_distinct_speaker_explicit(conn, episode_ids)
        finally:
            conn.close()

    # ----- Phase 3: sous-titres (délègue à db_subtitles) -----

    def add_track(
        self,
        track_id: str,
        episode_id: str,
        lang: str,
        fmt: str,
        source_path: str | None = None,
        imported_at: str | None = None,
        meta_json: str | None = None,
    ) -> None:
        """Enregistre une piste sous-titres (ou met à jour si track_id existe). fmt = "srt"|"vtt"."""
        conn = self._conn()
        try:
            db_subtitles.add_track(conn, track_id, episode_id, lang, fmt, source_path, imported_at, meta_json)
            conn.commit()
        finally:
            conn.close()

    def upsert_cues(self, track_id: str, episode_id: str, lang: str, cues: list) -> None:
        """Remplace les cues d'une piste (supprime anciennes, insère les nouvelles)."""
        conn = self._conn()
        try:
            db_subtitles.upsert_cues(conn, track_id, episode_id, lang, cues)
            conn.commit()
        finally:
            conn.close()

    def update_cue_text_clean(self, cue_id: str, text_clean: str) -> None:
        """Met à jour le champ text_clean d'une cue (propagation §8)."""
        conn = self._conn()
        try:
            db_subtitles.update_cue_text_clean(conn, cue_id, text_clean)
            conn.commit()
        finally:
            conn.close()

    def query_kwic_cues(
        self,
        term: str,
        lang: str | None = None,
        season: int | None = None,
        episode: int | None = None,
        window: int = 45,
        limit: int = 200,
    ) -> list[KwicHit]:
        """Recherche KWIC sur les cues sous-titres (FTS cues_fts). Délègue à db_kwic."""
        conn = self._conn()
        try:
            return _query_kwic_cues(
                conn, term, lang=lang, season=season, episode=episode, window=window, limit=limit
            )
        finally:
            conn.close()

    def get_tracks_for_episode(self, episode_id: str) -> list[dict]:
        """Retourne les pistes sous-titres d'un épisode avec nb_cues (pour l'UI)."""
        conn = self._conn()
        try:
            return db_subtitles.get_tracks_for_episode(conn, episode_id)
        finally:
            conn.close()

    def get_tracks_for_episodes(self, episode_ids: list[str]) -> dict[str, list[dict]]:
        """Retourne les pistes par épisode (episode_id -> liste). Batch pour refresh Corpus / arbre."""
        conn = self._conn()
        try:
            return db_subtitles.get_tracks_for_episodes(conn, episode_ids)
        finally:
            conn.close()

    def delete_subtitle_track(self, episode_id: str, lang: str) -> None:
        """Supprime une piste sous-titres (cues puis track). track_id = episode_id:lang."""
        conn = self._conn()
        try:
            db_subtitles.delete_subtitle_track(conn, episode_id, lang)
            conn.commit()
        finally:
            conn.close()

    def get_cues_for_episode_lang(self, episode_id: str, lang: str) -> list[dict]:
        """Retourne les cues d'un épisode pour une langue (pour l'Inspecteur). meta = dict si meta_json présent."""
        conn = self._conn()
        try:
            return db_subtitles.get_cues_for_episode_lang(conn, episode_id, lang)
        finally:
            conn.close()

    # ----- Phase 4: alignement (délègue à db_align) -----

    def create_align_run(
        self,
        align_run_id: str,
        episode_id: str,
        pivot_lang: str,
        params_json: str | None = None,
        created_at: str | None = None,
        summary_json: str | None = None,
    ) -> None:
        """Crée une entrée de run d'alignement."""
        conn = self._conn()
        try:
            db_align.create_align_run(conn, align_run_id, episode_id, pivot_lang, params_json, created_at, summary_json)
            conn.commit()
        finally:
            conn.close()

    def upsert_align_links(self, align_run_id: str, episode_id: str, links: list[dict]) -> None:
        """Remplace les liens d'un run (DELETE puis INSERT). Chaque link: segment_id?, cue_id?, cue_id_target?, lang?, role, confidence, status, meta_json?."""
        conn = self._conn()
        try:
            db_align.upsert_align_links(conn, align_run_id, episode_id, links)
            conn.commit()
        finally:
            conn.close()

    def set_align_status(self, link_id: str, status: str) -> None:
        """Met à jour le statut d'un lien (accepted / rejected)."""
        conn = self._conn()
        try:
            db_align.set_align_status(conn, link_id, status)
            conn.commit()
        finally:
            conn.close()

    def update_align_link_cues(
        self,
        link_id: str,
        cue_id: str | None = None,
        cue_id_target: str | None = None,
    ) -> None:
        """Modifie la cible d'un lien (réplique EN et/ou réplique cible). Met le statut à 'accepted' (correction manuelle)."""
        conn = self._conn()
        try:
            db_align.update_align_link_cues(conn, link_id, cue_id, cue_id_target)
            conn.commit()
        finally:
            conn.close()

    def get_align_runs_for_episode(self, episode_id: str) -> list[dict]:
        """Retourne les runs d'alignement d'un épisode (pour l'UI)."""
        conn = self._conn()
        try:
            return db_align.get_align_runs_for_episode(conn, episode_id)
        finally:
            conn.close()

    def get_align_runs_for_episodes(self, episode_ids: list[str]) -> dict[str, list[dict]]:
        """Retourne les runs d'alignement par épisode (episode_id -> liste). Batch pour refresh Corpus / arbre."""
        conn = self._conn()
        try:
            return db_align.get_align_runs_for_episodes(conn, episode_ids)
        finally:
            conn.close()

    def delete_align_run(self, align_run_id: str) -> None:
        """Supprime un run d'alignement et tous ses liens."""
        conn = self._conn()
        try:
            db_align.delete_align_run(conn, align_run_id)
            conn.commit()
        finally:
            conn.close()

    def delete_align_runs_for_episode(self, episode_id: str) -> None:
        """Supprime tous les runs d'alignement d'un épisode (évite liens orphelins après suppression piste ou re-segmentation)."""
        conn = self._conn()
        try:
            db_align.delete_align_runs_for_episode(conn, episode_id)
            conn.commit()
        finally:
            conn.close()

    def query_alignment_for_episode(
        self,
        episode_id: str,
        run_id: str | None = None,
        status_filter: str | None = None,
        min_confidence: float | None = None,
    ) -> list[dict]:
        """Retourne les liens d'alignement pour un épisode (optionnel: run_id, filtre status, min confidence)."""
        conn = self._conn()
        try:
            return db_align.query_alignment_for_episode(conn, episode_id, run_id, status_filter, min_confidence)
        finally:
            conn.close()

    # ----- Phase 5: concordancier parallèle et stats (délègue à db_align) -----

    def get_align_stats_for_run(
        self, episode_id: str, run_id: str, status_filter: str | None = None
    ) -> dict:
        """
        Statistiques d'alignement pour un run : nb_links, nb_pivot, nb_target,
        by_status (auto/accepted/rejected), avg_confidence.
        """
        conn = self._conn()
        try:
            return db_align.get_align_stats_for_run(conn, episode_id, run_id, status_filter)
        finally:
            conn.close()

    def get_parallel_concordance(
        self,
        episode_id: str,
        run_id: str,
        status_filter: str | None = None,
    ) -> list[dict]:
        """
        Construit les lignes du concordancier parallèle : segment (transcript) + cue EN + cues FR/IT
        à partir des liens d'alignement.
        """
        conn = self._conn()
        try:
            return db_align.get_parallel_concordance(conn, episode_id, run_id, status_filter)
        finally:
            conn.close()
