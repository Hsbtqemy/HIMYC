"""Utilitaires HTTP : requêtes avec timeout, retry, backoff, rate limit optionnel."""

import time
from typing import Optional

import httpx

# Dernière requête (monotonic) pour rate limit global entre appels get_html
_last_get_html_time: Optional[float] = None


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
    global _last_get_html_time
    headers = {}
    if user_agent:
        headers["User-Agent"] = user_agent

    if min_interval_s is not None and min_interval_s > 0 and _last_get_html_time is not None:
        elapsed = time.monotonic() - _last_get_html_time
        if elapsed < min_interval_s:
            time.sleep(min_interval_s - elapsed)

    last_exc: Optional[Exception] = None
    for attempt in range(retries):
        try:
            _last_get_html_time = time.monotonic()
            with httpx.Client(timeout=timeout_s, follow_redirects=True) as client:
                resp = client.get(url, headers=headers or None)
                resp.raise_for_status()
                # Prefer UTF-8 for HTML when charset is missing or dubious
                if resp.encoding in (None, "ascii", "ISO-8859-1"):
                    resp.encoding = "utf-8"
                return resp.text
        except (httpx.HTTPError, httpx.TimeoutException) as e:
            last_exc = e
            if attempt < retries - 1:
                time.sleep(backoff_s * (2**attempt))
    raise last_exc  # type: ignore
