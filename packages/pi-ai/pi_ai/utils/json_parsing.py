"""
Partial JSON parsing utilities.

Provides best-effort parsing of incomplete JSON strings during streaming.
"""

import json
from typing import Any


def parse_partial_json(text: str) -> dict[str, Any]:
    """
    Parse incomplete JSON strings with best-effort completion.

    During streaming, tool call arguments may arrive as incomplete JSON.
    This function attempts to parse partial JSON by trying common suffixes
    to complete the structure.

    Args:
        text: Potentially incomplete JSON string

    Returns:
        Parsed JSON object, or empty dict if unparseable

    Examples:
        >>> parse_partial_json('{"name": "test"')
        {'name': 'test'}

        >>> parse_partial_json('{"items": [1, 2')
        {'items': [1, 2]}

        >>> parse_partial_json('{"status":')
        {}
    """
    # Fast path: try parsing as-is
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Try completing with common suffixes
    # Order matters - try more specific completions first
    suffixes = [
        '"}}',  # Close string + nested objects
        '"}',   # Close string + object
        '"]',   # Close string + array
        '"]}',  # Close string + array + object
        '"}]',  # Close string + array + object (alternate)
        '"}}]', # Close string + nested objects + array
        '"]}}', # Close string + array + nested objects
        '}}',   # Close nested objects
        '}]',   # Close object + array
        ']}',   # Close array + object
        ']',    # Close array
        '}',    # Close object
    ]

    for suffix in suffixes:
        try:
            return json.loads(text + suffix)
        except json.JSONDecodeError:
            continue

    # If all attempts fail, return empty dict
    return {}


def try_parse_json(text: str) -> dict[str, Any] | None:
    """
    Try to parse JSON, returning None if invalid.

    Args:
        text: JSON string to parse

    Returns:
        Parsed JSON object or None if invalid
    """
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return None


__all__ = [
    "parse_partial_json",
    "try_parse_json",
]
