"""Stockage fichiers projet : layout, config, épisodes (RAW/CLEAN)."""

from __future__ import annotations

import json
import logging
import datetime
from pathlib import Path
from typing import Any

from howimetyourcorpus.core.models import ProjectConfig, SeriesIndex, TransformStats
from howimetyourcorpus.core.normalize.profiles import NormalizationProfile
from howimetyourcorpus.core.preparer import (
    DEFAULT_SEGMENTATION_OPTIONS,
    normalize_segmentation_options,
    validate_segmentation_options,
)
from howimetyourcorpus.core.preparer.status import PREP_STATUS_VALUES as PREPARER_STATUS_VALUES

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
        elif isinstance(v, bool):
            # bool doit être traité avant int/float (bool est un sous-type de int).
            lines.append(f"{k} = {str(v).lower()}")
        elif isinstance(v, (int, float)):
            lines.append(f"{k} = {v}")
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
        (root / ".cache").mkdir(exist_ok=True)  # Cache HTTP pour éviter requêtes répétées

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
        Format attendu : {"profiles": [{"id": "...", "merge_subtitle_breaks": true, 
                          "fix_double_spaces": true, "case_transform": "none", 
                          "custom_regex_rules": [{"pattern": "...", "replacement": "..."}], ...}]}
        """
        from howimetyourcorpus.core.normalize.profiles import validate_profiles_json, ProfileValidationError
        
        path = self.root_dir / self.PROFILES_JSON
        if not path.exists():
            return {}
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as e:
            # Syntaxe JSON invalide
            raise ValueError(f"Fichier profiles.json invalide (syntaxe JSON) : {e}")
        
        # Valider le schéma
        try:
            validate_profiles_json(data)
        except ProfileValidationError as e:
            raise ValueError(f"Fichier profiles.json invalide : {e}")
        
        out: dict[str, NormalizationProfile] = {}
        for p in data.get("profiles", []):
            pid = p.get("id") or ""
            if not pid or not isinstance(p.get("merge_subtitle_breaks"), bool):
                continue
            
            # Charger custom_regex_rules
            custom_regex = []
            if "custom_regex_rules" in p and isinstance(p["custom_regex_rules"], list):
                for rule in p["custom_regex_rules"]:
                    if isinstance(rule, dict) and "pattern" in rule and "replacement" in rule:
                        custom_regex.append((rule["pattern"], rule["replacement"]))
            
            out[pid] = NormalizationProfile(
                id=pid,
                merge_subtitle_breaks=bool(p.get("merge_subtitle_breaks", True)),
                max_merge_examples_in_debug=int(p.get("max_merge_examples_in_debug", 20)),
                fix_double_spaces=bool(p.get("fix_double_spaces", True)),
                fix_french_punctuation=bool(p.get("fix_french_punctuation", False)),
                normalize_apostrophes=bool(p.get("normalize_apostrophes", False)),
                normalize_quotes=bool(p.get("normalize_quotes", False)),
                strip_line_spaces=bool(p.get("strip_line_spaces", True)),
                case_transform=str(p.get("case_transform", "none")),
                custom_regex_rules=custom_regex,
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

    @staticmethod
    def _normalize_character_entry(raw: dict[str, Any]) -> dict[str, Any] | None:
        """Normalise une entrée personnage (id/canonical/names_by_lang) ou retourne None si vide."""
        if not isinstance(raw, dict):
            return None
        cid = (str(raw.get("id") or "")).strip()
        canonical = (str(raw.get("canonical") or "")).strip()
        if not cid and not canonical:
            return None
        cid = cid or canonical
        canonical = canonical or cid

        names_by_lang: dict[str, str] = {}
        raw_names = raw.get("names_by_lang")
        if isinstance(raw_names, dict):
            for lang, name in raw_names.items():
                lang_key = (str(lang or "")).strip().lower()
                label = (str(name or "")).strip()
                if lang_key and label:
                    names_by_lang[lang_key] = label

        return {
            "id": cid,
            "canonical": canonical,
            "names_by_lang": names_by_lang,
        }

    def _validate_character_catalog(self, characters: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """
        Valide le catalogue personnages:
        - id unique (insensible à la casse)
        - alias uniques (id/canonical/names_by_lang) entre personnages
        """
        normalized: list[dict[str, Any]] = []
        id_owner: dict[str, str] = {}
        token_owner: dict[str, str] = {}
        token_owner_display: dict[str, str] = {}
        duplicate_ids: list[str] = []
        token_conflicts: list[tuple[str, str, str]] = []

        for raw in characters or []:
            entry = self._normalize_character_entry(raw)
            if entry is None:
                continue
            cid = entry["id"]
            cid_key = cid.lower()
            prev_id = id_owner.get(cid_key)
            if prev_id is not None:
                duplicate_ids.append(cid)
                continue
            id_owner[cid_key] = cid
            normalized.append(entry)

            tokens = {cid, entry.get("canonical") or ""}
            tokens.update((entry.get("names_by_lang") or {}).values())
            for token in tokens:
                token_raw = (token or "").strip()
                if not token_raw:
                    continue
                token_key = token_raw.lower()
                prev_owner = token_owner.get(token_key)
                if prev_owner is not None and prev_owner != cid_key:
                    token_conflicts.append(
                        (
                            token_raw,
                            token_owner_display.get(token_key, prev_owner),
                            cid,
                        )
                    )
                    continue
                token_owner[token_key] = cid_key
                token_owner_display[token_key] = cid

        errors: list[str] = []
        if duplicate_ids:
            errors.append(
                "ID personnages dupliqués: " + ", ".join(sorted({x for x in duplicate_ids if x}))
            )
        if token_conflicts:
            preview = token_conflicts[:6]
            lines = [f"{token!r} ({left} / {right})" for token, left, right in preview]
            suffix = ""
            if len(token_conflicts) > len(preview):
                suffix = f" (+{len(token_conflicts) - len(preview)} autre(s))"
            errors.append("Collision d'alias personnages: " + "; ".join(lines) + suffix)
        if errors:
            raise ValueError("Catalogue personnages invalide: " + " | ".join(errors))
        return normalized

    def _validate_assignment_references(self, valid_character_ids: set[str]) -> None:
        """
        Vérifie que toutes les assignations référencent un character_id existant.
        """
        valid = {cid.lower() for cid in valid_character_ids if cid}
        if not valid:
            # Pas de catalogue: on autorise seulement absence d'assignations.
            orphan_ids = sorted(
                {
                    (a.get("character_id") or "").strip()
                    for a in self.load_character_assignments()
                    if (a.get("character_id") or "").strip()
                }
            )
            if orphan_ids:
                raise ValueError(
                    "Assignations invalides: aucun personnage défini mais des assignations existent "
                    f"({', '.join(orphan_ids[:8])}{'…' if len(orphan_ids) > 8 else ''})."
                )
            return

        orphan_ids = sorted(
            {
                cid
                for cid in (
                    (a.get("character_id") or "").strip()
                    for a in self.load_character_assignments()
                )
                if cid and cid.lower() not in valid
            }
        )
        if orphan_ids:
            preview = ", ".join(orphan_ids[:8])
            suffix = "…" if len(orphan_ids) > 8 else ""
            raise ValueError(
                "Assignations invalides: character_id inconnus référencés: "
                f"{preview}{suffix}."
            )

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
        except Exception as exc:
            logger.warning("Impossible de charger %s: %s", path, exc)
            return []
        return data.get("characters", [])

    def save_character_names(self, characters: list[dict[str, Any]]) -> None:
        """
        Sauvegarde la liste des personnages du projet.

        Validation:
        - pas de collisions id/alias entre personnages
        - pas d'assignations référencant un character_id absent
        """
        normalized = self._validate_character_catalog(characters)
        self._validate_assignment_references({(c.get("id") or "").strip() for c in normalized})
        path = self.root_dir / self.CHARACTER_NAMES_JSON
        path.write_text(
            json.dumps({"characters": normalized}, ensure_ascii=False, indent=2),
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
        except Exception as exc:
            logger.warning("Impossible de charger %s: %s", path, exc)
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
        except Exception as exc:
            logger.warning("Impossible de charger %s: %s", path, exc)
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
        except Exception as exc:
            logger.warning("Impossible de charger %s: %s", path, exc)
            return {}

    def save_episode_preferred_profiles(self, preferred: dict[str, str]) -> None:
        """Sauvegarde le mapping episode_id -> profile_id."""
        path = self.root_dir / self.EPISODE_PREFERRED_PROFILES_JSON
        path.write_text(json.dumps(preferred, ensure_ascii=False, indent=2), encoding="utf-8")

    EPISODE_PREP_STATUS_JSON = "episode_prep_status.json"
    PREP_STATUS_VALUES = set(PREPARER_STATUS_VALUES)

    EPISODE_SEGMENTATION_OPTIONS_JSON = "episode_segmentation_options.json"

    def load_episode_prep_status(self) -> dict[str, dict[str, str]]:
        """
        Charge les statuts de préparation par fichier.

        Format persistant:
        {
          "statuses": {
            "S01E01": {"transcript": "edited", "srt_en": "verified"}
          }
        }
        """
        path = self.root_dir / self.EPISODE_PREP_STATUS_JSON
        if not path.exists():
            return {}
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception as exc:
            logger.warning("Impossible de charger %s: %s", path, exc)
            return {}
        raw_statuses = data.get("statuses", data if isinstance(data, dict) else {})
        if not isinstance(raw_statuses, dict):
            return {}
        statuses: dict[str, dict[str, str]] = {}
        for episode_id, by_source in raw_statuses.items():
            if not isinstance(episode_id, str) or not isinstance(by_source, dict):
                continue
            clean_by_source: dict[str, str] = {}
            for source_key, status in by_source.items():
                if not isinstance(source_key, str) or not isinstance(status, str):
                    continue
                s = status.strip().lower()
                if s in self.PREP_STATUS_VALUES:
                    clean_by_source[source_key.strip()] = s
            if clean_by_source:
                statuses[episode_id.strip()] = clean_by_source
        return statuses

    def save_episode_prep_status(self, statuses: dict[str, dict[str, str]]) -> None:
        """Sauvegarde les statuts de préparation par fichier."""
        clean: dict[str, dict[str, str]] = {}
        for episode_id, by_source in (statuses or {}).items():
            if not isinstance(episode_id, str) or not isinstance(by_source, dict):
                continue
            clean_by_source: dict[str, str] = {}
            for source_key, status in by_source.items():
                if not isinstance(source_key, str) or not isinstance(status, str):
                    continue
                s = status.strip().lower()
                if s in self.PREP_STATUS_VALUES:
                    clean_by_source[source_key.strip()] = s
            if clean_by_source:
                clean[episode_id.strip()] = clean_by_source
        path = self.root_dir / self.EPISODE_PREP_STATUS_JSON
        path.write_text(
            json.dumps({"statuses": clean}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def get_episode_prep_status(self, episode_id: str, source_key: str, default: str = "raw") -> str:
        """Retourne le statut de préparation pour (épisode, source)."""
        statuses = self.load_episode_prep_status()
        status = (
            statuses.get((episode_id or "").strip(), {})
            .get((source_key or "").strip(), "")
            .strip()
            .lower()
        )
        if status in self.PREP_STATUS_VALUES:
            return status
        d = (default or "raw").strip().lower()
        return d if d in self.PREP_STATUS_VALUES else "raw"

    def set_episode_prep_status(self, episode_id: str, source_key: str, status: str) -> None:
        """Définit le statut de préparation pour (épisode, source)."""
        ep = (episode_id or "").strip()
        source = (source_key or "").strip()
        st = (status or "").strip().lower()
        if not ep or not source:
            return
        if st not in self.PREP_STATUS_VALUES:
            raise ValueError(f"Statut de préparation invalide: {status!r}")
        statuses = self.load_episode_prep_status()
        if ep not in statuses:
            statuses[ep] = {}
        statuses[ep][source] = st
        self.save_episode_prep_status(statuses)

    def load_episode_segmentation_options(self) -> dict[str, dict[str, dict[str, Any]]]:
        """
        Charge les options de segmentation par (épisode, source).

        Format:
        {
          "options": {
            "S01E01": {
              "transcript": { ... options ... }
            }
          }
        }
        """
        path = self.root_dir / self.EPISODE_SEGMENTATION_OPTIONS_JSON
        if not path.exists():
            return {}
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception as exc:
            logger.warning("Impossible de charger %s: %s", path, exc)
            return {}
        raw = data.get("options", data if isinstance(data, dict) else {})
        if not isinstance(raw, dict):
            return {}
        out: dict[str, dict[str, dict[str, Any]]] = {}
        for episode_id, by_source in raw.items():
            if not isinstance(episode_id, str) or not isinstance(by_source, dict):
                continue
            clean_by_source: dict[str, dict[str, Any]] = {}
            for source_key, options in by_source.items():
                if not isinstance(source_key, str) or not isinstance(options, dict):
                    continue
                normalized = normalize_segmentation_options(options)
                try:
                    validate_segmentation_options(normalized)
                except ValueError:
                    continue
                clean_by_source[source_key.strip()] = normalized
            if clean_by_source:
                out[episode_id.strip()] = clean_by_source
        return out

    def save_episode_segmentation_options(self, options_map: dict[str, dict[str, dict[str, Any]]]) -> None:
        """Sauvegarde les options de segmentation par (épisode, source)."""
        clean: dict[str, dict[str, dict[str, Any]]] = {}
        for episode_id, by_source in (options_map or {}).items():
            if not isinstance(episode_id, str) or not isinstance(by_source, dict):
                continue
            clean_by_source: dict[str, dict[str, Any]] = {}
            for source_key, options in by_source.items():
                if not isinstance(source_key, str) or not isinstance(options, dict):
                    continue
                normalized = normalize_segmentation_options(options)
                validate_segmentation_options(normalized)
                clean_by_source[source_key.strip()] = normalized
            if clean_by_source:
                clean[episode_id.strip()] = clean_by_source
        path = self.root_dir / self.EPISODE_SEGMENTATION_OPTIONS_JSON
        path.write_text(
            json.dumps({"options": clean}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def get_episode_segmentation_options(
        self,
        episode_id: str,
        source_key: str,
        default: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Retourne les options de segmentation pour (épisode, source), normalisées."""
        ep = (episode_id or "").strip()
        src = (source_key or "").strip()
        options_map = self.load_episode_segmentation_options()
        source_options = options_map.get(ep, {}).get(src, {})
        merged = dict(DEFAULT_SEGMENTATION_OPTIONS)
        merged.update(normalize_segmentation_options(default))
        if isinstance(source_options, dict):
            merged.update(normalize_segmentation_options(source_options))
        return normalize_segmentation_options(merged)

    def set_episode_segmentation_options(self, episode_id: str, source_key: str, options: dict[str, Any]) -> None:
        """Définit les options de segmentation pour (épisode, source)."""
        ep = (episode_id or "").strip()
        src = (source_key or "").strip()
        if not ep or not src:
            return
        normalized = normalize_segmentation_options(options)
        validate_segmentation_options(normalized)
        options_map = self.load_episode_segmentation_options()
        options_map.setdefault(ep, {})[src] = normalized
        self.save_episode_segmentation_options(options_map)

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
        except Exception as exc:
            logger.warning("Impossible de charger %s: %s", path, exc)
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

    def get_episode_text_presence(self) -> tuple[set[str], set[str]]:
        """
        Retourne les IDs d'épisodes disposant d'un `raw.txt` et/ou `clean.txt`.

        Permet de calculer les statuts en lot côté UI (évite N appels disque par épisode).
        """
        raw_ids: set[str] = set()
        clean_ids: set[str] = set()
        episodes_dir = self.root_dir / "episodes"
        if not episodes_dir.exists():
            return raw_ids, clean_ids
        try:
            for ep_dir in episodes_dir.iterdir():
                if not ep_dir.is_dir():
                    continue
                episode_id = ep_dir.name
                if (ep_dir / "raw.txt").exists():
                    raw_ids.add(episode_id)
                if (ep_dir / "clean.txt").exists():
                    clean_ids.add(episode_id)
        except OSError as exc:
            logger.warning("Impossible de scanner %s: %s", episodes_dir, exc)
        return raw_ids, clean_ids

    def get_db_path(self) -> Path:
        return self.root_dir / "corpus.db"

    def get_cache_dir(self) -> Path:
        """Retourne le répertoire cache HTTP (créé à l'init projet)."""
        return self.root_dir / ".cache"

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

    def remove_episode_subtitle(self, episode_id: str, lang: str) -> None:
        """Supprime les fichiers sous-titres pour cet épisode et langue (.srt/.vtt et _cues.jsonl)."""
        d = self._subs_dir(episode_id)
        for name in [f"{lang}.srt", f"{lang}.vtt", f"{lang}_cues.jsonl"]:
            p = d / name
            if p.exists():
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

    @staticmethod
    def _safe_run_id(run_id: str) -> str:
        return (run_id or "").replace(":", "_").strip() or "_"

    def _align_grouping_path(self, episode_id: str, run_id: str) -> Path:
        return self.align_dir(episode_id) / f"{self._safe_run_id(run_id)}_groups.json"

    def save_align_grouping(self, episode_id: str, run_id: str, grouping: dict[str, Any]) -> None:
        """Sauvegarde un regroupement multi-langues non destructif d'un run d'alignement."""
        d = self.align_dir(episode_id)
        d.mkdir(parents=True, exist_ok=True)
        path = self._align_grouping_path(episode_id, run_id)
        path.write_text(json.dumps(grouping, ensure_ascii=False, indent=2), encoding="utf-8")

    def load_align_grouping(self, episode_id: str, run_id: str) -> dict[str, Any] | None:
        """Charge un regroupement multi-langues sauvegardé pour un run, si présent."""
        path = self._align_grouping_path(episode_id, run_id)
        if not path.exists():
            return None
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception as exc:
            logger.warning("Impossible de charger %s: %s", path, exc)
            return None
        if not isinstance(data, dict):
            return None
        return data

    def generate_align_grouping(
        self,
        db: Any,
        episode_id: str,
        run_id: str,
        *,
        tolerant: bool = True,
    ) -> dict[str, Any]:
        """
        Génère des groupes multi-langues à partir d'un run d'alignement, sans modifier la base.

        Les groupes agrègent des unités contiguës par personnage assigné.
        """
        run = db.get_align_run(run_id)
        if not run:
            raise ValueError(f"Run introuvable: {run_id}")
        pivot_lang = (run.get("pivot_lang") or "en").strip().lower()
        links = db.query_alignment_for_episode(episode_id, run_id=run_id)
        if not links:
            grouping = {
                "episode_id": episode_id,
                "run_id": run_id,
                "pivot_lang": pivot_lang,
                "languages": [pivot_lang],
                "generated_at": datetime.datetime.now(datetime.UTC).isoformat().replace("+00:00", "Z"),
                "non_destructive": True,
                "tolerant": bool(tolerant),
                "groups": [],
            }
            self.save_align_grouping(episode_id, run_id, grouping)
            return grouping

        assignments = [
            dict(a)
            for a in self.load_character_assignments()
            if (a.get("episode_id") or "").strip() == episode_id
        ]
        assign_segment: dict[str, str] = {}
        assign_cue: dict[str, str] = {}
        for a in assignments:
            source_type = (a.get("source_type") or "").strip().lower()
            source_id = (a.get("source_id") or "").strip()
            character_id = (a.get("character_id") or "").strip()
            if not source_id or not character_id:
                continue
            if source_type == "segment":
                assign_segment[source_id] = character_id
            elif source_type == "cue":
                assign_cue[source_id] = character_id

        characters = self.load_character_names()
        char_by_id = {
            (ch.get("id") or ch.get("canonical") or "").strip(): ch
            for ch in characters
            if (ch.get("id") or ch.get("canonical") or "").strip()
        }

        pivot_links = [lnk for lnk in links if (lnk.get("role") or "").strip().lower() == "pivot"]
        target_links = [lnk for lnk in links if (lnk.get("role") or "").strip().lower() == "target"]

        # Ordre des unités = ordre naturel des segments (n croissant).
        segments = db.get_segments_for_episode(episode_id)
        seg_by_id = {(s.get("segment_id") or "").strip(): s for s in segments}
        pivot_links.sort(
            key=lambda lnk: int((seg_by_id.get((lnk.get("segment_id") or "").strip(), {}) or {}).get("n") or 0)
        )

        target_by_pivot_cue: dict[str, list[dict[str, Any]]] = {}
        langs: set[str] = {pivot_lang}
        for lnk in target_links:
            cue_pivot = (lnk.get("cue_id") or "").strip()
            lang = (lnk.get("lang") or "").strip().lower()
            if not cue_pivot or not lang:
                continue
            langs.add(lang)
            target_by_pivot_cue.setdefault(cue_pivot, []).append(lnk)

        cues_by_lang: dict[str, dict[str, dict[str, Any]]] = {}
        for lang in sorted(langs):
            cues = db.get_cues_for_episode_lang(episode_id, lang) or []
            cues_by_lang[lang] = {(c.get("cue_id") or "").strip(): c for c in cues}

        def cue_text(cue_row: dict[str, Any] | None) -> str:
            if not cue_row:
                return ""
            return ((cue_row.get("text_clean") or cue_row.get("text_raw") or "")).strip()

        def character_label(character_id: str, lang: str) -> str:
            if not character_id:
                return ""
            ch = char_by_id.get(character_id) or {}
            names = ch.get("names_by_lang") or {}
            if isinstance(names, dict):
                value = (names.get(lang) or "").strip()
                if value:
                    return value
            return (ch.get("canonical") or character_id).strip()

        units: list[dict[str, Any]] = []
        for idx, pl in enumerate(pivot_links):
            segment_id = (pl.get("segment_id") or "").strip()
            cue_id_pivot = (pl.get("cue_id") or "").strip()
            if not segment_id:
                continue
            seg = seg_by_id.get(segment_id) or {}
            text_segment = (seg.get("text") or "").strip()
            cues_target_links = target_by_pivot_cue.get(cue_id_pivot, [])

            character_id = assign_segment.get(segment_id, "")
            if not character_id and cue_id_pivot:
                character_id = assign_cue.get(cue_id_pivot, "")
            if not character_id:
                for tl in cues_target_links:
                    cue_id_target = (tl.get("cue_id_target") or "").strip()
                    if cue_id_target and cue_id_target in assign_cue:
                        character_id = assign_cue[cue_id_target]
                        break

            speaker_fallback = (seg.get("speaker_explicit") or "").strip()
            speaker_label = character_label(character_id, pivot_lang) if character_id else speaker_fallback

            texts_by_lang: dict[str, str] = {pivot_lang: cue_text(cues_by_lang.get(pivot_lang, {}).get(cue_id_pivot))}
            conf_by_lang: dict[str, float | None] = {}

            for tl in cues_target_links:
                lang = (tl.get("lang") or "").strip().lower()
                cue_id_target = (tl.get("cue_id_target") or "").strip()
                if not lang or not cue_id_target:
                    continue
                txt = cue_text(cues_by_lang.get(lang, {}).get(cue_id_target))
                if not txt:
                    continue
                if texts_by_lang.get(lang):
                    if txt not in texts_by_lang[lang]:
                        texts_by_lang[lang] = f"{texts_by_lang[lang]}\n{txt}".strip()
                else:
                    texts_by_lang[lang] = txt
                conf = tl.get("confidence")
                conf_by_lang[lang] = float(conf) if conf is not None else None

            units.append(
                {
                    "index": idx,
                    "segment_id": segment_id,
                    "cue_id_pivot": cue_id_pivot,
                    "character_id": character_id,
                    "speaker_label": speaker_label,
                    "text_segment": text_segment,
                    "texts_by_lang": texts_by_lang,
                    "confidence_pivot": pl.get("confidence"),
                    "confidence_by_lang": conf_by_lang,
                }
            )

        groups: list[dict[str, Any]] = []
        active_key: str | None = None
        for unit in units:
            character_id = (unit.get("character_id") or "").strip()
            speaker_label = (unit.get("speaker_label") or "").strip()
            current_key: str | None = None
            if character_id:
                current_key = f"character:{character_id}"
            elif speaker_label:
                current_key = f"speaker:{speaker_label.lower()}"

            if groups:
                if current_key and current_key == active_key:
                    target = groups[-1]
                    target["segment_ids"].append(unit["segment_id"])
                    target["cue_ids_pivot"].append(unit.get("cue_id_pivot") or "")
                    if unit.get("text_segment"):
                        target["text_segment"] = (
                            (target.get("text_segment") or "").rstrip() + "\n" + unit["text_segment"]
                        ).strip()
                    for lang, txt in (unit.get("texts_by_lang") or {}).items():
                        if not txt:
                            continue
                        by_lang = target.setdefault("texts_by_lang", {})
                        if by_lang.get(lang):
                            by_lang[lang] = (by_lang[lang].rstrip() + "\n" + txt).strip()
                        else:
                            by_lang[lang] = txt
                    continue
                if current_key is None and tolerant and active_key is not None:
                    target = groups[-1]
                    target["segment_ids"].append(unit["segment_id"])
                    target["cue_ids_pivot"].append(unit.get("cue_id_pivot") or "")
                    if unit.get("text_segment"):
                        target["text_segment"] = (
                            (target.get("text_segment") or "").rstrip() + "\n" + unit["text_segment"]
                        ).strip()
                    for lang, txt in (unit.get("texts_by_lang") or {}).items():
                        if not txt:
                            continue
                        by_lang = target.setdefault("texts_by_lang", {})
                        if by_lang.get(lang):
                            by_lang[lang] = (by_lang[lang].rstrip() + "\n" + txt).strip()
                        else:
                            by_lang[lang] = txt
                    continue

            group_index = len(groups)
            groups.append(
                {
                    "group_id": f"{run_id}:group:{group_index}",
                    "character_id": character_id,
                    "speaker_label": speaker_label,
                    "segment_ids": [unit["segment_id"]],
                    "cue_ids_pivot": [unit.get("cue_id_pivot") or ""],
                    "text_segment": unit.get("text_segment") or "",
                    "texts_by_lang": dict(unit.get("texts_by_lang") or {}),
                    "confidence_pivot": unit.get("confidence_pivot"),
                    "confidence_by_lang": dict(unit.get("confidence_by_lang") or {}),
                }
            )
            active_key = current_key

        grouping = {
            "episode_id": episode_id,
            "run_id": run_id,
            "pivot_lang": pivot_lang,
            "languages": sorted(langs),
            "generated_at": datetime.datetime.now(datetime.UTC).isoformat().replace("+00:00", "Z"),
            "non_destructive": True,
            "tolerant": bool(tolerant),
            "groups": groups,
        }
        self.save_align_grouping(episode_id, run_id, grouping)
        return grouping

    @staticmethod
    def align_grouping_to_parallel_rows(grouping: dict[str, Any]) -> list[dict[str, Any]]:
        """Convertit un grouping multi-langues en lignes compatibles export concordancier."""
        groups = grouping.get("groups") if isinstance(grouping, dict) else []
        if not isinstance(groups, list):
            return []
        rows: list[dict[str, Any]] = []
        for grp in groups:
            if not isinstance(grp, dict):
                continue
            texts = grp.get("texts_by_lang") or {}
            conf_by_lang = grp.get("confidence_by_lang") or {}
            rows.append(
                {
                    "segment_id": grp.get("group_id") or "",
                    "personnage": grp.get("speaker_label") or grp.get("character_id") or "",
                    "text_segment": grp.get("text_segment") or "",
                    "text_en": (texts.get("en") if isinstance(texts, dict) else "") or "",
                    "confidence_pivot": grp.get("confidence_pivot"),
                    "text_fr": (texts.get("fr") if isinstance(texts, dict) else "") or "",
                    "confidence_fr": conf_by_lang.get("fr") if isinstance(conf_by_lang, dict) else None,
                    "text_it": (texts.get("it") if isinstance(texts, dict) else "") or "",
                    "confidence_it": conf_by_lang.get("it") if isinstance(conf_by_lang, dict) else None,
                }
            )
        return rows

    def propagate_character_names(
        self,
        db: Any,
        episode_id: str,
        run_id: str,
        languages_to_rewrite: set[str] | None = None,
    ) -> tuple[int, int]:
        """
        Propagation §8 : à partir des assignations et des liens d'alignement,
        met à jour segments.speaker_explicit et les text_clean des cues, puis réécrit les SRT.
        Si languages_to_rewrite est fourni, seules ces langues ont leur fichier SRT réécrit
        (par défaut toutes les langues modifiées sont réécrites).
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

        run = db.get_align_run(run_id)
        pivot_lang = (run.get("pivot_lang") or "en").strip().lower() if run else "en"

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
        cues_pivot = db.get_cues_for_episode_lang(episode_id, pivot_lang)
        for cue_id, cid in assign_cue.items():
            cue_row = next((c for c in cues_pivot if c.get("cue_id") == cue_id), None)
            if cue_row:
                text = (cue_row.get("text_clean") or cue_row.get("text_raw") or "").strip()
                prefix = name_for_lang(cid, pivot_lang) + ": "
                if not text.startswith(prefix):
                    new_text = prefix + text
                    db.update_cue_text_clean(cue_id, new_text)
                    nb_cue += 1
                    langs_updated.add(pivot_lang)

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
            if languages_to_rewrite is not None and lang not in languages_to_rewrite:
                continue
            cues = db.get_cues_for_episode_lang(episode_id, lang)
            if cues:
                srt_content = cues_to_srt(cues)
                self.save_episode_subtitle_content(episode_id, lang, srt_content, "srt")

        return nb_seg, nb_cue
