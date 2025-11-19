"""Shared utilities for Claude agent wrappers."""
from __future__ import annotations

import os
from typing import Any, Callable, Dict, Iterable, List, Sequence

from anthropic import Anthropic, APIError
from anthropic.types import Message, MessageParam


ToolHandler = Callable[[dict[str, Any]], dict[str, Any] | str]


class ClaudeAgentBase:
    """Base class that wraps Anthropic client interactions."""

    def __init__(
        self,
        *,
        system_prompt: str,
        model: str | None = None,
        max_tokens: int = 2048,
        client: Anthropic | None = None,
    ) -> None:
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if client is None:
            if not api_key:
                msg = "ANTHROPIC_API_KEY environment variable is required"
                raise RuntimeError(msg)
            client = Anthropic(api_key=api_key)
        self.client = client
        self.system_prompt = system_prompt
        self.model = model or os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-5-20250929")
        self.max_tokens = max_tokens

    def _create_message(
        self,
        messages: Sequence[MessageParam],
        *,
        tools: Sequence[dict[str, Any]] | None = None,
    ) -> Message:
        kwargs = {
            "system": self.system_prompt,
            "model": self.model,
            "max_tokens": self.max_tokens,
            "messages": list(messages),
        }
        if tools is not None:
            kwargs["tools"] = list(tools)
        return self.client.messages.create(**kwargs)

    @staticmethod
    def _build_tool_result_payload(tool_use_id: str, content: dict[str, Any] | str) -> MessageParam:
        text = content if isinstance(content, str) else json_dumps(content)
        return {
            "role": "user",
            "content": [
                {
                    "type": "tool_result",
                    "tool_use_id": tool_use_id,
                    "content": text,
                }
            ],
        }

    def _exchange_with_tools(
        self,
        messages: List[MessageParam],
        tool_handlers: Dict[str, ToolHandler],
        *,
        tools: Sequence[dict[str, Any]],
    ) -> Message:
        response = self._create_message(messages, tools=tools)
        while True:
            tool_use = next((item for item in response.content if item.type == "tool_use"), None)
            if not tool_use:
                return response
            handler = tool_handlers.get(tool_use.name)
            if not handler:
                msg = f"No handler registered for tool '{tool_use.name}'"
                raise RuntimeError(msg)
            tool_output = handler(tool_use.input)
            messages.append(
                {
                    "role": "assistant",
                    "content": [tool_use],
                }
            )
            messages.append(self._build_tool_result_payload(tool_use.id, tool_output))
            response = self._create_message(messages, tools=tools)


def json_dumps(payload: dict[str, Any] | list[dict[str, Any]]) -> str:
    import json

    return json.dumps(payload, indent=2, sort_keys=True)
