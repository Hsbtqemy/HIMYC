"""Stockage fichiers projet : layout, config, épisodes (RAW/CLEAN)."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from howimetyourcorpus.core.models import ProjectConfig, SeriesIndex, TransformStats
from howimetyourcorpus.core.normalize.profiles import NormalizationProfile
from howimetyourcorpus.core.storage.align_grouping import (
    align_grouping_to_parallel_rows as _align_grouping_to_parallel_rows,
    generate_align_grouping as _generate_align_grouping,
)
from howimetyourcorpus.core.storage.character_propagation import (
    propagate_character_names as _propagate_character_names,
)
from howimetyourcorpus.core.storage.project_store_characters import (
    load_character_assignments as _load_character_assignments,
    load_character_names as _load_character_names,
    normalize_character_entry as _normalize_character_entry,
    save_character_assignments as _save_character_assignments,
    save_character_names as _save_character_names,
    validate_assignment_references as _validate_assignment_references,
    validate_character_catalog as _validate_character_catalog,
)
from howimetyourcorpus.core.storage.project_store_config import (
    init_project as _init_project,
    load_config_extra as _load_config_extra,
    load_project_config as _load_project_config,
    read_toml as _read_toml_impl,
    save_config_extra as _save_config_extra,
    save_config_main as _save_config_main,
    write_toml as _write_toml_impl,
)
from howimetyourcorpus.core.storage.project_store_profiles import (
    load_episode_preferred_profiles as _load_episode_preferred_profiles,
    load_source_profile_defaults as _load_source_profile_defaults,
    save_episode_preferred_profiles as _save_episode_preferred_profiles,
    save_source_profile_defaults as _save_source_profile_defaults,
)
from howimetyourcorpus.core.storage.project_store_prep import (
    get_episode_prep_status as _get_episode_prep_status,
    get_episode_segmentation_options as _get_episode_segmentation_options,
    load_episode_prep_status as _load_episode_prep_status,
    load_episode_segmentation_options as _load_episode_segmentation_options,
    load_project_languages as _load_project_languages,
    save_episode_prep_status as _save_episode_prep_status,
    save_episode_segmentation_options as _save_episode_segmentation_options,
    save_project_languages as _save_project_languages,
    set_episode_prep_status as _set_episode_prep_status,
    set_episode_segmentation_options as _set_episode_segmentation_options,
)
from howimetyourcorpus.core.storage.project_store_episode_io import (
    episode_dir as _episode_dir_impl,
    get_episode_text_presence as _get_episode_text_presence,
    get_episode_transform_meta_path as _get_episode_transform_meta_path,
    has_episode_clean as _has_episode_clean,
    has_episode_html as _has_episode_html,
    has_episode_raw as _has_episode_raw,
    load_episode_notes as _load_episode_notes,
    load_episode_text as _load_episode_text,
    load_episode_transform_meta as _load_episode_transform_meta,
    save_episode_clean as _save_episode_clean,
    save_episode_html as _save_episode_html,
    save_episode_notes as _save_episode_notes,
    save_episode_raw as _save_episode_raw,
)
from howimetyourcorpus.core.preparer.status import PREP_STATUS_VALUES as PREPARER_STATUS_VALUES
from howimetyourcorpus.core.storage.project_store_subtitles import (
    get_episode_subtitle_path as _get_episode_subtitle_path,
    has_episode_subs as _has_episode_subs,
    load_episode_subtitle_content as _load_episode_subtitle_content,
    normalize_subtitle_track as _normalize_subtitle_track,
    remove_episode_subtitle as _remove_episode_subtitle,
    save_episode_subtitle_content as _save_episode_subtitle_content,
    save_episode_subtitles as _save_episode_subtitles,
    subs_dir as _subs_dir_impl,
)

logger = logging.getLogger(__name__)


def _read_toml(path: Path) -> dict[str, Any]:
    """Lit un fichier TOML (stdlib tomllib en 3.11+)."""
    return _read_toml_impl(path)


def load_project_config(path: Path) -> dict[str, Any]:
    """API publique : charge la config projet depuis un fichier TOML."""
    return _load_project_config(path)


def _write_toml(path: Path, data: dict[str, Any]) -> None:
    """Écrit un fichier TOML (écriture manuelle pour éviter dépendance)."""
    _write_toml_impl(path, data)


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
        _init_project(config)

    def load_config_extra(self) -> dict[str, Any]:
        """Charge config.toml en dict (clés optionnelles : opensubtitles_api_key, series_imdb_id, etc.)."""
        return _load_config_extra(self)

    def save_config_extra(self, updates: dict[str, str | int | float | bool]) -> None:
        """Met à jour des clés dans config.toml (ex. opensubtitles_api_key, series_imdb_id)."""
        _save_config_extra(self, updates)

    def save_config_main(
        self,
        series_url: str = "",
        source_id: str | None = None,
        rate_limit_s: float | None = None,
        normalize_profile: str | None = None,
        project_name: str | None = None,
    ) -> None:
        """Met à jour les champs principaux de config.toml (URL série, source, etc.) sans écraser les clés extra."""
        _save_config_main(
            self,
            series_url=series_url,
            source_id=source_id,
            rate_limit_s=rate_limit_s,
            normalize_profile=normalize_profile,
            project_name=project_name,
        )

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
        return _normalize_character_entry(raw)

    def _validate_character_catalog(self, characters: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """
        Valide le catalogue personnages:
        - id unique (insensible à la casse)
        - alias uniques (id/canonical/names_by_lang) entre personnages
        """
        return _validate_character_catalog(characters)

    def _validate_assignment_references(self, valid_character_ids: set[str]) -> None:
        """
        Vérifie que toutes les assignations référencent un character_id existant.
        """
        _validate_assignment_references(self.load_character_assignments(), valid_character_ids)

    def load_character_names(self) -> list[dict[str, Any]]:
        """
        Charge la liste des personnages du projet (noms canoniques + par langue).
        Format : {"characters": [{"id": "...", "canonical": "...", "names_by_lang": {"en": "...", "fr": "..."}}]}
        """
        return _load_character_names(self, logger_obj=logger)

    def save_character_names(self, characters: list[dict[str, Any]]) -> None:
        """
        Sauvegarde la liste des personnages du projet.

        Validation:
        - pas de collisions id/alias entre personnages
        - pas d'assignations référencant un character_id absent
        """
        _save_character_names(self, characters)

    CHARACTER_ASSIGNMENTS_JSON = "character_assignments.json"

    def load_character_assignments(self) -> list[dict[str, Any]]:
        """Charge les assignations personnage (segment_id ou cue_id -> character_id)."""
        return _load_character_assignments(self, logger_obj=logger)

    def save_character_assignments(self, assignments: list[dict[str, Any]]) -> None:
        """Sauvegarde les assignations personnage."""
        _save_character_assignments(self, assignments)

    SOURCE_PROFILE_DEFAULTS_JSON = "source_profile_defaults.json"

    def load_source_profile_defaults(self) -> dict[str, str]:
        """Charge le mapping source_id -> profile_id (profil par défaut par source)."""
        return _load_source_profile_defaults(self, logger_obj=logger)

    def save_source_profile_defaults(self, defaults: dict[str, str]) -> None:
        """Sauvegarde le mapping source_id -> profile_id."""
        _save_source_profile_defaults(self, defaults)

    EPISODE_PREFERRED_PROFILES_JSON = "episode_preferred_profiles.json"

    def load_episode_preferred_profiles(self) -> dict[str, str]:
        """Charge le mapping episode_id -> profile_id (profil préféré par épisode)."""
        return _load_episode_preferred_profiles(self, logger_obj=logger)

    def save_episode_preferred_profiles(self, preferred: dict[str, str]) -> None:
        """Sauvegarde le mapping episode_id -> profile_id."""
        _save_episode_preferred_profiles(self, preferred)

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
        return _load_episode_prep_status(self, logger_obj=logger)

    def save_episode_prep_status(self, statuses: dict[str, dict[str, str]]) -> None:
        """Sauvegarde les statuts de préparation par fichier."""
        _save_episode_prep_status(self, statuses)

    def get_episode_prep_status(self, episode_id: str, source_key: str, default: str = "raw") -> str:
        """Retourne le statut de préparation pour (épisode, source)."""
        return _get_episode_prep_status(self, episode_id, source_key, default=default)

    def set_episode_prep_status(self, episode_id: str, source_key: str, status: str) -> None:
        """Définit le statut de préparation pour (épisode, source)."""
        _set_episode_prep_status(self, episode_id, source_key, status)

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
        return _load_episode_segmentation_options(self, logger_obj=logger)

    def save_episode_segmentation_options(self, options_map: dict[str, dict[str, dict[str, Any]]]) -> None:
        """Sauvegarde les options de segmentation par (épisode, source)."""
        _save_episode_segmentation_options(self, options_map)

    def get_episode_segmentation_options(
        self,
        episode_id: str,
        source_key: str,
        default: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Retourne les options de segmentation pour (épisode, source), normalisées."""
        return _get_episode_segmentation_options(self, episode_id, source_key, default=default)

    def set_episode_segmentation_options(self, episode_id: str, source_key: str, options: dict[str, Any]) -> None:
        """Définit les options de segmentation pour (épisode, source)."""
        _set_episode_segmentation_options(self, episode_id, source_key, options)

    LANGUAGES_JSON = "languages.json"
    DEFAULT_LANGUAGES = ["en", "fr", "it"]

    def load_project_languages(self) -> list[str]:
        """Charge la liste des langues du projet (sous-titres, personnages, etc.)."""
        return _load_project_languages(self, logger_obj=logger)

    def save_project_languages(self, languages: list[str]) -> None:
        """Sauvegarde la liste des langues du projet."""
        _save_project_languages(self, languages)

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
        return _episode_dir_impl(self, episode_id)

    def save_episode_html(self, episode_id: str, html: str) -> None:
        """Sauvegarde le HTML brut de la page épisode."""
        _save_episode_html(self, episode_id, html)

    def save_episode_raw(
        self, episode_id: str, raw_text: str, meta: dict[str, Any]
    ) -> None:
        """Sauvegarde le texte brut extrait + métadonnées parse."""
        _save_episode_raw(self, episode_id, raw_text, meta)

    def save_episode_clean(
        self,
        episode_id: str,
        clean_text: str,
        stats: TransformStats,
        debug: dict[str, Any],
    ) -> None:
        """Sauvegarde le texte normalisé + stats + debug (exemples merges)."""
        _save_episode_clean(self, episode_id, clean_text, stats, debug)

    def load_episode_text(self, episode_id: str, kind: str = "raw") -> str:
        """Charge le texte d'un épisode (kind = 'raw' ou 'clean')."""
        return _load_episode_text(self, episode_id, kind=kind)

    def has_episode_html(self, episode_id: str) -> bool:
        return _has_episode_html(self, episode_id)

    def has_episode_raw(self, episode_id: str) -> bool:
        return _has_episode_raw(self, episode_id)

    def has_episode_clean(self, episode_id: str) -> bool:
        return _has_episode_clean(self, episode_id)

    def get_episode_text_presence(self) -> tuple[set[str], set[str]]:
        """
        Retourne les IDs d'épisodes disposant d'un `raw.txt` et/ou `clean.txt`.

        Permet de calculer les statuts en lot côté UI (évite N appels disque par épisode).
        """
        return _get_episode_text_presence(self, logger_obj=logger)

    def get_db_path(self) -> Path:
        return self.root_dir / "corpus.db"

    def get_cache_dir(self) -> Path:
        """Retourne le répertoire cache HTTP (créé à l'init projet)."""
        return self.root_dir / ".cache"

    def get_episode_transform_meta_path(self, episode_id: str) -> Path:
        """Chemin du fichier transform_meta.json pour un épisode."""
        return _get_episode_transform_meta_path(self, episode_id)

    def load_episode_transform_meta(self, episode_id: str) -> dict[str, Any] | None:
        """Charge les métadonnées de transformation d'un épisode, ou None si absent."""
        return _load_episode_transform_meta(self, episode_id)

    def load_episode_notes(self, episode_id: str) -> str:
        """Charge les notes « à vérifier / à affiner » pour un épisode (Inspecteur)."""
        return _load_episode_notes(self, episode_id)

    def save_episode_notes(self, episode_id: str, text: str) -> None:
        """Sauvegarde les notes « à vérifier / à affiner » pour un épisode."""
        _save_episode_notes(self, episode_id, text)

    # ----- Phase 3: sous-titres (audit) -----

    def _subs_dir(self, episode_id: str) -> Path:
        """Répertoire episodes/<id>/subs/ pour les sous-titres."""
        return _subs_dir_impl(self, episode_id)

    def save_episode_subtitles(
        self,
        episode_id: str,
        lang: str,
        content: str,
        fmt: str,
        cues_audit: list[dict[str, Any]],
    ) -> None:
        """Sauvegarde le fichier sous-titre + audit cues (episodes/<id>/subs/<lang>.(srt|vtt) + <lang>_cues.jsonl)."""
        _save_episode_subtitles(self, episode_id, lang, content, fmt, cues_audit)

    def has_episode_subs(self, episode_id: str, lang: str) -> bool:
        """True si un fichier subs existe pour cet épisode et cette langue."""
        return _has_episode_subs(self, episode_id, lang)

    def get_episode_subtitle_path(self, episode_id: str, lang: str) -> tuple[Path, str] | None:
        """Retourne (chemin du fichier, "srt"|"vtt") si une piste existe pour cet épisode et langue."""
        return _get_episode_subtitle_path(self, episode_id, lang)

    def remove_episode_subtitle(self, episode_id: str, lang: str) -> None:
        """Supprime les fichiers sous-titres pour cet épisode et langue (.srt/.vtt et _cues.jsonl)."""
        _remove_episode_subtitle(self, episode_id, lang)

    def load_episode_subtitle_content(self, episode_id: str, lang: str) -> tuple[str, str] | None:
        """Charge le contenu brut du fichier SRT/VTT. Retourne (contenu, "srt"|"vtt") ou None."""
        return _load_episode_subtitle_content(self, episode_id, lang)

    def save_episode_subtitle_content(self, episode_id: str, lang: str, content: str, fmt: str) -> Path:
        """Sauvegarde le contenu brut SRT/VTT (écrase le fichier). Retourne le chemin du fichier."""
        return _save_episode_subtitle_content(self, episode_id, lang, content, fmt)

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
        return _normalize_subtitle_track(
            self,
            db,
            episode_id,
            lang,
            profile_id,
            rewrite_srt=rewrite_srt,
        )

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
        return _generate_align_grouping(
            self,
            db,
            episode_id,
            run_id,
            tolerant=tolerant,
        )

    @staticmethod
    def align_grouping_to_parallel_rows(grouping: dict[str, Any]) -> list[dict[str, Any]]:
        return _align_grouping_to_parallel_rows(grouping)

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
        return _propagate_character_names(
            self,
            db,
            episode_id,
            run_id,
            languages_to_rewrite=languages_to_rewrite,
        )
