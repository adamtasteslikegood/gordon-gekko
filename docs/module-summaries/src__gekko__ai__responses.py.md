# src/gekko/ai/responses.py

**Purpose:** Key module in the repository.

**Public API:** build_text_message, generate_response_with_tools, run_gpt5_agent_cli

**Key symbols:**
- function `build_text_message` (4 lines) — Create a Responses-style message containing a plain text block.
- function `_normalize_dict` (14 lines)
- function `_normalize_content` (7 lines)
- function `_extract_output_items` (11 lines)
- function `_extract_output_text` (12 lines)
- function `_call_responses` (2 lines)
- function `generate_response_with_tools` (129 lines) — Execute a Responses completion loop that fulfils tool calls.
- function `run_gpt5_agent_cli` (54 lines) — Launch an interactive GPT-5 session in the terminal.

**Internal deps:** _None_
**External deps:** __future__, asyncio, json, logging, openai, typing
**Used by:** tests/test_responses_agent.py

**Complexity:** 218 LOC, 8 functions, max function length 129
**Tests:** tests/test_responses_agent.py
**Annotations:** None
**Security notes:** None
**Risk profile:** complexity=medium, global_state=False, io_side_effects=False
