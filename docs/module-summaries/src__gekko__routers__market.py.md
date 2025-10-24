# src/gekko/routers/market.py

**Purpose:** Key module in the repository.

**Public API:** arbitrage, coin_tickers, coins_markets, exchanges, simple_price, supported_vs_currencies

**Key symbols:**
- function `simple_price` (10 lines) — Proxy to CoinGecko's /simple/price endpoint.
- function `exchanges` (5 lines)
- function `supported_vs_currencies` (2 lines)
- function `coins_markets` (15 lines)
- function `coin_tickers` (25 lines) — Fetch tickers for a coin across exchanges and normalize prices to `vs_currency`.
- function `arbitrage` (62 lines) — Compute simple cross-exchange arbitrage opportunities based on last trade prices.

**Internal deps:** _None_
**External deps:** fastapi, typing
**Used by:** _No dependents identified_

**Complexity:** 135 LOC, 6 functions, max function length 62
**Tests:** _No tests located_
**Annotations:** None
**Security notes:** None
**Risk profile:** complexity=medium, global_state=False, io_side_effects=False
