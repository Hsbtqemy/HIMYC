"""Client REST pour l'API OpenSubtitles (api.opensubtitles.com/api/v1)."""

from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass
from typing import Any

import httpx

logger = logging.getLogger(__name__)

BASE_URL = "https://api.opensubtitles.com/api/v1"
USER_AGENT = "HowIMetYourCorpus/0.5 (research)"
_RETRYABLE_STATUS_CODES = {
    408,
    409,
    425,
    429,
    500,
    502,
    503,
    504,
}

_last_opensubtitles_request_time: float | None = None
_last_opensubtitles_request_lock = threading.Lock()


class OpenSubtitlesError(Exception):
    """Erreur API OpenSubtitles (quota, auth, réseau)."""

    pass


@dataclass
class OpenSubtitlesSearchHit:
    """Un résultat de recherche : sous-titre téléchargeable."""

    file_id: int
    subtitle_id: str
    release_name: str
    language: str
    download_count: int = 0


class OpenSubtitlesClient:
    """
    Client pour recherche et téléchargement de sous-titres.
    Headers : Api-Key (requis), User-Agent.
    """

    def __init__(
        self,
        api_key: str,
        base_url: str = BASE_URL,
        user_agent: str = USER_AGENT,
        timeout_s: float = 30.0,
        retries: int = 3,
        backoff_s: float = 2.0,
        min_interval_s: float | None = None,
    ):
        self.api_key = api_key.strip()
        self.base_url = base_url.rstrip("/")
        self.user_agent = user_agent
        self.timeout_s = timeout_s
        self.retries = max(1, int(retries))
        self.backoff_s = max(0.0, float(backoff_s))
        self.min_interval_s = (
            max(0.0, float(min_interval_s)) if min_interval_s is not None else None
        )

    def _headers(self) -> dict[str, str]:
        return {
            "Api-Key": self.api_key,
            "User-Agent": self.user_agent,
            "Accept": "application/json",
            "Content-Type": "application/json",
        }

    @staticmethod
    def _parse_retry_after_seconds(response: httpx.Response | None) -> float | None:
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

    def _reserve_request_slot(self) -> None:
        global _last_opensubtitles_request_time
        if self.min_interval_s is None or self.min_interval_s <= 0:
            return
        while True:
            with _last_opensubtitles_request_lock:
                now = time.monotonic()
                if _last_opensubtitles_request_time is None:
                    _last_opensubtitles_request_time = now
                    return
                wait_s = (_last_opensubtitles_request_time + self.min_interval_s) - now
                if wait_s <= 0:
                    _last_opensubtitles_request_time = now
                    return
            time.sleep(wait_s)

    def _request(
        self,
        method: str,
        url: str,
        *,
        params: dict[str, Any] | None = None,
        json_body: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
        follow_redirects: bool = False,
    ) -> httpx.Response:
        last_exc: Exception | None = None
        with httpx.Client(timeout=self.timeout_s, follow_redirects=follow_redirects) as client:
            for attempt in range(self.retries):
                self._reserve_request_slot()
                try:
                    response = client.request(
                        method,
                        url,
                        params=params,
                        json=json_body,
                        headers=headers,
                    )
                    response.raise_for_status()
                    return response
                except httpx.HTTPStatusError as e:
                    last_exc = e
                    status_code = e.response.status_code if e.response is not None else None
                    if status_code not in _RETRYABLE_STATUS_CODES or attempt >= self.retries - 1:
                        raise
                    retry_after = self._parse_retry_after_seconds(e.response)
                    delay = (
                        retry_after
                        if retry_after is not None
                        else self.backoff_s * (2**attempt)
                    )
                    if delay > 0:
                        time.sleep(delay)
                except httpx.TransportError as e:
                    last_exc = e
                    if attempt >= self.retries - 1:
                        break
                    delay = self.backoff_s * (2**attempt)
                    if delay > 0:
                        time.sleep(delay)
        if last_exc is not None:
            raise last_exc
        raise RuntimeError("OpenSubtitles request failed without explicit exception")

    def search(
        self,
        imdb_id: str,
        season: int,
        episode: int,
        language: str,
    ) -> list[OpenSubtitlesSearchHit]:
        """
        Recherche des sous-titres pour un épisode (série).
        imdb_id : IMDb ID de la série (ex. tt0460649 pour HIMYM).
        language : code ISO 639-2 (en, fr, etc.).
        """
        if not self.api_key:
            raise OpenSubtitlesError("Clé API OpenSubtitles manquante.")
        imdb_clean = imdb_id.strip().lower()
        if imdb_clean.startswith("tt"):
            pass
        else:
            imdb_clean = f"tt{imdb_clean}"
        lang_clean = language.strip().lower()[:3]
        url = f"{self.base_url}/subtitles"
        params: dict[str, Any] = {
            "imdb_id": imdb_clean,
            "type": "episode",
            "season_number": season,
            "episode_number": episode,
            "languages": lang_clean,
        }
        try:
            r = self._request(
                "GET",
                url,
                params=params,
                headers=self._headers(),
            )
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 401:
                raise OpenSubtitlesError("Clé API OpenSubtitles invalide ou expirée.") from e
            if e.response.status_code == 429:
                raise OpenSubtitlesError("Quota OpenSubtitles dépassé. Réessayez plus tard.") from e
            raise OpenSubtitlesError(f"API OpenSubtitles: {e.response.status_code}") from e
        except (httpx.HTTPError, httpx.TimeoutException) as e:
            raise OpenSubtitlesError(f"Réseau OpenSubtitles: {e!s}") from e

        data = r.json()
        hits: list[OpenSubtitlesSearchHit] = []
        for item in data.get("data") or []:
            attrs = item.get("attributes") or {}
            files = attrs.get("files") or []
            if not files:
                continue
            fid = files[0].get("file_id")
            if fid is None:
                continue
            hits.append(
                OpenSubtitlesSearchHit(
                    file_id=int(fid),
                    subtitle_id=str(item.get("id", "")),
                    release_name=files[0].get("file_name") or "",
                    language=attrs.get("language") or lang_clean,
                    download_count=int(attrs.get("download_count") or 0),
                )
            )
        return hits

    def download(self, file_id: int) -> str:
        """
        Télécharge le fichier sous-titre et retourne son contenu (texte SRT).
        """
        if not self.api_key:
            raise OpenSubtitlesError("Clé API OpenSubtitles manquante.")
        url = f"{self.base_url}/download"
        body = {"file_id": file_id}
        try:
            r = self._request(
                "POST",
                url,
                json_body=body,
                headers=self._headers(),
                follow_redirects=True,
            )
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 401:
                raise OpenSubtitlesError("Clé API OpenSubtitles invalide ou expirée.") from e
            if e.response.status_code == 429:
                raise OpenSubtitlesError("Quota téléchargement dépassé.") from e
            raise OpenSubtitlesError(f"API OpenSubtitles download: {e.response.status_code}") from e
        except (httpx.HTTPError, httpx.TimeoutException) as e:
            raise OpenSubtitlesError(f"Réseau OpenSubtitles: {e!s}") from e

        info = r.json()
        link = info.get("link")
        if not link:
            raise OpenSubtitlesError("Réponse OpenSubtitles sans lien de téléchargement.")
        try:
            r2 = self._request(
                "GET",
                link,
                headers={"User-Agent": self.user_agent},
                follow_redirects=True,
            )
            if r2.encoding in (None, "ascii", "ISO-8859-1"):
                r2.encoding = "utf-8"
            return r2.text
        except (httpx.HTTPError, httpx.TimeoutException) as e:
            raise OpenSubtitlesError(f"Téléchargement fichier: {e!s}") from e
