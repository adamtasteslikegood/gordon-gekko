# src/gekko/routers/arbitrage.py

**Purpose:** Key module in the repository.

**Public API:** arbitrage_opportunities, per_exchange_prices

**Key symbols:**
- function `arbitrage_opportunities` (20 lines) — Compute a simple cross-exchange arbitrage opportunity summary using CoinGecko tickers.
- function `per_exchange_prices` (42 lines) — Return last trade prices per exchange for a coin filtered by `vs_currency`.

**Internal deps:** _None_
**External deps:** fastapi, typing
**Used by:** _No dependents identified_

**Complexity:** 65 LOC, 2 functions, max function length 42
**Tests:** tests/test_arbitrage.py, tests/test_arbitrage_fees.py
**Annotations:** None
**Security notes:** None
**Risk profile:** complexity=elevated, global_state=False, io_side_effects=False
