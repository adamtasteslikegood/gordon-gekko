import asyncio
from typing import Any, Dict, List

import httpx
import pytest

from gekko.services import coingecko


class DummyResponse:
    def __init__(self, payload: Dict[str, Any]):
        self._payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self) -> Dict[str, Any]:
        return self._payload


class DummyClient:
    def __init__(self, payload: Dict[str, Any]):
        self._payload = payload

    async def __aenter__(self) -> "DummyClient":
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:  # type: ignore[override]
        return None

    async def get(self, path: str, params: Dict[str, Any] | None = None) -> DummyResponse:
        assert path == "/search"
        return DummyResponse(self._payload)


def _patch_client(monkeypatch: pytest.MonkeyPatch, payload: Dict[str, Any]) -> None:
    def _factory(*args: Any, **kwargs: Any) -> DummyClient:
        return DummyClient(payload)

    monkeypatch.setattr(coingecko.httpx, "AsyncClient", _factory)


def test_async_client_injects_api_key_header(monkeypatch: pytest.MonkeyPatch):
    captured: Dict[str, Any] = {}

    class SpyClient:
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            captured["headers"] = kwargs.get("headers")

        async def __aenter__(self) -> "SpyClient":
            return self

        async def __aexit__(self, exc_type, exc, tb) -> None:  # type: ignore[override]
            return None

        async def get(self, path: str, params: Dict[str, Any] | None = None) -> DummyResponse:
            return DummyResponse({"bitcoin": {"usd": 1}})

    monkeypatch.setenv("CG_API_KEY", "demo-key-123")
    monkeypatch.setattr(coingecko.httpx, "AsyncClient", lambda *args, **kwargs: SpyClient(*args, **kwargs))

    asyncio.run(coingecko.get_simple_price(["bitcoin"], ["usd"]))
    assert captured["headers"]["x-cg-demo-api-key"] == "demo-key-123"
    monkeypatch.delenv("CG_API_KEY")


def test_resolve_coin_id_matches_symbol(monkeypatch: pytest.MonkeyPatch):
    coingecko._COIN_ID_CACHE.clear()
    payload = {
        "coins": [
            {"id": "bitcoin", "symbol": "btc", "name": "Bitcoin"},
        ]
    }
    _patch_client(monkeypatch, payload)

    result = asyncio.run(coingecko.resolve_coin_id("BTC"))
    assert result == "bitcoin"


def test_resolve_coin_id_falls_back_on_error(monkeypatch: pytest.MonkeyPatch):
    coingecko._COIN_ID_CACHE.clear()

    class ErrorClient:
        async def __aenter__(self) -> "ErrorClient":
            return self

        async def __aexit__(self, exc_type, exc, tb) -> None:  # type: ignore[override]
            return None

        async def get(self, path: str, params: Dict[str, Any] | None = None) -> Any:
            request = httpx.Request("GET", "https://api.coingecko.com/search")
            raise httpx.HTTPStatusError("boom", request=request, response=httpx.Response(500, request=request))

    monkeypatch.setattr(coingecko.httpx, "AsyncClient", lambda *_, **__: ErrorClient())

    result = asyncio.run(coingecko.resolve_coin_id("My Coin"))
    assert result == "my-coin"


def test_resolve_coin_id_requires_identifier():
    coingecko._COIN_ID_CACHE.clear()
    with pytest.raises(ValueError):
        asyncio.run(coingecko.resolve_coin_id(""))
