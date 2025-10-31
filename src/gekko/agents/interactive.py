from __future__ import annotations

import logging
from typing import Any, Dict, List

import httpx
from jsonschema import Draft7Validator, ValidationError

from .tools import Tool, list_tools


class GekkoAgent:
    """Async dispatcher that routes tool requests with validation and logging."""

    def __init__(self) -> None:
        self._logger = logging.getLogger("gekko.agent")
        self._tools: Dict[str, Tool] = {tool.name: tool for tool in list_tools()}
        self._validators: Dict[str, Draft7Validator] = {
            name: Draft7Validator(tool.schema) for name, tool in self._tools.items()
        }

    def available_tools(self) -> List[Dict[str, Any]]:
        # Expose Gordon Gekko function tools plus OpenAI built-in web search.
        tools: List[Dict[str, Any]] = [tool.as_function_tool() for tool in self._tools.values()]
        # Enable built-in web search in GPT Responses API
        tools.append({"type": "web_search"})
        return tools

    async def dispatch(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        tool = self._tools.get(tool_name)
        if tool is None:
            self._logger.warning("Unknown tool requested: %s", tool_name)
            return {
                "status": "error",
                "error": {
                    "type": "unknown_tool",
                    "message": f"Tool '{tool_name}' is not available.",
                },
            }

        validator = self._validators[tool_name]
        try:
            validator.validate(arguments)
        except ValidationError as exc:
            self._logger.warning("Validation error for %s: %s", tool_name, exc)
            return {
                "status": "error",
                "error": {
                    "type": "validation_error",
                    "message": exc.message,
                    "path": list(exc.path),
                },
            }

        try:
            result = await tool.handler(arguments)
        except httpx.HTTPError as exc:
            self._logger.error("HTTP error in tool %s: %s", tool_name, exc, exc_info=True)
            return {
                "status": "error",
                "error": {
                    "type": "http_error",
                    "message": str(exc),
                },
            }
        except Exception as exc:  # pragma: no cover - defensive logging
            self._logger.exception("Unhandled error in tool %s", tool_name)
            return {
                "status": "error",
                "error": {
                    "type": "internal_error",
                    "message": str(exc),
                },
            }

        return {"status": "ok", "data": result}
