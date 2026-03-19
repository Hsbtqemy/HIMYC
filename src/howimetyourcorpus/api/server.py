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
from pydantic import BaseModel

from howimetyourcorpus.core.storage.db import CorpusDB
from howimetyourcorpus.core.storage.project_store import ProjectStore
from howimetyourcorpus.api.jobs import JOB_TYPES, get_job_store

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

        # Source transcript — état dérivé des fichiers sur disque
        # (le store natif ne supporte pas "segmented", on le détecte via segments.jsonl)
        from pathlib import Path as _Path
        _seg_file = _Path(store.root_dir) / "episodes" / eid / "segments.jsonl"
        if _seg_file.exists():
            _transcript_state = "segmented"
        elif store.has_episode_clean(eid):
            _transcript_state = "normalized"
        elif store.has_episode_raw(eid):
            _transcript_state = "raw"
        else:
            _transcript_state = ep_status.get("transcript", "unknown")

        sources: list[dict[str, Any]] = [
            {
                "source_key": "transcript",
                "available": store.has_episode_raw(eid),
                "has_clean": store.has_episode_clean(eid),
                "state": _transcript_state,
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


# ─── /episodes/{id}/sources/{source_key} POST (import — MX-005) ──────────────


class _TranscriptImport(BaseModel):
    content: str


class _SrtImport(BaseModel):
    content: str
    fmt: str = "srt"  # "srt" | "vtt"


@app.post(
    "/episodes/{episode_id}/sources/transcript",
    status_code=201,
    summary="Importer un transcript (texte brut) pour un episode",
)
def import_transcript(
    episode_id: str,
    body: _TranscriptImport,
    store: ProjectStore = Depends(_get_store),
) -> dict[str, Any]:
    if not body.content.strip():
        raise HTTPException(
            status_code=422,
            detail={
                "error": "EMPTY_CONTENT",
                "message": "Le contenu du transcript est vide.",
            },
        )
    ep_dir = store._episode_dir(episode_id)
    ep_dir.mkdir(parents=True, exist_ok=True)
    (ep_dir / "raw.txt").write_text(body.content, encoding="utf-8")
    store.set_episode_prep_status(episode_id, "transcript", "raw")
    return {"episode_id": episode_id, "source_key": "transcript", "state": "raw"}


@app.post(
    "/episodes/{episode_id}/sources/{source_key}",
    status_code=201,
    summary="Importer une piste SRT/VTT pour un episode",
)
def import_source(
    episode_id: str,
    source_key: str,
    body: _SrtImport,
    store: ProjectStore = Depends(_get_store),
) -> dict[str, Any]:
    if not source_key.startswith("srt_") or len(source_key) < 5:
        raise HTTPException(
            status_code=400,
            detail={
                "error": "INVALID_SOURCE_KEY",
                "message": (
                    f"Cle source invalide : « {source_key} ». "
                    "Format attendu : srt_<lang> (ex: srt_en, srt_fr)."
                ),
            },
        )
    lang = source_key[4:]
    fmt = body.fmt if body.fmt in ("srt", "vtt") else "srt"
    if not body.content.strip():
        raise HTTPException(
            status_code=422,
            detail={
                "error": "EMPTY_CONTENT",
                "message": f"Le contenu de la piste {source_key} est vide.",
            },
        )
    store.save_episode_subtitle_content(episode_id, lang, body.content, fmt)
    store.set_episode_prep_status(episode_id, source_key, "raw")
    return {
        "episode_id": episode_id,
        "source_key": source_key,
        "language": lang,
        "fmt": fmt,
        "state": "raw",
    }


# ─── /episodes/{id}/alignment_runs (MX-009) ──────────────────────────────────


@app.get(
    "/episodes/{episode_id}/alignment_runs",
    summary="Liste les runs d alignement pour un episode",
)
def list_alignment_runs(
    episode_id: str,
    store: ProjectStore = Depends(_get_store),
) -> dict[str, Any]:
    align_dir = store.align_dir(episode_id)
    runs: list[dict[str, Any]] = []
    if align_dir.is_dir():
        import json as _json
        for sub in sorted(align_dir.iterdir()):
            if not sub.is_dir():
                continue
            run_id = sub.name
            # Lire le rapport si présent
            report_path = sub / "report.json"
            if report_path.exists():
                try:
                    rep = _json.loads(report_path.read_text(encoding="utf-8"))
                    runs.append({
                        "run_id":       run_id,
                        "episode_id":   episode_id,
                        "pivot_lang":   rep.get("pivot_lang", ""),
                        "target_langs": rep.get("target_langs", []),
                        "segment_kind": rep.get("segment_kind", "sentence"),
                        "created_at":   rep.get("created_at", ""),
                    })
                except Exception:
                    runs.append({"run_id": run_id, "episode_id": episode_id})
    return {"episode_id": episode_id, "runs": runs}


# ─── /jobs (MX-006) ───────────────────────────────────────────────────────────


class _JobCreate(BaseModel):
    job_type: str
    episode_id: str
    source_key: str = ""
    params: dict[str, Any] = {}


@app.get("/jobs", summary="Liste des jobs avec statut")
def list_jobs(path: Path = Depends(_require_project_path)) -> dict[str, Any]:
    store = get_job_store(path)
    jobs = [j.to_dict() for j in store.list_all()]
    # Tri : running en premier, puis pending, puis par date desc
    order = {"running": 0, "pending": 1, "done": 2, "error": 3, "cancelled": 4}
    jobs.sort(key=lambda j: (order.get(j["status"], 9), j["created_at"]))
    return {"jobs": jobs}


@app.post("/jobs", status_code=201, summary="Creer un job")
def create_job(
    body: _JobCreate,
    path: Path = Depends(_require_project_path),
) -> dict[str, Any]:
    if body.job_type not in JOB_TYPES:
        raise HTTPException(
            status_code=400,
            detail={
                "error": "INVALID_JOB_TYPE",
                "message": (
                    f"Type de job invalide : {body.job_type!r}. "
                    f"Valeurs : {sorted(JOB_TYPES)}"
                ),
            },
        )
    store = get_job_store(path)
    job = store.create(body.job_type, body.episode_id, body.source_key, params=body.params)
    return job.to_dict()


@app.get("/jobs/{job_id}", summary="Statut d un job")
def get_job(
    job_id: str,
    path: Path = Depends(_require_project_path),
) -> dict[str, Any]:
    store = get_job_store(path)
    job = store.get(job_id)
    if not job:
        raise HTTPException(
            status_code=404,
            detail={
                "error": "JOB_NOT_FOUND",
                "message": f"Job {job_id!r} introuvable.",
            },
        )
    return job.to_dict()


@app.delete("/jobs/{job_id}", summary="Annuler un job pending")
def cancel_job(
    job_id: str,
    path: Path = Depends(_require_project_path),
) -> dict[str, Any]:
    store = get_job_store(path)
    if not store.get(job_id):
        raise HTTPException(
            status_code=404,
            detail={"error": "JOB_NOT_FOUND", "message": f"Job {job_id!r} introuvable."},
        )
    cancelled = store.cancel(job_id)
    if not cancelled:
        raise HTTPException(
            status_code=409,
            detail={
                "error": "JOB_NOT_CANCELLABLE",
                "message": "Seuls les jobs en 'pending' peuvent être annulés.",
            },
        )
    return {"job_id": job_id, "status": "cancelled"}
