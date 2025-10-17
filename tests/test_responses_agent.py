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
                "function": {
                    "name": "list_tickers",
                    "description": "List tickers",
                    "parameters": {"type": "object", "properties": {}},
                },
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
                        "type": "tool_call",
                        "id": "call-1",
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
            model="gpt-5.1-mini",
        )
    )

    assert result.splitlines()[-1] == "Found 1 opportunity."
    assert "Checking markets." in result
    assert agent.calls == [("list_tickers", {"coin": "bitcoin", "vs": "usd"})]
    assert len(responses_api.calls) == 2

    tool_messages = [m for m in messages if m.get("role") == "tool"]
    assert len(tool_messages) == 1
    payload = json.loads(tool_messages[0]["content"][0]["text"])  # type: ignore[index]
    assert payload["status"] == "ok"


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
            model="gpt-5.1-mini",
        )
    )

    assert result == "Hello there."
    assert not agent.calls
    assert messages[-1]["role"] == "assistant"
