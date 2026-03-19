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
from howimetyourcorpus.core.adapters.tvmaze import TvmazeAdapter
from howimetyourcorpus.core.adapters.subslikescript import SubslikescriptAdapter

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


# ─── /query (MX-022) ──────────────────────────────────────────────────────────

QUERY_SCOPES = frozenset(["episodes", "segments", "cues"])
QUERY_KINDS  = frozenset(["sentence", "utterance"])


class _QueryRequest(BaseModel):
    term:       str
    scope:      str                  = "segments"
    kind:       str | None           = None   # segments uniquement
    lang:       str | None           = None   # cues uniquement
    episode_id: str | None           = None   # filtre post-query par episode_id
    speaker:    str | None           = None   # filtre post-query par locuteur
    window:     int                  = 60
    limit:      int                  = 200


@app.post("/query", summary="Recherche KWIC concordancier (MX-022)")
def query_corpus(
    body: _QueryRequest,
    db: CorpusDB | None = Depends(_get_db_optional),
) -> dict[str, Any]:
    if db is None:
        raise HTTPException(
            status_code=503,
            detail={
                "error": "NO_DB",
                "message": "corpus.db introuvable — indexez d'abord le projet.",
            },
        )
    term = body.term.strip()
    if not term:
        raise HTTPException(
            status_code=422,
            detail={"error": "EMPTY_TERM", "message": "Le terme de recherche est vide."},
        )
    if body.scope not in QUERY_SCOPES:
        raise HTTPException(
            status_code=400,
            detail={
                "error": "INVALID_SCOPE",
                "message": f"Scope invalide : {body.scope!r}. Valeurs : {sorted(QUERY_SCOPES)}",
            },
        )
    if body.kind and body.kind not in QUERY_KINDS:
        raise HTTPException(
            status_code=400,
            detail={
                "error": "INVALID_KIND",
                "message": f"Kind invalide : {body.kind!r}. Valeurs : {sorted(QUERY_KINDS)}",
            },
        )

    limit = max(1, min(body.limit, 2000))
    window = max(10, min(body.window, 200))

    if body.scope == "segments":
        hits = db.query_kwic_segments(term, kind=body.kind, window=window, limit=limit)
    elif body.scope == "cues":
        hits = db.query_kwic_cues(term, lang=body.lang, window=window, limit=limit)
    else:
        hits = db.query_kwic(term, window=window, limit=limit)

    # Filtres post-query
    if body.episode_id:
        hits = [h for h in hits if h.episode_id == body.episode_id]
    if body.speaker:
        needle = body.speaker.lower()
        hits = [h for h in hits if h.speaker and needle in h.speaker.lower()]

    from dataclasses import asdict
    return {
        "term":  term,
        "scope": body.scope,
        "total": len(hits),
        "hits":  [asdict(h) for h in hits],
    }


# ─── /characters (MX-021c) ────────────────────────────────────────────────────

class _CharacterCatalogBody(BaseModel):
    characters: list[dict[str, Any]]

class _AssignmentsBody(BaseModel):
    assignments: list[dict[str, Any]]


@app.get("/characters", summary="Liste le catalogue personnages (MX-021c)")
def list_characters(store: ProjectStore = Depends(_get_store)) -> dict[str, Any]:
    return {"characters": store.load_character_names()}


@app.put("/characters", summary="Sauvegarde le catalogue personnages (MX-021c)")
def save_characters(
    body: _CharacterCatalogBody,
    store: ProjectStore = Depends(_get_store),
) -> dict[str, Any]:
    try:
        store.save_character_names(body.characters)
    except ValueError as exc:
        raise HTTPException(
            status_code=422,
            detail={"error": "INVALID_CATALOG", "message": str(exc)},
        ) from exc
    return {"saved": len(body.characters)}


@app.get("/assignments", summary="Liste les assignations personnage (MX-021c)")
def list_assignments(store: ProjectStore = Depends(_get_store)) -> dict[str, Any]:
    return {"assignments": store.load_character_assignments()}


@app.put("/assignments", summary="Sauvegarde les assignations personnage (MX-021c)")
def save_assignments(
    body: _AssignmentsBody,
    store: ProjectStore = Depends(_get_store),
) -> dict[str, Any]:
    try:
        store.save_character_assignments(body.assignments)
    except ValueError as exc:
        raise HTTPException(
            status_code=422,
            detail={"error": "INVALID_ASSIGNMENTS", "message": str(exc)},
        ) from exc
    return {"saved": len(body.assignments)}


# ─── /web — Sources web (MX-021b) ─────────────────────────────────────────────


class _TvmazeDiscoverBody(BaseModel):
    series_name: str


class _SubslikeDiscoverBody(BaseModel):
    series_url: str


class _SubslikeFetchBody(BaseModel):
    episode_id: str
    episode_url: str


def _episode_ref_to_dict(ep) -> dict[str, Any]:
    return {
        "episode_id": ep.episode_id,
        "season": ep.season,
        "episode": ep.episode,
        "title": ep.title,
        "url": ep.url,
    }


@app.post("/web/tvmaze/discover", summary="Découvrir une série via TVMaze (MX-021b)")
def web_tvmaze_discover(body: _TvmazeDiscoverBody) -> dict[str, Any]:
    """Recherche une série par nom sur TVMaze et retourne la liste des épisodes."""
    name = body.series_name.strip()
    if not name:
        raise HTTPException(
            status_code=422,
            detail={"error": "EMPTY_NAME", "message": "Le nom de la série est requis."},
        )
    try:
        adapter = TvmazeAdapter()
        index = adapter.discover_series(name)
    except Exception as exc:
        raise HTTPException(
            status_code=422,
            detail={"error": "TVMAZE_ERROR", "message": str(exc)},
        ) from exc
    return {
        "series_title": index.series_title,
        "series_url": index.series_url,
        "episode_count": len(index.episodes),
        "episodes": [_episode_ref_to_dict(ep) for ep in index.episodes],
    }


@app.post("/web/subslikescript/discover", summary="Découvrir une série via Subslikescript (MX-021b)")
def web_subslikescript_discover(body: _SubslikeDiscoverBody) -> dict[str, Any]:
    """Parse la page série Subslikescript et retourne la liste des épisodes."""
    url = body.series_url.strip()
    if not url:
        raise HTTPException(
            status_code=422,
            detail={"error": "EMPTY_URL", "message": "L'URL de la série est requise."},
        )
    try:
        adapter = SubslikescriptAdapter()
        index = adapter.discover_series(url)
    except Exception as exc:
        raise HTTPException(
            status_code=422,
            detail={"error": "SUBSLIKE_ERROR", "message": str(exc)},
        ) from exc
    return {
        "series_title": index.series_title,
        "series_url": index.series_url,
        "episode_count": len(index.episodes),
        "episodes": [_episode_ref_to_dict(ep) for ep in index.episodes],
    }


@app.post(
    "/web/subslikescript/fetch_transcript",
    status_code=201,
    summary="Télécharger et importer un transcript depuis Subslikescript (MX-021b)",
)
def web_subslikescript_fetch_transcript(
    body: _SubslikeFetchBody,
    store: ProjectStore = Depends(_get_store),
) -> dict[str, Any]:
    """Récupère le transcript d'un épisode depuis Subslikescript et le sauvegarde dans le projet."""
    episode_id = body.episode_id.strip()
    episode_url = body.episode_url.strip()
    if not episode_id or not episode_url:
        raise HTTPException(
            status_code=422,
            detail={"error": "MISSING_FIELDS", "message": "episode_id et episode_url sont requis."},
        )
    try:
        adapter = SubslikescriptAdapter()
        html = adapter.fetch_episode_html(episode_url)
        raw_text, _meta = adapter.parse_episode(html, episode_url)
    except Exception as exc:
        raise HTTPException(
            status_code=422,
            detail={"error": "FETCH_ERROR", "message": str(exc)},
        ) from exc
    ep_dir = store._episode_dir(episode_id)
    ep_dir.mkdir(parents=True, exist_ok=True)
    (ep_dir / "raw.txt").write_text(raw_text, encoding="utf-8")
    store.set_episode_prep_status(episode_id, "transcript", "raw")
    return {
        "episode_id": episode_id,
        "source_key": "transcript",
        "chars": len(raw_text),
        "state": "raw",
    }


# ─── /export (MX-021b Exporter) ───────────────────────────────────────────────


class _ExportBody(BaseModel):
    scope: str = "corpus"          # "corpus" | "segments"
    fmt: str = "txt"               # "txt" | "csv" | "json" | "tsv"
    use_clean: bool = True         # clean.txt si disponible, sinon raw.txt


@app.post("/export", status_code=201, summary="Exporter corpus ou segments (Exporter section)")
def run_export(
    body: _ExportBody,
    store: ProjectStore = Depends(_get_store),
) -> dict[str, Any]:
    """Génère un fichier d'export dans {project_path}/exports/ et retourne son chemin."""
    import json as _json
    from howimetyourcorpus.core.export_utils import (
        export_corpus_txt, export_corpus_csv, export_corpus_json, export_corpus_docx,
        export_segments_txt, export_segments_csv, export_segments_tsv,
    )
    from howimetyourcorpus.core.models import EpisodeRef

    scope = body.scope
    fmt = body.fmt
    if scope not in ("corpus", "segments"):
        raise HTTPException(422, detail={"error": "INVALID_SCOPE", "message": f"scope invalide: {scope}"})
    if fmt not in ("txt", "csv", "json", "tsv", "docx"):
        raise HTTPException(422, detail={"error": "INVALID_FORMAT", "message": f"format invalide: {fmt}"})

    index = store.load_series_index()
    if index is None or not index.episodes:
        raise HTTPException(422, detail={"error": "NO_EPISODES", "message": "Aucun épisode dans le projet."})

    export_dir = Path(store.root_dir) / "exports"
    export_dir.mkdir(exist_ok=True)
    out_path = export_dir / f"{scope}.{fmt}"

    if scope == "corpus":
        pairs: list[tuple[EpisodeRef, str]] = []
        for ep in index.episodes:
            kind = "clean" if (body.use_clean and store.has_episode_clean(ep.episode_id)) else "raw"
            text = store.load_episode_text(ep.episode_id, kind=kind)
            if text.strip():
                pairs.append((ep, text))
        if not pairs:
            raise HTTPException(422, detail={"error": "NO_TEXT", "message": "Aucun texte disponible pour l'export."})
        if fmt == "txt":    export_corpus_txt(pairs, out_path)
        elif fmt == "csv":  export_corpus_csv(pairs, out_path)
        elif fmt == "json": export_corpus_json(pairs, out_path)
        elif fmt == "docx": export_corpus_docx(pairs, out_path)
        else:
            raise HTTPException(422, detail={"error": "UNSUPPORTED_FORMAT", "message": f"Format {fmt} non supporté pour corpus."})
        return {"scope": scope, "fmt": fmt, "episodes": len(pairs), "path": str(out_path)}

    # scope == "segments"
    all_segments: list[dict[str, Any]] = []
    for ep in index.episodes:
        seg_path = Path(store.root_dir) / "episodes" / ep.episode_id / "segments.jsonl"
        if seg_path.exists():
            for line in seg_path.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if line:
                    try:
                        all_segments.append(_json.loads(line))
                    except Exception:
                        pass
    if not all_segments:
        raise HTTPException(422, detail={"error": "NO_SEGMENTS", "message": "Aucun segment disponible. Lancez la segmentation d'abord."})
    if fmt == "txt":    export_segments_txt(all_segments, out_path)
    elif fmt == "csv":  export_segments_csv(all_segments, out_path)
    elif fmt == "tsv":  export_segments_tsv(all_segments, out_path)
    else:
        raise HTTPException(422, detail={"error": "UNSUPPORTED_FORMAT", "message": f"Format {fmt} non supporté pour segments."})
    return {"scope": scope, "fmt": fmt, "segments": len(all_segments), "path": str(out_path)}
