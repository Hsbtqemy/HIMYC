"""Tests integration bridge API HIMYC (MX-003).

Valide :
- /health toujours disponible
- Format d erreur standard (happy path + backend indisponible)
- /episodes sans projet configure → 503
- /episodes/{id}/sources/{key} sans projet → 503
- /config sans projet → 503
- /jobs → stub retourne liste vide
"""

from __future__ import annotations

import os
import json
import pytest
from fastapi.testclient import TestClient

from howimetyourcorpus.api.server import app

client = TestClient(app, raise_server_exceptions=False)


# ─── /health ──────────────────────────────────────────────────────────────────

def test_health_always_up():
    """GET /health retourne 200 et {"status": "ok"} meme sans projet configure."""
    r = client.get("/health")
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "ok"
    assert "version" in data


# ─── Format d erreur standard ─────────────────────────────────────────────────

def test_error_format_no_project_config():
    """Sans HIMYC_PROJECT_PATH, /config retourne 503 avec format d erreur standard."""
    env_backup = os.environ.pop("HIMYC_PROJECT_PATH", None)
    try:
        r = client.get("/config")
        assert r.status_code == 503
        detail = r.json()["detail"]
        assert "error" in detail
        assert "message" in detail
        assert detail["error"] == "NO_PROJECT"
    finally:
        if env_backup is not None:
            os.environ["HIMYC_PROJECT_PATH"] = env_backup


def test_error_format_no_project_episodes():
    """Sans HIMYC_PROJECT_PATH, /episodes retourne 503 avec format d erreur standard."""
    env_backup = os.environ.pop("HIMYC_PROJECT_PATH", None)
    try:
        r = client.get("/episodes")
        assert r.status_code == 503
        detail = r.json()["detail"]
        assert "error" in detail
        assert detail["error"] == "NO_PROJECT"
    finally:
        if env_backup is not None:
            os.environ["HIMYC_PROJECT_PATH"] = env_backup


def test_error_format_project_not_found():
    """Chemin projet inexistant → 503 PROJECT_NOT_FOUND."""
    os.environ["HIMYC_PROJECT_PATH"] = "/tmp/himyc_nonexistent_test_path_xyz"
    try:
        r = client.get("/episodes")
        assert r.status_code == 503
        detail = r.json()["detail"]
        assert detail["error"] == "PROJECT_NOT_FOUND"
    finally:
        del os.environ["HIMYC_PROJECT_PATH"]


def test_error_format_invalid_source_key(tmp_path):
    """Cle source invalide → 400 INVALID_SOURCE_KEY."""
    # Projet minimal : dossier vide suffit pour passer la validation chemin
    os.environ["HIMYC_PROJECT_PATH"] = str(tmp_path)
    try:
        r = client.get("/episodes/S01E01/sources/invalid_key")
        assert r.status_code == 400
        detail = r.json()["detail"]
        assert detail["error"] == "INVALID_SOURCE_KEY"
    finally:
        del os.environ["HIMYC_PROJECT_PATH"]


def test_error_format_source_not_found(tmp_path):
    """Transcript absent → 404 SOURCE_NOT_FOUND."""
    os.environ["HIMYC_PROJECT_PATH"] = str(tmp_path)
    try:
        r = client.get("/episodes/S01E01/sources/transcript")
        assert r.status_code == 404
        detail = r.json()["detail"]
        assert detail["error"] == "SOURCE_NOT_FOUND"
    finally:
        del os.environ["HIMYC_PROJECT_PATH"]


# ─── /episodes happy path (projet minimal) ────────────────────────────────────

def test_episodes_empty_project(tmp_path):
    """Projet sans series_index.json → retourne liste vide sans crash."""
    os.environ["HIMYC_PROJECT_PATH"] = str(tmp_path)
    try:
        r = client.get("/episodes")
        assert r.status_code == 200
        data = r.json()
        assert data["episodes"] == []
        assert data["series_title"] is None
    finally:
        del os.environ["HIMYC_PROJECT_PATH"]


def test_episodes_with_series_index(tmp_path):
    """Projet avec series_index.json → retourne les episodes."""
    # Creer un series_index.json minimal
    index = {
        "series_title": "Test Series",
        "series_url": "http://example.com",
        "episodes": [
            {
                "episode_id": "S01E01",
                "season": 1,
                "episode": 1,
                "title": "Pilot",
                "url": "http://example.com/S01E01",
                "source_id": None,
            }
        ],
    }
    (tmp_path / "series_index.json").write_text(json.dumps(index))
    os.environ["HIMYC_PROJECT_PATH"] = str(tmp_path)
    try:
        r = client.get("/episodes")
        assert r.status_code == 200
        data = r.json()
        assert data["series_title"] == "Test Series"
        assert len(data["episodes"]) == 1
        ep = data["episodes"][0]
        assert ep["episode_id"] == "S01E01"
        assert ep["title"] == "Pilot"
        # La source transcript doit etre listee
        sources = ep["sources"]
        assert any(s["source_key"] == "transcript" for s in sources)
    finally:
        del os.environ["HIMYC_PROJECT_PATH"]


def test_episodes_source_transcript_content(tmp_path):
    """Episode avec raw.txt → /sources/transcript retourne le contenu."""
    ep_dir = tmp_path / "episodes" / "S01E01"
    ep_dir.mkdir(parents=True)
    (ep_dir / "raw.txt").write_text("Hello world raw")
    (ep_dir / "clean.txt").write_text("Hello world clean")
    os.environ["HIMYC_PROJECT_PATH"] = str(tmp_path)
    try:
        r = client.get("/episodes/S01E01/sources/transcript")
        assert r.status_code == 200
        data = r.json()
        assert data["source_key"] == "transcript"
        assert "Hello world raw" in data["raw"]
        assert "Hello world clean" in data["clean"]
    finally:
        del os.environ["HIMYC_PROJECT_PATH"]


# ─── /config ──────────────────────────────────────────────────────────────────

def test_config_minimal_project(tmp_path):
    """Projet minimal → /config retourne au moins project_name et project_path."""
    os.environ["HIMYC_PROJECT_PATH"] = str(tmp_path)
    try:
        r = client.get("/config")
        assert r.status_code == 200
        data = r.json()
        assert "project_name" in data
        assert "project_path" in data
        assert "languages" in data
    finally:
        del os.environ["HIMYC_PROJECT_PATH"]


# ─── /jobs stub ───────────────────────────────────────────────────────────────

def test_jobs_stub_returns_empty_list(tmp_path):
    """GET /jobs retourne une liste vide (stub MX-006)."""
    os.environ["HIMYC_PROJECT_PATH"] = str(tmp_path)
    try:
        r = client.get("/jobs")
        assert r.status_code == 200
        assert r.json()["jobs"] == []
    finally:
        del os.environ["HIMYC_PROJECT_PATH"]


def test_jobs_post_stub_501(tmp_path):
    """POST /jobs retourne 501 NOT_IMPLEMENTED (stub MX-006)."""
    os.environ["HIMYC_PROJECT_PATH"] = str(tmp_path)
    try:
        r = client.post("/jobs", json={})
        assert r.status_code == 501
        assert r.json()["detail"]["error"] == "NOT_IMPLEMENTED"
    finally:
        del os.environ["HIMYC_PROJECT_PATH"]


def test_jobs_get_by_id_stub_404(tmp_path):
    """GET /jobs/{id} retourne 404 JOB_NOT_FOUND (stub MX-006)."""
    os.environ["HIMYC_PROJECT_PATH"] = str(tmp_path)
    try:
        r = client.get("/jobs/some-job-id")
        assert r.status_code == 404
        assert r.json()["detail"]["error"] == "JOB_NOT_FOUND"
    finally:
        del os.environ["HIMYC_PROJECT_PATH"]
