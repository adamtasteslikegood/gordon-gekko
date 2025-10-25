import asyncio
import json
from typing import Any, Dict, List

from gekko.ai.responses import build_text_message, generate_response_with_tools


class StubAgent:
    def __init__(self) -> None:
        self.calls: List[tuple[str, Dict[str, Any]]] = []
        self._tools = [
            {
                "type": "function",
                "name": "list_tickers",
                "description": "List tickers",
                "parameters": {"type": "object", "properties": {}},
            }
        ]

    def available_tools(self) -> List[Dict[str, Any]]:
        return self._tools

    async def dispatch(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        self.calls.append((tool_name, arguments))
        return {"status": "ok", "data": arguments}


class FakeContent:
    def __init__(self, payload: Dict[str, Any]):
        self._payload = payload

    def model_dump(self) -> Dict[str, Any]:
        return dict(self._payload)


class FakeOutput:
    def __init__(self, payload: Dict[str, Any]):
        self._payload = payload

    def model_dump(self) -> Dict[str, Any]:
        data = dict(self._payload)
        if "content" in data and isinstance(data["content"], list):
            data["content"] = [FakeContent(block) for block in data["content"]]
        return data


class FakeResponse:
    def __init__(self, output: List[Dict[str, Any]], *, output_text: str = ""):
        self.output = [FakeOutput(item) for item in output]
        self.output_text = output_text


class FakeResponsesAPI:
    def __init__(self, responses: List[FakeResponse]):
        self._responses = list(responses)
        self.calls: List[Dict[str, Any]] = []

    def create(self, **kwargs: Any) -> FakeResponse:
        self.calls.append(kwargs)
        return self._responses.pop(0)


def test_generate_response_with_tools_handles_tool_call():
    agent = StubAgent()
    responses_api = FakeResponsesAPI(
        [
            FakeResponse(
                [
                    {
                        "type": "message",
                        "role": "assistant",
                        "content": [{"type": "text", "text": "Checking markets."}],
                    },
                    {
                        "type": "function_call",
                        "id": "call-1",
                        "call_id": "call-1",
                        "name": "list_tickers",
                        "arguments": json.dumps({"coin": "bitcoin", "vs": "usd"}),
                    },
                ]
            ),
            FakeResponse(
                [
                    {
                        "type": "message",
                        "role": "assistant",
                        "content": [
                            {"type": "text", "text": "Found 1 opportunity."},
                        ],
                    }
                ],
                output_text="Found 1 opportunity.",
            ),
        ]
    )

    messages = [build_text_message("system", "You are helpful.")]

    result = asyncio.run(
        generate_response_with_tools(
            responses_api=responses_api,
            agent=agent,  # type: ignore[arg-type]
            messages=messages,
            model="gpt-5",
        )
    )

    assert result.splitlines()[-1] == "Found 1 opportunity."
    assert "Checking markets." in result
    assert agent.calls == [("list_tickers", {"coin": "bitcoin", "vs": "usd"})]
    assert len(responses_api.calls) == 2

    tool_messages = [m for m in messages if m.get("type") == "function_call_output"]
    assert len(tool_messages) == 1
    payload = json.loads(tool_messages[0]["output"])  # type: ignore[index]
    assert payload["status"] == "ok"
    call_entries = [m for m in messages if m.get("type") == "function_call"]
    assert call_entries[0]["id"] == "call-1"


def test_generate_response_with_tools_handles_dict_arguments():
    agent = StubAgent()
    responses_api = FakeResponsesAPI(
        [
            FakeResponse(
                [
                    {
                        "type": "message",
                        "role": "assistant",
                        "content": [{"type": "text", "text": "Checking dict."}],
                    },
                    {
                        "type": "function_call",
                        "id": "call-1",
                        "call_id": "call-1",
                        "name": "list_tickers",
                        "arguments": {"coin": "ethereum", "vs": "usd"},
                    },
                ]
            ),
            FakeResponse(
                [
                    {
                        "type": "message",
                        "role": "assistant",
                        "content": [
                            {"type": "text", "text": "Dict handled."},
                        ],
                    }
                ],
                output_text="Dict handled.",
            ),
        ]
    )

    messages = [build_text_message("system", "You are helpful.")]

    result = asyncio.run(
        generate_response_with_tools(
            responses_api=responses_api,
            agent=agent,  # type: ignore[arg-type]
            messages=messages,
            model="gpt-5",
        )
    )

    assert "Dict handled." in result
    assert agent.calls == [("list_tickers", {"coin": "ethereum", "vs": "usd"})]


def test_generate_response_with_tools_handles_non_object_arguments_gracefully():
    agent = StubAgent()
    responses_api = FakeResponsesAPI(
        [
            FakeResponse(
                [
                    {
                        "type": "function_call",
                        "id": "call-1",
                        "call_id": "call-1",
                        "name": "list_tickers",
                        "arguments": ["unexpected"],
                    },
                ]
            ),
            FakeResponse(
                [
                    {
                        "type": "message",
                        "role": "assistant",
                        "content": [
                            {"type": "text", "text": "Still working."},
                        ],
                    }
                ],
                output_text="Still working.",
            ),
        ]
    )

    messages = [build_text_message("system", "You are helpful.")]

    result = asyncio.run(
        generate_response_with_tools(
            responses_api=responses_api,
            agent=agent,  # type: ignore[arg-type]
            messages=messages,
            model="gpt-5",
        )
    )

    assert result.endswith("Still working.")
    assert agent.calls == [("list_tickers", {})]


def test_generate_response_with_tools_returns_direct_message():
    agent = StubAgent()
    responses_api = FakeResponsesAPI(
        [
            FakeResponse(
                [
                    {
                        "type": "message",
                        "role": "assistant",
                        "content": [{"type": "text", "text": "Hello there."}],
                    }
                ],
                output_text="Hello there.",
            )
        ]
    )

    messages = [build_text_message("system", "You are helpful."), build_text_message("user", "Hi")]

    result = asyncio.run(
        generate_response_with_tools(
            responses_api=responses_api,
            agent=agent,  # type: ignore[arg-type]
            messages=messages,
            model="gpt-5",
        )
    )

    assert result == "Hello there."
    assert not agent.calls
    assert messages[-1]["role"] == "assistant"


def test_generate_response_with_tools_handles_function_blob_payloads():
    agent = StubAgent()
    responses_api = FakeResponsesAPI(
        [
            FakeResponse(
                [
                    {
                        "type": "function_call",
                        "function": {
                            "id": "call-fn",
                            "call_id": "call-fn",
                            "name": "list_tickers",
                            "arguments": json.dumps({"coin": "dogecoin"}),
                        },
                    }
                ]
            ),
            FakeResponse(
                [
                    {
                        "type": "message",
                        "role": "assistant",
                        "content": [
                            {"type": "text", "text": "Dogecoin fetched."},
                        ],
                    }
                ],
                output_text="Dogecoin fetched.",
            ),
        ]
    )

    messages = [build_text_message("system", "You are helpful.")]

    result = asyncio.run(
        generate_response_with_tools(
            responses_api=responses_api,
            agent=agent,  # type: ignore[arg-type]
            messages=messages,
            model="gpt-5",
        )
    )

    assert "Dogecoin fetched." in result
    assert agent.calls == [("list_tickers", {"coin": "dogecoin"})]

    tool_messages = [m for m in messages if m.get("type") == "function_call_output"]
    assert tool_messages[0]["call_id"] == "call-fn"
    call_entries = [m for m in messages if m.get("type") == "function_call"]
    assert call_entries[0]["function"]["name"] == "list_tickers"

