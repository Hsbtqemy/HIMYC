"""Modèles Qt pour la table épisodes et les résultats KWIC."""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import Qt, QAbstractTableModel, QModelIndex

from howimetyourcorpus.core.models import EpisodeRef, EpisodeStatus
from howimetyourcorpus.core.storage.db import CorpusDB, KwicHit
from howimetyourcorpus.core.storage.project_store import ProjectStore


class EpisodesTableModel(QAbstractTableModel):
    """Modèle pour la table des épisodes (id, saison, épisode, titre, statut)."""

    COLUMNS = ["episode_id", "season", "episode", "title", "status"]
    HEADERS = ["ID", "Saison", "Épisode", "Titre", "Statut"]

    def __init__(self, parent=None):
        super().__init__(parent)
        self._episodes: list[EpisodeRef] = []
        self._status_map: dict[str, str] = {}  # episode_id -> status
        self._store: ProjectStore | None = None
        self._db: CorpusDB | None = None

    def set_store(self, store: ProjectStore | None) -> None:
        self._store = store
        self._refresh_status()

    def set_db(self, db: CorpusDB | None) -> None:
        self._db = db
        self._refresh_status()

    def set_episodes(self, episodes: list[EpisodeRef]) -> None:
        self.beginResetModel()
        self._episodes = list(episodes)
        self._refresh_status()
        self.endResetModel()

    def _refresh_status(self) -> None:
        self._status_map.clear()
        if not self._episodes:
            return
        if self._db:
            indexed = set(self._db.get_episode_ids_indexed())
        else:
            indexed = set()
        for ref in self._episodes:
            s = EpisodeStatus.NEW.value
            if self._store:
                if self._store.has_episode_clean(ref.episode_id):
                    s = EpisodeStatus.NORMALIZED.value
                elif self._store.has_episode_raw(ref.episode_id):
                    s = EpisodeStatus.FETCHED.value
            if ref.episode_id in indexed:
                s = EpisodeStatus.INDEXED.value
            self._status_map[ref.episode_id] = s

    def rowCount(self, parent=QModelIndex()):
        if parent.isValid():
            return 0
        return len(self._episodes)

    def columnCount(self, parent=QModelIndex()):
        if parent.isValid():
            return 0
        return len(self.COLUMNS)

    def data(self, index: QModelIndex, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid() or index.row() >= len(self._episodes):
            return None
        ref = self._episodes[index.row()]
        col = index.column()
        if role == Qt.ItemDataRole.DisplayRole:
            if col == 0:
                return ref.episode_id
            if col == 1:
                return ref.season
            if col == 2:
                return ref.episode
            if col == 3:
                return ref.title or ""
            if col == 4:
                return self._status_map.get(ref.episode_id, EpisodeStatus.NEW.value)
        return None

    def headerData(self, section: int, orientation: Qt.Orientation, role=Qt.ItemDataRole.DisplayRole):
        if orientation == Qt.Orientation.Horizontal and role == Qt.ItemDataRole.DisplayRole:
            if 0 <= section < len(self.HEADERS):
                return self.HEADERS[section]
        return None

    def get_episode_at(self, row: int) -> EpisodeRef | None:
        if 0 <= row < len(self._episodes):
            return self._episodes[row]
        return None

    def get_episode_ids_selection(self, indices: list[QModelIndex]) -> list[str]:
        rows = sorted(set(i.row() for i in indices if i.isValid()))
        return [self._episodes[r].episode_id for r in rows if 0 <= r < len(self._episodes)]


class KwicTableModel(QAbstractTableModel):
    """Modèle pour les résultats KWIC (épisode, titre, gauche, match, droite)."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._hits: list[KwicHit] = []

    def set_hits(self, hits: list[KwicHit]) -> None:
        self.beginResetModel()
        self._hits = list(hits)
        self.endResetModel()

    def rowCount(self, parent=QModelIndex()):
        if parent.isValid():
            return 0
        return len(self._hits)

    def columnCount(self, parent=QModelIndex()):
        return 5

    def data(self, index: QModelIndex, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid() or index.row() >= len(self._hits):
            return None
        h = self._hits[index.row()]
        if role == Qt.ItemDataRole.DisplayRole:
            return [h.episode_id, h.title, h.left, h.match, h.right][index.column()]
        if role == Qt.ItemDataRole.UserRole:
            return h
        return None

    def headerData(self, section: int, orientation: Qt.Orientation, role=Qt.ItemDataRole.DisplayRole):
        if orientation == Qt.Orientation.Horizontal and role == Qt.ItemDataRole.DisplayRole:
            return ["Épisode", "Titre", "Contexte gauche", "Match", "Contexte droit"][section]
        return None

    def get_hit_at(self, row: int) -> KwicHit | None:
        if 0 <= row < len(self._hits):
            return self._hits[row]
        return None

    def get_all_hits(self) -> list[KwicHit]:
        """Retourne la liste complète des résultats KWIC (pour export)."""
        return list(self._hits)


class AlignLinksTableModel(QAbstractTableModel):
    """Modèle pour la table des liens d'alignement (Phase 4)."""

    COLUMNS = ["link_id", "segment_id", "cue_id", "cue_id_target", "lang", "role", "confidence", "status"]
    HEADERS = ["Link ID", "Segment", "Cue", "Cue target", "Lang", "Rôle", "Confiance", "Statut"]

    def __init__(self, parent=None):
        super().__init__(parent)
        self._links: list[dict] = []
        self._db: CorpusDB | None = None

    def set_links(self, links: list[dict], db: CorpusDB | None = None) -> None:
        self.beginResetModel()
        self._links = list(links)
        self._db = db
        self.endResetModel()

    def rowCount(self, parent=QModelIndex()):
        if parent.isValid():
            return 0
        return len(self._links)

    def columnCount(self, parent=QModelIndex()):
        if parent.isValid():
            return 0
        return len(self.COLUMNS)

    def data(self, index: QModelIndex, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid() or index.row() >= len(self._links):
            return None
        row = self._links[index.row()]
        col = index.column()
        if role == Qt.ItemDataRole.DisplayRole:
            key = self.COLUMNS[col] if 0 <= col < len(self.COLUMNS) else None
            if key:
                v = row.get(key)
                return str(v) if v is not None else ""
        if role == Qt.ItemDataRole.UserRole:
            return row
        return None

    def headerData(self, section: int, orientation: Qt.Orientation, role=Qt.ItemDataRole.DisplayRole):
        if orientation == Qt.Orientation.Horizontal and role == Qt.ItemDataRole.DisplayRole:
            if 0 <= section < len(self.HEADERS):
                return self.HEADERS[section]
        return None

    def get_link_at(self, row: int) -> dict | None:
        if 0 <= row < len(self._links):
            return self._links[row]
        return None
