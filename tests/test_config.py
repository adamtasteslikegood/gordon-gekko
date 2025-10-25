from __future__ import annotations

import json
import os

from gekko.config import resolve_responses_config, ResponsesConfig


def test_resolve_config_use_env(monkeypatch, tmp_path):
    # File exists but should be ignored in USE_ENV mode in favor of env vars
    cfg_path = tmp_path / "gekko.config.json"
    cfg_path.write_text(
        json.dumps({
            "mode": "USE_ENV",
            "responses": {"max_tool_items": 5}
        }),
        encoding="utf-8",
    )

    monkeypatch.setenv("GEKKO_CONFIG_PATH", str(cfg_path))
    monkeypatch.setenv("GEKKO_RESPONSES_MAX_TOOL_ITEMS", "123")

    cfg = resolve_responses_config(None)
    assert isinstance(cfg, ResponsesConfig)
    assert cfg.max_tool_items == 123


def test_resolve_config_use_config_ignores_env(monkeypatch, tmp_path):
    cfg_path = tmp_path / "gekko.config.json"
    cfg_path.write_text(
        json.dumps({
            "mode": "USE_CONFIG",
            "responses": {"max_tool_items": 50, "target_input_tokens": 70000}
        }),
        encoding="utf-8",
    )

    monkeypatch.setenv("GEKKO_RESPONSES_MAX_TOOL_ITEMS", "999")

    cfg = resolve_responses_config(str(cfg_path))
    assert cfg.max_tool_items == 50
    assert cfg.target_input_tokens == 70000


def test_resolve_config_reset_to_default(monkeypatch, tmp_path):
    cfg_path = tmp_path / "gekko.config.json"
    cfg_path.write_text(
        json.dumps({
            "mode": "RESET_TO_DEFAULT",
            "responses": {"max_tool_items": 1}
        }),
        encoding="utf-8",
    )

    monkeypatch.setenv("GEKKO_RESPONSES_MAX_TOOL_ITEMS", "777")

    cfg = resolve_responses_config(str(cfg_path))
    # Hard defaults from dataclass
    assert cfg.max_input_tokens == 100_000
    assert cfg.target_input_tokens == 80_000
    assert cfg.max_tool_output_chars == 200_000
    assert cfg.max_tool_items == 200
    assert cfg.min_messages_to_keep == 8
    assert cfg.save_tool_outputs is False
