"""API serveur HIMYC — backend HTTP pour le frontend Tauri (MX-003).

Usage :
    HIMYC_PROJECT_PATH=/path/to/project \\
    uvicorn howimetyourcorpus.api.server:app --port 8765 --reload

Le chemin projet est lu depuis la variable d environnement HIMYC_PROJECT_PATH.
Le token HIMYC_API_TOKEN est optionnel (pilote : non requis).
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from howimetyourcorpus.core.storage.db import CorpusDB
from howimetyourcorpus.core.storage.project_store import ProjectStore

VERSION = "0.1.0"

app = FastAPI(
    title="HIMYC API",
    version=VERSION,
    description="Backend HTTP pour le frontend Tauri HIMYC (constitution, inspection, alignement).",
)

# CORS : dev Vite (1421) + Tauri WebView
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:1421",
        "tauri://localhost",
        "https://tauri.localhost",
    ],
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["*"],
)

# ─── Dépendances ──────────────────────────────────────────────────────────────


def _require_project_path() -> Path:
    """Lit HIMYC_PROJECT_PATH depuis l env et valide le dossier."""
    raw = os.environ.get("HIMYC_PROJECT_PATH", "").strip()
    if not raw:
        raise HTTPException(
            status_code=503,
            detail={
                "error": "NO_PROJECT",
                "message": (
                    "Variable d environnement HIMYC_PROJECT_PATH non definie. "
                    "Lancez : HIMYC_PROJECT_PATH=/chemin/projet uvicorn ... --port 8765"
                ),
            },
        )
    path = Path(raw)
    if not path.is_dir():
        raise HTTPException(
            status_code=503,
            detail={
                "error": "PROJECT_NOT_FOUND",
                "message": f"Dossier projet introuvable : {raw}",
            },
        )
    return path


def _get_store(path: Path = Depends(_require_project_path)) -> ProjectStore:
    return ProjectStore(path)


def _get_db_optional(path: Path = Depends(_require_project_path)) -> CorpusDB | None:
    """Retourne CorpusDB si corpus.db existe, sinon None (pas bloquant)."""
    db_path = path / "corpus.db"
    if not db_path.exists():
        return None
    return CorpusDB(db_path)


# ─── /health ──────────────────────────────────────────────────────────────────


@app.get("/health", summary="Healthcheck — verifie que le backend est en ligne")
def health() -> dict[str, str]:
    return {"status": "ok", "version": VERSION}


# ─── /config ──────────────────────────────────────────────────────────────────


@app.get("/config", summary="Configuration du projet courant")
def config(store: ProjectStore = Depends(_get_store)) -> dict[str, Any]:
    extra = store.load_config_extra()
    languages = store.load_project_languages()
    return {
        "project_name": extra.get("project_name", store.root_dir.name),
        "project_path": str(store.root_dir),
        "languages": languages,
        "normalize_profile": extra.get("normalize_profile", "default_en_v1"),
    }


# ─── /episodes ────────────────────────────────────────────────────────────────


@app.get("/episodes", summary="Liste des episodes avec sources et etats")
def list_episodes(
    store: ProjectStore = Depends(_get_store),
    db: CorpusDB | None = Depends(_get_db_optional),
) -> dict[str, Any]:
    index = store.load_series_index()
    if index is None:
        return {"series_title": None, "episodes": []}

    prep_status: dict[str, dict[str, str]] = {}
    try:
        prep_status = store.load_episode_prep_status()
    except Exception:
        pass

    # Tracks SRT par episode (batch si DB disponible)
    tracks_by_episode: dict[str, list[dict[str, Any]]] = {}
    if db is not None:
        episode_ids = [ep.episode_id for ep in index.episodes]
        try:
            tracks_by_episode = db.get_tracks_for_episodes(episode_ids)
        except Exception:
            pass

    episodes = []
    for ep in index.episodes:
        eid = ep.episode_id
        ep_status = prep_status.get(eid, {})

        # Source transcript
        sources: list[dict[str, Any]] = [
            {
                "source_key": "transcript",
                "available": store.has_episode_raw(eid),
                "has_clean": store.has_episode_clean(eid),
                "state": ep_status.get("transcript", "unknown"),
            }
        ]

        # Sources SRT (depuis DB si disponible)
        for track in tracks_by_episode.get(eid, []):
            lang = track.get("lang", "")
            if lang:
                sources.append(
                    {
                        "source_key": f"srt_{lang}",
                        "available": True,
                        "language": lang,
                        "state": ep_status.get(f"srt_{lang}", "unknown"),
                        "nb_cues": track.get("nb_cues", 0),
                        "format": track.get("fmt", "srt"),
                    }
                )

        episodes.append(
            {
                "episode_id": eid,
                "season": ep.season,
                "episode": ep.episode,
                "title": ep.title,
                "sources": sources,
            }
        )

    return {
        "series_title": index.series_title,
        "episodes": episodes,
    }


# ─── /episodes/{id}/sources/{source_key} ─────────────────────────────────────


@app.get(
    "/episodes/{episode_id}/sources/{source_key}",
    summary="Contenu d une source (transcript ou SRT)",
)
def get_episode_source(
    episode_id: str,
    source_key: str,
    store: ProjectStore = Depends(_get_store),
) -> dict[str, Any]:
    if source_key == "transcript":
        if not store.has_episode_raw(episode_id):
            raise HTTPException(
                status_code=404,
                detail={
                    "error": "SOURCE_NOT_FOUND",
                    "message": f"Transcript RAW introuvable pour l episode {episode_id}.",
                },
            )
        return {
            "episode_id": episode_id,
            "source_key": "transcript",
            "raw": store.load_episode_text(episode_id, kind="raw"),
            "clean": store.load_episode_text(episode_id, kind="clean"),
        }

    if source_key.startswith("srt_"):
        lang = source_key[4:]
        result = store.load_episode_subtitle_content(episode_id, lang)
        if result is None:
            raise HTTPException(
                status_code=404,
                detail={
                    "error": "SOURCE_NOT_FOUND",
                    "message": f"Piste SRT « {lang} » introuvable pour l episode {episode_id}.",
                },
            )
        content, fmt = result
        return {
            "episode_id": episode_id,
            "source_key": source_key,
            "language": lang,
            "format": fmt,
            "content": content,
        }

    raise HTTPException(
        status_code=400,
        detail={
            "error": "INVALID_SOURCE_KEY",
            "message": (
                f"Cle source invalide : « {source_key} ». "
                "Valeurs valides : transcript, srt_<lang> (ex: srt_en, srt_fr)."
            ),
        },
    )


# ─── /jobs (stub — MX-006) ────────────────────────────────────────────────────


@app.get("/jobs", summary="File de jobs (stub MX-006)")
def list_jobs(_store: ProjectStore = Depends(_get_store)) -> dict[str, Any]:
    """Stub MX-006 — la gestion des jobs sera implementee dans MX-006."""
    return {"jobs": [], "_note": "MX-006 implementera la queue, progression et reprise."}


@app.post("/jobs", summary="Creer un job (stub MX-006)")
def create_job(_store: ProjectStore = Depends(_get_store)) -> None:
    raise HTTPException(
        status_code=501,
        detail={
            "error": "NOT_IMPLEMENTED",
            "message": "Gestion des jobs implementee dans MX-006.",
        },
    )


@app.get("/jobs/{job_id}", summary="Statut d un job (stub MX-006)")
def get_job(job_id: str, _store: ProjectStore = Depends(_get_store)) -> None:
    raise HTTPException(
        status_code=404,
        detail={
            "error": "JOB_NOT_FOUND",
            "message": f"Job {job_id!r} introuvable. MX-006 implementera la gestion des jobs.",
        },
    )
