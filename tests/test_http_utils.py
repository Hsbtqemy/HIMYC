"""Tests unitaires des utilitaires HTTP (retry/backoff/rate-limit)."""

from __future__ import annotations

import httpx
import pytest

from howimetyourcorpus.core.utils import http as http_utils


def _response(
    status_code: int,
    *,
    text: str = "",
    headers: dict[str, str] | None = None,
    url: str = "https://example.test/page",
) -> httpx.Response:
    req = httpx.Request("GET", url)
    return httpx.Response(status_code=status_code, text=text, headers=headers, request=req)


class _ClientFactory:
    def __init__(self, sequence: list[httpx.Response | Exception]):
        self._sequence = list(sequence)
        self.calls: list[tuple[str, dict | None]] = []

    def __call__(self, *args, **kwargs):
        factory = self

        class _Client:
            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

            def get(self, url: str, headers=None):
                factory.calls.append((url, headers))
                if not factory._sequence:
                    raise AssertionError("No more fake HTTP responses configured")
                item = factory._sequence.pop(0)
                if isinstance(item, Exception):
                    raise item
                return item

        return _Client()


@pytest.fixture(autouse=True)
def _reset_global_rate_limit_state():
    http_utils._last_get_html_time = None
    yield
    http_utils._last_get_html_time = None


def test_get_html_retries_on_503_then_succeeds(monkeypatch: pytest.MonkeyPatch) -> None:
    client_factory = _ClientFactory(
        [
            _response(503, text="retry me"),
            _response(200, text="<html>ok</html>"),
        ]
    )
    sleep_calls: list[float] = []
    monkeypatch.setattr(http_utils.httpx, "Client", client_factory)
    monkeypatch.setattr(http_utils.time, "sleep", lambda seconds: sleep_calls.append(seconds))

    html = http_utils.get_html("https://example.test/page", retries=3, backoff_s=1.5)

    assert html == "<html>ok</html>"
    assert len(client_factory.calls) == 2
    assert sleep_calls == [1.5]


def test_get_html_does_not_retry_on_404(monkeypatch: pytest.MonkeyPatch) -> None:
    client_factory = _ClientFactory([_response(404, text="not found")])
    sleep_calls: list[float] = []
    monkeypatch.setattr(http_utils.httpx, "Client", client_factory)
    monkeypatch.setattr(http_utils.time, "sleep", lambda seconds: sleep_calls.append(seconds))

    with pytest.raises(httpx.HTTPStatusError):
        http_utils.get_html("https://example.test/missing", retries=3, backoff_s=2.0)

    assert len(client_factory.calls) == 1
    assert sleep_calls == []


def test_get_html_uses_retry_after_header(monkeypatch: pytest.MonkeyPatch) -> None:
    client_factory = _ClientFactory(
        [
            _response(429, text="slow down", headers={"Retry-After": "7"}),
            _response(200, text="<html>ok</html>"),
        ]
    )
    sleep_calls: list[float] = []
    monkeypatch.setattr(http_utils.httpx, "Client", client_factory)
    monkeypatch.setattr(http_utils.time, "sleep", lambda seconds: sleep_calls.append(seconds))

    html = http_utils.get_html("https://example.test/limited", retries=2, backoff_s=1.0)

    assert html == "<html>ok</html>"
    assert len(client_factory.calls) == 2
    assert sleep_calls == [7.0]


def test_get_html_treats_retries_zero_as_one_attempt(monkeypatch: pytest.MonkeyPatch) -> None:
    client_factory = _ClientFactory([_response(503, text="down")])
    monkeypatch.setattr(http_utils.httpx, "Client", client_factory)

    with pytest.raises(httpx.HTTPStatusError):
        http_utils.get_html("https://example.test/down", retries=0, backoff_s=1.0)

    assert len(client_factory.calls) == 1
