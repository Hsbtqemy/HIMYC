"""Opérations DB sur l'alignement (Phase 4) et concordancier parallèle (Phase 5)."""

from __future__ import annotations

import datetime
import json
import sqlite3

from howimetyourcorpus.core.storage import db_segments
from howimetyourcorpus.core.storage import db_subtitles


def create_align_run(
    conn: sqlite3.Connection,
    align_run_id: str,
    episode_id: str,
    pivot_lang: str,
    params_json: str | None = None,
    created_at: str | None = None,
    summary_json: str | None = None,
) -> None:
    """Crée une entrée de run d'alignement."""
    if not created_at:
        created_at = datetime.datetime.now(datetime.UTC).isoformat().replace("+00:00", "Z")
    conn.execute(
        """
        INSERT INTO align_runs (align_run_id, episode_id, pivot_lang, params_json, created_at, summary_json)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (align_run_id, episode_id, pivot_lang, params_json, created_at, summary_json),
    )


def upsert_align_links(
    conn: sqlite3.Connection,
    align_run_id: str,
    episode_id: str,
    links: list[dict],
) -> None:
    """Remplace les liens d'un run (DELETE puis INSERT). Chaque link: segment_id?, cue_id?, cue_id_target?, lang?, role, confidence, status, meta_json?."""
    conn.execute("DELETE FROM align_links WHERE align_run_id = ?", (align_run_id,))
    rows: list[tuple] = []
    for i, link in enumerate(links):
        link_id = link.get("link_id") or f"{align_run_id}:{i}"
        segment_id = link.get("segment_id")
        cue_id = link.get("cue_id")
        cue_id_target = link.get("cue_id_target")
        lang = link.get("lang") or ""
        role = link.get("role", "pivot")
        confidence = link.get("confidence")
        status = link.get("status", "auto")
        meta_json = json.dumps(link["meta"]) if link.get("meta") else None
        rows.append(
            (
                link_id,
                align_run_id,
                episode_id,
                segment_id,
                cue_id,
                cue_id_target,
                lang,
                role,
                confidence,
                status,
                meta_json,
            )
        )
    if rows:
        conn.executemany(
            """
            INSERT INTO align_links (link_id, align_run_id, episode_id, segment_id, cue_id, cue_id_target, lang, role, confidence, status, meta_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            rows,
        )


def set_align_status(conn: sqlite3.Connection, link_id: str, status: str) -> None:
    """Met à jour le statut d'un lien (accepted / rejected)."""
    conn.execute("UPDATE align_links SET status = ? WHERE link_id = ?", (status, link_id))


def update_align_link_cues(
    conn: sqlite3.Connection,
    link_id: str,
    cue_id: str | None = None,
    cue_id_target: str | None = None,
) -> None:
    """Modifie la cible d'un lien (réplique EN et/ou réplique cible). Met le statut à 'accepted' (correction manuelle)."""
    if cue_id is None and cue_id_target is None:
        return
    if cue_id is not None and cue_id_target is not None:
        conn.execute(
            "UPDATE align_links SET cue_id = ?, cue_id_target = ?, status = ? WHERE link_id = ?",
            (cue_id, cue_id_target, "accepted", link_id),
        )
    elif cue_id is not None:
        conn.execute("UPDATE align_links SET cue_id = ?, status = ? WHERE link_id = ?", (cue_id, "accepted", link_id))
    else:
        conn.execute("UPDATE align_links SET cue_id_target = ?, status = ? WHERE link_id = ?", (cue_id_target, "accepted", link_id))


def get_align_runs_for_episode(conn: sqlite3.Connection, episode_id: str) -> list[dict]:
    """Retourne les runs d'alignement d'un épisode (pour l'UI)."""
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT align_run_id, episode_id, pivot_lang, params_json, created_at, summary_json FROM align_runs WHERE episode_id = ? ORDER BY created_at DESC",
        (episode_id,),
    ).fetchall()
    return [dict(r) for r in rows]


def get_align_runs_for_episodes(conn: sqlite3.Connection, episode_ids: list[str]) -> dict[str, list[dict]]:
    """Retourne les runs d'alignement par épisode (episode_id -> liste de runs). Évite N requêtes au refresh Corpus / arbre."""
    if not episode_ids:
        return {}
    conn.row_factory = sqlite3.Row
    placeholders = ",".join("?" * len(episode_ids))
    rows = conn.execute(
        f"""SELECT align_run_id, episode_id, pivot_lang, params_json, created_at, summary_json
           FROM align_runs WHERE episode_id IN ({placeholders}) ORDER BY episode_id, created_at DESC""",
        episode_ids,
    ).fetchall()
    result: dict[str, list[dict]] = {eid: [] for eid in episode_ids}
    for r in rows:
        d = dict(r)
        eid = d.get("episode_id", "")
        if eid in result:
            result[eid].append(d)
    return result


def delete_align_run(conn: sqlite3.Connection, align_run_id: str) -> None:
    """Supprime un run d'alignement et tous ses liens."""
    conn.execute("DELETE FROM align_links WHERE align_run_id = ?", (align_run_id,))
    conn.execute("DELETE FROM align_runs WHERE align_run_id = ?", (align_run_id,))


def delete_align_runs_for_episode(conn: sqlite3.Connection, episode_id: str) -> None:
    """Supprime tous les runs d'alignement d'un épisode (et leurs liens). À appeler après suppression d'une piste SRT ou re-segmentation pour éviter les liens orphelins."""
    conn.execute("DELETE FROM align_links WHERE episode_id = ?", (episode_id,))
    conn.execute("DELETE FROM align_runs WHERE episode_id = ?", (episode_id,))


def query_alignment_for_episode(
    conn: sqlite3.Connection,
    episode_id: str,
    run_id: str | None = None,
    status_filter: str | None = None,
    min_confidence: float | None = None,
) -> list[dict]:
    """Retourne les liens d'alignement pour un épisode (optionnel: run_id, filtre status, min confidence)."""
    conn.row_factory = sqlite3.Row
    where = "WHERE episode_id = ?"
    params: list = [episode_id]
    if run_id:
        where += " AND align_run_id = ?"
        params.append(run_id)
    if status_filter:
        where += " AND status = ?"
        params.append(status_filter)
    if min_confidence is not None:
        where += " AND confidence >= ?"
        params.append(min_confidence)
    rows = conn.execute(
        f"""SELECT link_id, align_run_id, episode_id, segment_id, cue_id, cue_id_target, lang, role, confidence, status, meta_json
            FROM align_links {where} ORDER BY segment_id, cue_id, lang""",
        params,
    ).fetchall()
    result = []
    for r in rows:
        d = dict(r)
        meta_raw = d.pop("meta_json", None)
        d["meta"] = json.loads(meta_raw) if meta_raw and meta_raw.strip() else {}
        result.append(d)
    return result


def get_align_stats_for_run(
    conn: sqlite3.Connection,
    episode_id: str,
    run_id: str,
    status_filter: str | None = None,
) -> dict:
    """
    Statistiques d'alignement pour un run : nb_links, nb_pivot, nb_target,
    by_status (auto/accepted/rejected), avg_confidence.
    """
    conn.row_factory = sqlite3.Row
    where = "WHERE episode_id = ? AND align_run_id = ?"
    params: list = [episode_id, run_id]
    if status_filter:
        where += " AND status = ?"
        params.append(status_filter)
    rows = conn.execute(
        f"""SELECT role, status, COUNT(*) AS cnt,
                    SUM(CASE WHEN confidence IS NOT NULL THEN confidence ELSE 0 END) AS conf_sum,
                    COUNT(confidence) AS conf_count
           FROM align_links {where}
           GROUP BY role, status""",
        params,
    ).fetchall()
    nb_links = 0
    nb_pivot = 0
    nb_target = 0
    by_status: dict[str, int] = {}
    conf_sum = 0.0
    conf_count = 0
    for r in rows:
        cnt = r["cnt"]
        nb_links += cnt
        if r["role"] == "pivot":
            nb_pivot += cnt
        else:
            nb_target += cnt
        st = r["status"] or "auto"
        by_status[st] = by_status.get(st, 0) + cnt
        conf_sum += float(r["conf_sum"] or 0.0)
        conf_count += int(r["conf_count"] or 0)
    avg_confidence = conf_sum / conf_count if conf_count else None
    return {
        "episode_id": episode_id,
        "run_id": run_id,
        "nb_links": nb_links,
        "nb_pivot": nb_pivot,
        "nb_target": nb_target,
        "by_status": by_status,
        "avg_confidence": round(avg_confidence, 4) if avg_confidence is not None else None,
    }


def get_parallel_concordance(
    conn: sqlite3.Connection,
    episode_id: str,
    run_id: str,
    status_filter: str | None = None,
) -> list[dict]:
    """
    Construit les lignes du concordancier parallèle : segment (transcript) + cue EN + cues cibles
    à partir des liens d'alignement.
    """
    links = query_alignment_for_episode(conn, episode_id, run_id=run_id, status_filter=status_filter)
    segments = db_segments.get_segments_for_episode(conn, episode_id, kind="sentence")
    cues_en = db_subtitles.get_cues_for_episode_lang(conn, episode_id, "en")
    target_langs = sorted({
        (lnk.get("lang") or "").lower()
        for lnk in links
        if lnk.get("role") == "target" and (lnk.get("lang") or "").lower() not in ("", "en")
    })

    seg_by_id = {s["segment_id"]: (s.get("text") or "").strip() for s in segments}

    def cue_text(c: dict) -> str:
        return (c.get("text_clean") or c.get("text_raw") or "").strip()

    cue_en_by_id = {c["cue_id"]: cue_text(c) for c in cues_en}
    cue_by_lang_by_id: dict[str, dict[str, str]] = {}
    for lang in target_langs:
        cues = db_subtitles.get_cues_for_episode_lang(conn, episode_id, lang)
        cue_by_lang_by_id[lang] = {c["cue_id"]: cue_text(c) for c in cues}

    pivot_links = [lnk for lnk in links if lnk.get("role") == "pivot"]
    target_by_cue_en: dict[str, list[dict]] = {}
    for lnk in links:
        if lnk.get("role") != "target" or not lnk.get("cue_id"):
            continue
        cue_en = lnk["cue_id"]
        target_by_cue_en.setdefault(cue_en, []).append(lnk)

    result: list[dict] = []
    for pl in pivot_links:
        seg_id = pl.get("segment_id")
        cue_id_en = pl.get("cue_id")
        text_seg = seg_by_id.get(seg_id, "")
        text_en = cue_en_by_id.get(cue_id_en or "", "")
        conf_pivot = pl.get("confidence")
        row = {
            "segment_id": seg_id,
            "text_segment": text_seg,
            "text_en": text_en,
            "confidence_pivot": conf_pivot,
        }
        for lang in target_langs:
            row[f"text_{lang}"] = ""
            row[f"confidence_{lang}"] = None
        for tl in target_by_cue_en.get(cue_id_en or "", []):
            lang = (tl.get("lang") or "").lower()
            cid_t = tl.get("cue_id_target")
            if lang in cue_by_lang_by_id and cid_t:
                row[f"text_{lang}"] = cue_by_lang_by_id[lang].get(cid_t, "")
                row[f"confidence_{lang}"] = tl.get("confidence")
        result.append(row)
    return result
