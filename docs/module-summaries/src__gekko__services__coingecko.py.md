# src/gekko/services/coingecko.py

**Purpose:** Key module in the repository.

**Public API:** get_coin_tickers, get_coins_markets, get_exchanges_list, get_simple_price, get_supported_vs_currencies

**Key symbols:**
- function `get_simple_price` (9 lines)
- function `get_coin_tickers` (28 lines) — Fetch tickers for a coin across exchanges.
- function `get_supported_vs_currencies` (5 lines)
- function `get_coins_markets` (22 lines)
- function `get_exchanges_list` (6 lines)

**Internal deps:** _None_
**External deps:** httpx, typing
**Used by:** _No dependents identified_

**Complexity:** 71 LOC, 5 functions, max function length 28
**Tests:** _No tests located_
**Annotations:** None
**Security notes:** None
**Risk profile:** complexity=elevated, global_state=False, io_side_effects=True
