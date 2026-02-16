"""Utilitaires HTTP : requêtes avec timeout, retry, backoff, rate limit, cache disque optionnel."""

import hashlib
import time
from pathlib import Path
from typing import Optional

import httpx

# Dernière requête (monotonic) pour rate limit global entre appels get_html
_last_get_html_time: Optional[float] = None


def _cache_path(url: str, cache_dir: Path) -> Path:
    """Retourne le chemin du fichier cache pour une URL (hash SHA256)."""
    h = hashlib.sha256(url.encode()).hexdigest()[:16]
    return cache_dir / f"{h}.html"


def get_html(
    url: str,
    *,
    timeout_s: float = 30.0,
    user_agent: Optional[str] = None,
    retries: int = 3,
    backoff_s: float = 2.0,
    min_interval_s: Optional[float] = None,
    cache_dir: Optional[Path] = None,
    cache_ttl_s: float = 7 * 24 * 3600,  # 7 jours par défaut
) -> str:
    """
    Récupère le contenu HTML d'une URL avec retry, backoff et cache disque optionnel.

    Args:
        url: URL à récupérer.
        timeout_s: Timeout en secondes.
        user_agent: User-Agent (optionnel).
        retries: Nombre de tentatives en cas d'échec.
        backoff_s: Délai de base entre tentatives (backoff exponentiel).
        min_interval_s: Délai minimal en secondes entre le début de deux appels
            successifs (rate limit). Si fourni, attend avant la requête pour
            respecter l'intervalle depuis le dernier appel (politesse en boucle).
        cache_dir: Répertoire cache (optionnel). Si fourni et valide (TTL), retourne
            le contenu depuis le cache. Sinon, fetch et écrit le cache.
        cache_ttl_s: Durée de validité du cache en secondes (default 7 jours).

    Returns:
        Contenu de la réponse en texte.

    Raises:
        httpx.HTTPError: Si toutes les tentatives échouent.
    """
    global _last_get_html_time

    # Vérifier le cache
    if cache_dir and cache_dir.is_dir():
        cache_file = _cache_path(url, cache_dir)
        if cache_file.exists():
            age = time.time() - cache_file.stat().st_mtime
            if age < cache_ttl_s:
                return cache_file.read_text(encoding="utf-8")

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
                
                # Gestion spécifique 429 (Too Many Requests)
                if resp.status_code == 429:
                    retry_after = resp.headers.get("Retry-After")
                    wait_time = 60.0  # Default 60s si pas de header
                    if retry_after:
                        try:
                            wait_time = float(retry_after)
                        except ValueError:
                            pass
                    if attempt < retries - 1:
                        time.sleep(wait_time)
                        continue
                
                resp.raise_for_status()
                # Prefer UTF-8 for HTML when charset is missing or dubious
                if resp.encoding in (None, "ascii", "ISO-8859-1"):
                    resp.encoding = "utf-8"
                
                # Écrire le cache
                if cache_dir and cache_dir.is_dir():
                    cache_file = _cache_path(url, cache_dir)
                    cache_file.write_text(resp.text, encoding="utf-8")
                
                return resp.text
        except (httpx.HTTPError, httpx.TimeoutException) as e:
            last_exc = e
            if attempt < retries - 1:
                time.sleep(backoff_s * (2**attempt))
    raise last_exc  # type: ignore
