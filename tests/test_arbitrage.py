from gekko.services.arbitrage import normalize_tickers, compute_opportunities


def _ticker(exchange_id, exchange_name, base, target, last, ts="green", vol_usd=1_000_000):
    return {
        "base": base,
        "target": target,
        "last": last,
        "converted_last": {"usd": last},
        "converted_volume": {"usd": vol_usd},
        "market": {"identifier": exchange_id, "name": exchange_name},
        "trust_score": ts,
        "is_stale": False,
        "is_anomaly": False,
        "trade_url": f"https://{exchange_id}.com/trade",
    }


def test_normalize_and_arbitrage_detection():
    tickers = [
        _ticker("exA", "Exchange A", "BTC", "USD", 60000.0),
        _ticker("exB", "Exchange B", "BTC", "USD", 61200.0),
        _ticker("exC", "Exchange C", "BTC", "USD", 59800.0),
    ]

    normalized = normalize_tickers(tickers, vs_currency="usd", min_trust="yellow", exclude_risky=True)
    assert len(normalized) == 3
    prices = sorted([t["price"] for t in normalized])
    assert prices == [59800.0, 60000.0, 61200.0]

    opps = compute_opportunities(normalized, min_spread_pct=1.0, top_n=5)
    # Best opp is buy at 59800 (exC) and sell at 61200 (exB)
    assert opps, "Expected at least one opportunity"
    best = opps[0]
    assert best["buy"]["exchange_id"] == "exC"
    assert best["sell"]["exchange_id"] == "exB"
    spread = (61200.0 - 59800.0) / 59800.0 * 100.0
    assert abs(best["raw_spread_pct"] - spread) < 1e-6
