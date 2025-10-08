from typing import List, Optional

from fastapi import APIRouter, Query

from ..services.coingecko import get_coin_tickers
from ..analysis.arbitrage import compute_opportunity_from_tickers, filter_tickers_by_vs_currency

router = APIRouter()


@router.get("/opportunities")
async def arbitrage_opportunities(
    coin_id: str = Query(..., description="CoinGecko coin id, e.g. 'bitcoin'"),
    vs_currency: str = Query("usd", description="Quote currency, e.g. 'usd'"),
    min_spread_pct: float = Query(0.5, ge=0.0, description="Minimum spread percent to report"),
    pages: int = Query(1, ge=1, le=3, description="How many ticker pages to fetch"),
):
    """
    Compute a simple cross-exchange arbitrage opportunity summary using CoinGecko tickers.
    """
    all_tickers: List[dict] = []
    for page in range(1, pages + 1):
        data = await get_coin_tickers(coin_id=coin_id, page=page)
        page_tickers = data.get("tickers", [])
        if not page_tickers:
            break
        all_tickers.extend(page_tickers)

    filtered = filter_tickers_by_vs_currency(all_tickers, vs_currency)
    summary = compute_opportunity_from_tickers(coin_id, vs_currency, filtered, min_spread_pct)
    return summary


@router.get("/per-exchange-prices/{coin_id}")
async def per_exchange_prices(
    coin_id: str,
    vs_currency: str = Query("usd", description="Quote currency to filter on"),
    pages: int = Query(1, ge=1, le=3),
):
    """
    Return last trade prices per exchange for a coin filtered by `vs_currency`.
    Useful for custom arbitrage logic on the client.
    """
    all_tickers: List[dict] = []
    for page in range(1, pages + 1):
        data = await get_coin_tickers(coin_id=coin_id, page=page)
        page_tickers = data.get("tickers", [])
        if not page_tickers:
            break
        all_tickers.extend(page_tickers)

    filtered = filter_tickers_by_vs_currency(all_tickers, vs_currency)
    # project essential fields only
    items = []
    for t in filtered:
        market = t.get("market") or {}
        items.append(
            {
                "exchange": market.get("name") or market.get("identifier"),
                "pair": f"{t.get('base')}/{t.get('target')}",
                "last": t.get("last"),
                "bid_ask_spread_percentage": t.get("bid_ask_spread_percentage"),
                "volume": t.get("volume"),
                "trust_score": t.get("trust_score"),
                "is_stale": t.get("is_stale"),
                "is_anomaly": t.get("is_anomaly"),
                "trade_url": t.get("trade_url"),
            }
        )

    return {
        "coin_id": coin_id,
        "vs_currency": vs_currency,
        "count": len(items),
        "tickers": items,
    }

