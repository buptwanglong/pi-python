"""
Serialize/deserialize basket_ai Message types to/from SessionEntry.data.

SessionEntry.data format: {"role": "user"|"assistant"|"toolResult", "payload": <message dict>}.
Payload uses model_dump(mode="json") so aliases (toolCallId, toolName, etc.) round-trip.
"""

from typing import Any, Dict, List, Union

from basket_ai.types import (
    AssistantMessage,
    Message,
    ToolResultMessage,
    UserMessage,
)


def message_to_entry_data(message: Message) -> Dict[str, Any]:
    """
    Convert a Message to SessionEntry.data dict.
    data = {"role": ..., "payload": message.model_dump(mode="json")}.
    """
    role = getattr(message, "role", None)
    if role is None:
        raise ValueError("Message has no role")
    payload = message.model_dump(mode="json")
    return {"role": role, "payload": payload}


def entry_data_to_message(data: Dict[str, Any]) -> Message:
    """
    Deserialize SessionEntry.data to UserMessage, AssistantMessage, or ToolResultMessage.
    Uses payload with populate_by_name so aliases (toolCallId, toolName, etc.) work.
    """
    role = data.get("role")
    payload = data.get("payload")
    if not isinstance(payload, dict):
        raise ValueError("entry data must have 'payload' dict")
    if role == "user":
        return UserMessage.model_validate(payload)
    if role == "assistant":
        return AssistantMessage.model_validate(payload)
    if role == "toolResult":
        return ToolResultMessage.model_validate(payload)
    raise ValueError(f"Unknown message role: {role!r}")


def entry_data_to_message_safe(data: Dict[str, Any]) -> Union[Message, None]:
    """Like entry_data_to_message but returns None on invalid data (skip bad entries)."""
    try:
        return entry_data_to_message(data)
    except Exception:
        return None
