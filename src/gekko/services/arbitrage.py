from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple


TRUST_ORDER = {"red": 0, "yellow": 1, "green": 2}


def _norm_vs_price(t: Dict[str, Any], vs_currency: str) -> Optional[float]:
    target = (t.get("target") or "").lower()
    vs = (vs_currency or "").lower()
    if vs and vs == target:
        return float(t.get("last")) if t.get("last") is not None else None
    conv = t.get("converted_last") or {}
    if vs in conv:
        try:
            return float(conv[vs])
        except Exception:
            return None
    return None


def _norm_vs_volume(t: Dict[str, Any], vs_currency: str) -> Optional[float]:
    vs = (vs_currency or "").lower()
    conv = t.get("converted_volume") or {}
    if vs in conv:
        try:
            return float(conv[vs])
        except Exception:
            return None
    # Fallback if volume is expressed in target vs and matches requested
    if (t.get("target") or "").lower() == vs and t.get("volume") is not None:
        try:
            return float(t.get("volume"))
        except Exception:
            return None
    return None


def normalize_tickers(
    tickers: List[Dict[str, Any]],
    *,
    vs_currency: str = "usd",
    min_trust: str = "yellow",
    exclude_risky: bool = True,
    min_volume: Optional[float] = None,
) -> List[Dict[str, Any]]:
    min_trust_rank = TRUST_ORDER.get(min_trust, 1)
    out: List[Dict[str, Any]] = []
    for t in tickers:
        # Risk filtering
        if exclude_risky and (t.get("is_stale") or t.get("is_anomaly")):
            continue
        trust = t.get("trust_score") or "red"
        if TRUST_ORDER.get(trust, 0) < min_trust_rank:
            continue

        last_vs = _norm_vs_price(t, vs_currency)
        if last_vs is None:
            continue
        vol_vs = _norm_vs_volume(t, vs_currency)
        if min_volume is not None and (vol_vs is None or vol_vs < float(min_volume)):
            continue

        market = t.get("market") or {}
        out.append(
            {
                "exchange": market.get("name") or market.get("identifier"),
                "exchange_id": market.get("identifier"),
                "pair": f"{t.get('base')}/{t.get('target')}",
                "last_vs": last_vs,
                "price": last_vs,
                "volume_vs": vol_vs,
                "trust_score": trust,
                "trade_url": t.get("trade_url"),
                "raw": t,
            }
        )

    return out


def _net_spread(buy: float, sell: float, *,
                buy_fee_pct: float, sell_fee_pct: float,
                buy_slippage_pct: float, sell_slippage_pct: float,
                transfer_fee_vs: float, latency_risk_buffer_pct: float) -> Tuple[float, float, float]:
    net_buy = buy * (1 + (buy_fee_pct + buy_slippage_pct) / 100.0)
    net_sell = sell * (1 - (sell_fee_pct + sell_slippage_pct) / 100.0)
    net_profit_vs = net_sell - net_buy - transfer_fee_vs
    net_spread_pct = (net_profit_vs / net_buy * 100.0) if net_buy > 0 else 0.0
    net_spread_pct -= latency_risk_buffer_pct
    gross_spread_pct = (sell - buy) / buy * 100.0 if buy > 0 else 0.0
    return gross_spread_pct, net_spread_pct, net_profit_vs


def compute_opportunities(
    tickers: List[Dict[str, Any]],
    *,
    min_spread_pct: float = 0.5,
    top_n: int = 10,
    buy_fee_pct: float = 0.0,
    sell_fee_pct: float = 0.0,
    buy_slippage_pct: float = 0.0,
    sell_slippage_pct: float = 0.0,
    transfer_fee_vs: float = 0.0,
    notional_vs: float = 1000.0,
    latency_risk_buffer_pct: float = 0.0,
) -> List[Dict[str, Any]]:
    if not tickers:
        return []

    # Sort candidates
    def _price(d: Dict[str, Any]) -> float:
        return float(d.get("last_vs") if d.get("last_vs") is not None else d.get("price"))

    buys = sorted(tickers, key=lambda t: _price(t))[: min(top_n, 25)]
    sells = list(reversed(sorted(tickers, key=lambda t: _price(t))))[
        : min(top_n, 25)
    ]

    results: List[Dict[str, Any]] = []
    seen_pairs = set()
    for b in buys:
        for s in sells:
            if b["exchange"] == s["exchange"]:
                continue
            pb, ps = _price(b), _price(s)
            pair_key = (b["exchange"], s["exchange"]) if pb <= ps else (s["exchange"], b["exchange"])
            if pair_key in seen_pairs:
                continue
            seen_pairs.add(pair_key)

            gross_spread_pct, _, _ = _net_spread(
                pb,
                ps,
                buy_fee_pct=buy_fee_pct,
                sell_fee_pct=sell_fee_pct,
                buy_slippage_pct=buy_slippage_pct,
                sell_slippage_pct=sell_slippage_pct,
                transfer_fee_vs=transfer_fee_vs,
                latency_risk_buffer_pct=latency_risk_buffer_pct,
            )
            total_fees_slippage = (buy_fee_pct + sell_fee_pct + buy_slippage_pct + sell_slippage_pct)
            flat_fees_pct = (transfer_fee_vs / notional_vs * 100.0) if notional_vs > 0 else 0.0
            net_spread_pct = gross_spread_pct - total_fees_slippage - flat_fees_pct - latency_risk_buffer_pct
            net_profit_vs = pb * (net_spread_pct / 100.0)
            est_net_profit_vs = notional_vs * (net_spread_pct / 100.0)

            if net_spread_pct < min_spread_pct:
                continue

            results.append(
                {
                    "buy": {
                        "exchange": b.get("exchange"),
                        "exchange_id": b.get("exchange_id"),
                        "price": pb,
                        "pair": b.get("pair"),
                        "trade_url": b.get("trade_url"),
                    },
                    "sell": {
                        "exchange": s.get("exchange"),
                        "exchange_id": s.get("exchange_id"),
                        "price": ps,
                        "pair": s.get("pair"),
                        "trade_url": s.get("trade_url"),
                    },
                    "raw_spread_pct": gross_spread_pct,
                    "net_spread_pct": net_spread_pct,
                    "fees_slippage_pct": total_fees_slippage,
                    "flat_fees_pct": flat_fees_pct,
                    "est_net_profit_vs_per_unit": net_profit_vs,
                    "est_net_profit_vs": est_net_profit_vs,
                }
            )

            if len(results) >= top_n:
                break
        if len(results) >= top_n:
            break

    # Order by highest net spread
    results.sort(key=lambda x: x["net_spread_pct"], reverse=True)
    return results
