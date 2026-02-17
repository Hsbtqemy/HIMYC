"""Modèles Qt pour la table/arbre épisodes et les résultats KWIC."""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import Qt, QAbstractItemModel, QAbstractTableModel, QModelIndex, QSortFilterProxyModel

from howimetyourcorpus.core.models import EpisodeRef, EpisodeStatus
from howimetyourcorpus.core.storage.db import CorpusDB, KwicHit
from howimetyourcorpus.core.storage.project_store import ProjectStore


def _node_season(node: tuple) -> int | None:
    """Retourne le numéro de saison si node est ('season', sn), sinon None."""
    if isinstance(node, tuple) and len(node) >= 2 and node[0] == "season":
        return node[1]
    return None


def _node_episode(node: tuple) -> EpisodeRef | None:
    """Retourne l'EpisodeRef si node est ('episode', ref), sinon None."""
    if isinstance(node, tuple) and len(node) >= 2 and node[0] == "episode":
        return node[1]
    return None


class EpisodesTreeModel(QAbstractItemModel):
    """Modèle d'arbre : racine → Saisons → Épisodes (même colonnes que la table + case à cocher)."""

    COLUMNS = ["checked", "episode_id", "season", "episode", "title", "status", "srt", "aligned"]
    HEADERS = ["", "ID", "Saison", "Épisode", "Titre", "Statut", "SRT", "Aligné"]
    COL_CHECKED = 0

    def __init__(self, parent=None):
        super().__init__(parent)
        self._episodes: list[EpisodeRef] = []
        self._season_numbers: list[int] = []
        self._season_episodes: dict[int, list[EpisodeRef]] = {}
        self._status_map: dict[str, str] = {}
        self._srt_map: dict[str, str] = {}
        self._align_map: dict[str, str] = {}
        self._checked: set[str] = set()
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
        self._season_numbers = sorted({ref.season for ref in self._episodes})
        self._season_episodes = {}
        for ref in self._episodes:
            self._season_episodes.setdefault(ref.season, []).append(ref)
        for k in self._season_episodes:
            self._season_episodes[k].sort(key=lambda r: (r.season, r.episode))
        self._refresh_status()
        self.endResetModel()

    def _refresh_status(self) -> None:
        try:
            self._status_map.clear()
            self._srt_map.clear()
            self._align_map.clear()
            if not self._episodes:
                return
            indexed = set(self._db.get_episode_ids_indexed()) if self._db else set()
            episode_ids = [ref.episode_id for ref in self._episodes]
            tracks_by_ep = self._db.get_tracks_for_episodes(episode_ids) if self._db else {}
            runs_by_ep = self._db.get_align_runs_for_episodes(episode_ids) if self._db else {}
            for ref in self._episodes:
                s = EpisodeStatus.NEW.value
                if self._store:
                    if self._store.has_episode_raw(ref.episode_id):
                        s = EpisodeStatus.FETCHED.value
                    if self._store.has_episode_clean(ref.episode_id):
                        s = EpisodeStatus.NORMALIZED.value
                if ref.episode_id in indexed:
                    s = EpisodeStatus.INDEXED.value
                self._status_map[ref.episode_id] = s
                if self._db:
                    tracks = tracks_by_ep.get(ref.episode_id, [])
                    langs = sorted({t.get("lang", "") for t in tracks if t.get("lang")})
                    self._srt_map[ref.episode_id] = ", ".join(langs) if langs else "—"
                    runs = runs_by_ep.get(ref.episode_id, [])
                    self._align_map[ref.episode_id] = "oui" if runs else "—"
                else:
                    self._srt_map[ref.episode_id] = "—"
                    self._align_map[ref.episode_id] = "—"
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.exception("Error in EpisodesTreeModel._refresh_status()")
            # Continue silencieusement pour ne pas bloquer l'UI

    def _node(self, index: QModelIndex) -> tuple | None:
        if not index.isValid():
            return None
        return index.internalPointer()

    def index(self, row: int, column: int, parent: QModelIndex = QModelIndex()) -> QModelIndex:
        if row < 0 or column < 0 or column >= len(self.COLUMNS):
            return QModelIndex()
        node = self._node(parent)
        if node is None:
            if row >= len(self._season_numbers):
                return QModelIndex()
            return self.createIndex(row, column, ("season", self._season_numbers[row]))
        sn = _node_season(node)
        if sn is not None:
            eps = self._season_episodes.get(sn, [])
            if row >= len(eps):
                return QModelIndex()
            return self.createIndex(row, column, ("episode", eps[row]))
        return QModelIndex()


    def parent(self, index: QModelIndex) -> QModelIndex:
        if not index.isValid():
            return QModelIndex()
        node = index.internalPointer()
        ref = _node_episode(node)
        if ref is not None:
            try:
                r = self._season_numbers.index(ref.season)
                return self.createIndex(r, 0, ("season", ref.season))
            except ValueError:
                pass
        return QModelIndex()

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:
        node = self._node(parent)
        if node is None:
            return len(self._season_numbers)
        if _node_season(node) is not None:
            sn = _node_season(node)
            return len(self._season_episodes.get(sn, []))
        return 0

    def columnCount(self, parent: QModelIndex = QModelIndex()) -> int:
        return len(self.COLUMNS)

    def data(self, index: QModelIndex, role=Qt.ItemDataRole.DisplayRole) -> Any:
        if not index.isValid():
            return None
        node = index.internalPointer()
        col = index.column()
        sn = _node_season(node)
        ref = _node_episode(node)
        if sn is not None:
            if role == Qt.ItemDataRole.DisplayRole and col == 1:
                return f"Saison {sn}"
            return None
        if ref is None:
            return None
        if col == self.COL_CHECKED and role == Qt.ItemDataRole.CheckStateRole:
            return Qt.CheckState.Checked if ref.episode_id in self._checked else Qt.CheckState.Unchecked
        if role == Qt.ItemDataRole.DisplayRole:
            if col == 1:
                return ref.episode_id
            if col == 2:
                return ref.season
            if col == 3:
                return ref.episode
            if col == 4:
                return ref.title or ""
            if col == 5:
                return self._status_map.get(ref.episode_id, EpisodeStatus.NEW.value)
            if col == 6:
                return self._srt_map.get(ref.episode_id, "—")
            if col == 7:
                return self._align_map.get(ref.episode_id, "—")
        return None

    def setData(self, index: QModelIndex, value: Any, role=Qt.ItemDataRole.EditRole) -> bool:
        if not index.isValid() or index.column() != self.COL_CHECKED or role != Qt.ItemDataRole.CheckStateRole:
            return False
        ref = _node_episode(index.internalPointer())
        if ref is None:
            return False
        if value == Qt.CheckState.Checked.value or value == Qt.CheckState.Checked:
            self._checked.add(ref.episode_id)
        else:
            self._checked.discard(ref.episode_id)
        self.dataChanged.emit(index, index, [Qt.ItemDataRole.CheckStateRole])
        return True

    def flags(self, index: QModelIndex) -> Qt.ItemFlag:
        if not index.isValid():
            return super().flags(index)
        f = super().flags(index)
        ref = _node_episode(index.internalPointer())
        if ref is not None and index.column() == self.COL_CHECKED:
            return f | Qt.ItemFlag.ItemIsUserCheckable
        return f

    def headerData(self, section: int, orientation: Qt.Orientation, role=Qt.ItemDataRole.DisplayRole) -> Any:
        if orientation == Qt.Orientation.Horizontal and role == Qt.ItemDataRole.DisplayRole:
            if 0 <= section < len(self.HEADERS):
                return self.HEADERS[section]
        return None

    def get_episode_id_for_index(self, index: QModelIndex) -> str | None:
        """Retourne l'episode_id pour un index (épisode uniquement)."""
        ref = _node_episode(index.internalPointer() if index.isValid() else None)
        return ref.episode_id if ref else None

    def get_episode_ids_selection(self, indices: list[QModelIndex]) -> list[str]:
        ids = []
        for ix in indices:
            if ix.isValid():
                eid = self.get_episode_id_for_index(ix)
                if eid and eid not in ids:
                    ids.append(eid)
        return ids

    def get_checked_episode_ids(self) -> list[str]:
        """Ordre des épisodes dans l'arbre (par saison puis numéro)."""
        out = []
        for sn in self._season_numbers:
            for ref in self._season_episodes.get(sn, []):
                if ref.episode_id in self._checked:
                    out.append(ref.episode_id)
        return out

    def get_episode_ids_for_season(self, season: int | None) -> list[str]:
        if season is None:
            return [ref.episode_id for ref in self._episodes]
        return [ref.episode_id for ref in self._season_episodes.get(season, [])]

    def get_season_numbers(self) -> list[int]:
        return list(self._season_numbers)

    def set_checked(self, episode_ids: set[str] | None = None, checked: bool = True) -> None:
        if episode_ids is None:
            episode_ids = {ref.episode_id for ref in self._episodes}
        if checked:
            self._checked |= episode_ids
        else:
            self._checked -= episode_ids
        self._emit_checked_changed()

    def set_all_checked(self, checked: bool) -> None:
        if checked:
            self._checked = {ref.episode_id for ref in self._episodes}
        else:
            self._checked.clear()
        self._emit_checked_changed()

    def _emit_checked_changed(self) -> None:
        if not self._episodes:
            return
        for sn in self._season_numbers:
            for row, ref in enumerate(self._season_episodes.get(sn, [])):
                ix = self.index(row, self.COL_CHECKED, self.index(self._season_numbers.index(sn), 0, QModelIndex()))
                self.dataChanged.emit(ix, ix, [Qt.ItemDataRole.CheckStateRole])

    def get_season_at_root_row(self, row: int) -> int | None:
        """Pour le proxy : numéro de saison à la ligne row sous la racine."""
        if 0 <= row < len(self._season_numbers):
            return self._season_numbers[row]
        return None

    def _key_episode(self, ref: EpisodeRef, column: int) -> Any:
        """Valeur de tri pour un épisode (colonne donnée)."""
        if column == 1:
            return (ref.episode_id or "").lower()
        if column == 2:
            return ref.season
        if column == 3:
            return ref.episode
        if column == 4:
            return (ref.title or "").lower()
        if column == 5:
            return (self._status_map.get(ref.episode_id, "") or "").lower()
        if column == 6:
            return (self._srt_map.get(ref.episode_id, "—") or "—").lower()
        if column == 7:
            return (self._align_map.get(ref.episode_id, "—") or "—").lower()
        return (ref.episode_id or "").lower()

    def sort(self, column: int, order: Qt.SortOrder = Qt.SortOrder.AscendingOrder) -> None:
        """Tri par colonne : saisons au niveau racine (par numéro), épisodes au niveau enfant (par colonne cliquée)."""
        self.layoutAboutToBeChanged.emit([], QAbstractItemModel.VerticalSortHint)
        reverse = order == Qt.SortOrder.DescendingOrder
        self._season_numbers = sorted(self._season_numbers, reverse=reverse)
        for sn in self._season_episodes:
            eps = self._season_episodes[sn]
            self._season_episodes[sn] = sorted(
                eps,
                key=lambda r: self._key_episode(r, column),
                reverse=reverse,
            )
        self.layoutChanged.emit([], QAbstractItemModel.VerticalSortHint)


class EpisodesTreeFilterProxyModel(QSortFilterProxyModel):
    """Proxy qui filtre l'arbre par saison (n'affiche que la saison choisie et ses épisodes)."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._season_filter: int | None = None

    def set_season_filter(self, season: int | None) -> None:
        self._season_filter = season
        self.invalidateFilter()

    def filterAcceptsRow(self, source_row: int, source_parent: QModelIndex) -> bool:
        if self._season_filter is None:
            return True
        sm = self.sourceModel()
        if not isinstance(sm, EpisodesTreeModel):
            return True
        if not source_parent.isValid():
            return sm.get_season_at_root_row(source_row) == self._season_filter
        return True


class EpisodesTableModel(QAbstractTableModel):
    """Modèle pour la table des épisodes (case à cocher, id, saison, épisode, titre, statut)."""

    COLUMNS = ["checked", "episode_id", "season", "episode", "title", "status", "srt", "aligned"]
    HEADERS = ["", "ID", "Saison", "Épisode", "Titre", "Statut", "SRT", "Aligné"]
    COL_CHECKED = 0

    def __init__(self, parent=None):
        super().__init__(parent)
        self._episodes: list[EpisodeRef] = []
        self._status_map: dict[str, str] = {}  # episode_id -> status
        self._srt_map: dict[str, str] = {}    # episode_id -> "EN, FR" or "—"
        self._align_map: dict[str, str] = {}  # episode_id -> "oui" or "—"
        self._checked: set[str] = set()  # episode_id des lignes cochées
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
        self._srt_map.clear()
        self._align_map.clear()
        if not self._episodes:
            return
        if self._db:
            indexed = set(self._db.get_episode_ids_indexed())
        else:
            indexed = set()
        episode_ids = [ref.episode_id for ref in self._episodes]
        tracks_by_ep = self._db.get_tracks_for_episodes(episode_ids) if self._db else {}
        runs_by_ep = self._db.get_align_runs_for_episodes(episode_ids) if self._db else {}
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
            if self._db:
                tracks = tracks_by_ep.get(ref.episode_id, [])
                langs = sorted({t.get("lang", "") for t in tracks if t.get("lang")})
                self._srt_map[ref.episode_id] = ", ".join(langs) if langs else "—"
                runs = runs_by_ep.get(ref.episode_id, [])
                self._align_map[ref.episode_id] = "oui" if runs else "—"
            else:
                self._srt_map[ref.episode_id] = "—"
                self._align_map[ref.episode_id] = "—"

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
        if col == self.COL_CHECKED and role == Qt.ItemDataRole.CheckStateRole:
            return (
                Qt.CheckState.Checked
                if ref.episode_id in self._checked
                else Qt.CheckState.Unchecked
            )
        if role == Qt.ItemDataRole.DisplayRole:
            if col == 1:
                return ref.episode_id
            if col == 2:
                return ref.season
            if col == 3:
                return ref.episode
            if col == 4:
                return ref.title or ""
            if col == 5:
                return self._status_map.get(ref.episode_id, EpisodeStatus.NEW.value)
            if col == 6:
                return self._srt_map.get(ref.episode_id, "—")
            if col == 7:
                return self._align_map.get(ref.episode_id, "—")
        return None

    def setData(self, index: QModelIndex, value: Any, role=Qt.ItemDataRole.EditRole) -> bool:
        if not index.isValid() or index.column() != self.COL_CHECKED or role != Qt.ItemDataRole.CheckStateRole:
            return False
        if index.row() >= len(self._episodes):
            return False
        ref = self._episodes[index.row()]
        if value == Qt.CheckState.Checked.value or value == Qt.CheckState.Checked:
            self._checked.add(ref.episode_id)
        else:
            self._checked.discard(ref.episode_id)
        self.dataChanged.emit(index, index, [Qt.ItemDataRole.CheckStateRole])
        return True

    def flags(self, index: QModelIndex) -> Qt.ItemFlag:
        if not index.isValid():
            return super().flags(index)
        f = super().flags(index)
        if index.column() == self.COL_CHECKED:
            return f | Qt.ItemFlag.ItemIsUserCheckable
        return f

    def headerData(self, section: int, orientation: Qt.Orientation, role=Qt.ItemDataRole.DisplayRole):
        if orientation == Qt.Orientation.Horizontal and role == Qt.ItemDataRole.DisplayRole:
            if 0 <= section < len(self.HEADERS):
                return self.HEADERS[section]
        return None

    def get_episode_at(self, row: int) -> EpisodeRef | None:
        if 0 <= row < len(self._episodes):
            return self._episodes[row]
        return None

    def get_episode_id_for_index(self, index: QModelIndex) -> str | None:
        """Retourne l'episode_id pour un index (ligne de la table)."""
        ref = self.get_episode_at(index.row()) if index.isValid() else None
        return ref.episode_id if ref else None

    def get_episode_ids_selection(self, indices: list[QModelIndex]) -> list[str]:
        rows = sorted(set(i.row() for i in indices if i.isValid()))
        return [self._episodes[r].episode_id for r in rows if 0 <= r < len(self._episodes)]

    def get_checked_episode_ids(self) -> list[str]:
        """Retourne les episode_id des lignes cochées (ordre des épisodes dans la table)."""
        return [ref.episode_id for ref in self._episodes if ref.episode_id in self._checked]

    def get_episode_ids_for_season(self, season: int | None) -> list[str]:
        """Retourne les episode_id des épisodes de la saison donnée. Si season est None, tous."""
        if season is None:
            return [ref.episode_id for ref in self._episodes]
        return [ref.episode_id for ref in self._episodes if ref.season == season]

    def get_season_numbers(self) -> list[int]:
        """Retourne la liste des numéros de saison présents dans les épisodes (triés)."""
        return sorted({ref.season for ref in self._episodes})

    def set_checked(self, episode_ids: set[str] | None = None, checked: bool = True) -> None:
        """Coche ou décoche les épisodes. Si episode_ids est None, agit sur tous."""
        if episode_ids is None:
            episode_ids = {ref.episode_id for ref in self._episodes}
        if checked:
            self._checked |= episode_ids
        else:
            self._checked -= episode_ids
        self._emit_checked_changed()

    def set_all_checked(self, checked: bool) -> None:
        """Coche ou décoche toutes les lignes."""
        if checked:
            self._checked = {ref.episode_id for ref in self._episodes}
        else:
            self._checked.clear()
        self._emit_checked_changed()

    def _emit_checked_changed(self) -> None:
        if not self._episodes:
            return
        top_left = self.index(0, self.COL_CHECKED)
        bottom_right = self.index(len(self._episodes) - 1, self.COL_CHECKED)
        self.dataChanged.emit(top_left, bottom_right, [Qt.ItemDataRole.CheckStateRole])


class EpisodesFilterProxyModel(QSortFilterProxyModel):
    """Proxy qui filtre les épisodes par numéro de saison (colonne Saison = 2)."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._season_filter: int | None = None  # None = toutes les saisons

    def set_season_filter(self, season: int | None) -> None:
        self._season_filter = season
        self.invalidateFilter()

    def filterAcceptsRow(self, source_row: int, source_parent: QModelIndex) -> bool:
        if self._season_filter is None:
            return True
        src = self.sourceModel()
        if not isinstance(src, EpisodesTableModel):
            return True
        ref = src.get_episode_at(source_row)
        if ref is None:
            return True
        return ref.season == self._season_filter


class KwicTableModel(QAbstractTableModel):
    """Modèle pour les résultats KWIC (épisode, titre, gauche, match, droite) + Pack Rapide C9: Highlight."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._hits: list[KwicHit] = []
        self._search_term: str = ""  # Pack Rapide C9: Stocker terme pour highlight

    def set_hits(self, hits: list[KwicHit], search_term: str = "") -> None:
        self.beginResetModel()
        self._hits = list(hits)
        self._search_term = search_term  # Pack Rapide C9
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
        # Pack Rapide C9: Highlight colonne "Match" (colonne 3)
        if role == Qt.ItemDataRole.BackgroundRole and index.column() == 3:
            from PySide6.QtGui import QBrush, QColor
            return QBrush(QColor("#FFEB3B"))  # Jaune
        if role == Qt.ItemDataRole.ForegroundRole and index.column() == 3:
            from PySide6.QtGui import QBrush, QColor
            return QBrush(QColor("#000000"))  # Texte noir pour contraste
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


def _truncate(s: str, max_len: int = 55) -> str:
    if not s:
        return ""
    s = (s or "").replace("\n", " ")
    return (s[:max_len] + "…") if len(s) > max_len else s


class AlignLinksTableModel(QAbstractTableModel):
    """Modèle pour la table des liens d'alignement (Phase 4). Affiche des extraits de texte si episode_id fourni."""

    COLUMNS = ["link_id", "segment_id", "cue_id", "cue_id_target", "lang", "role", "confidence", "status"]
    HEADERS = ["Link ID", "Segment (extrait)", "Cue pivot (extrait)", "Cue cible (extrait)", "Lang", "Rôle", "Confiance", "Statut"]

    def __init__(self, parent=None):
        super().__init__(parent)
        self._links: list[dict] = []
        self._db: CorpusDB | None = None

    def set_links(
        self,
        links: list[dict],
        db: CorpusDB | None = None,
        episode_id: str | None = None,
    ) -> None:
        self.beginResetModel()
        self._links = list(links)
        self._db = db
        if db and episode_id and links:
            segments_by_id = {s["segment_id"]: (s.get("text") or "") for s in db.get_segments_for_episode(episode_id)}
            cues_en = {c["cue_id"]: (c.get("text_clean") or c.get("text_raw") or "") for c in db.get_cues_for_episode_lang(episode_id, "en")}
            langs_seen = {((lnk.get("lang") or "fr") or "fr").lower() for lnk in links}
            cues_by_lang: dict[str, dict[str, str]] = {"en": cues_en}
            for lang in langs_seen:
                if lang != "en":
                    cues_by_lang[lang] = {c["cue_id"]: (c.get("text_clean") or c.get("text_raw") or "") for c in db.get_cues_for_episode_lang(episode_id, lang)}
            for lnk in self._links:
                seg_id = lnk.get("segment_id")
                cue_id = lnk.get("cue_id")
                cue_tid = lnk.get("cue_id_target")
                lang = ((lnk.get("lang") or "fr") or "fr").lower()
                lnk["_segment_text"] = _truncate(segments_by_id.get(seg_id, "")) if seg_id else ""
                lnk["_cue_text"] = _truncate(cues_en.get(cue_id, "")) if cue_id else ""
                cues_t = cues_by_lang.get(lang, {})
                lnk["_cue_target_text"] = _truncate(cues_t.get(cue_tid, "")) if cue_tid else ""
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
            if col == 1:
                return row.get("_segment_text") or str(row.get("segment_id", ""))
            if col == 2:
                return row.get("_cue_text") or str(row.get("cue_id", ""))
            if col == 3:
                return row.get("_cue_target_text") or str(row.get("cue_id_target", ""))
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
