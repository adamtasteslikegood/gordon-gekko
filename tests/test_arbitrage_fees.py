from gekko.services.arbitrage import compute_opportunities


def test_net_spread_with_fees_and_slippage():
    # Two normalized tickers: buy at 100, sell at 110
    normalized = [
        {
            "exchange": "A",
            "exchange_id": "exA",
            "pair": "BTC/USD",
            "price": 100.0,
            "volume_vs": 1_000_000,
            "trust_score": "green",
        },
        {
            "exchange": "B",
            "exchange_id": "exB",
            "pair": "BTC/USD",
            "price": 110.0,
            "volume_vs": 1_000_000,
            "trust_score": "green",
        },
    ]

    # Fees and slippage: 0.1% buy, 0.1% sell, 0.2% slippage each, flat transfer $5 on $1000 notional
    opps = compute_opportunities(
        normalized,
        min_spread_pct=0.0,
        top_n=5,
        buy_fee_pct=0.1,
        sell_fee_pct=0.1,
        buy_slippage_pct=0.2,
        sell_slippage_pct=0.2,
        transfer_fee_vs=5.0,
        notional_vs=1000.0,
        latency_risk_buffer_pct=0.0,
    )

    assert opps, "Expected an opportunity to exist"
    best = opps[0]
    # Raw spread is 10%
    assert abs(best["raw_spread_pct"] - 10.0) < 1e-6
    # Total percentage deductions (fees+slippage) = 0.1+0.1+0.2+0.2 = 0.6%
    assert abs(best["fees_slippage_pct"] - 0.6) < 1e-6
    # Flat fee impact = 5/1000 = 0.5%
    assert abs(best["flat_fees_pct"] - 0.5) < 1e-6
    # Net spread = 10 - 0.6 - 0.5 = 8.9%
    assert abs(best["net_spread_pct"] - 8.9) < 1e-6
    # Profit on $1000 notional ≈ $89
    assert abs(best["est_net_profit_vs"] - 89.0) < 1e-6

