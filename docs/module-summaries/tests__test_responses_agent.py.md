# tests/test_responses_agent.py

**Purpose:** Key module in the repository.

**Public API:** FakeContent, FakeOutput, FakeResponse, FakeResponsesAPI, StubAgent, test_generate_response_with_tools_handles_dict_arguments, test_generate_response_with_tools_handles_non_object_arguments_gracefully, test_generate_response_with_tools_handles_tool_call, test_generate_response_with_tools_returns_direct_message

**Key symbols:**
- class `StubAgent` (20 lines)
- class `FakeContent` (6 lines)
- class `FakeOutput` (9 lines)
- class `FakeResponse` (4 lines)
- class `FakeResponsesAPI` (8 lines)
- function `test_generate_response_with_tools_handles_tool_call` (54 lines)
- function `test_generate_response_with_tools_handles_dict_arguments` (47 lines)
- function `test_generate_response_with_tools_handles_non_object_arguments_gracefully` (42 lines)
- function `test_generate_response_with_tools_returns_direct_message` (31 lines)

**Internal deps:** gekko.ai.responses
**External deps:** asyncio, json, typing
**Used by:** _No dependents identified_

**Complexity:** 207 LOC, 4 functions, max function length 54
**Tests:** tests/test_responses_agent.py
**Annotations:** None
**Security notes:** None
**Risk profile:** complexity=medium, global_state=False, io_side_effects=False
