# src/gekko/cli.py

**Purpose:** Key module in the repository.

**Public API:** build_parser, main, run_agent, run_arbitrage, run_gpt_cli, run_interactive, run_tickers, serve_agent

**Key symbols:**
- function `_print_table` (10 lines)
- function `_fetch_normalized_tickers` (21 lines)
- function `run_tickers` (24 lines)
- function `run_arbitrage` (70 lines)
- function `build_parser` (77 lines)
- function `main` (8 lines)
- function `serve_agent` (89 lines)
- function `run_agent` (4 lines)
- function `run_gpt_cli` (18 lines)
- function `run_interactive` (151 lines)

**Internal deps:** _None_
**External deps:** argparse, asyncio, json, logging, os, sys, typing
**Used by:** tests/test_agent.py

**Complexity:** 454 LOC, 10 functions, max function length 151
**Tests:** _No tests located_
**Annotations:** None
**Security notes:** None
**Risk profile:** complexity=high, global_state=False, io_side_effects=False
