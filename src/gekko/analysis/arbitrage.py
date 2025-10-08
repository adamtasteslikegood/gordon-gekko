from __future__ import annotations

from typing import List, Dict, Any, Optional


def filter_tickers_by_vs_currency(tickers: List[Dict[str, Any]], vs_currency: str) -> List[Dict[str, Any]]:
    vc = (vs_currency or "").upper()
    out: List[Dict[str, Any]] = []
    for t in tickers:
        try:
            # Filter by target currency and some basic sanity checks
            if (t.get("target") or "").upper() != vc:
                continue
            if t.get("last") is None:
                continue
            if t.get("is_stale") is True:
                continue
            if t.get("is_anomaly") is True:
                continue
            out.append(t)
        except Exception:
            # Skip malformed entries
            continue
    return out


def compute_opportunity_from_tickers(
    coin_id: str,
    vs_currency: str,
    tickers: List[Dict[str, Any]],
    min_spread_pct: float = 0.5,
) -> Dict[str, Any]:
    if not tickers:
        return {
            "coin_id": coin_id,
            "vs_currency": vs_currency,
            "exchanges": 0,
            "min_price": None,
            "max_price": None,
            "spread_pct": 0.0,
            "opportunity": None,
            "top_samples": [],
        }

    # Find min and max last price across exchanges
    sorted_by_price = sorted(tickers, key=lambda t: (t.get("last") or 0))
    min_t = sorted_by_price[0]
    max_t = sorted_by_price[-1]

    min_price = float(min_t.get("last"))
    max_price = float(max_t.get("last"))
    spread_pct = 0.0 if min_price <= 0 else (max_price - min_price) / min_price * 100.0

    market_min = (min_t.get("market") or {})
    market_max = (max_t.get("market") or {})

    opportunity: Optional[Dict[str, Any]] = None
    if spread_pct >= min_spread_pct:
        opportunity = {
            "buy_exchange": market_min.get("name") or market_min.get("identifier"),
            "sell_exchange": market_max.get("name") or market_max.get("identifier"),
            "buy_price": min_price,
            "sell_price": max_price,
            "spread_pct": spread_pct,
            "pair": f"{min_t.get('base')}/{min_t.get('target')}",
            "buy_trade_url": min_t.get("trade_url"),
            "sell_trade_url": max_t.get("trade_url"),
        }

    # Provide some sample tickers for transparency (top 5 cheapest and top 5 most expensive)
    samples = []
    for t in (sorted_by_price[:5] + list(reversed(sorted_by_price[-5:]))):
        m = t.get("market") or {}
        samples.append(
            {
                "exchange": m.get("name") or m.get("identifier"),
                "last": t.get("last"),
                "volume": t.get("volume"),
                "trust_score": t.get("trust_score"),
                "bid_ask_spread_percentage": t.get("bid_ask_spread_percentage"),
                "trade_url": t.get("trade_url"),
            }
        )

    return {
        "coin_id": coin_id,
        "vs_currency": vs_currency,
        "exchanges": len(tickers),
        "min_price": min_price,
        "max_price": max_price,
        "spread_pct": spread_pct,
        "opportunity": opportunity,
        "top_samples": samples,
    }

