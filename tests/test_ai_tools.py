from __future__ import annotations

import asyncio
from typing import Any, Dict, List

from gekko.ai import tools as ai_tools


def _get_spec(name: str) -> ai_tools.ToolSpec:
    return next(spec for spec in ai_tools.TOOL_SPECS if spec.name == name)


def test_tool_specs_have_expected_schema():
    expected_names = [
        "simple_price",
        "coins_markets",
        "coin_tickers",
        "market.arbitrage",
        "arbitrage.opportunities",
        "arbitrage.per_exchange_prices",
    ]
    assert [spec.name for spec in ai_tools.TOOL_SPECS] == expected_names

    for spec in ai_tools.TOOL_SPECS:
        assert spec.parameters["type"] == "object"
        assert "properties" in spec.parameters
        assert "function" in spec.to_openai_dict()


def test_list_tools_matches_specs():
    tools = ai_tools.list_tools()
    assert len(tools) == len(ai_tools.TOOL_SPECS)
    for spec, payload in zip(ai_tools.TOOL_SPECS, tools):
        assert payload["type"] == "function"
        fn = payload["function"]
        assert fn["name"] == spec.name
        assert fn["description"] == spec.description
        assert fn["parameters"] == spec.parameters


def test_simple_price_handler_delegates(monkeypatch):
    captured: Dict[str, Any] = {}

    async def fake_simple_price(*, ids: List[str], vs_currencies: List[str]) -> Dict[str, Any]:
        captured["args"] = (ids, vs_currencies)
        return {"payload": True}

    monkeypatch.setattr(ai_tools.coingecko_service, "get_simple_price", fake_simple_price)

    spec = _get_spec("simple_price")
    result = asyncio.run(spec.handler(ids=["bitcoin"], vs_currencies=["usd"]))

    assert result == {"payload": True}
    assert captured["args"] == (["bitcoin"], ["usd"])


def test_coins_markets_handler_delegates(monkeypatch):
    captured: Dict[str, Any] = {}

    async def fake_markets(*, vs_currency: str, ids: List[str] | None, per_page: int, page: int, price_change_percentage: str | None):
        captured["args"] = (vs_currency, ids, per_page, page, price_change_percentage)
        return ["ok"]

    monkeypatch.setattr(ai_tools.coingecko_service, "get_coins_markets", fake_markets)

    spec = _get_spec("coins_markets")
    result = asyncio.run(spec.handler(
        vs_currency="usd",
        ids=["bitcoin"],
        per_page=25,
        page=2,
        price_change_percentage="24h",
    ))

    assert result == ["ok"]
    assert captured["args"] == ("usd", ["bitcoin"], 25, 2, "24h")


def test_coin_tickers_handler_normalizes(monkeypatch):
    pages_requested: List[int] = []

    async def fake_coin_tickers(*, coin_id: str, page: int) -> Dict[str, Any]:
        pages_requested.append(page)
        return {"tickers": [
            {"market": {"name": "foo"}, "base": "BTC", "target": "USD"}
        ]}

    def fake_normalize(tickers: List[Dict[str, Any]], **kwargs: Any) -> List[Dict[str, Any]]:
        return [{"normalized": tickers, "kwargs": kwargs}]

    monkeypatch.setattr(ai_tools.coingecko_service, "get_coin_tickers", fake_coin_tickers)
    monkeypatch.setattr(ai_tools.arbitrage_service, "normalize_tickers", fake_normalize)

    spec = _get_spec("coin_tickers")
    result = asyncio.run(spec.handler(
        coin_id="bitcoin",
        vs_currency="usd",
        min_trust="yellow",
        exclude_risky=True,
        min_volume=None,
        pages=2,
    ))

    assert pages_requested == [1, 2]
    assert result["count"] == 1
    assert result["tickers"][0]["kwargs"]["vs_currency"] == "usd"


def test_market_arbitrage_handler_pipeline(monkeypatch):
    async def fake_coin_tickers(*, coin_id: str, page: int) -> Dict[str, Any]:
        return {"tickers": [
            {"market": {"name": "foo"}, "base": "BTC", "target": "USD"}
        ]}

    def fake_normalize(tickers: List[Dict[str, Any]], **kwargs: Any) -> List[Dict[str, Any]]:
        return [tickers, kwargs]

    def fake_compute(tickers: List[Dict[str, Any]], **kwargs: Any) -> List[Dict[str, Any]]:
        return [{"tickers": tickers, "kwargs": kwargs}]

    monkeypatch.setattr(ai_tools.coingecko_service, "get_coin_tickers", fake_coin_tickers)
    monkeypatch.setattr(ai_tools.arbitrage_service, "normalize_tickers", fake_normalize)
    monkeypatch.setattr(ai_tools.arbitrage_service, "compute_opportunities", fake_compute)

    spec = _get_spec("market.arbitrage")
    result = asyncio.run(spec.handler(coin_id="bitcoin", vs_currency="usd"))

    assert result["coin_id"] == "bitcoin"
    assert result["opportunities"][0]["tickers"][0][0]["market"]["name"] == "foo"


def test_arbitrage_opportunities_handler_uses_analysis(monkeypatch):
    async def fake_coin_tickers(*, coin_id: str, page: int) -> Dict[str, Any]:
        if page > 1:
            return {"tickers": []}
        return {"tickers": ["raw"]}

    def fake_filter(tickers: List[Dict[str, Any]], vs_currency: str) -> List[str]:
        return ["filtered", vs_currency]

    def fake_compute(coin_id: str, vs_currency: str, tickers: List[str], min_spread_pct: float) -> Dict[str, Any]:
        return {
            "coin_id": coin_id,
            "vs_currency": vs_currency,
            "tickers": tickers,
            "min_spread_pct": min_spread_pct,
        }

    monkeypatch.setattr(ai_tools.coingecko_service, "get_coin_tickers", fake_coin_tickers)
    monkeypatch.setattr(ai_tools.arbitrage_analysis, "filter_tickers_by_vs_currency", fake_filter)
    monkeypatch.setattr(ai_tools.arbitrage_analysis, "compute_opportunity_from_tickers", fake_compute)

    spec = _get_spec("arbitrage.opportunities")
    result = asyncio.run(spec.handler(coin_id="bitcoin", vs_currency="usd", min_spread_pct=1.0, pages=2))

    assert result["tickers"] == ["filtered", "usd"]
    assert result["min_spread_pct"] == 1.0


def test_arbitrage_per_exchange_prices_handler_projects(monkeypatch):
    async def fake_coin_tickers(*, coin_id: str, page: int) -> Dict[str, Any]:
        return {"tickers": [
            {
                "market": {"name": "Exchange"},
                "base": "BTC",
                "target": "USD",
                "last": 123,
                "bid_ask_spread_percentage": 0.1,
                "volume": 1000,
                "trust_score": "green",
                "is_stale": False,
                "is_anomaly": False,
                "trade_url": "https://example.com",
            }
        ]}

    def fake_filter(tickers: List[Dict[str, Any]], vs_currency: str) -> List[Dict[str, Any]]:
        return tickers

    monkeypatch.setattr(ai_tools.coingecko_service, "get_coin_tickers", fake_coin_tickers)
    monkeypatch.setattr(ai_tools.arbitrage_analysis, "filter_tickers_by_vs_currency", fake_filter)

    spec = _get_spec("arbitrage.per_exchange_prices")
    result = asyncio.run(spec.handler(coin_id="bitcoin", vs_currency="usd", pages=1))

    assert result["count"] == 1
    assert result["tickers"][0]["exchange"] == "Exchange"

