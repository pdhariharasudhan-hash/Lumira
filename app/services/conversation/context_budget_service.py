# Adapted from Nanobot's MIT-licensed context-cost utilities.
# Upstream: https://github.com/HKUDS/nanobot
# Revision: cdaae66c894b3364fc4aeed21072b37e913ee917
# Copyright (c) 2025-present Xubin Ren and the nanobot contributors.
# See docs/third_party_notices.md for the full MIT permission notice.

from __future__ import annotations

import json
from typing import Any


class ContextBudgetService:
    """Bound conversation history while preserving the newest complete turns.

    The conservative UTF-8 byte estimate is adapted from Nanobot's MIT-licensed
    prompt-token estimation utilities. It deliberately avoids a mandatory tokenizer
    dependency so Lumira remains lightweight on low-memory Windows machines.
    """

    DEFAULT_HISTORY_TOKEN_BUDGET = 6_000
    MAX_MESSAGE_CHARS = 4_000

    @staticmethod
    def estimate_message_tokens(message: dict[str, Any]) -> int:
        """Estimate message cost using a conservative byte-based fallback."""
        parts: list[str] = []
        content = message.get("content")
        if isinstance(content, str):
            parts.append(content)
        elif isinstance(content, list):
            for item in content:
                if isinstance(item, dict) and item.get("type") == "text":
                    value = item.get("text")
                    if isinstance(value, str) and value:
                        parts.append(value)
                elif item is not None:
                    parts.append(json.dumps(item, ensure_ascii=False))
        elif content is not None:
            parts.append(json.dumps(content, ensure_ascii=False))

        for key in ("name", "tool_call_id"):
            value = message.get(key)
            if isinstance(value, str) and value:
                parts.append(value)
        if message.get("tool_calls"):
            parts.append(json.dumps(message["tool_calls"], ensure_ascii=False))
        payload = "\n".join(parts)
        return max(4, len(payload.encode("utf-8")) + 4)

    @classmethod
    def select_recent_history(
        cls,
        messages: Any,
        *,
        max_messages: int,
        max_chars: int,
        max_tokens: int = DEFAULT_HISTORY_TOKEN_BUDGET,
    ) -> list[dict[str, str]]:
        """Keep the newest valid user/assistant messages within all three limits."""
        if not isinstance(messages, list) or max_messages <= 0 or max_chars <= 0 or max_tokens <= 0:
            return []

        accepted: list[dict[str, str]] = []
        total_chars = 0
        total_tokens = 0
        for item in reversed(messages):
            if len(accepted) >= max_messages:
                break
            if not isinstance(item, dict) or item.get("role") not in {"user", "assistant"}:
                continue
            content = item.get("content")
            if not isinstance(content, str) or not content.strip():
                continue
            content = content.strip()[-cls.MAX_MESSAGE_CHARS:]
            candidate = {"role": item["role"], "content": content}
            char_cost = len(content)
            token_cost = cls.estimate_message_tokens(candidate)
            if total_chars + char_cost > max_chars or total_tokens + token_cost > max_tokens:
                continue
            accepted.append(candidate)
            total_chars += char_cost
            total_tokens += token_cost

        accepted.reverse()
        return accepted
