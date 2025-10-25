# src/gekko/agents/tools.py

**Purpose:** Key module in the repository.

**Public API:** Tool, list_tools

**Key symbols:**
- class `Tool` (19 lines) — Metadata describing an agent tool.
- function `_to_bool` (8 lines)
- function `_to_float` (7 lines)
- function `_float_default` (3 lines)
- function `_to_int` (7 lines)
- function `_fetch_normalized_tickers` (25 lines)
- function `_tool_list_tickers` (10 lines)
- function `_tool_find_arbitrage` (24 lines)
- function `list_tools` (56 lines)

**Internal deps:** _None_
**External deps:** __future__, asyncio, dataclasses, typing
**Used by:** _No dependents identified_

**Complexity:** 163 LOC, 8 functions, max function length 56
**Tests:** tests/test_ai_tools.py
**Annotations:** None
**Security notes:** None
**Risk profile:** complexity=medium, global_state=False, io_side_effects=False
