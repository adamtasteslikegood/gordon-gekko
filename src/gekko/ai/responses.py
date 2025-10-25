"""Integration helpers for the OpenAI Responses API."""

from __future__ import annotations

import asyncio
import json
import logging
import os
from typing import Any, Dict, Iterable, List, MutableMapping, Tuple

from ..agents.interactive import GekkoAgent

logger = logging.getLogger("gekko.ai.responses")

DEFAULT_SYSTEM_PROMPT = (
    "You are Gordon Gekko's market intelligence analyst. "
    "Use the provided tools to fetch live market data and arbitrage insights. "
    "Only rely on the tools for fresh numbers; summarise the results for the user."
)

TOOL_CALL_TYPES = {"tool_call", "function_call"}

# Context management defaults (tunable via env vars):
MAX_INPUT_TOKENS = int(os.getenv("GEKKO_RESPONSES_MAX_INPUT_TOKENS", "100000"))
TARGET_INPUT_TOKENS = int(os.getenv("GEKKO_RESPONSES_TARGET_INPUT_TOKENS", "80000"))
MAX_TOOL_OUTPUT_CHARS = int(os.getenv("GEKKO_RESPONSES_MAX_TOOL_OUTPUT_CHARS", "200000"))
MAX_TOOL_ITEMS = int(os.getenv("GEKKO_RESPONSES_MAX_TOOL_ITEMS", "200"))
MIN_MESSAGES_TO_KEEP = int(os.getenv("GEKKO_RESPONSES_MIN_MESSAGES_TO_KEEP", "8"))


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


def _estimate_message_tokens(msg: Message | Dict[str, Any]) -> int:
    """Rough token estimate for a message to keep us under model limits.

    Heuristic: ~4 characters per token for English text plus a small overhead per block.
    """
    try:
        role = msg.get("role", "")
        content = msg.get("content", [])
        total_chars = len(role)
        overhead = 6  # role + JSON punctuation
        if isinstance(content, list):
            for block in content:
                if not isinstance(block, MutableMapping):
                    continue
                text = block.get("text", "")
                if isinstance(text, str):
                    total_chars += len(text)
                    overhead += 4
        # Some message types (tool call/output) use alternative fields
        if msg.get("type") in {"function_call", "tool_call"}:
            args = msg.get("arguments")
            if isinstance(args, (str, bytes, bytearray)):
                total_chars += len(args)
            elif isinstance(args, MutableMapping):
                try:
                    total_chars += len(json.dumps(args))
                except Exception:
                    total_chars += 0
            overhead += 16
        if msg.get("type") == "function_call_output":
            out = msg.get("output", "")
            if isinstance(out, str):
                total_chars += len(out)
            overhead += 8
        # Convert chars to tokens
        return int(total_chars / 4) + overhead
    except Exception:
        return 128


def _estimate_tokens(messages: List[Message]) -> int:
    return sum(_estimate_message_tokens(m) for m in messages)


def _summarize_messages(messages: List[Message]) -> str:
    """Programmatic, lossy summary for removed history."""
    lines: List[str] = ["Conversation summary (truncated history):"]
    for m in messages:
        role = m.get("role") or m.get("type") or "message"
        if role in {"user", "assistant", "system"}:
            content = m.get("content", [])
            texts = []
            if isinstance(content, list):
                for b in content:
                    if isinstance(b, MutableMapping) and isinstance(b.get("text"), str):
                        t = b["text"].strip()
                        if t:
                            texts.append(t.replace("\n", " "))
            snippet = (" ".join(texts))[:300]
            if snippet:
                lines.append(f"- {role}: {snippet}...")
        elif m.get("type") in {"function_call", "tool_call"}:
            name = m.get("name") or (m.get("function") or {}).get("name")
            lines.append(f"- tool_call: {name}")
        elif m.get("type") == "function_call_output":
            lines.append("- tool_output: (omitted)")
    return "\n".join(lines)


def _prune_history(messages: List[Message]) -> Tuple[List[Message], bool]:
    """Ensure messages stay under TARGET_INPUT_TOKENS by dropping oldest and inserting a summary.

    Returns (new_messages, pruned_flag).
    """
    total = _estimate_tokens(messages)
    if total <= TARGET_INPUT_TOKENS:
        return messages, False

    # Keep system message(s)
    system_msgs = [m for m in messages if m.get("role") == "system"]
    non_system = [m for m in messages if m.get("role") != "system"]

    # Always keep the most recent slice
    tail_keep = max(MIN_MESSAGES_TO_KEEP, 4)
    recent = non_system[-tail_keep:]
    removed = non_system[:-tail_keep]

    summary_text = _summarize_messages(removed)
    summary_msg = build_text_message("system", summary_text)

    pruned: List[Message] = []
    pruned.extend(system_msgs[:1])  # first system prompt
    pruned.append(summary_msg)
    # If there were additional system messages, keep them too
    if len(system_msgs) > 1:
        pruned.extend(system_msgs[1:])
    pruned.extend(recent)

    # If still above hard cap, drop more from the head of 'recent'
    while _estimate_tokens(pruned) > MAX_INPUT_TOKENS and len(recent) > 2:
        recent = recent[1:]
        pruned = pruned[: len(system_msgs[:1]) + 1] + recent

    return pruned, True


def _shrink_large_lists(obj: Any) -> Any:
    """Truncate large list fields in dicts to bound size.

    - For dicts: if a value is a list longer than MAX_TOOL_ITEMS, keep the first N and add a metadata key with omitted count.
    - For lists at the top level: truncate to MAX_TOOL_ITEMS.
    - For long strings: truncate to reasonable length.
    """
    try:
        if isinstance(obj, list):
            if len(obj) > MAX_TOOL_ITEMS:
                return obj[:MAX_TOOL_ITEMS] + [f"…omitted {len(obj) - MAX_TOOL_ITEMS} items"]
            return obj
        if isinstance(obj, MutableMapping):
            new: Dict[str, Any] = {}
            for k, v in obj.items():
                if isinstance(v, list) and len(v) > MAX_TOOL_ITEMS:
                    new[k] = v[:MAX_TOOL_ITEMS]
                    new[f"_{k}_omitted_count"] = len(v) - MAX_TOOL_ITEMS
                elif isinstance(v, str) and len(v) > 4000:
                    new[k] = v[:4000] + "…"
                else:
                    new[k] = v
            return new
        return obj
    except Exception:
        return obj


def _compact_tool_output(payload: Any) -> Any:
    """Return a payload safe for the model: shrink oversized JSON by truncating lists/strings.
    If serialized size still exceeds MAX_TOOL_OUTPUT_CHARS, replace with a stub containing counts.
    """
    try:
        compact = _shrink_large_lists(payload)
        text = json.dumps(compact)
        if len(text) <= MAX_TOOL_OUTPUT_CHARS:
            return compact
        # Fallback: produce a stub
        if isinstance(payload, list):
            return {"_truncated": True, "type": "list", "length": len(payload)}
        if isinstance(payload, MutableMapping):
            return {
                "_truncated": True,
                "type": "object",
                "keys": list(payload.keys())[:MAX_TOOL_ITEMS],
            }
        return {"_truncated": True, "type": type(payload).__name__}
    except Exception:
        return payload


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
        # Proactively prune long histories before each model call
        messages, was_pruned = _prune_history(messages)
        if was_pruned:
            log.debug("Pruned message history to stay within token budget.")
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
            result = _compact_tool_output(result)
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
        # Prune again since tool outputs can be large
        messages, _ = _prune_history(messages)
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
