"""Utilities for exposing Gordon Gekko services as GPT tools."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Awaitable, Callable, Dict, Iterable, List, Optional, Sequence

from ..analysis import arbitrage as arbitrage_analysis
from ..services import arbitrage as arbitrage_service
from ..services import coingecko as coingecko_service

JSONSchema = Dict[str, Any]
ToolHandler = Callable[..., Awaitable[Any]]


@dataclass(frozen=True)
class ToolSpec:
    """Definition of a single GPT tool backed by Gordon Gekko services."""

    name: str
    description: str
    parameters: JSONSchema
    handler: ToolHandler

    def to_openai_dict(self) -> Dict[str, Any]:
        """Return a dictionary formatted for GPT function calling."""

        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }


def _ensure_sequence(values: Iterable[str]) -> List[str]:
    return list(values)


async def _simple_price_handler(*, ids: Sequence[str], vs_currencies: Sequence[str]) -> Dict[str, Any]:
    return await coingecko_service.get_simple_price(
        ids=_ensure_sequence(ids),
        vs_currencies=_ensure_sequence(vs_currencies),
    )


async def _coins_markets_handler(
    *,
    vs_currency: str,
    ids: Optional[Sequence[str]] = None,
    per_page: int = 50,
    page: int = 1,
    price_change_percentage: Optional[str] = None,
) -> List[Dict[str, Any]]:
    return await coingecko_service.get_coins_markets(
        vs_currency=vs_currency,
        ids=_ensure_sequence(ids) if ids else None,
        per_page=per_page,
        page=page,
        price_change_percentage=price_change_percentage,
    )


async def _coin_tickers_handler(
    *,
    coin_id: str,
    vs_currency: str = "usd",
    min_trust: str = "yellow",
    exclude_risky: bool = True,
    min_volume: Optional[float] = None,
    pages: int = 1,
) -> Dict[str, Any]:
    all_tickers: List[Dict[str, Any]] = []
    for page in range(1, pages + 1):
        payload = await coingecko_service.get_coin_tickers(coin_id=coin_id, page=page)
        all_tickers.extend(payload.get("tickers", []))

    normalized = arbitrage_service.normalize_tickers(
        all_tickers,
        vs_currency=vs_currency,
        min_trust=min_trust,
        exclude_risky=exclude_risky,
        min_volume=min_volume,
    )
    return {"count": len(normalized), "tickers": normalized}


async def _market_arbitrage_handler(
    *,
    coin_id: str,
    vs_currency: str = "usd",
    min_trust: str = "yellow",
    exclude_risky: bool = True,
    min_volume: Optional[float] = None,
    min_spread_pct: float = 0.5,
    pages: int = 2,
    top_n: int = 10,
    buy_fee_pct: float = 0.0,
    sell_fee_pct: float = 0.0,
    buy_slippage_pct: float = 0.0,
    sell_slippage_pct: float = 0.0,
    transfer_fee_vs: float = 0.0,
    notional_vs: float = 1000.0,
    latency_risk_buffer_pct: float = 0.0,
) -> Dict[str, Any]:
    all_tickers: List[Dict[str, Any]] = []
    for page in range(1, pages + 1):
        payload = await coingecko_service.get_coin_tickers(coin_id=coin_id, page=page)
        all_tickers.extend(payload.get("tickers", []))

    normalized = arbitrage_service.normalize_tickers(
        all_tickers,
        vs_currency=vs_currency,
        min_trust=min_trust,
        exclude_risky=exclude_risky,
        min_volume=min_volume,
    )
    opportunities = arbitrage_service.compute_opportunities(
        normalized,
        min_spread_pct=min_spread_pct,
        top_n=top_n,
        buy_fee_pct=buy_fee_pct,
        sell_fee_pct=sell_fee_pct,
        buy_slippage_pct=buy_slippage_pct,
        sell_slippage_pct=sell_slippage_pct,
        transfer_fee_vs=transfer_fee_vs,
        notional_vs=notional_vs,
        latency_risk_buffer_pct=latency_risk_buffer_pct,
    )
    return {
        "coin_id": coin_id,
        "vs_currency": vs_currency,
        "params": {
            "min_spread_pct": min_spread_pct,
            "buy_fee_pct": buy_fee_pct,
            "sell_fee_pct": sell_fee_pct,
            "buy_slippage_pct": buy_slippage_pct,
            "sell_slippage_pct": sell_slippage_pct,
            "transfer_fee_vs": transfer_fee_vs,
            "notional_vs": notional_vs,
            "latency_risk_buffer_pct": latency_risk_buffer_pct,
        },
        "opportunities": opportunities,
    }


async def _arbitrage_opportunities_handler(
    *,
    coin_id: str,
    vs_currency: str = "usd",
    min_spread_pct: float = 0.5,
    pages: int = 1,
) -> Dict[str, Any]:
    all_tickers: List[Dict[str, Any]] = []
    for page in range(1, pages + 1):
        data = await coingecko_service.get_coin_tickers(coin_id=coin_id, page=page)
        page_tickers = data.get("tickers", [])
        if not page_tickers:
            break
        all_tickers.extend(page_tickers)

    filtered = arbitrage_analysis.filter_tickers_by_vs_currency(all_tickers, vs_currency)
    return arbitrage_analysis.compute_opportunity_from_tickers(
        coin_id,
        vs_currency,
        filtered,
        min_spread_pct,
    )


async def _arbitrage_per_exchange_prices_handler(
    *,
    coin_id: str,
    vs_currency: str = "usd",
    pages: int = 1,
) -> Dict[str, Any]:
    all_tickers: List[Dict[str, Any]] = []
    for page in range(1, pages + 1):
        data = await coingecko_service.get_coin_tickers(coin_id=coin_id, page=page)
        page_tickers = data.get("tickers", [])
        if not page_tickers:
            break
        all_tickers.extend(page_tickers)

    filtered = arbitrage_analysis.filter_tickers_by_vs_currency(all_tickers, vs_currency)
    items: List[Dict[str, Any]] = []
    for ticker in filtered:
        market = ticker.get("market") or {}
        items.append(
            {
                "exchange": market.get("name") or market.get("identifier"),
                "pair": f"{ticker.get('base')}/{ticker.get('target')}",
                "last": ticker.get("last"),
                "bid_ask_spread_percentage": ticker.get("bid_ask_spread_percentage"),
                "volume": ticker.get("volume"),
                "trust_score": ticker.get("trust_score"),
                "is_stale": ticker.get("is_stale"),
                "is_anomaly": ticker.get("is_anomaly"),
                "trade_url": ticker.get("trade_url"),
            }
        )

    return {
        "coin_id": coin_id,
        "vs_currency": vs_currency,
        "count": len(items),
        "tickers": items,
    }


TOOL_SPECS: List[ToolSpec] = [
    ToolSpec(
        name="simple_price",
        description="Fetch the latest simple price for a list of coins from CoinGecko.",
        parameters={
            "type": "object",
            "properties": {
                "ids": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "CoinGecko coin identifiers, e.g., ['bitcoin', 'ethereum'].",
                },
                "vs_currencies": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Quote currencies to convert into, e.g., ['usd', 'eur'].",
                },
            },
            "required": ["ids", "vs_currencies"],
        },
        handler=_simple_price_handler,
    ),
    ToolSpec(
        name="coins_markets",
        description="Retrieve market data for coins, mirroring /coins/markets from CoinGecko.",
        parameters={
            "type": "object",
            "properties": {
                "vs_currency": {
                    "type": "string",
                    "description": "The target currency of market data (e.g., 'usd').",
                },
                "ids": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Optional list of coin ids to filter on.",
                },
                "per_page": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": 250,
                    "default": 50,
                    "description": "Number of results per page (max 250).",
                },
                "page": {
                    "type": "integer",
                    "minimum": 1,
                    "default": 1,
                    "description": "Page number to fetch.",
                },
                "price_change_percentage": {
                    "type": "string",
                    "description": "Optional comma separated timeframes for price change percentage (e.g., '24h,7d').",
                },
            },
            "required": ["vs_currency"],
        },
        handler=_coins_markets_handler,
    ),
    ToolSpec(
        name="coin_tickers",
        description="Fetch and normalize tickers for a coin across exchanges.",
        parameters={
            "type": "object",
            "properties": {
                "coin_id": {
                    "type": "string",
                    "description": "CoinGecko coin identifier (e.g., 'bitcoin').",
                },
                "vs_currency": {
                    "type": "string",
                    "default": "usd",
                    "description": "Currency to normalize prices against.",
                },
                "min_trust": {
                    "type": "string",
                    "default": "yellow",
                    "description": "Minimum trust score required (red < yellow < green).",
                },
                "exclude_risky": {
                    "type": "boolean",
                    "default": True,
                    "description": "Whether to drop stale or anomalous tickers.",
                },
                "min_volume": {
                    "type": "number",
                    "description": "Minimum 24h converted volume in the vs_currency to include.",
                },
                "pages": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": 5,
                    "default": 1,
                    "description": "How many paginated results to retrieve from CoinGecko.",
                },
            },
            "required": ["coin_id"],
        },
        handler=_coin_tickers_handler,
    ),
    ToolSpec(
        name="market.arbitrage",
        description="Scan for arbitrage opportunities using normalized ticker data.",
        parameters={
            "type": "object",
            "properties": {
                "coin_id": {
                    "type": "string",
                    "description": "CoinGecko coin identifier (e.g., 'bitcoin').",
                },
                "vs_currency": {
                    "type": "string",
                    "default": "usd",
                    "description": "Currency to normalize prices against.",
                },
                "min_trust": {
                    "type": "string",
                    "default": "yellow",
                    "description": "Minimum trust score required (red < yellow < green).",
                },
                "exclude_risky": {
                    "type": "boolean",
                    "default": True,
                    "description": "Whether to drop stale or anomalous tickers.",
                },
                "min_volume": {
                    "type": "number",
                    "description": "Minimum 24h converted volume in the vs_currency to include.",
                },
                "min_spread_pct": {
                    "type": "number",
                    "default": 0.5,
                    "description": "Minimum spread percentage to report.",
                },
                "pages": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": 5,
                    "default": 2,
                    "description": "How many paginated results to retrieve from CoinGecko.",
                },
                "top_n": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": 50,
                    "default": 10,
                    "description": "Maximum number of opportunities to return.",
                },
                "buy_fee_pct": {
                    "type": "number",
                    "default": 0.0,
                    "description": "Assumed buy fee percentage.",
                },
                "sell_fee_pct": {
                    "type": "number",
                    "default": 0.0,
                    "description": "Assumed sell fee percentage.",
                },
                "buy_slippage_pct": {
                    "type": "number",
                    "default": 0.0,
                    "description": "Assumed buy slippage percentage.",
                },
                "sell_slippage_pct": {
                    "type": "number",
                    "default": 0.0,
                    "description": "Assumed sell slippage percentage.",
                },
                "transfer_fee_vs": {
                    "type": "number",
                    "default": 0.0,
                    "description": "Flat transfer/network fees expressed in the vs_currency.",
                },
                "notional_vs": {
                    "type": "number",
                    "default": 1000.0,
                    "description": "Assumed trade notional in the vs_currency.",
                },
                "latency_risk_buffer_pct": {
                    "type": "number",
                    "default": 0.0,
                    "description": "Additional buffer percentage to cover latency/transfer risk.",
                },
            },
            "required": ["coin_id"],
        },
        handler=_market_arbitrage_handler,
    ),
    ToolSpec(
        name="arbitrage.opportunities",
        description="Summarize arbitrage opportunities with CoinGecko tickers.",
        parameters={
            "type": "object",
            "properties": {
                "coin_id": {
                    "type": "string",
                    "description": "CoinGecko coin identifier (e.g., 'bitcoin').",
                },
                "vs_currency": {
                    "type": "string",
                    "default": "usd",
                    "description": "Quote currency to filter on.",
                },
                "min_spread_pct": {
                    "type": "number",
                    "default": 0.5,
                    "description": "Minimum spread percentage required to report an opportunity.",
                },
                "pages": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": 3,
                    "default": 1,
                    "description": "How many pages of tickers to inspect.",
                },
            },
            "required": ["coin_id"],
        },
        handler=_arbitrage_opportunities_handler,
    ),
    ToolSpec(
        name="arbitrage.per_exchange_prices",
        description="Retrieve per-exchange last trade prices for a coin.",
        parameters={
            "type": "object",
            "properties": {
                "coin_id": {
                    "type": "string",
                    "description": "CoinGecko coin identifier (e.g., 'bitcoin').",
                },
                "vs_currency": {
                    "type": "string",
                    "default": "usd",
                    "description": "Quote currency to filter tickers on.",
                },
                "pages": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": 3,
                    "default": 1,
                    "description": "How many pages of tickers to inspect.",
                },
            },
            "required": ["coin_id"],
        },
        handler=_arbitrage_per_exchange_prices_handler,
    ),
]


def list_tools() -> List[Dict[str, Any]]:
    """Return tool specifications formatted for GPT function calling."""

    return [spec.to_openai_dict() for spec in TOOL_SPECS]


__all__ = ["ToolSpec", "TOOL_SPECS", "list_tools"]

