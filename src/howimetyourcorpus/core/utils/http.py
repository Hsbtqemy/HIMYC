"""Utilitaires HTTP : requêtes avec timeout, retry, backoff."""

import time
from typing import Optional

import httpx


def get_html(
    url: str,
    *,
    timeout_s: float = 30.0,
    user_agent: Optional[str] = None,
    retries: int = 3,
    backoff_s: float = 2.0,
) -> str:
    """
    Récupère le contenu HTML d'une URL avec retry et backoff.

    Args:
        url: URL à récupérer.
        timeout_s: Timeout en secondes.
        user_agent: User-Agent (optionnel).
        retries: Nombre de tentatives en cas d'échec.
        backoff_s: Délai de base entre tentatives (backoff exponentiel).

    Returns:
        Contenu de la réponse en texte.

    Raises:
        httpx.HTTPError: Si toutes les tentatives échouent.
    """
    headers = {}
    if user_agent:
        headers["User-Agent"] = user_agent

    last_exc: Optional[Exception] = None
    for attempt in range(retries):
        try:
            with httpx.Client(timeout=timeout_s, follow_redirects=True) as client:
                resp = client.get(url, headers=headers or None)
                resp.raise_for_status()
                return resp.text
        except (httpx.HTTPError, httpx.TimeoutException) as e:
            last_exc = e
            if attempt < retries - 1:
                time.sleep(backoff_s * (2**attempt))
    raise last_exc  # type: ignore
