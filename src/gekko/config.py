from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any, Dict, Optional


@dataclass
class ResponsesConfig:
    # Token budgets
    max_input_tokens: int = 100_000
    target_input_tokens: int = 80_000
    # Tool output clamping
    max_tool_output_chars: int = 200_000
    max_tool_items: int = 200
    min_messages_to_keep: int = 8
    # Persistence of raw tool outputs
    save_tool_outputs: bool = False
    tool_outputs_dir: str = "tool_outputs"


def default_responses_config() -> ResponsesConfig:
    cfg = ResponsesConfig()
    # Apply environment defaults here to keep parity with prior behavior
    cfg.max_input_tokens = int(os.getenv("GEKKO_RESPONSES_MAX_INPUT_TOKENS", cfg.max_input_tokens))
    cfg.target_input_tokens = int(os.getenv("GEKKO_RESPONSES_TARGET_INPUT_TOKENS", cfg.target_input_tokens))
    cfg.max_tool_output_chars = int(os.getenv("GEKKO_RESPONSES_MAX_TOOL_OUTPUT_CHARS", cfg.max_tool_output_chars))
    cfg.max_tool_items = int(os.getenv("GEKKO_RESPONSES_MAX_TOOL_ITEMS", cfg.max_tool_items))
    cfg.min_messages_to_keep = int(os.getenv("GEKKO_RESPONSES_MIN_MESSAGES_TO_KEEP", cfg.min_messages_to_keep))
    save_env = os.getenv("GEKKO_RESPONSES_SAVE_TOOL_OUTPUTS")
    if save_env is not None:
        cfg.save_tool_outputs = save_env.lower() in {"1", "true", "yes", "on"}
    cfg.tool_outputs_dir = os.getenv("GEKKO_RESPONSES_TOOL_OUTPUTS_DIR", cfg.tool_outputs_dir)
    return cfg


def _from_dict(data: Dict[str, Any]) -> ResponsesConfig:
    cfg = default_responses_config()
    responses = data.get("responses", {}) if isinstance(data, dict) else {}
    if isinstance(responses, dict):
        cfg.max_input_tokens = int(responses.get("max_input_tokens", cfg.max_input_tokens))
        cfg.target_input_tokens = int(responses.get("target_input_tokens", cfg.target_input_tokens))
        cfg.max_tool_output_chars = int(responses.get("max_tool_output_chars", cfg.max_tool_output_chars))
        cfg.max_tool_items = int(responses.get("max_tool_items", cfg.max_tool_items))
        cfg.min_messages_to_keep = int(responses.get("min_messages_to_keep", cfg.min_messages_to_keep))
        sto = responses.get("save_tool_outputs")
        if isinstance(sto, bool):
            cfg.save_tool_outputs = sto
        tod = responses.get("tool_outputs_dir")
        if isinstance(tod, str) and tod:
            cfg.tool_outputs_dir = tod
    return cfg


def resolve_responses_config(config_path: Optional[str] = None) -> ResponsesConfig:
    """Load ResponsesConfig from file and/or environment according to precedence mode.

    Config file format (JSON):
    {
      "mode": "USE_ENV" | "USE_CONFIG" | "RESET_TO_DEFAULT",
      "responses": { ... }
    }
    """
    # Determine path: explicit, env, or default file in CWD
    path = config_path or os.getenv("GEKKO_CONFIG_PATH") or "gekko.config.json"
    data: Dict[str, Any] | None = None
    try:
        if path and os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
    except Exception:
        data = None

    mode = None
    if isinstance(data, dict):
        mode = data.get("mode")

    mode = str(mode).upper() if isinstance(mode, str) else "USE_ENV"

    if mode == "RESET_TO_DEFAULT":
        return ResponsesConfig()
    if mode == "USE_CONFIG":
        return _from_dict(data or {})

    # USE_ENV (default): start from env-driven defaults, ignore file values
    return default_responses_config()


__all__ = [
    "ResponsesConfig",
    "default_responses_config",
    "resolve_responses_config",
]

