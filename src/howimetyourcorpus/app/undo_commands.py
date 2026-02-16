"""Commandes Undo/Redo pour QUndoStack (Basse Priorité #3)."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from PySide6.QtGui import QUndoCommand

if TYPE_CHECKING:
    from howimetyourcorpus.core.storage.db import CorpusDB


class SetAlignStatusCommand(QUndoCommand):
    """Commande pour changer le statut d'un lien d'alignement (accept/reject)."""
    
    def __init__(
        self,
        db: CorpusDB,
        link_id: str,
        new_status: str,
        old_status: str,
        description: str | None = None
    ):
        super().__init__(description or f"Changer statut alignement → {new_status}")
        self.db = db
        self.link_id = link_id
        self.new_status = new_status
        self.old_status = old_status
    
    def redo(self) -> None:
        """Applique le nouveau statut."""
        self.db.set_align_status(self.link_id, self.new_status)
    
    def undo(self) -> None:
        """Restaure l'ancien statut."""
        self.db.set_align_status(self.link_id, self.old_status)


class EditAlignLinkCommand(QUndoCommand):
    """Commande pour modifier la cible d'un lien d'alignement."""
    
    def __init__(
        self,
        db: CorpusDB,
        link_id: str,
        new_target_id: str | None,
        old_target_id: str | None,
        new_status: str = "manual",
        old_status: str = "auto"
    ):
        super().__init__("Modifier lien alignement")
        self.db = db
        self.link_id = link_id
        self.new_target_id = new_target_id
        self.old_target_id = old_target_id
        self.new_status = new_status
        self.old_status = old_status
    
    def redo(self) -> None:
        """Applique la nouvelle cible."""
        with self.db.connection() as conn:
            conn.execute(
                "UPDATE align_links SET target_id = ?, status = ? WHERE link_id = ?",
                (self.new_target_id, self.new_status, self.link_id)
            )
            conn.commit()
    
    def undo(self) -> None:
        """Restaure l'ancienne cible."""
        with self.db.connection() as conn:
            conn.execute(
                "UPDATE align_links SET target_id = ?, status = ? WHERE link_id = ?",
                (self.old_target_id, self.old_status, self.link_id)
            )
            conn.commit()


class DeleteAlignRunCommand(QUndoCommand):
    """Commande pour supprimer un run d'alignement (avec backup des liens)."""
    
    def __init__(
        self,
        db: CorpusDB,
        run_id: str,
        episode_id: str
    ):
        super().__init__(f"Supprimer run alignement {run_id}")
        self.db = db
        self.run_id = run_id
        self.episode_id = episode_id
        self.backup_links: list[dict[str, Any]] = []
        self.backup_run: dict[str, Any] | None = None
        
        # Sauvegarder les données avant suppression
        self._backup_data()
    
    def _backup_data(self) -> None:
        """Sauvegarde les liens et métadonnées du run."""
        # Sauvegarder tous les liens
        self.backup_links = self.db.query_alignment_for_episode(
            self.episode_id,
            run_id=self.run_id
        )
        
        # Sauvegarder métadonnées du run
        with self.db.connection() as conn:
            cursor = conn.execute(
                "SELECT run_id, episode_id, timestamp, by_similarity FROM align_runs WHERE run_id = ?",
                (self.run_id,)
            )
            row = cursor.fetchone()
            if row:
                self.backup_run = {
                    "run_id": row[0],
                    "episode_id": row[1],
                    "timestamp": row[2],
                    "by_similarity": row[3]
                }
    
    def redo(self) -> None:
        """Supprime le run."""
        self.db.delete_align_run(self.run_id)
    
    def undo(self) -> None:
        """Restaure le run et ses liens."""
        if not self.backup_run:
            return
        
        with self.db.connection() as conn:
            # Restaurer le run
            conn.execute(
                "INSERT INTO align_runs (run_id, episode_id, timestamp, by_similarity) VALUES (?, ?, ?, ?)",
                (
                    self.backup_run["run_id"],
                    self.backup_run["episode_id"],
                    self.backup_run["timestamp"],
                    self.backup_run["by_similarity"]
                )
            )
            
            # Restaurer tous les liens
            for link in self.backup_links:
                conn.execute(
                    """INSERT INTO align_links 
                       (link_id, run_id, episode_id, role, source_id, target_id, confidence, status)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        link["link_id"],
                        link["run_id"],
                        link["episode_id"],
                        link["role"],
                        link["source_id"],
                        link["target_id"],
                        link["confidence"],
                        link["status"]
                    )
                )
            
            conn.commit()


class BulkAcceptLinksCommand(QUndoCommand):
    """Commande pour accepter en masse des liens d'alignement."""
    
    def __init__(
        self,
        db: CorpusDB,
        link_ids: list[str],
        count: int
    ):
        super().__init__(f"Accepter {count} lien(s)")
        self.db = db
        self.link_ids = link_ids
    
    def redo(self) -> None:
        """Accepte tous les liens."""
        with self.db.connection() as conn:
            for link_id in self.link_ids:
                conn.execute(
                    "UPDATE align_links SET status = 'accepted' WHERE link_id = ?",
                    (link_id,)
                )
            conn.commit()
    
    def undo(self) -> None:
        """Restaure le statut 'auto' pour tous les liens."""
        with self.db.connection() as conn:
            for link_id in self.link_ids:
                conn.execute(
                    "UPDATE align_links SET status = 'auto' WHERE link_id = ?",
                    (link_id,)
                )
            conn.commit()


class BulkRejectLinksCommand(QUndoCommand):
    """Commande pour rejeter en masse des liens d'alignement."""
    
    def __init__(
        self,
        db: CorpusDB,
        link_ids: list[str],
        count: int
    ):
        super().__init__(f"Rejeter {count} lien(s)")
        self.db = db
        self.link_ids = link_ids
    
    def redo(self) -> None:
        """Rejette tous les liens."""
        with self.db.connection() as conn:
            for link_id in self.link_ids:
                conn.execute(
                    "UPDATE align_links SET status = 'rejected' WHERE link_id = ?",
                    (link_id,)
                )
            conn.commit()
    
    def undo(self) -> None:
        """Restaure le statut 'auto' pour tous les liens."""
        with self.db.connection() as conn:
            for link_id in self.link_ids:
                conn.execute(
                    "UPDATE align_links SET status = 'auto' WHERE link_id = ?",
                    (link_id,)
                )
            conn.commit()


class DeleteSubtitleTrackCommand(QUndoCommand):
    """Commande pour supprimer une piste de sous-titres (avec backup)."""
    
    def __init__(
        self,
        db: CorpusDB,
        episode_id: str,
        lang: str,
        track_format: str
    ):
        super().__init__(f"Supprimer piste SRT {episode_id} ({lang})")
        self.db = db
        self.episode_id = episode_id
        self.lang = lang
        self.track_format = track_format
        self.backup_cues: list[dict[str, Any]] = []
        
        # Sauvegarder les cues avant suppression
        self._backup_data()
    
    def _backup_data(self) -> None:
        """Sauvegarde toutes les cues de la piste."""
        with self.db.connection() as conn:
            cursor = conn.execute(
                """SELECT cue_id, episode_id, lang, n, start_ms, end_ms, text, fmt
                   FROM subtitle_cues 
                   WHERE episode_id = ? AND lang = ? AND fmt = ?
                   ORDER BY n""",
                (self.episode_id, self.lang, self.track_format)
            )
            for row in cursor:
                self.backup_cues.append({
                    "cue_id": row[0],
                    "episode_id": row[1],
                    "lang": row[2],
                    "n": row[3],
                    "start_ms": row[4],
                    "end_ms": row[5],
                    "text": row[6],
                    "fmt": row[7]
                })
    
    def redo(self) -> None:
        """Supprime la piste."""
        with self.db.connection() as conn:
            conn.execute(
                "DELETE FROM subtitle_cues WHERE episode_id = ? AND lang = ? AND fmt = ?",
                (self.episode_id, self.lang, self.track_format)
            )
            conn.commit()
    
    def undo(self) -> None:
        """Restaure la piste."""
        with self.db.connection() as conn:
            for cue in self.backup_cues:
                conn.execute(
                    """INSERT INTO subtitle_cues 
                       (cue_id, episode_id, lang, n, start_ms, end_ms, text, fmt)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        cue["cue_id"],
                        cue["episode_id"],
                        cue["lang"],
                        cue["n"],
                        cue["start_ms"],
                        cue["end_ms"],
                        cue["text"],
                        cue["fmt"]
                    )
                )
            conn.commit()
