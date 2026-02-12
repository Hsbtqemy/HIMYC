"""SQLite + FTS5 + requêtes KWIC."""

from __future__ import annotations

import datetime
import re
import sqlite3
from dataclasses import dataclass
from pathlib import Path

import json

from howimetyourcorpus.core.models import EpisodeRef, EpisodeStatus

# Schéma DDL
STORAGE_DIR = Path(__file__).parent
SCHEMA_SQL = (STORAGE_DIR / "schema.sql").read_text(encoding="utf-8")
MIGRATIONS_DIR = STORAGE_DIR / "migrations"


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
    segment_id: str | None = None  # Phase 2: hit au niveau segment
    kind: str | None = None  # "sentence" | "utterance"
    cue_id: str | None = None  # Phase 3: hit au niveau cue sous-titre
    lang: str | None = None  # Phase 3: langue de la cue


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
                "CREATE TABLE IF NOT EXISTS schema_version (version INTEGER NOT NULL)"
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
        if not term or not term.strip():
            return []
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

    # ----- Phase 2: segments -----

    def upsert_segments(
        self,
        episode_id: str,
        kind: str,
        segments: list,
    ) -> None:
        """Insère ou met à jour les segments d'un épisode (sentence ou utterance)."""
        from howimetyourcorpus.core.segment import Segment

        conn = self._conn()
        try:
            conn.execute(
                "DELETE FROM segments WHERE episode_id = ? AND kind = ?",
                (episode_id, kind),
            )
            for seg in segments:
                if not isinstance(seg, Segment):
                    continue
                sid = f"{episode_id}:{seg.kind}:{seg.n}"
                meta_json = json.dumps(seg.meta) if seg.meta else None
                conn.execute(
                    """
                    INSERT INTO segments (segment_id, episode_id, kind, n, start_char, end_char, text, speaker_explicit, meta_json)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        sid,
                        episode_id,
                        kind,
                        seg.n,
                        seg.start_char,
                        seg.end_char,
                        seg.text,
                        seg.speaker_explicit,
                        meta_json,
                    ),
                )
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
        """
        Recherche KWIC au niveau segments (FTS segments_fts).
        Retourne des KwicHit avec segment_id et kind renseignés.
        """
        if not term or not term.strip():
            return []
        conn = self._conn()
        conn.row_factory = sqlite3.Row
        try:
            fts_query = self._fts5_match_query(term)
            params: list = [fts_query]
            where_extra = ""
            if kind is not None:
                where_extra += " AND s.kind = ?"
                params.append(kind)
            if season is not None:
                where_extra += " AND e.season = ?"
                params.append(season)
            if episode is not None:
                where_extra += " AND e.episode = ?"
                params.append(episode)
            rows = conn.execute(
                f"""
                SELECT s.segment_id, s.episode_id, s.kind, s.text, e.title
                FROM segments_fts
                JOIN segments s ON s.rowid = segments_fts.rowid
                JOIN episodes e ON e.episode_id = s.episode_id
                WHERE segments_fts MATCH ?{where_extra}
                """,
                params,
            ).fetchall()

            hits: list[KwicHit] = []
            pattern = re.compile(re.escape(term), re.IGNORECASE)
            for row in rows:
                segment_id = row["segment_id"]
                episode_id = row["episode_id"]
                k = row["kind"]
                title = row["title"] or ""
                text = row["text"] or ""
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
                            segment_id=segment_id,
                            kind=k,
                        )
                    )
                    if len(hits) >= limit:
                        return hits
            return hits
        finally:
            conn.close()

    def get_segments_for_episode(
        self,
        episode_id: str,
        kind: str | None = None,
    ) -> list[dict]:
        """Retourne les segments d'un épisode (pour l'Inspecteur). kind = 'sentence' | 'utterance' | None (tous)."""
        conn = self._conn()
        conn.row_factory = sqlite3.Row
        try:
            if kind:
                rows = conn.execute(
                    "SELECT segment_id, episode_id, kind, n, start_char, end_char, text, speaker_explicit, meta_json FROM segments WHERE episode_id = ? AND kind = ? ORDER BY kind, n",
                    (episode_id, kind),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT segment_id, episode_id, kind, n, start_char, end_char, text, speaker_explicit, meta_json FROM segments WHERE episode_id = ? ORDER BY kind, n",
                    (episode_id,),
                ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    # ----- Phase 3: sous-titres (tracks + cues) -----

    def _normalize_cue_text_for_db(self, raw: str) -> str:
        """Normalisation minimaliste pour text_clean (fallback si Cue.text_clean vide)."""
        if not raw:
            return ""
        t = raw.replace("\n", " ").replace("\r", " ")
        return " ".join(t.split()).strip()

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
            conn.execute(
                """
                INSERT INTO subtitle_tracks (track_id, episode_id, lang, format, source_path, imported_at, meta_json)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(track_id) DO UPDATE SET
                  episode_id=excluded.episode_id, lang=excluded.lang, format=excluded.format,
                  source_path=excluded.source_path, imported_at=excluded.imported_at, meta_json=excluded.meta_json
                """,
                (track_id, episode_id, lang, fmt, source_path, imported_at, meta_json),
            )
            conn.commit()
        finally:
            conn.close()

    def upsert_cues(self, track_id: str, episode_id: str, lang: str, cues: list) -> None:
        """Remplace les cues d'une piste (supprime anciennes, insère les nouvelles)."""
        from howimetyourcorpus.core.subtitles import Cue

        conn = self._conn()
        try:
            conn.execute("DELETE FROM subtitle_cues WHERE track_id = ?", (track_id,))
            for c in cues:
                if not isinstance(c, Cue):
                    continue
                cid = f"{episode_id}:{lang}:{c.n}" if episode_id and lang else f":{c.lang}:{c.n}"
                meta_json_str = json.dumps(c.meta) if c.meta else None
                conn.execute(
                    """
                    INSERT INTO subtitle_cues (cue_id, track_id, episode_id, lang, n, start_ms, end_ms, text_raw, text_clean, meta_json)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        cid,
                        track_id,
                        episode_id,
                        lang,
                        c.n,
                        c.start_ms,
                        c.end_ms,
                        c.text_raw,
                        c.text_clean or self._normalize_cue_text_for_db(c.text_raw),
                        meta_json_str,
                    ),
                )
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
        """
        Recherche KWIC sur les cues sous-titres (FTS cues_fts).
        Retourne des KwicHit avec cue_id et lang renseignés.
        """
        if not term or not term.strip():
            return []
        conn = self._conn()
        conn.row_factory = sqlite3.Row
        try:
            fts_query = self._fts5_match_query(term)
            params: list = [fts_query]
            where_extra = ""
            if lang:
                where_extra += " AND c.lang = ?"
                params.append(lang)
            if season is not None:
                where_extra += " AND e.season = ?"
                params.append(season)
            if episode is not None:
                where_extra += " AND e.episode = ?"
                params.append(episode)
            rows = conn.execute(
                f"""
                SELECT c.cue_id, c.episode_id, c.lang, c.text_clean, e.title
                FROM cues_fts
                JOIN subtitle_cues c ON c.rowid = cues_fts.rowid
                JOIN episodes e ON e.episode_id = c.episode_id
                WHERE cues_fts MATCH ?{where_extra}
                """,
                params,
            ).fetchall()

            hits: list[KwicHit] = []
            pattern = re.compile(re.escape(term), re.IGNORECASE)
            for row in rows:
                cue_id = row["cue_id"]
                episode_id = row["episode_id"]
                lang_val = row["lang"]
                title = row["title"] or ""
                text = row["text_clean"] or ""
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
                            cue_id=cue_id,
                            lang=lang_val,
                        )
                    )
                    if len(hits) >= limit:
                        return hits
            return hits
        finally:
            conn.close()

    def get_tracks_for_episode(self, episode_id: str) -> list[dict]:
        """Retourne les pistes sous-titres d'un épisode avec nb_cues (pour l'UI)."""
        conn = self._conn()
        conn.row_factory = sqlite3.Row
        try:
            rows = conn.execute(
                """SELECT t.track_id, t.episode_id, t.lang, t.format, t.source_path, t.imported_at,
                          COUNT(c.cue_id) AS nb_cues
                   FROM subtitle_tracks t
                   LEFT JOIN subtitle_cues c ON c.track_id = t.track_id
                   WHERE t.episode_id = ?
                   GROUP BY t.track_id
                   ORDER BY t.lang""",
                (episode_id,),
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def get_cues_for_episode_lang(self, episode_id: str, lang: str) -> list[dict]:
        """Retourne les cues d'un épisode pour une langue (pour l'Inspecteur). meta = dict si meta_json présent."""
        conn = self._conn()
        conn.row_factory = sqlite3.Row
        try:
            rows = conn.execute(
                """SELECT cue_id, track_id, episode_id, lang, n, start_ms, end_ms, text_raw, text_clean, meta_json
                   FROM subtitle_cues WHERE episode_id = ? AND lang = ? ORDER BY n""",
                (episode_id, lang),
            ).fetchall()
            result = []
            for r in rows:
                d = dict(r)
                meta_raw = d.pop("meta_json", None)
                d["meta"] = json.loads(meta_raw) if meta_raw and meta_raw.strip() else {}
                result.append(d)
            return result
        finally:
            conn.close()

    # ----- Phase 4: alignement -----

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
        if not created_at:
            created_at = datetime.datetime.utcnow().isoformat() + "Z"
        conn = self._conn()
        try:
            conn.execute(
                """
                INSERT INTO align_runs (align_run_id, episode_id, pivot_lang, params_json, created_at, summary_json)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (align_run_id, episode_id, pivot_lang, params_json, created_at, summary_json),
            )
            conn.commit()
        finally:
            conn.close()

    def upsert_align_links(self, align_run_id: str, episode_id: str, links: list[dict]) -> None:
        """Remplace les liens d'un run (DELETE puis INSERT). Chaque link: segment_id?, cue_id?, cue_id_target?, lang?, role, confidence, status, meta_json?."""
        conn = self._conn()
        try:
            conn.execute("DELETE FROM align_links WHERE align_run_id = ?", (align_run_id,))
            for i, link in enumerate(links):
                link_id = link.get("link_id") or f"{align_run_id}:{i}"
                segment_id = link.get("segment_id")
                cue_id = link.get("cue_id")
                cue_id_target = link.get("cue_id_target")
                lang = link.get("lang") or ""
                role = link.get("role", "pivot")
                confidence = link.get("confidence")
                status = link.get("status", "auto")
                meta_json = json.dumps(link["meta"]) if link.get("meta") else None
                conn.execute(
                    """
                    INSERT INTO align_links (link_id, align_run_id, episode_id, segment_id, cue_id, cue_id_target, lang, role, confidence, status, meta_json)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (link_id, align_run_id, episode_id, segment_id, cue_id, cue_id_target, lang, role, confidence, status, meta_json),
                )
            conn.commit()
        finally:
            conn.close()

    def set_align_status(self, link_id: str, status: str) -> None:
        """Met à jour le statut d'un lien (accepted / rejected)."""
        conn = self._conn()
        try:
            conn.execute("UPDATE align_links SET status = ? WHERE link_id = ?", (status, link_id))
            conn.commit()
        finally:
            conn.close()

    def get_align_runs_for_episode(self, episode_id: str) -> list[dict]:
        """Retourne les runs d'alignement d'un épisode (pour l'UI)."""
        conn = self._conn()
        conn.row_factory = sqlite3.Row
        try:
            rows = conn.execute(
                "SELECT align_run_id, episode_id, pivot_lang, params_json, created_at, summary_json FROM align_runs WHERE episode_id = ? ORDER BY created_at DESC",
                (episode_id,),
            ).fetchall()
            return [dict(r) for r in rows]
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
        conn.row_factory = sqlite3.Row
        try:
            where = "WHERE episode_id = ?"
            params: list = [episode_id]
            if run_id:
                where += " AND align_run_id = ?"
                params.append(run_id)
            if status_filter:
                where += " AND status = ?"
                params.append(status_filter)
            if min_confidence is not None:
                where += " AND confidence >= ?"
                params.append(min_confidence)
            rows = conn.execute(
                f"""SELECT link_id, align_run_id, episode_id, segment_id, cue_id, cue_id_target, lang, role, confidence, status, meta_json
                    FROM align_links {where} ORDER BY segment_id, cue_id, lang""",
                params,
            ).fetchall()
            result = []
            for r in rows:
                d = dict(r)
                meta_raw = d.pop("meta_json", None)
                d["meta"] = json.loads(meta_raw) if meta_raw and meta_raw.strip() else {}
                result.append(d)
            return result
        finally:
            conn.close()

    # ----- Phase 5: concordancier parallèle et stats -----

    def get_align_stats_for_run(
        self, episode_id: str, run_id: str, status_filter: str | None = None
    ) -> dict:
        """
        Statistiques d'alignement pour un run : nb_links, nb_pivot, nb_target,
        by_status (auto/accepted/rejected), avg_confidence.
        Si status_filter est fourni (ex. "accepted"), seuls les liens avec ce statut sont comptés.
        """
        conn = self._conn()
        conn.row_factory = sqlite3.Row
        try:
            where = "WHERE episode_id = ? AND align_run_id = ?"
            params: list = [episode_id, run_id]
            if status_filter:
                where += " AND status = ?"
                params.append(status_filter)
            rows = conn.execute(
                f"""SELECT role, status, confidence, COUNT(*) AS cnt
                   FROM align_links {where}
                   GROUP BY role, status""",
                params,
            ).fetchall()
            nb_links = 0
            nb_pivot = 0
            nb_target = 0
            by_status: dict[str, int] = {}
            conf_sum = 0.0
            conf_count = 0
            for r in rows:
                cnt = r["cnt"]
                nb_links += cnt
                if r["role"] == "pivot":
                    nb_pivot += cnt
                else:
                    nb_target += cnt
                st = r["status"] or "auto"
                by_status[st] = by_status.get(st, 0) + cnt
                if r["confidence"] is not None:
                    conf_sum += r["confidence"] * cnt
                    conf_count += cnt
            avg_confidence = conf_sum / conf_count if conf_count else None
            return {
                "episode_id": episode_id,
                "run_id": run_id,
                "nb_links": nb_links,
                "nb_pivot": nb_pivot,
                "nb_target": nb_target,
                "by_status": by_status,
                "avg_confidence": round(avg_confidence, 4) if avg_confidence is not None else None,
            }
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
        à partir des liens d'alignement. Chaque ligne : segment_id, text_segment, text_en, confidence_pivot,
        text_fr, confidence_fr, text_it, confidence_it.
        Au plus une valeur FR et une valeur IT par ligne (pivot) sont retournées (dernier lien target par langue).
        """
        links = self.query_alignment_for_episode(episode_id, run_id=run_id, status_filter=status_filter)
        segments = self.get_segments_for_episode(episode_id, kind="sentence")
        cues_en = self.get_cues_for_episode_lang(episode_id, "en")
        cues_fr = self.get_cues_for_episode_lang(episode_id, "fr")
        cues_it = self.get_cues_for_episode_lang(episode_id, "it")

        seg_by_id = {s["segment_id"]: (s.get("text") or "").strip() for s in segments}
        def cue_text(c: dict) -> str:
            return (c.get("text_clean") or c.get("text_raw") or "").strip()
        cue_en_by_id = {c["cue_id"]: cue_text(c) for c in cues_en}
        cue_fr_by_id = {c["cue_id"]: cue_text(c) for c in cues_fr}
        cue_it_by_id = {c["cue_id"]: cue_text(c) for c in cues_it}

        pivot_links = [lnk for lnk in links if lnk.get("role") == "pivot"]
        target_by_cue_en: dict[str, list[dict]] = {}
        for lnk in links:
            if lnk.get("role") != "target" or not lnk.get("cue_id"):
                continue
            cue_en = lnk["cue_id"]
            target_by_cue_en.setdefault(cue_en, []).append(lnk)

        result: list[dict] = []
        for pl in pivot_links:
            seg_id = pl.get("segment_id")
            cue_id_en = pl.get("cue_id")
            text_seg = seg_by_id.get(seg_id, "")
            text_en = cue_en_by_id.get(cue_id_en or "", "")
            conf_pivot = pl.get("confidence")
            text_fr = ""
            conf_fr = None
            text_it = ""
            conf_it = None
            for tl in target_by_cue_en.get(cue_id_en or "", []):
                lang = (tl.get("lang") or "").lower()
                cid_t = tl.get("cue_id_target")
                if lang == "fr" and cid_t:
                    text_fr = cue_fr_by_id.get(cid_t, "")
                    conf_fr = tl.get("confidence")
                elif lang == "it" and cid_t:
                    text_it = cue_it_by_id.get(cid_t, "")
                    conf_it = tl.get("confidence")
            result.append({
                "segment_id": seg_id,
                "text_segment": text_seg,
                "text_en": text_en,
                "confidence_pivot": conf_pivot,
                "text_fr": text_fr,
                "confidence_fr": conf_fr,
                "text_it": text_it,
                "confidence_it": conf_it,
            })
        return result
