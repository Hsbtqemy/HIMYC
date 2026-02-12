"""Stockage fichiers projet : layout, config, épisodes (RAW/CLEAN)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from howimetyourcorpus.core.models import ProjectConfig, SeriesIndex, TransformStats


def _read_toml(path: Path) -> dict[str, Any]:
    """Lit un fichier TOML (stdlib tomllib en 3.11+)."""
    try:
        import tomllib
    except ImportError:
        import tomli as tomllib  # type: ignore
    with open(path, "rb") as f:
        return tomllib.load(f)


def load_project_config(path: Path) -> dict[str, Any]:
    """API publique : charge la config projet depuis un fichier TOML."""
    return _read_toml(path)


def _write_toml(path: Path, data: dict[str, Any]) -> None:
    """Écrit un fichier TOML (écriture manuelle pour éviter dépendance)."""
    lines = []
    for k, v in data.items():
        if isinstance(v, str):
            # Échapper les guillemets dans la chaîne
            escaped = v.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")
            lines.append(f'{k} = "{escaped}"')
        elif isinstance(v, (int, float)):
            lines.append(f"{k} = {v}")
        elif isinstance(v, bool):
            lines.append(f"{k} = {str(v).lower()}")
        else:
            lines.append(f'{k} = "{v!s}"')
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


class ProjectStore:
    """
    Gestion du layout projet et I/O fichiers.
    Layout:
      projects/<project_name>/
        config.toml
        runs/
        series_index.json
        episodes/<episode_id>/
          page.html, raw.txt, clean.txt, parse_meta.json, transform_meta.json
        corpus.db
    """

    def __init__(self, root_dir: Path):
        self.root_dir = Path(root_dir)

    @staticmethod
    def init_project(config: ProjectConfig) -> None:
        """Crée le layout du projet et écrit config.toml."""
        root = Path(config.root_dir)
        root.mkdir(parents=True, exist_ok=True)
        (root / "runs").mkdir(exist_ok=True)
        (root / "episodes").mkdir(exist_ok=True)

        data = {
            "project_name": config.project_name,
            "source_id": config.source_id,
            "series_url": config.series_url,
            "rate_limit_s": config.rate_limit_s,
            "user_agent": config.user_agent,
            "normalize_profile": config.normalize_profile,
        }
        _write_toml(root / "config.toml", data)

    def save_series_index(self, series_index: SeriesIndex) -> None:
        """Sauvegarde l'index série en JSON."""
        path = self.root_dir / "series_index.json"
        obj = {
            "series_title": series_index.series_title,
            "series_url": series_index.series_url,
            "episodes": [
                {
                    "episode_id": e.episode_id,
                    "season": e.season,
                    "episode": e.episode,
                    "title": e.title,
                    "url": e.url,
                }
                for e in series_index.episodes
            ],
        }
        path.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")

    def load_series_index(self) -> SeriesIndex | None:
        """Charge l'index série depuis JSON. Retourne None si absent."""
        path = self.root_dir / "series_index.json"
        if not path.exists():
            return None
        from howimetyourcorpus.core.models import EpisodeRef
        obj = json.loads(path.read_text(encoding="utf-8"))
        episodes = [
            EpisodeRef(
                episode_id=e["episode_id"],
                season=e["season"],
                episode=e["episode"],
                title=e["title"],
                url=e["url"],
            )
            for e in obj.get("episodes", [])
        ]
        return SeriesIndex(
            series_title=obj.get("series_title", ""),
            series_url=obj.get("series_url", ""),
            episodes=episodes,
        )

    def _episode_dir(self, episode_id: str) -> Path:
        return self.root_dir / "episodes" / episode_id

    def save_episode_html(self, episode_id: str, html: str) -> None:
        """Sauvegarde le HTML brut de la page épisode."""
        d = self._episode_dir(episode_id)
        d.mkdir(parents=True, exist_ok=True)
        (d / "page.html").write_text(html, encoding="utf-8")

    def save_episode_raw(
        self, episode_id: str, raw_text: str, meta: dict[str, Any]
    ) -> None:
        """Sauvegarde le texte brut extrait + métadonnées parse."""
        d = self._episode_dir(episode_id)
        d.mkdir(parents=True, exist_ok=True)
        (d / "raw.txt").write_text(raw_text, encoding="utf-8")
        (d / "parse_meta.json").write_text(
            json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    def save_episode_clean(
        self,
        episode_id: str,
        clean_text: str,
        stats: TransformStats,
        debug: dict[str, Any],
    ) -> None:
        """Sauvegarde le texte normalisé + stats + debug (exemples merges)."""
        d = self._episode_dir(episode_id)
        d.mkdir(parents=True, exist_ok=True)
        (d / "clean.txt").write_text(clean_text, encoding="utf-8")
        transform_meta = {
            "raw_lines": stats.raw_lines,
            "clean_lines": stats.clean_lines,
            "merges": stats.merges,
            "kept_breaks": stats.kept_breaks,
            "duration_ms": stats.duration_ms,
            "debug": debug,
        }
        (d / "transform_meta.json").write_text(
            json.dumps(transform_meta, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    def load_episode_text(self, episode_id: str, kind: str = "raw") -> str:
        """Charge le texte d'un épisode (kind = 'raw' ou 'clean')."""
        d = self._episode_dir(episode_id)
        if kind == "clean":
            path = d / "clean.txt"
        else:
            path = d / "raw.txt"
        if not path.exists():
            return ""
        return path.read_text(encoding="utf-8")

    def has_episode_html(self, episode_id: str) -> bool:
        return (self._episode_dir(episode_id) / "page.html").exists()

    def has_episode_raw(self, episode_id: str) -> bool:
        return (self._episode_dir(episode_id) / "raw.txt").exists()

    def has_episode_clean(self, episode_id: str) -> bool:
        return (self._episode_dir(episode_id) / "clean.txt").exists()

    def get_db_path(self) -> Path:
        return self.root_dir / "corpus.db"

    def get_episode_transform_meta_path(self, episode_id: str) -> Path:
        """Chemin du fichier transform_meta.json pour un épisode."""
        return self._episode_dir(episode_id) / "transform_meta.json"

    def load_episode_transform_meta(self, episode_id: str) -> dict[str, Any] | None:
        """Charge les métadonnées de transformation d'un épisode, ou None si absent."""
        path = self.get_episode_transform_meta_path(episode_id)
        if not path.exists():
            return None
        return json.loads(path.read_text(encoding="utf-8"))

    # ----- Phase 3: sous-titres (audit) -----

    def _subs_dir(self, episode_id: str) -> Path:
        """Répertoire episodes/<id>/subs/ pour les sous-titres."""
        return self._episode_dir(episode_id) / "subs"

    def save_episode_subtitles(
        self,
        episode_id: str,
        lang: str,
        content: str,
        fmt: str,
        cues_audit: list[dict[str, Any]],
    ) -> None:
        """Sauvegarde le fichier sous-titre + audit cues (episodes/<id>/subs/<lang>.(srt|vtt) + <lang>_cues.jsonl)."""
        d = self._subs_dir(episode_id)
        d.mkdir(parents=True, exist_ok=True)
        ext = "srt" if fmt == "srt" else "vtt"
        (d / f"{lang}.{ext}").write_text(content, encoding="utf-8")
        (d / f"{lang}_cues.jsonl").write_text(
            "\n".join(json.dumps(c, ensure_ascii=False) for c in cues_audit),
            encoding="utf-8",
        )

    def has_episode_subs(self, episode_id: str, lang: str) -> bool:
        """True si un fichier subs existe pour cet épisode et cette langue."""
        d = self._subs_dir(episode_id)
        return (d / f"{lang}.srt").exists() or (d / f"{lang}.vtt").exists()

    # ----- Phase 4: alignement (audit) -----

    def align_dir(self, episode_id: str) -> Path:
        """Répertoire episodes/<id>/align/ pour les runs d'alignement."""
        return self._episode_dir(episode_id) / "align"

    def save_align_audit(self, episode_id: str, run_id: str, links_audit: list[dict], report: dict) -> None:
        """Sauvegarde l'audit d'un run : align/<run_id>.jsonl + report.json (run_id sans ':' pour Windows)."""
        d = self.align_dir(episode_id)
        d.mkdir(parents=True, exist_ok=True)
        safe_run_id = run_id.replace(":", "_")
        with (d / f"{safe_run_id}.jsonl").open("w", encoding="utf-8") as f:
            for row in links_audit:
                f.write(json.dumps(row, ensure_ascii=False) + "\n")
        (d / f"{safe_run_id}_report.json").write_text(
            json.dumps(report, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
