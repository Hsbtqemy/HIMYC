"""Contrôleur des actions "Sources" de l'onglet Corpus."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QVBoxLayout,
    QLabel,
)

from howimetyourcorpus.core.adapters.base import AdapterRegistry
from howimetyourcorpus.core.models import EpisodeRef, SeriesIndex
from howimetyourcorpus.core.pipeline.tasks import FetchAndMergeSeriesIndexStep


class CorpusSourcesController:
    """Gère les actions liées à la constitution des sources du corpus."""

    def __init__(self, tab: Any) -> None:
        self._tab = tab

    def discover_merge(self) -> None:
        tab = self._tab
        context = tab._get_context()
        if not context or not context.get("config"):
            QMessageBox.warning(tab, "Corpus", "Ouvrez un projet d'abord.")
            return
        config = context["config"]
        dialog = QDialog(tab)
        dialog.setWindowTitle("Découvrir (fusionner une autre source)")
        layout = QFormLayout(dialog)
        url_edit = QLineEdit()
        url_edit.setPlaceholderText("https://subslikescript.com/series/...")
        layout.addRow("URL série (autre source):", url_edit)
        source_combo = QComboBox()
        source_combo.addItems(AdapterRegistry.list_ids() or ["subslikescript"])
        layout.addRow("Source:", source_combo)
        bbox = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        bbox.accepted.connect(dialog.accept)
        bbox.rejected.connect(dialog.reject)
        layout.addRow(bbox)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        url = url_edit.text().strip()
        if not url:
            QMessageBox.warning(tab, "Corpus", "Indiquez l'URL de la série.")
            return
        source_id = source_combo.currentText() or "subslikescript"
        step = FetchAndMergeSeriesIndexStep(url, source_id, config.user_agent)
        tab._run_job([step])

    @staticmethod
    def _parse_episode_ids(lines: list[str]) -> list[EpisodeRef]:
        refs: list[EpisodeRef] = []
        for line in lines:
            match = re.match(r"S(\d+)E(\d+)", line, re.IGNORECASE)
            if not match:
                continue
            refs.append(
                EpisodeRef(
                    episode_id=f"S{int(match.group(1)):02d}E{int(match.group(2)):02d}",
                    season=int(match.group(1)),
                    episode=int(match.group(2)),
                    title="",
                    url="",
                )
            )
        return refs

    def add_episodes_manually(self) -> None:
        tab = self._tab
        store = tab._get_store()
        dialog = QDialog(tab)
        dialog.setWindowTitle("Ajouter des épisodes")
        layout = QVBoxLayout(dialog)
        layout.addWidget(QLabel("Un episode_id par ligne (ex. S01E01, s01e02) :"))
        text_edit = QPlainTextEdit()
        text_edit.setPlaceholderText("S01E01\nS01E02\nS02E01")
        text_edit.setMinimumHeight(120)
        layout.addWidget(text_edit)
        bbox = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        bbox.accepted.connect(dialog.accept)
        bbox.rejected.connect(dialog.reject)
        layout.addWidget(bbox)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        lines = [line.strip().upper() for line in text_edit.toPlainText().strip().splitlines() if line.strip()]
        if not lines:
            QMessageBox.information(tab, "Corpus", "Aucun episode_id saisi.")
            return
        new_refs = self._parse_episode_ids(lines)
        if not new_refs:
            QMessageBox.warning(tab, "Corpus", "Aucun episode_id valide (format S01E01).")
            return
        index = store.load_series_index()
        existing_ids = {episode.episode_id for episode in (index.episodes or [])} if index else set()
        episodes = list(index.episodes or []) if index else []
        added_count = 0
        for ref in new_refs:
            if ref.episode_id in existing_ids:
                continue
            episodes.append(ref)
            existing_ids.add(ref.episode_id)
            added_count += 1
        store.save_series_index(
            SeriesIndex(
                series_title=index.series_title if index else "",
                series_url=index.series_url if index else "",
                episodes=episodes,
            )
        )
        tab.refresh()
        tab._refresh_after_episodes_added()
        tab._show_status(f"{added_count} épisode(s) ajouté(s).", 3000)

    def import_srt_selection(self) -> None:
        tab = self._tab
        store = tab._get_store()
        index = store.load_series_index()
        if not index or not index.episodes:
            QMessageBox.warning(
                tab,
                "Sous-titres",
                "Ajoutez d'abord des épisodes (via Transcripts → Découvrir ou Sous-titres → Ajouter épisodes).",
            )
            return
        ids = tab._get_selected_or_checked_episode_ids()
        if not ids:
            QMessageBox.warning(
                tab,
                "Sous-titres",
                "Cochez au moins un épisode ou sélectionnez des lignes dans l'arbre.",
            )
            return
        QMessageBox.information(
            tab,
            "Sous-titres",
            f"{len(ids)} épisode(s) sélectionné(s).\n\n"
            "Pour chaque épisode, vous pourrez importer un ou plusieurs fichiers .srt.\n"
            "Accédez à l'onglet Inspecteur pour gérer les pistes de sous-titres.",
        )
        if ids and tab._on_open_inspector:
            tab._on_open_inspector(sorted(ids)[0])

    @staticmethod
    def _detect_srt_files(folder_path: Path) -> list[tuple[str, Path]]:
        detected: list[tuple[str, Path]] = []
        srt_files = list(folder_path.glob("*.srt")) + list(folder_path.glob("**/*.srt"))
        for srt_file in srt_files:
            match = re.search(r"S(\d+)E(\d+)", srt_file.stem, re.IGNORECASE)
            if not match:
                continue
            episode_id = f"S{int(match.group(1)):02d}E{int(match.group(2)):02d}"
            detected.append((episode_id, srt_file))
        return detected

    def import_srt_batch(self) -> None:
        tab = self._tab
        store = tab._get_store()
        folder = QFileDialog.getExistingDirectory(
            tab,
            "Choisir le dossier contenant les fichiers .srt",
            "",
            QFileDialog.Option.ShowDirsOnly,
        )
        if not folder:
            return
        folder_path = Path(folder)
        detected = self._detect_srt_files(folder_path)
        if not detected:
            QMessageBox.warning(
                tab,
                "Sous-titres",
                f"Aucun fichier avec format SxxExx trouvé dans :\n{folder}\n\n"
                "Les fichiers .srt doivent contenir S01E01, S01E02, etc. dans leur nom.",
            )
            return

        recap = "\n".join([f"• {episode_id} ← {path.name}" for episode_id, path in detected[:10]])
        if len(detected) > 10:
            recap += f"\n... et {len(detected) - 10} autres"
        reply = QMessageBox.question(
            tab,
            "Import batch",
            f"{len(detected)} fichier(s) .srt détecté(s) :\n\n{recap}\n\n"
            "Continuer l'import automatique ?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        index = store.load_series_index()
        existing_ids = {episode.episode_id for episode in (index.episodes or [])} if index else set()
        episodes = list(index.episodes or []) if index else []
        new_episodes: list[str] = []
        for episode_id, _ in detected:
            if episode_id in existing_ids:
                continue
            match = re.match(r"S(\d+)E(\d+)", episode_id)
            if not match:
                continue
            episodes.append(
                EpisodeRef(
                    episode_id=episode_id,
                    season=int(match.group(1)),
                    episode=int(match.group(2)),
                    title="",
                    url="",
                )
            )
            existing_ids.add(episode_id)
            new_episodes.append(episode_id)

        if new_episodes:
            store.save_series_index(
                SeriesIndex(
                    series_title=index.series_title if index else "",
                    series_url=index.series_url if index else "",
                    episodes=episodes,
                )
            )

        QMessageBox.information(
            tab,
            "Import batch",
            f"✅ Détection terminée !\n\n"
            f"• {len(detected)} fichier(s) .srt détecté(s)\n"
            f"• {len(new_episodes)} nouvel(aux) épisode(s) créé(s)\n\n"
            "Pour terminer l'import, accédez à l'onglet Inspecteur pour chaque épisode "
            "et importez manuellement les pistes de sous-titres.\n\n"
            "💡 Une fonctionnalité d'import automatique complet sera ajoutée prochainement.",
        )
        tab.refresh()
        tab._refresh_after_episodes_added()

    def open_subtitles_manager(self) -> None:
        tab = self._tab
        store = tab._get_store()
        index = store.load_series_index()
        if not index or not index.episodes:
            QMessageBox.information(
                tab,
                "Sous-titres",
                "Ajoutez d'abord des épisodes avant de gérer les sous-titres.",
            )
            return
        if tab._on_open_inspector:
            tab._on_open_inspector(index.episodes[0].episode_id)
            return
        QMessageBox.information(
            tab,
            "Sous-titres",
            "Accédez à l'onglet Inspecteur pour gérer les pistes de sous-titres de chaque épisode.",
        )
