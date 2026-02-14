"""Utilitaires HTTP : requêtes avec timeout, retry, backoff, rate limit optionnel."""

from __future__ import annotations

import threading
import time
from typing import Optional

import httpx

# Dernière requête (monotonic) pour rate limit global entre appels get_html
_last_get_html_time: Optional[float] = None
_last_get_html_lock = threading.Lock()

_RETRYABLE_STATUS_CODES = {
    408,  # Request Timeout
    409,  # Conflict
    425,  # Too Early
    429,  # Too Many Requests
    500,
    502,
    503,
    504,
}


def _reserve_request_slot(min_interval_s: Optional[float]) -> None:
    """Réserve un créneau d'appel en respectant un intervalle minimal global."""
    global _last_get_html_time
    if min_interval_s is None or min_interval_s <= 0:
        return
    while True:
        with _last_get_html_lock:
            now = time.monotonic()
            if _last_get_html_time is None:
                _last_get_html_time = now
                return
            wait_s = (_last_get_html_time + min_interval_s) - now
            if wait_s <= 0:
                _last_get_html_time = now
                return
        time.sleep(wait_s)


def _parse_retry_after_seconds(response: httpx.Response | None) -> float | None:
    """Parse Retry-After en secondes (format numérique uniquement)."""
    if response is None:
        return None
    raw = (response.headers.get("Retry-After") or "").strip()
    if not raw:
        return None
    try:
        value = float(raw)
    except ValueError:
        return None
    if value < 0:
        return None
    return value


def get_html(
    url: str,
    *,
    timeout_s: float = 30.0,
    user_agent: Optional[str] = None,
    retries: int = 3,
    backoff_s: float = 2.0,
    min_interval_s: Optional[float] = None,
) -> str:
    """
    Récupère le contenu HTML d'une URL avec retry et backoff.

    Args:
        url: URL à récupérer.
        timeout_s: Timeout en secondes.
        user_agent: User-Agent (optionnel).
        retries: Nombre de tentatives en cas d'échec.
        backoff_s: Délai de base entre tentatives (backoff exponentiel).
        min_interval_s: Délai minimal en secondes entre le début de deux appels
            successifs (rate limit). Si fourni, attend avant la requête pour
            respecter l'intervalle depuis le dernier appel (politesse en boucle).

    Returns:
        Contenu de la réponse en texte.

    Raises:
        httpx.HTTPError: Si toutes les tentatives échouent.
    """
    headers = {}
    if user_agent:
        headers["User-Agent"] = user_agent

    attempts = max(1, int(retries))
    backoff_base = max(0.0, float(backoff_s))
    last_exc: Exception | None = None

    with httpx.Client(timeout=timeout_s, follow_redirects=True) as client:
        for attempt in range(attempts):
            _reserve_request_slot(min_interval_s)
            try:
                resp = client.get(url, headers=headers or None)
                resp.raise_for_status()
                # Prefer UTF-8 for HTML when charset is missing or dubious
                if resp.encoding in (None, "ascii", "ISO-8859-1"):
                    resp.encoding = "utf-8"
                return resp.text
            except httpx.HTTPStatusError as exc:
                last_exc = exc
                status_code = exc.response.status_code if exc.response is not None else None
                is_retryable = status_code in _RETRYABLE_STATUS_CODES
                if not is_retryable or attempt >= attempts - 1:
                    raise
                retry_after = _parse_retry_after_seconds(exc.response)
                delay = retry_after if retry_after is not None else backoff_base * (2**attempt)
                if delay > 0:
                    time.sleep(delay)
            except httpx.TransportError as exc:
                last_exc = exc
                if attempt >= attempts - 1:
                    break
                delay = backoff_base * (2**attempt)
                if delay > 0:
                    time.sleep(delay)

    if last_exc is not None:
        raise last_exc
    raise RuntimeError("get_html failed without explicit exception")
