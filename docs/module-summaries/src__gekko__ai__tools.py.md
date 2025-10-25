# src/gekko/ai/tools.py

**Purpose:** Key module in the repository.

**Public API:** ToolSpec, TOOL_SPECS, list_tools

**Key symbols:**
- class `ToolSpec` (19 lines) — Definition of a single GPT tool backed by Gordon Gekko services.
- function `_ensure_sequence` (2 lines)
- function `_simple_price_handler` (5 lines)
- function `_coins_markets_handler` (15 lines)
- function `_coin_tickers_handler` (22 lines)
- function `_market_arbitrage_handler` (57 lines)
- function `_arbitrage_opportunities_handler` (22 lines)
- function `_arbitrage_per_exchange_prices_handler` (38 lines)
- function `list_tools` (4 lines) — Return tool specifications formatted for GPT function calling.

**Internal deps:** _None_
**External deps:** __future__, dataclasses, typing
**Used by:** _No dependents identified_

**Complexity:** 434 LOC, 8 functions, max function length 57
**Tests:** tests/test_ai_tools.py
**Annotations:** None
**Security notes:** None
**Risk profile:** complexity=high, global_state=False, io_side_effects=False
