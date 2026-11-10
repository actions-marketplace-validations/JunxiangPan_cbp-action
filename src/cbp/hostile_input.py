"""Strict validators for hostile release inputs (opt-in hardening helpers)."""
from __future__ import annotations

import json
import re
import unicodedata
from typing import Any

ARTIFACT = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
INPUT = re.compile(r"^[A-Za-z_][A-Za-z0-9_-]{0,63}$")
REF = re.compile(r"^[A-Za-z0-9._/-]{1,200}$")
RESERVED = {"CON", "PRN", "AUX", "NUL", *(f"COM{i}" for i in range(1, 10)), *(f"LPT{i}" for i in range(1, 10))}


class HostileInput(ValueError):
    """An input that must never be accepted by a gate or workflow."""


def _no_control(value: str, name: str) -> None:
    if any(ord(char) < 0x20 or ord(char) == 0x7f for char in value):
        raise HostileInput(f"{name}: control character")
    if "\u202a" <= max(value, default="\0") <= "\u202e" or any(char in value for char in "\u200b\u200c\u200d\u2066\u2067\u2068\u2069"):
        raise HostileInput(f"{name}: bidi/zero-width character")


def artifact_name(value: str) -> str:
    if not isinstance(value, str) or not ARTIFACT.fullmatch(value):
        raise HostileInput("artifact name must match [A-Za-z0-9][A-Za-z0-9._-]{0,127}")
    if ".." in value or value.rsplit(".", 1)[0].upper() in RESERVED:
        raise HostileInput("artifact name is a traversal/reserved name")
    _no_control(value, "artifact name")
    return value


def action_input(value: str) -> str:
    if not isinstance(value, str) or not INPUT.fullmatch(value):
        raise HostileInput("action input must match [A-Za-z_][A-Za-z0-9_-]{0,63}")
    if "${{" in value or "}}" in value:
        raise HostileInput("action input contains an expression")
    _no_control(value, "action input")
    return value


def checkout_ref(value: str) -> str:
    if not isinstance(value, str) or not REF.fullmatch(value):
        raise HostileInput("checkout ref contains a forbidden character")
    if value.startswith(("-", "/")) or ".." in value or value.endswith("/"):
        raise HostileInput("checkout ref is not a safe relative ref")
    _no_control(value, "checkout ref")
    return value


def relative_path(value: str) -> str:
    if not isinstance(value, str) or not value or value.startswith(("/", "\\")):
        raise HostileInput("path must be relative")
    if re.match(r"^[A-Za-z]:", value) or ".." in value.replace("\\", "/").split("/") or "\\" in value:
        raise HostileInput("path traversal or backslash")
    _no_control(value, "path")
    return value


def unicode_text(value: str) -> str:
    if not isinstance(value, str) or not unicodedata.is_normalized("NFC", value):
        raise HostileInput("text is not NFC-normalized")
    _no_control(value, "text")
    return value


def workflow_permissions(value: Any) -> Any:
    if not isinstance(value, dict):
        raise HostileInput("permissions must be a mapping")
    allowed = {"contents": {"read"}, "actions": {"read"}, "id-token": {"write"}}
    for key, level in value.items():
        if key not in allowed or level not in allowed[key]:
            raise HostileInput(f"permission {key}: {level} is not allowed")
    return value


def _json_strings(value: Any) -> None:
    if isinstance(value, str):
        _no_control(value, "JSON string")
    elif isinstance(value, dict):
        for key, item in value.items():
            _json_strings(key); _json_strings(item)
    elif isinstance(value, list):
        for item in value:
            _json_strings(item)


def strict_json(text: str, *, duplicate_keys: bool = False) -> Any:
    def reject_constant(value: str):
        raise HostileInput(f"non-finite JSON number: {value}")
    if duplicate_keys:
        def pairs(items):
            seen = set()
            for key, value in items:
                if key in seen:
                    raise HostileInput(f"duplicate JSON key: {key}")
                seen.add(key)
            return dict(items)
        value = json.loads(text, object_pairs_hook=pairs, parse_constant=reject_constant)
    _json_strings(value)
    return value
    value = json.loads(text, parse_constant=reject_constant)
    _json_strings(value)
    return value
