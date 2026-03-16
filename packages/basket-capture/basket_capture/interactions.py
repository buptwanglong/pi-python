"""Interaction detector: map cast events to Interaction list (placeholder)."""

from typing import Any

from pydantic import BaseModel, Field

from basket_capture.cast import CastResult


class Interaction(BaseModel):
    """One detected interaction: timestamp, type, and optional payload."""

    timestamp: float = Field(..., description="Event time in seconds")
    type: str = Field(..., description="Interaction type (e.g. send, switch_session)")
    payload: Any = Field(default=None, description="Optional event payload")


def detect_interactions(parsed: CastResult) -> list[Interaction]:
    """
    Build a list of interactions from parsed cast result.

    Placeholder: if CastResult.events is non-empty, map each event to Interaction;
    otherwise return empty list. Cast parser currently always gives events=[].
    """
    if not parsed.events:
        return []
    out: list[Interaction] = []
    for e in parsed.events:
        if not isinstance(e, dict):
            continue
        ts = e.get("timestamp", e.get("time", 0.0))
        t = e.get("type", "unknown")
        payload = e.get("payload", e.get("data"))
        out.append(Interaction(timestamp=float(ts), type=str(t), payload=payload))
    return out
