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

TOOL_CALL_TYPES = {"tool_call", "function_call"}


ContentBlock = Dict[str, Any]
Message = Dict[str, Any]
RESPONSE_ONLY_FIELDS = {"status"}


def _default_content_type(role: str) -> str:
    """Map a chat role to the Responses API content type."""

    return "output_text" if role == "assistant" else "input_text"


def _normalize_block_type(role: str, block_type: str | None) -> str:
    """Ensure outgoing content blocks always use a valid Responses content type."""

    if block_type in {"input_text", "output_text"}:
        return block_type
    if block_type == "text":
        return _default_content_type(role)
    return block_type or _default_content_type(role)


def build_text_message(role: str, text: str) -> Message:
    """Create a Responses-style message containing a plain text block."""

    return {
        "role": role,
        "content": [{"type": _default_content_type(role), "text": text}],
    }


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


def _strip_response_fields(item: Dict[str, Any]) -> Dict[str, Any]:
    """Remove fields that the Responses API rejects when echoed back."""

    return {key: value for key, value in item.items() if key not in RESPONSE_ONLY_FIELDS}


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
    pending_reasoning: List[Message] = []

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

        for raw_item in output_items:
            item = _normalize_dict(raw_item)
            item_type = item.get("type")

            if item_type in TOOL_CALL_TYPES:
                if pending_reasoning:
                    messages.extend(pending_reasoning)
                    pending_reasoning = []
                sanitized = _strip_response_fields(item)
                tool_calls.append(sanitized)
                messages.append(sanitized)
                continue

            if item_type == "message":
                pending_reasoning = []
                role = item.get("role", "assistant")
                content = _normalize_content(item.get("content"))

                text_blocks = {"input_text", "output_text", "text"}
                text_fragments = [
                    block.get("text", "")
                    for block in content
                    if block.get("type") in text_blocks
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
                            "type": _normalize_block_type(role, block.get("type")),
                            "text": block.get("text", ""),
                        }
                        for block in content
                        if isinstance(block.get("text"), str)
                    ],
                }

                if role == "tool" and "tool_call_id" in item:
                    message_payload["tool_call_id"] = item["tool_call_id"]

                messages.append(message_payload)
                continue

            if item_type == "function_call_output":
                pending_reasoning = []
                messages.append(_strip_response_fields(item))
                continue

            if item_type == "reasoning":
                pending_reasoning.append(_strip_response_fields(item))
                continue

        if not tool_calls:
            pending_reasoning = []
            break

        tool_messages: List[Message] = []
        for call in tool_calls:
            function_blob = call.get("function")
            if isinstance(function_blob, MutableMapping):
                function_payload = dict(function_blob)
            else:
                function_payload = {}

            tool_name = (
                call.get("name")
                or function_payload.get("name")
                or ""
            )
            arguments_raw = call.get("arguments")
            if arguments_raw is None:
                arguments_raw = function_payload.get("arguments")

            if isinstance(arguments_raw, (str, bytes, bytearray)):
                try:
                    arguments = json.loads(arguments_raw)
                except (json.JSONDecodeError, TypeError):
                    log.warning(
                        "Failed to decode tool arguments for %s: %s",
                        tool_name,
                        arguments_raw,
                    )
                    arguments = {}
                if arguments and not isinstance(arguments, MutableMapping):
                    log.warning(
                        "Tool arguments for %s must be an object; received %r",
                        tool_name,
                        arguments,
                    )
                    arguments = {}
            else:
                arguments = _normalize_dict(arguments_raw)
                if arguments_raw not in (None, {}) and not arguments:
                    log.warning(
                        "Unexpected tool arguments type for %s: %r",
                        tool_name,
                        arguments_raw,
                    )

            result = await agent.dispatch(tool_name, arguments)
            tool_call_id = (
                function_payload.get("call_id")
                or call.get("call_id")
                or function_payload.get("id")
                or call.get("id")
            )

            if not tool_call_id:
                log.warning("Skipping tool result for %s; missing call id.", tool_name)
                continue

            tool_messages.append(
                {
                    "type": "function_call_output",
                    "call_id": tool_call_id,
                    "output": json.dumps(result),
                }
            )

        messages.extend(tool_messages)
        pending_reasoning = []

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
        name = tool.get("name") or fn.get("name") or "unnamed_tool"
        description = tool.get("description") or fn.get("description") or ""
        if not description:
            description = "No description provided."
        print(f"  • {name}: {description}")

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
