"""Utilitaires purs pour le panneau de logs."""

from __future__ import annotations

import re
import shlex
from dataclasses import dataclass

_EPISODE_RE = re.compile(r"\bS\d+E\d+\b", re.IGNORECASE)
_LEVEL_IN_LINE_RE = re.compile(r"\[(DEBUG|INFO|WARNING|ERROR|CRITICAL)\]", re.IGNORECASE)

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
    haystack = f"{entry.formatted_line}\n{entry.message}".lower()
    return _matches_query_expression(haystack, query or "")


def _token_matches(haystack: str, token: str) -> bool:
    term = token.strip().lower()
    if not term:
        return True
    if "|" in term:
        alternatives = [part for part in term.split("|") if part]
        return any(alt in haystack for alt in alternatives)
    return term in haystack


def _matches_query_expression(haystack: str, query: str) -> bool:
    raw_query = (query or "").strip()
    if not raw_query:
        return True
    try:
        tokens = shlex.split(raw_query)
    except ValueError:
        # Fallback permissif si guillemets mal fermés.
        tokens = raw_query.split()
    for raw in tokens:
        token = raw.strip()
        if not token:
            continue
        if token.startswith("-") and len(token) > 1:
            if _token_matches(haystack, token[1:]):
                return False
            continue
        if not _token_matches(haystack, token):
            return False
    return True


def parse_formatted_log_line(line: str) -> LogEntry:
    """Parse une ligne formatée de log vers LogEntry."""
    text = (line or "").rstrip("\n")
    level = "INFO"
    message = text
    match = _LEVEL_IN_LINE_RE.search(text)
    if match:
        level = match.group(1).upper()
        tail = text[match.end() :].strip()
        if tail:
            message = tail
    return LogEntry(level=level, message=message, formatted_line=text)


def build_logs_diagnostic_report(
    *,
    selected_line: str,
    episode_id: str | None,
    preset_label: str,
    level_filter: str,
    query: str,
    recent_lines: list[str],
) -> str:
    """Construit un diagnostic texte prêt à partager depuis le panneau Logs."""
    lines: list[str] = [
        "HowIMetYourCorpus - Diagnostic logs",
        f"Preset: {preset_label or 'Personnalisé'}",
        f"Niveau min: {(level_filter or 'ALL').upper()}",
        f"Recherche: {query or '—'}",
        f"Épisode détecté: {episode_id or '—'}",
        "",
        "Ligne sélectionnée:",
        selected_line or "—",
        "",
        "Dernières lignes pertinentes:",
    ]
    if recent_lines:
        lines.extend(f"- {line}" for line in recent_lines)
    else:
        lines.append("- —")
    return "\n".join(lines)
