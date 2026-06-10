"""
Per-user conversation history store.

Maintains an in-memory dictionary of conversation transcripts keyed by
WhatsApp phone number.  Each transcript is a ``list[dict]`` of Anthropic
Messages-API-formatted message objects (user, assistant, and tool_result).

For production use this should be replaced with a Redis-backed store to
survive server restarts and scale across multiple workers.
"""

from __future__ import annotations

from typing import Any


class ConversationMemory:
    """Thread-safe-ish store for per-phone conversation histories."""

    def __init__(self) -> None:
        self._store: dict[str, list[dict[str, Any]]] = {}

    # -- retrieval ------------------------------------------------------------

    def get(self, phone: str) -> list[dict[str, Any]]:
        """Return the full history for *phone*, or an empty list.

        Uses ``dict.get`` rather than ``dict.setdefault`` to avoid creating
        a permanent empty entry for every new phone number that contacts
        the bot (which would cause unbounded memory growth).
        """
        return self._store.get(phone, [])

    # -- mutation -------------------------------------------------------------

    def add_user_message(self, phone: str, text: str) -> None:
        """Append a user-turn message to the history."""
        self._store.setdefault(phone, []).append(
            {"role": "user", "content": text}
        )

    def add_assistant_message(self, phone: str, text: str) -> None:
        """Append an assistant-turn text response."""
        self._store.setdefault(phone, []).append(
            {"role": "assistant", "content": text}
        )

    def add_tool_result(
        self, phone: str, tool_use_id: str, result: str
    ) -> None:
        """Append a tool_result content block as a user-turn message.

        Per the Anthropic API spec, tool results are sent back with
        ``role: "user"`` and a ``tool_result`` content block.
        """
        self._store.setdefault(phone, []).append(
            {
                "role": "user",
                "content": [
                    {
                        "type": "tool_result",
                        "tool_use_id": tool_use_id,
                        "content": result,
                    }
                ],
            }
        )

    # -- lifecycle ------------------------------------------------------------

    def clear(self, phone: str) -> None:
        """Drop the conversation history for *phone*."""
        self._store.pop(phone, None)
