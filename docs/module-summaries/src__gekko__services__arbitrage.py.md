# src/gekko/services/arbitrage.py

**Purpose:** Key module in the repository.

**Public API:** compute_opportunities, normalize_tickers

**Key symbols:**
- function `_norm_vs_price` (12 lines)
- function `_norm_vs_volume` (15 lines)
- function `normalize_tickers` (41 lines)
- function `_net_spread` (11 lines)
- function `compute_opportunities` (102 lines)

**Internal deps:** _None_
**External deps:** __future__, typing
**Used by:** tests/test_arbitrage.py, tests/test_arbitrage_fees.py

**Complexity:** 167 LOC, 5 functions, max function length 102
**Tests:** tests/test_arbitrage.py, tests/test_arbitrage_fees.py
**Annotations:** None
**Security notes:** None
**Risk profile:** complexity=medium, global_state=False, io_side_effects=False
