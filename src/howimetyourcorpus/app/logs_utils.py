"""Utilitaires purs pour le panneau de logs."""

from __future__ import annotations

import re
from dataclasses import dataclass

_EPISODE_RE = re.compile(r"\bS\d+E\d+\b", re.IGNORECASE)

_LEVEL_RANK = {
    "DEBUG": 10,
    "INFO": 20,
    "WARNING": 30,
    "ERROR": 40,
    "CRITICAL": 50,
}


@dataclass(frozen=True)
class LogEntry:
    level: str
    message: str
    formatted_line: str


def extract_episode_id(text: str) -> str | None:
    """Extrait un episode_id canonique (ex. S01E01) depuis une ligne de log."""
    match = _EPISODE_RE.search(text or "")
    if not match:
        return None
    return match.group(0).upper()


def matches_log_filters(
    entry: LogEntry,
    *,
    level_min: str = "ALL",
    query: str = "",
) -> bool:
    """Retourne True si l'entrée correspond aux filtres UI."""
    level_key = (level_min or "ALL").strip().upper()
    if level_key != "ALL":
        wanted_rank = _LEVEL_RANK.get(level_key, 0)
        current_rank = _LEVEL_RANK.get((entry.level or "").strip().upper(), 0)
        if current_rank < wanted_rank:
            return False
    q = (query or "").strip().lower()
    if q:
        haystack = f"{entry.formatted_line}\n{entry.message}".lower()
        if q not in haystack:
            return False
    return True
