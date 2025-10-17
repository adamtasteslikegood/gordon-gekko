import asyncio
import io
import json
from typing import Any, Dict, List

from gekko.agents.interactive import GekkoAgent
from gekko.cli import serve_agent


def test_agent_cli_routes_requests(monkeypatch):
    async def fake_fetch_normalized_tickers(**_: Any) -> List[Dict[str, Any]]:
        return [
            {
                "exchange": "FooEx",
                "exchange_id": "foo",
                "pair": "BTC/USD",
                "price": 30000.0,
                "last_vs": 30000.0,
                "volume_vs": 120.0,
                "trust_score": "green",
            }
        ]

    def fake_compute_opportunities(tickers: List[Dict[str, Any]], **_: Any) -> List[Dict[str, Any]]:
        assert tickers
        return [
            {
                "buy": {"exchange": "FooEx", "price": 30000.0, "pair": "BTC/USD"},
                "sell": {"exchange": "BarEx", "price": 31500.0, "pair": "BTC/USD"},
                "raw_spread_pct": 5.0,
                "net_spread_pct": 4.5,
                "est_net_profit_vs": 450.0,
            }
        ]

    monkeypatch.setattr(
        "gekko.agents.tools._fetch_normalized_tickers", fake_fetch_normalized_tickers
    )
    monkeypatch.setattr(
        "gekko.agents.tools.compute_opportunities", fake_compute_opportunities
    )

    requests = "\n".join(
        [
            json.dumps(
                {
                    "request_id": "tickers-1",
                    "tool": "list_tickers",
                    "arguments": {"coin": "bitcoin", "vs": "usd", "pages": 2},
                }
            ),
            json.dumps(
                {
                    "request_id": "arb-1",
                    "tool": "find_arbitrage",
                    "arguments": {"coin": "bitcoin", "vs": "usd", "min_spread_pct": 2.5},
                }
            ),
        ]
    )
    input_stream = io.StringIO(requests)
    output_stream = io.StringIO()

    agent = GekkoAgent()
    asyncio.run(
        serve_agent(agent=agent, input_stream=input_stream, output_stream=output_stream)
    )

    output_stream.seek(0)
    messages = [json.loads(line) for line in output_stream.getvalue().splitlines()]
    assert messages[0]["status"] == "ready"
    assert len(messages[0]["tools"]) >= 2
    assert all(tool["type"] == "function" for tool in messages[0]["tools"])
    first_tool = messages[0]["tools"][0]["function"]
    assert first_tool["name"] == "list_tickers"
    assert first_tool["parameters"]["type"] == "object"

    tickers_response = messages[1]
    assert tickers_response["status"] == "ok"
    assert tickers_response["tool"] == "list_tickers"
    assert tickers_response["data"]["count"] == 1
    assert tickers_response["data"]["tickers"][0]["exchange"] == "FooEx"

    arb_response = messages[2]
    assert arb_response["status"] == "ok"
    assert arb_response["tool"] == "find_arbitrage"
    assert arb_response["data"]["count"] == 1
    assert arb_response["data"]["opportunities"][0]["sell"]["exchange"] == "BarEx"


def test_agent_cli_validation_error():
    requests = json.dumps({"request_id": "bad", "tool": "list_tickers", "arguments": {}})
    input_stream = io.StringIO(requests)
    output_stream = io.StringIO()

    agent = GekkoAgent()
    asyncio.run(
        serve_agent(agent=agent, input_stream=input_stream, output_stream=output_stream)
    )

    output_stream.seek(0)
    messages = [json.loads(line) for line in output_stream.getvalue().splitlines()]
    assert messages[0]["status"] == "ready"

    error_payload = messages[1]
    assert error_payload["status"] == "error"
    assert error_payload["error"]["type"] == "validation_error"
    assert error_payload["request_id"] == "bad"


def test_agent_cli_unknown_tool():
    requests = json.dumps({"request_id": "oops", "tool": "nope", "arguments": {}})
    input_stream = io.StringIO(requests)
    output_stream = io.StringIO()

    agent = GekkoAgent()
    asyncio.run(
        serve_agent(agent=agent, input_stream=input_stream, output_stream=output_stream)
    )

    output_stream.seek(0)
    messages = [json.loads(line) for line in output_stream.getvalue().splitlines()]
    assert messages[0]["status"] == "ready"

    error_payload = messages[1]
    assert error_payload["status"] == "error"
    assert error_payload["tool"] == "nope"
    assert error_payload["error"]["type"] == "unknown_tool"


def test_agent_cli_invalid_json():
    requests = "{not json}\n"
    input_stream = io.StringIO(requests)
    output_stream = io.StringIO()

    agent = GekkoAgent()
    asyncio.run(
        serve_agent(agent=agent, input_stream=input_stream, output_stream=output_stream)
    )

    output_stream.seek(0)
    raw_lines = output_stream.getvalue().splitlines()
    assert json.loads(raw_lines[0])["status"] == "ready"

    error_payload = json.loads(raw_lines[1])
    assert error_payload["status"] == "error"
    assert error_payload["error"]["type"] == "invalid_json"
