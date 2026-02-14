"""Tests OpenSubtitlesClient: retries/backoff et robustesse réseau."""

from __future__ import annotations

import httpx
import pytest

from howimetyourcorpus.core.opensubtitles import client as os_client
from howimetyourcorpus.core.opensubtitles.client import OpenSubtitlesClient


def _response(
    status_code: int,
    *,
    url: str,
    method: str,
    headers: dict[str, str] | None = None,
    json_data=None,
    text: str = "",
) -> httpx.Response:
    req = httpx.Request(method, url)
    if json_data is not None:
        return httpx.Response(status_code=status_code, headers=headers, json=json_data, request=req)
    return httpx.Response(status_code=status_code, headers=headers, text=text, request=req)


class _ClientFactory:
    def __init__(self, sequence: list[httpx.Response | Exception]):
        self._sequence = list(sequence)
        self.calls: list[dict[str, object]] = []

    def __call__(self, *args, **kwargs):
        factory = self

        class _Client:
            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

            def request(self, method: str, url: str, params=None, json=None, headers=None):
                factory.calls.append(
                    {
                        "method": method,
                        "url": url,
                        "params": params,
                        "json": json,
                        "headers": headers,
                    }
                )
                if not factory._sequence:
                    raise AssertionError("No more fake responses configured")
                item = factory._sequence.pop(0)
                if isinstance(item, Exception):
                    raise item
                return item

        return _Client()


@pytest.fixture(autouse=True)
def _reset_opensubtitles_rate_limit_state():
    os_client._last_opensubtitles_request_time = None
    yield
    os_client._last_opensubtitles_request_time = None


def test_search_retries_on_429_then_succeeds(monkeypatch: pytest.MonkeyPatch) -> None:
    api_url = "https://api.opensubtitles.com/api/v1/subtitles"
    client_factory = _ClientFactory(
        [
            _response(
                429,
                url=api_url,
                method="GET",
                headers={"Retry-After": "7"},
                json_data={"data": []},
            ),
            _response(
                200,
                url=api_url,
                method="GET",
                json_data={
                    "data": [
                        {
                            "id": "sub-1",
                            "attributes": {
                                "language": "en",
                                "download_count": 10,
                                "files": [{"file_id": 123, "file_name": "x.srt"}],
                            },
                        }
                    ]
                },
            ),
        ]
    )
    sleep_calls: list[float] = []
    monkeypatch.setattr(os_client.httpx, "Client", client_factory)
    monkeypatch.setattr(os_client.time, "sleep", lambda seconds: sleep_calls.append(seconds))

    client = OpenSubtitlesClient(api_key="k", retries=2, backoff_s=1.0)
    hits = client.search("tt0460649", 1, 1, "en")

    assert len(hits) == 1
    assert hits[0].file_id == 123
    assert sleep_calls == [7.0]
    assert len(client_factory.calls) == 2


def test_download_retries_transport_error_on_file_link(monkeypatch: pytest.MonkeyPatch) -> None:
    download_url = "https://api.opensubtitles.com/api/v1/download"
    file_url = "https://files.opensubtitles.example/x.srt"
    transient_err = httpx.ConnectError("temporary network failure", request=httpx.Request("GET", file_url))
    client_factory = _ClientFactory(
        [
            _response(
                200,
                url=download_url,
                method="POST",
                json_data={"link": file_url},
            ),
            transient_err,
            _response(
                200,
                url=file_url,
                method="GET",
                text="1\n00:00:00,000 --> 00:00:01,000\nHello\n",
            ),
        ]
    )
    sleep_calls: list[float] = []
    monkeypatch.setattr(os_client.httpx, "Client", client_factory)
    monkeypatch.setattr(os_client.time, "sleep", lambda seconds: sleep_calls.append(seconds))

    client = OpenSubtitlesClient(api_key="k", retries=2, backoff_s=1.5)
    content = client.download(123)

    assert "Hello" in content
    assert sleep_calls == [1.5]
    assert len(client_factory.calls) == 3
