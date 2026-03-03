"""
In-memory state store for multi-step verification calls.

Each call_sid maps to its collected data while the call progresses.
Values can be strings (order/address fields) or lists (messages history).
State is cleared after the final step processes the result.
"""
from __future__ import annotations
from typing import Any

# { call_sid: { key: value } }
_store: dict[str, dict[str, Any]] = {}


def save(call_sid: str, key: str, value: Any) -> None:
    if call_sid not in _store:
        _store[call_sid] = {}
    _store[call_sid][key] = value


def load(call_sid: str) -> dict[str, Any]:
    return dict(_store.get(call_sid, {}))


def clear(call_sid: str) -> None:
    _store.pop(call_sid, None)
