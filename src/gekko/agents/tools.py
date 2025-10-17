from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any, Awaitable, Callable, Dict, List

from ..services.arbitrage import compute_opportunities, normalize_tickers
from ..services.coingecko import get_coin_tickers


@dataclass
class Tool:
    """Metadata describing an agent tool."""

    name: str
    description: str
    schema: Dict[str, Any]
    handler: Callable[[Dict[str, Any]], Awaitable[Dict[str, Any]]]

    def as_function_tool(self) -> Dict[str, Any]:
        """Represent the tool using OpenAI's function-calling shape."""

        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.schema,
            },
        }


def _to_bool(value: Any, default: bool = False) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.lower() in {"1", "true", "yes", "y", "on"}
    return bool(value)


def _to_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _float_default(value: Any, default: float) -> float:
    coerced = _to_float(value)
    return default if coerced is None else coerced


def _to_int(value: Any, default: int) -> int:
    if value is None:
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


async def _fetch_normalized_tickers(
    *,
    coin_id: str,
    vs_currency: str,
    pages: int,
    min_trust: str,
    include_risky: bool,
    min_volume: float | None,
) -> List[Dict[str, Any]]:
    tasks = []
    pages = max(1, min(5, pages))
    for page in range(1, pages + 1):
        tasks.append(get_coin_tickers(coin_id=coin_id, page=page))
    payloads = await asyncio.gather(*tasks)
    tickers: List[Dict[str, Any]] = []
    for payload in payloads:
        tickers.extend(payload.get("tickers", []))
    normalized = normalize_tickers(
        tickers,
        vs_currency=vs_currency,
        min_trust=min_trust,
        exclude_risky=not include_risky,
        min_volume=min_volume,
    )
    return normalized


async def _tool_list_tickers(arguments: Dict[str, Any]) -> Dict[str, Any]:
    normalized = await _fetch_normalized_tickers(
        coin_id=arguments["coin"],
        vs_currency=arguments.get("vs", "usd"),
        pages=_to_int(arguments.get("pages"), 1),
        min_trust=arguments.get("min_trust", "yellow"),
        include_risky=_to_bool(arguments.get("include_risky"), False),
        min_volume=_to_float(arguments.get("min_volume")),
    )
    return {"count": len(normalized), "tickers": normalized}


async def _tool_find_arbitrage(arguments: Dict[str, Any]) -> Dict[str, Any]:
    normalized = await _fetch_normalized_tickers(
        coin_id=arguments["coin"],
        vs_currency=arguments.get("vs", "usd"),
        pages=_to_int(arguments.get("pages"), 1),
        min_trust=arguments.get("min_trust", "yellow"),
        include_risky=_to_bool(arguments.get("include_risky"), False),
        min_volume=_to_float(arguments.get("min_volume")),
    )
    opportunities = compute_opportunities(
        normalized,
        min_spread_pct=_float_default(arguments.get("min_spread_pct"), 1.0),
        top_n=_to_int(arguments.get("top_n"), 5),
        buy_fee_pct=_float_default(arguments.get("buy_fee_pct"), 0.0),
        sell_fee_pct=_float_default(arguments.get("sell_fee_pct"), 0.0),
        buy_slippage_pct=_float_default(arguments.get("buy_slippage_pct"), 0.0),
        sell_slippage_pct=_float_default(arguments.get("sell_slippage_pct"), 0.0),
        transfer_fee_vs=_float_default(arguments.get("transfer_fee_vs"), 0.0),
        notional_vs=_float_default(arguments.get("notional_vs"), 1000.0),
        latency_risk_buffer_pct=_float_default(
            arguments.get("latency_risk_buffer_pct"), 0.0
        ),
    )
    return {"count": len(opportunities), "opportunities": opportunities}


def list_tools() -> List[Tool]:
    return [
        Tool(
            name="list_tickers",
            description="List normalized exchange tickers for a specific coin",
            schema={
                "type": "object",
                "properties": {
                    "coin": {"type": "string"},
                    "vs": {"type": "string", "default": "usd"},
                    "pages": {"type": "integer", "minimum": 1, "maximum": 5, "default": 1},
                    "min_trust": {
                        "type": "string",
                        "enum": ["red", "yellow", "green"],
                        "default": "yellow",
                    },
                    "include_risky": {"type": "boolean", "default": False},
                    "min_volume": {"type": ["number", "null"], "default": None},
                },
                "required": ["coin"],
                "additionalProperties": False,
            },
            handler=_tool_list_tickers,
        ),
        Tool(
            name="find_arbitrage",
            description="Compute arbitrage opportunities for a coin across exchanges",
            schema={
                "type": "object",
                "properties": {
                    "coin": {"type": "string"},
                    "vs": {"type": "string", "default": "usd"},
                    "pages": {"type": "integer", "minimum": 1, "maximum": 5, "default": 1},
                    "min_trust": {
                        "type": "string",
                        "enum": ["red", "yellow", "green"],
                        "default": "yellow",
                    },
                    "include_risky": {"type": "boolean", "default": False},
                    "min_volume": {"type": ["number", "null"], "default": None},
                    "min_spread_pct": {"type": "number", "default": 1.0},
                    "top_n": {"type": "integer", "default": 5},
                    "buy_fee_pct": {"type": "number", "default": 0.0},
                    "sell_fee_pct": {"type": "number", "default": 0.0},
                    "buy_slippage_pct": {"type": "number", "default": 0.0},
                    "sell_slippage_pct": {"type": "number", "default": 0.0},
                    "transfer_fee_vs": {"type": "number", "default": 0.0},
                    "notional_vs": {"type": "number", "default": 1000.0},
                    "latency_risk_buffer_pct": {"type": "number", "default": 0.0},
                },
                "required": ["coin"],
                "additionalProperties": False,
            },
            handler=_tool_find_arbitrage,
        ),
    ]
