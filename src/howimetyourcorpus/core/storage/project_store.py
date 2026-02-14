"""Stockage fichiers projet : layout, config, épisodes (RAW/CLEAN)."""

from __future__ import annotations

from datetime import datetime, timezone
import json
import logging
from pathlib import Path
from typing import Any

from howimetyourcorpus.core.models import ProjectConfig, SeriesIndex, TransformStats
from howimetyourcorpus.core.normalize.profiles import NormalizationProfile

logger = logging.getLogger(__name__)


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


def _load_json_with_default(path: Path, *, default: Any, context: str) -> Any:
    """Charge un JSON avec fallback + journalisation explicite en cas d'échec."""
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        logger.exception("Failed to load %s from %s", context, path)
        return default


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

    def load_config_extra(self) -> dict[str, Any]:
        """Charge config.toml en dict (clés optionnelles : opensubtitles_api_key, series_imdb_id, etc.)."""
        path = self.root_dir / "config.toml"
        if not path.exists():
            return {}
        return _read_toml(path)

    def save_config_extra(self, updates: dict[str, str | int | float | bool]) -> None:
        """Met à jour des clés dans config.toml (ex. opensubtitles_api_key, series_imdb_id)."""
        path = self.root_dir / "config.toml"
        data = dict(self.load_config_extra())
        for k, v in updates.items():
            if v is not None and v != "":
                data[k] = v
        if data:
            _write_toml(path, data)

    def save_config_main(
        self,
        series_url: str = "",
        source_id: str | None = None,
        rate_limit_s: float | None = None,
        normalize_profile: str | None = None,
        project_name: str | None = None,
    ) -> None:
        """Met à jour les champs principaux de config.toml (URL série, source, etc.) sans écraser les clés extra."""
        path = self.root_dir / "config.toml"
        if not path.exists():
            return
        data = dict(_read_toml(path))
        if series_url is not None:
            data["series_url"] = series_url
        if source_id is not None:
            data["source_id"] = source_id
        if rate_limit_s is not None:
            data["rate_limit_s"] = rate_limit_s
        if normalize_profile is not None:
            data["normalize_profile"] = normalize_profile
        if project_name is not None:
            data["project_name"] = project_name
        _write_toml(path, data)

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
        data = _load_json_with_default(path, default={}, context="custom profiles")
        if not isinstance(data, dict):
            return {}
        out: dict[str, NormalizationProfile] = {}
        for p in data.get("profiles", []):
            pid = p.get("id") or ""
            if not pid or not isinstance(p.get("merge_subtitle_breaks"), bool):
                continue
            try:
                max_examples = int(p.get("max_merge_examples_in_debug", 20))
            except Exception:
                max_examples = 20
            out[pid] = NormalizationProfile(
                id=pid,
                merge_subtitle_breaks=bool(p.get("merge_subtitle_breaks", True)),
                max_merge_examples_in_debug=max_examples,
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
        data = _load_json_with_default(path, default={}, context="character names")
        if not isinstance(data, dict):
            return []
        characters = data.get("characters", [])
        return characters if isinstance(characters, list) else []

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
        data = _load_json_with_default(path, default={}, context="character assignments")
        if not isinstance(data, dict):
            return []
        assignments = data.get("assignments", [])
        return assignments if isinstance(assignments, list) else []

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
        data = _load_json_with_default(path, default={}, context="source profile defaults")
        return dict(data) if isinstance(data, dict) else {}

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
        data = _load_json_with_default(path, default={}, context="episode preferred profiles")
        return dict(data) if isinstance(data, dict) else {}

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
        data = _load_json_with_default(path, default=list(self.DEFAULT_LANGUAGES), context="project languages")
        if isinstance(data, dict):
            langs = data.get("languages", [])
        elif isinstance(data, list):
            langs = data
        else:
            langs = []
        normalized = [str(x).strip().lower() for x in langs if str(x).strip()]
        return normalized if normalized else list(self.DEFAULT_LANGUAGES)

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
        obj = _load_json_with_default(path, default=None, context="series index")
        if not isinstance(obj, dict):
            return None
        episodes = []
        for e in obj.get("episodes", []):
            if not isinstance(e, dict):
                continue
            episode_id = str(e.get("episode_id", "")).strip().upper()
            if not episode_id:
                logger.warning("Skipping series-index episode without episode_id in %s: %r", path, e)
                continue
            try:
                season = int(e.get("season", 0))
                episode_num = int(e.get("episode", 0))
            except Exception:
                logger.warning("Skipping malformed episode entry in %s: %r", path, e)
                continue
            episodes.append(
                EpisodeRef(
                    episode_id=episode_id,
                    season=season,
                    episode=episode_num,
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
        r"""Répertoire d'un épisode. Sanitize episode_id pour éviter path traversal (.., /, \)."""
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
        *,
        profile_id: str | None = None,
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
            "normalized_at_utc": datetime.now(timezone.utc).isoformat(),
        }
        if profile_id:
            transform_meta["profile_id"] = profile_id
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
        obj = _load_json_with_default(path, default=None, context="episode transform meta")
        return obj if isinstance(obj, dict) else None

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

    def _subtitle_normalize_meta_path(self, episode_id: str, lang: str) -> Path:
        lang_norm = (lang or "").strip().lower()
        return self._subs_dir(episode_id) / f"{lang_norm}_normalize_meta.json"

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
        return self.get_episode_subtitle_path(episode_id, lang) is not None

    def get_episode_subtitle_path(self, episode_id: str, lang: str) -> tuple[Path, str] | None:
        """Retourne (chemin du fichier, "srt"|"vtt") si une piste existe pour cet épisode et langue."""
        d = self._subs_dir(episode_id)
        if not d.exists():
            return None
        lang_norm = (lang or "").strip().lower()
        candidates: list[Path] = []
        for p in d.iterdir():
            if not p.is_file():
                continue
            if p.stem.lower() != lang_norm:
                continue
            suffix = p.suffix.lower()
            if suffix not in {".srt", ".vtt"}:
                continue
            candidates.append(p)
        if not candidates:
            return None
        # Priorité SRT puis VTT pour préserver le comportement historique.
        candidates.sort(key=lambda p: (p.suffix.lower() != ".srt", p.name.lower()))
        best = candidates[0]
        return (best, "srt" if best.suffix.lower() == ".srt" else "vtt")

    def remove_episode_subtitle(self, episode_id: str, lang: str) -> None:
        """Supprime les fichiers sous-titres pour cet épisode et langue (.srt/.vtt, _cues.jsonl, meta)."""
        d = self._subs_dir(episode_id)
        if not d.exists():
            return
        lang_norm = (lang or "").strip().lower()
        cue_stem = f"{lang_norm}_cues"
        normalize_meta_stem = f"{lang_norm}_normalize_meta"
        for p in d.iterdir():
            if not p.is_file():
                continue
            stem = p.stem.lower()
            suffix = p.suffix.lower()
            if stem == lang_norm and suffix in {".srt", ".vtt"}:
                p.unlink()
            elif stem == cue_stem and suffix == ".jsonl":
                p.unlink()
            elif stem == normalize_meta_stem and suffix == ".json":
                p.unlink()

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

    def load_subtitle_normalize_meta(self, episode_id: str, lang: str) -> dict[str, Any] | None:
        """Charge la meta de normalisation d'une piste (profile_id, timestamp, compteurs)."""
        path = self._subtitle_normalize_meta_path(episode_id, lang)
        if not path.exists():
            return None
        obj = _load_json_with_default(path, default=None, context="subtitle normalize meta")
        return obj if isinstance(obj, dict) else None

    def normalize_subtitle_track(
        self,
        db: Any,
        episode_id: str,
        lang: str,
        profile_id: str,
        *,
        rewrite_srt: bool = False,
    ) -> int:
        """
        §11 — Applique un profil de normalisation aux cues d'une piste (text_raw → text_clean).
        Retourne le nombre de cues mises à jour.
        Si rewrite_srt=True, réécrit le fichier SRT sur disque à partir de text_clean (écrase l'original).
        """
        from howimetyourcorpus.core.normalize.profiles import get_profile
        from howimetyourcorpus.core.subtitles.parsers import cues_to_srt

        custom = self.load_custom_profiles()
        profile = get_profile(profile_id, custom)
        if not profile:
            return 0
        cues = db.get_cues_for_episode_lang(episode_id, lang)
        if not cues:
            return 0
        nb = 0
        for cue in cues:
            raw = (cue.get("text_raw") or "").strip()
            clean_text, _, _ = profile.apply(raw)
            cue_id = cue.get("cue_id")
            if cue_id:
                db.update_cue_text_clean(cue_id, clean_text)
                nb += 1
        if rewrite_srt and nb > 0:
            cues = db.get_cues_for_episode_lang(episode_id, lang)
            if cues:
                srt_content = cues_to_srt(cues)
                self.save_episode_subtitle_content(episode_id, lang, srt_content, "srt")
        if nb > 0:
            meta_path = self._subtitle_normalize_meta_path(episode_id, lang)
            meta_path.parent.mkdir(parents=True, exist_ok=True)
            meta_path.write_text(
                json.dumps(
                    {
                        "profile_id": profile_id,
                        "updated_cues": nb,
                        "rewrite_srt": bool(rewrite_srt),
                        "normalized_at_utc": datetime.now(timezone.utc).isoformat(),
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )
        return nb

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

    def propagate_character_names(
        self,
        db: Any,
        episode_id: str,
        run_id: str,
    ) -> tuple[int, int]:
        """
        Propagation §8 : à partir des assignations et des liens d'alignement,
        met à jour segments.speaker_explicit et les text_clean des cues, puis réécrit les SRT.
        Retourne (nb_segments_updated, nb_cues_updated).
        """
        from howimetyourcorpus.core.subtitles.parsers import cues_to_srt

        assignments = self.load_character_assignments()
        characters = self.load_character_names()
        char_by_id = {ch.get("id") or ch.get("canonical") or "": ch for ch in characters}
        episode_assignments = [a for a in assignments if a.get("episode_id") == episode_id]
        assign_segment: dict[str, str] = {}
        assign_cue: dict[str, str] = {}
        for a in episode_assignments:
            st = a.get("source_type") or ""
            sid = (a.get("source_id") or "").strip()
            cid = (a.get("character_id") or "").strip()
            if not sid or not cid:
                continue
            if st == "segment":
                assign_segment[sid] = cid
            else:
                assign_cue[sid] = cid

        links = db.query_alignment_for_episode(episode_id, run_id=run_id)
        for lnk in links:
            if lnk.get("role") == "pivot" and lnk.get("segment_id") and lnk.get("cue_id"):
                seg_id = lnk["segment_id"]
                cue_id = lnk["cue_id"]
                if seg_id in assign_segment and cue_id not in assign_cue:
                    assign_cue[cue_id] = assign_segment[seg_id]

        nb_seg = 0
        for seg_id, cid in assign_segment.items():
            db.update_segment_speaker(seg_id, cid)
            nb_seg += 1

        def name_for_lang(character_id: str, lang: str) -> str:
            ch = char_by_id.get(character_id) or {}
            names = ch.get("names_by_lang") or {}
            return names.get(lang) or ch.get("canonical") or character_id

        langs_updated: set[str] = set()
        nb_cue = 0
        for cue_id, cid in assign_cue.items():
            cues_en = db.get_cues_for_episode_lang(episode_id, "en")
            cue_row = next((c for c in cues_en if c.get("cue_id") == cue_id), None)
            if cue_row:
                text = (cue_row.get("text_clean") or cue_row.get("text_raw") or "").strip()
                prefix = name_for_lang(cid, "en") + ": "
                if not text.startswith(prefix):
                    new_text = prefix + text
                    db.update_cue_text_clean(cue_id, new_text)
                    nb_cue += 1
                    langs_updated.add("en")

        for lnk in links:
            if lnk.get("role") != "target" or not lnk.get("cue_id") or not lnk.get("cue_id_target"):
                continue
            cue_en = lnk["cue_id"]
            cue_target = lnk["cue_id_target"]
            lang = (lnk.get("lang") or "fr").strip().lower()
            if cue_en not in assign_cue:
                continue
            cid = assign_cue[cue_en]
            name = name_for_lang(cid, lang)
            cues_lang = db.get_cues_for_episode_lang(episode_id, lang)
            cue_row = next((c for c in cues_lang if c.get("cue_id") == cue_target), None)
            if cue_row:
                text = (cue_row.get("text_clean") or cue_row.get("text_raw") or "").strip()
                prefix = name + ": "
                if not text.startswith(prefix):
                    new_text = prefix + text
                    db.update_cue_text_clean(cue_target, new_text)
                    nb_cue += 1
                    langs_updated.add(lang)

        for lang in langs_updated:
            cues = db.get_cues_for_episode_lang(episode_id, lang)
            if cues:
                srt_content = cues_to_srt(cues)
                self.save_episode_subtitle_content(episode_id, lang, srt_content, "srt")

        return nb_seg, nb_cue
