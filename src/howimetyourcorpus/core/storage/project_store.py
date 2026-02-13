"""Stockage fichiers projet : layout, config, épisodes (RAW/CLEAN)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from howimetyourcorpus.core.models import ProjectConfig, SeriesIndex, TransformStats
from howimetyourcorpus.core.normalize.profiles import NormalizationProfile


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
                    **({"source_id": e.source_id} if e.source_id else {}),
                }
                for e in series_index.episodes
            ],
        }
        path.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")

    PROFILES_JSON = "profiles.json"

    def load_custom_profiles(self) -> dict[str, NormalizationProfile]:
        """
        Charge les profils personnalisés du projet (fichier profiles.json à la racine).
        Format attendu : {"profiles": [{"id": "...", "merge_subtitle_breaks": true, "max_merge_examples_in_debug": 10}]}
        """
        path = self.root_dir / self.PROFILES_JSON
        if not path.exists():
            return {}
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return {}
        out: dict[str, NormalizationProfile] = {}
        for p in data.get("profiles", []):
            pid = p.get("id") or ""
            if not pid or not isinstance(p.get("merge_subtitle_breaks"), bool):
                continue
            out[pid] = NormalizationProfile(
                id=pid,
                merge_subtitle_breaks=bool(p.get("merge_subtitle_breaks", True)),
                max_merge_examples_in_debug=int(p.get("max_merge_examples_in_debug", 20)),
            )
        return out

    def save_custom_profiles(self, profiles: list[dict[str, Any]]) -> None:
        """Sauvegarde les profils personnalisés du projet (profiles.json)."""
        path = self.root_dir / self.PROFILES_JSON
        path.write_text(
            json.dumps({"profiles": profiles}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    CHARACTER_NAMES_JSON = "character_names.json"

    def load_character_names(self) -> list[dict[str, Any]]:
        """
        Charge la liste des personnages du projet (noms canoniques + par langue).
        Format : {"characters": [{"id": "...", "canonical": "...", "names_by_lang": {"en": "...", "fr": "..."}}]}
        """
        path = self.root_dir / self.CHARACTER_NAMES_JSON
        if not path.exists():
            return []
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return []
        return data.get("characters", [])

    def save_character_names(self, characters: list[dict[str, Any]]) -> None:
        """Sauvegarde la liste des personnages du projet."""
        path = self.root_dir / self.CHARACTER_NAMES_JSON
        path.write_text(
            json.dumps({"characters": characters}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    CHARACTER_ASSIGNMENTS_JSON = "character_assignments.json"

    def load_character_assignments(self) -> list[dict[str, Any]]:
        """Charge les assignations personnage (segment_id ou cue_id -> character_id)."""
        path = self.root_dir / self.CHARACTER_ASSIGNMENTS_JSON
        if not path.exists():
            return []
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return []
        return data.get("assignments", [])

    def save_character_assignments(self, assignments: list[dict[str, Any]]) -> None:
        """Sauvegarde les assignations personnage."""
        path = self.root_dir / self.CHARACTER_ASSIGNMENTS_JSON
        path.write_text(
            json.dumps({"assignments": assignments}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    SOURCE_PROFILE_DEFAULTS_JSON = "source_profile_defaults.json"

    def load_source_profile_defaults(self) -> dict[str, str]:
        """Charge le mapping source_id -> profile_id (profil par défaut par source)."""
        path = self.root_dir / self.SOURCE_PROFILE_DEFAULTS_JSON
        if not path.exists():
            return {}
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            return dict(data) if isinstance(data, dict) else {}
        except Exception:
            return {}

    def save_source_profile_defaults(self, defaults: dict[str, str]) -> None:
        """Sauvegarde le mapping source_id -> profile_id."""
        path = self.root_dir / self.SOURCE_PROFILE_DEFAULTS_JSON
        path.write_text(json.dumps(defaults, ensure_ascii=False, indent=2), encoding="utf-8")

    EPISODE_PREFERRED_PROFILES_JSON = "episode_preferred_profiles.json"

    def load_episode_preferred_profiles(self) -> dict[str, str]:
        """Charge le mapping episode_id -> profile_id (profil préféré par épisode)."""
        path = self.root_dir / self.EPISODE_PREFERRED_PROFILES_JSON
        if not path.exists():
            return {}
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            return dict(data) if isinstance(data, dict) else {}
        except Exception:
            return {}

    def save_episode_preferred_profiles(self, preferred: dict[str, str]) -> None:
        """Sauvegarde le mapping episode_id -> profile_id."""
        path = self.root_dir / self.EPISODE_PREFERRED_PROFILES_JSON
        path.write_text(json.dumps(preferred, ensure_ascii=False, indent=2), encoding="utf-8")

    LANGUAGES_JSON = "languages.json"
    DEFAULT_LANGUAGES = ["en", "fr", "it"]

    def load_project_languages(self) -> list[str]:
        """Charge la liste des langues du projet (sous-titres, personnages, etc.)."""
        path = self.root_dir / self.LANGUAGES_JSON
        if not path.exists():
            return list(self.DEFAULT_LANGUAGES)
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            langs = data.get("languages", data if isinstance(data, list) else [])
            return [str(x).strip().lower() for x in langs if str(x).strip()]
        except Exception:
            return list(self.DEFAULT_LANGUAGES)

    def save_project_languages(self, languages: list[str]) -> None:
        """Sauvegarde la liste des langues du projet."""
        path = self.root_dir / self.LANGUAGES_JSON
        path.write_text(
            json.dumps({"languages": [str(x).strip().lower() for x in languages if str(x).strip()]}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def load_series_index(self) -> SeriesIndex | None:
        """Charge l'index série depuis JSON. Retourne None si absent."""
        path = self.root_dir / "series_index.json"
        if not path.exists():
            return None
        from howimetyourcorpus.core.models import EpisodeRef
        obj = json.loads(path.read_text(encoding="utf-8"))
        episodes = []
        for e in obj.get("episodes", []):
            if not isinstance(e, dict):
                continue
            episodes.append(
                EpisodeRef(
                    episode_id=e.get("episode_id", ""),
                    season=int(e.get("season", 0)),
                    episode=int(e.get("episode", 0)),
                    title=e.get("title", "") or "",
                    url=e.get("url", "") or "",
                    source_id=e.get("source_id"),
                )
            )
        return SeriesIndex(
            series_title=obj.get("series_title", ""),
            series_url=obj.get("series_url", ""),
            episodes=episodes,
        )

    def _episode_dir(self, episode_id: str) -> Path:
        """Répertoire d'un épisode. Sanitize episode_id pour éviter path traversal (.., /, \)."""
        safe_id = (
            episode_id.replace("\\", "_").replace("/", "_").replace("..", "_").strip("._ ")
        )
        if not safe_id:
            safe_id = "_"
        return self.root_dir / "episodes" / safe_id

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

    def load_episode_notes(self, episode_id: str) -> str:
        """Charge les notes « à vérifier / à affiner » pour un épisode (Inspecteur)."""
        path = self._episode_dir(episode_id) / "notes.txt"
        if not path.exists():
            return ""
        return path.read_text(encoding="utf-8")

    def save_episode_notes(self, episode_id: str, text: str) -> None:
        """Sauvegarde les notes « à vérifier / à affiner » pour un épisode."""
        d = self._episode_dir(episode_id)
        d.mkdir(parents=True, exist_ok=True)
        (d / "notes.txt").write_text(text, encoding="utf-8")

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

    def get_episode_subtitle_path(self, episode_id: str, lang: str) -> tuple[Path, str] | None:
        """Retourne (chemin du fichier, "srt"|"vtt") si une piste existe pour cet épisode et langue."""
        d = self._subs_dir(episode_id)
        if (d / f"{lang}.srt").exists():
            return (d / f"{lang}.srt", "srt")
        if (d / f"{lang}.vtt").exists():
            return (d / f"{lang}.vtt", "vtt")
        return None

    def load_episode_subtitle_content(self, episode_id: str, lang: str) -> tuple[str, str] | None:
        """Charge le contenu brut du fichier SRT/VTT. Retourne (contenu, "srt"|"vtt") ou None."""
        res = self.get_episode_subtitle_path(episode_id, lang)
        if not res:
            return None
        path, fmt = res
        return (path.read_text(encoding="utf-8"), fmt)

    def save_episode_subtitle_content(self, episode_id: str, lang: str, content: str, fmt: str) -> Path:
        """Sauvegarde le contenu brut SRT/VTT (écrase le fichier). Retourne le chemin du fichier."""
        d = self._subs_dir(episode_id)
        d.mkdir(parents=True, exist_ok=True)
        ext = "srt" if fmt == "srt" else "vtt"
        path = d / f"{lang}.{ext}"
        path.write_text(content, encoding="utf-8")
        return path

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
