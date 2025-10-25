# tests/test_arbitrage.py

**Purpose:** Key module in the repository.

**Public API:** test_arbitrage_considers_later_pairs_after_failure, test_arbitrage_handles_multiple_pairs_per_exchange_combo, test_normalize_and_arbitrage_detection

**Key symbols:**
- function `_ticker` (13 lines)
- function `test_normalize_and_arbitrage_detection` (20 lines)
- function `test_arbitrage_considers_later_pairs_after_failure` (35 lines)
- function `test_arbitrage_handles_multiple_pairs_per_exchange_combo` (39 lines)

**Internal deps:** gekko.services.arbitrage
**External deps:** _None_
**Used by:** _No dependents identified_

**Complexity:** 99 LOC, 4 functions, max function length 39
**Tests:** tests/test_arbitrage.py, tests/test_arbitrage_fees.py
**Annotations:** None
**Security notes:** None
**Risk profile:** complexity=elevated, global_state=False, io_side_effects=False
