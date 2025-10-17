"""Integration helpers for the OpenAI Responses API."""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, Dict, Iterable, List, MutableMapping

from ..agents.interactive import GekkoAgent

logger = logging.getLogger("gekko.ai.responses")

DEFAULT_SYSTEM_PROMPT = (
    "You are Gordon Gekko's market intelligence analyst. "
    "Use the provided tools to fetch live market data and arbitrage insights. "
    "Only rely on the tools for fresh numbers; summarise the results for the user."
)


ContentBlock = Dict[str, Any]
Message = Dict[str, Any]


def build_text_message(role: str, text: str) -> Message:
    """Create a Responses-style message containing a plain text block."""

    return {"role": role, "content": [{"type": "text", "text": text}]}


def _normalize_dict(item: Any) -> Dict[str, Any]:
    if item is None:
        return {}
    if isinstance(item, MutableMapping):
        return dict(item)
    if hasattr(item, "model_dump"):
        return item.model_dump()  # type: ignore[no-any-return]
    if hasattr(item, "__dict__"):
        return {
            key: value
            for key, value in item.__dict__.items()
            if not key.startswith("_")
        }
    return {}


def _normalize_content(blocks: Iterable[Any] | None) -> List[ContentBlock]:
    if not blocks:
        return []
    normalized: List[ContentBlock] = []
    for block in blocks:
        normalized.append(_normalize_dict(block))
    return normalized


def _extract_output_items(response: Any) -> List[Dict[str, Any]]:
    if response is None:
        return []
    raw_items: Any = None
    if hasattr(response, "output"):
        raw_items = getattr(response, "output")
    elif isinstance(response, MutableMapping):
        raw_items = response.get("output")
    if not isinstance(raw_items, Iterable):
        return []
    return [_normalize_dict(item) for item in raw_items]


def _extract_output_text(response: Any) -> str:
    if response is None:
        return ""
    if hasattr(response, "output_text"):
        text = getattr(response, "output_text")
        if isinstance(text, str):
            return text
    if isinstance(response, MutableMapping):
        text = response.get("output_text")
        if isinstance(text, str):
            return text
    return ""


async def _call_responses(responses_api: Any, **kwargs: Any) -> Any:
    return await asyncio.to_thread(responses_api.create, **kwargs)


async def generate_response_with_tools(
    *,
    responses_api: Any,
    agent: GekkoAgent,
    messages: List[Message],
    model: str,
    logger: logging.Logger | None = None,
    max_iterations: int = 8,
) -> str:
    """Execute a Responses completion loop that fulfils tool calls."""

    log = logger or logging.getLogger("gekko.ai.responses.loop")
    tools = agent.available_tools()

    final_chunks: List[str] = []
    iteration = 0

    while iteration < max_iterations:
        iteration += 1
        response = await _call_responses(
            responses_api,
            model=model,
            input=messages,
            tools=tools,
        )

        output_items = _extract_output_items(response)
        output_text = _extract_output_text(response)

        tool_calls: List[Dict[str, Any]] = []

        if not output_items and output_text:
            final_chunks.append(output_text.strip())
            break

        for item in output_items:
            item_type = item.get("type")
            if item_type == "tool_call":
                tool_calls.append(item)
                continue

            if item_type == "message":
                role = item.get("role", "assistant")
                content = _normalize_content(item.get("content"))

                text_fragments = [
                    block.get("text", "")
                    for block in content
                    if block.get("type") in {"text", "output_text"}
                    and isinstance(block.get("text"), str)
                ]

                if role == "assistant" and text_fragments:
                    combined = "\n".join(fragment.strip() for fragment in text_fragments if fragment.strip())
                    if combined:
                        final_chunks.append(combined)

                message_payload: Message = {
                    "role": role,
                    "content": [
                        {
                            "type": block.get("type", "text"),
                            "text": block.get("text", ""),
                        }
                        for block in content
                        if isinstance(block.get("text"), str)
                    ],
                }

                if role == "tool" and "tool_call_id" in item:
                    message_payload["tool_call_id"] = item["tool_call_id"]

                messages.append(message_payload)

        if not tool_calls:
            break

        tool_messages: List[Message] = []
        for call in tool_calls:
            tool_name = call.get("name") or ""
            arguments_raw = call.get("arguments") or "{}"
            try:
                arguments = json.loads(arguments_raw)
            except json.JSONDecodeError:
                log.warning(
                    "Failed to decode tool arguments for %s: %s",
                    tool_name,
                    arguments_raw,
                )
                arguments = {}

            result = await agent.dispatch(tool_name, arguments)
            tool_messages.append(
                {
                    "role": "tool",
                    "tool_call_id": call.get("id"),
                    "content": [
                        {
                            "type": "output_text",
                            "text": json.dumps(result),
                        }
                    ],
                }
            )

        messages.extend(tool_messages)

    else:  # pragma: no cover - defensive guard against API regressions
        raise RuntimeError("Exceeded maximum iterations while processing tool calls.")

    response_text = "\n\n".join(chunk for chunk in final_chunks if chunk).strip()
    return response_text


async def run_gpt5_agent_cli(
    *,
    model: str,
    system_prompt: str | None = None,
    agent: GekkoAgent | None = None,
    responses_api: Any | None = None,
) -> None:
    """Launch an interactive GPT-5 session in the terminal."""

    agent = agent or GekkoAgent()

    if responses_api is None:
        from openai import OpenAI  # pylint: disable=import-error

        client = OpenAI()
        responses_api = client.responses

    prompt = system_prompt or DEFAULT_SYSTEM_PROMPT
    messages: List[Message] = []
    if prompt:
        messages.append(build_text_message("system", prompt))

    print("Connected to GPT-5 Responses API. Type 'exit' to quit.")
    print("Available tools:")
    for tool in agent.available_tools():
        fn = tool.get("function", {})
        print(f"  • {fn.get('name')}: {fn.get('description')}")

    while True:
        user_input = await asyncio.to_thread(input, "You> ")
        if user_input.strip().lower() in {"exit", "quit", ":q"}:
            print("Bye.")
            return
        if not user_input.strip():
            continue

        messages.append(build_text_message("user", user_input))

        try:
            response_text = await generate_response_with_tools(
                responses_api=responses_api,
                agent=agent,
                messages=messages,
                model=model,
            )
        except Exception as exc:  # pragma: no cover - defensive logging for CLI use
            logger.exception("GPT-5 agent failed")
            print(f"[error] {exc}")
            continue

        if response_text:
            print(f"GekkoGPT> {response_text}")
        else:
            print("GekkoGPT> (no response)")
