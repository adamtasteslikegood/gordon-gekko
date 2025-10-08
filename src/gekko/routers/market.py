from typing import List, Optional

from fastapi import APIRouter, Query

from ..services.coingecko import (
    get_simple_price,
    get_coin_tickers,
    get_supported_vs_currencies,
    get_coins_markets,
    get_exchanges_list,
)
from ..services.arbitrage import (
    normalize_tickers,
    compute_opportunities,
)

router = APIRouter()


@router.get("/simple-price")
async def simple_price(
    ids: List[str] = Query(..., description="Comma-separated coin IDs", alias="ids"),
    vs_currencies: List[str] = Query(..., description="Comma-separated vs currencies", alias="vs_currencies"),
):
    """
    Proxy to CoinGecko's /simple/price endpoint.
    Example: /market/simple-price?ids=bitcoin,ethereum&vs_currencies=usd,eur
    """
    data = await get_simple_price(ids=ids, vs_currencies=vs_currencies)
    return data


@router.get("/exchanges")
async def exchanges(
    per_page: int = Query(100, ge=1, le=250),
    page: int = Query(1, ge=1),
):
    return await get_exchanges_list(per_page=per_page, page=page)


@router.get("/supported-vs-currencies")
async def supported_vs_currencies():
    return await get_supported_vs_currencies()


@router.get("/coins-markets")
async def coins_markets(
    vs_currency: str = Query("usd"),
    ids: Optional[List[str]] = Query(None, description="Comma-separated coin ids"),
    per_page: int = Query(50, ge=1, le=250),
    page: int = Query(1, ge=1),
    price_change_percentage: str = Query("24h"),
):
    data = await get_coins_markets(
        vs_currency=vs_currency,
        ids=ids,
        per_page=per_page,
        page=page,
        price_change_percentage=price_change_percentage,
    )
    return data


@router.get("/coin-tickers")
async def coin_tickers(
    coin_id: str = Query(..., description="CoinGecko coin id, e.g., 'bitcoin'"),
    vs_currency: str = Query("usd", description="Target currency for price normalization (usd, btc, eth or exact ticker target)"),
    min_trust: str = Query("yellow", description="Minimum trust score: red < yellow < green"),
    exclude_risky: bool = Query(True, description="Exclude stale or anomalous tickers"),
    min_volume: Optional[float] = Query(None, description="Minimum 24h converted volume in vs_currency"),
    pages: int = Query(1, ge=1, le=5, description="Number of pages to fetch from CoinGecko"),
):
    """
    Fetch tickers for a coin across exchanges and normalize prices to `vs_currency`.
    Useful source data for arbitrage scanning.
    """
    all_tickers = []
    for page in range(1, pages + 1):
        payload = await get_coin_tickers(coin_id=coin_id, page=page)
        all_tickers.extend(payload.get("tickers", []))

    normalized = normalize_tickers(
        all_tickers,
        vs_currency=vs_currency,
        min_trust=min_trust,
        exclude_risky=exclude_risky,
        min_volume=min_volume,
    )
    return {"count": len(normalized), "tickers": normalized}


@router.get("/arbitrage")
async def arbitrage(
    coin_id: str = Query(..., description="CoinGecko coin id, e.g., 'bitcoin'"),
    vs_currency: str = Query("usd", description="Target currency for price normalization (usd, btc, eth or exact ticker target)"),
    min_trust: str = Query("yellow", description="Minimum trust score: red < yellow < green"),
    exclude_risky: bool = Query(True, description="Exclude stale or anomalous tickers"),
    min_volume: Optional[float] = Query(None, description="Minimum 24h converted volume in vs_currency"),
    min_spread_pct: float = Query(0.5, ge=0.0, description="Minimum spread percentage between buy and sell"),
    pages: int = Query(2, ge=1, le=5, description="Number of pages to fetch from CoinGecko"),
    top_n: int = Query(10, ge=1, le=50, description="Max number of opportunities to return"),
    # Fees and slippage (percentage points, e.g., 0.1 == 0.1%)
    buy_fee_pct: float = Query(0.0, ge=0.0, le=5.0),
    sell_fee_pct: float = Query(0.0, ge=0.0, le=5.0),
    buy_slippage_pct: float = Query(0.0, ge=0.0, le=5.0),
    sell_slippage_pct: float = Query(0.0, ge=0.0, le=5.0),
    # Flat fees in vs_currency (e.g., network withdrawal)
    transfer_fee_vs: float = Query(0.0, ge=0.0),
    notional_vs: float = Query(1000.0, gt=0.0, description="Assumed trade size in vs_currency to compute flat fee impact"),
    latency_risk_buffer_pct: float = Query(0.0, ge=0.0, le=10.0, description="Extra buffer to account for transfer/latency risk"),
):
    """
    Compute simple cross-exchange arbitrage opportunities based on last trade prices.
    Not financial advice; does not account for fees, slippage, or latency.
    """
    all_tickers = []
    for page in range(1, pages + 1):
        payload = await get_coin_tickers(coin_id=coin_id, page=page)
        all_tickers.extend(payload.get("tickers", []))

    normalized = normalize_tickers(
        all_tickers,
        vs_currency=vs_currency,
        min_trust=min_trust,
        exclude_risky=exclude_risky,
        min_volume=min_volume,
    )
    opportunities = compute_opportunities(
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
