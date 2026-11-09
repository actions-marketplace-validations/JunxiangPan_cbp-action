"""cbc-event 0.1.x JSONL emission for CBP.

The protocol is implemented locally (no dependency on the cbc-event package):

* ``seq`` starts at 1 and increments by one;
* ``prev_hash`` is the previous ``event_hash`` (genesis = 64 zeroes);
* ``event_hash = sha256(prev_hash + "\\n" + canonical_json(event_without_event_hash))``;
* ``canonical_json`` sorts keys, uses no insignificant whitespace and rejects
  values that have no stable canonical form.

Emission is disabled by default. A run may cap the number of events; dropped
events are counted and printed, never silently ignored. An optional HMAC-SHA256
key (read from an environment variable) binds each event to the writer.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import math
import os
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any

GENESIS = "sha256:" + ("0" * 64)
HEAD_NAME = "head.json"
EVENTS_NAME = "events.jsonl"


class CanonicalizationError(ValueError):
    """Raised when a value has no stable canonical representation."""


def _number(value: int | float) -> str:
    if isinstance(value, int) and not isinstance(value, bool):
        return str(value)
    if not math.isfinite(value):
        raise CanonicalizationError("NaN and Infinity are not canonical")
    if value == 0:
        return "0"
    sign = "-" if value < 0 else ""
    decimal = Decimal(repr(abs(value)))
    digits = "".join(str(digit) for digit in decimal.as_tuple().digits)
    exponent = decimal.as_tuple().exponent
    while len(digits) > 1 and digits.endswith("0"):
        digits = digits[:-1]
        exponent += 1
    point = len(digits) + exponent
    if 0 < point <= 21:
        text = digits + "0" * (point - len(digits)) if point >= len(digits) else digits[:point] + "." + digits[point:]
    elif -6 < point <= 0:
        text = "0." + "0" * (-point) + digits
    else:
        fraction = digits[1:]
        text = digits[0] + ("." + fraction if fraction else "") + "e" + ("+" if point - 1 >= 0 else "") + str(point - 1)
    return sign + text


def _string(value: str) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def _encode(value: Any) -> str:
    if value is None:
        return "null"
    if value is True:
        return "true"
    if value is False:
        return "false"
    if isinstance(value, (int, float)):
        return _number(value)
    if isinstance(value, str):
        return _string(value)
    if isinstance(value, (list, tuple)):
        return "[" + ",".join(_encode(item) for item in value) + "]"
    if isinstance(value, dict):
        for key in value:
            if not isinstance(key, str):
                raise CanonicalizationError("object keys must be strings")
        keys = sorted(value, key=lambda key: key.encode("utf-16-be", "surrogatepass"))
        return "{" + ",".join(_string(key) + ":" + _encode(value[key]) for key in keys) + "}"
    raise CanonicalizationError(f"unsupported value type: {type(value).__name__}")


def canonical_json(value: Any) -> str:
    """Return the canonical JSON text for a supported value."""
    return _encode(value)


def canonical_bytes(value: Any) -> bytes:
    """Return canonical JSON encoded as UTF-8."""
    return canonical_json(value).encode("utf-8")


def sha256_text(text: str) -> str:
    return "sha256:" + hashlib.sha256(text.encode("utf-8")).hexdigest()


def event_hash(prev_hash: str, event: dict[str, Any]) -> str:
    body = {key: value for key, value in event.items() if key != "event_hash"}
    return "sha256:" + hashlib.sha256(
        prev_hash.encode("utf-8") + b"\n" + canonical_bytes(body)
    ).hexdigest()


def _timestamp() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def _read_head(event_dir: Path) -> dict[str, Any] | None:
    path = event_dir / HEAD_NAME
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if isinstance(data, dict) and isinstance(data.get("seq"), int) and isinstance(data.get("last_hash"), str):
        return data
    return None


class EventEmitter:
    """Append cbc-event rows; disabled emitters never touch the filesystem."""

    def __init__(
        self,
        event_dir: Path | str | None,
        *,
        source: dict[str, str] | None = None,
        enabled: bool = False,
        max_events: int = 1000,
        hmac_key: str = "",
        instance: str = "",
    ) -> None:
        self.event_dir = Path(event_dir) if event_dir else None
        self.source = dict(source or {"kind": "tool", "name": "cbp", "version": "0", "instance": instance or "cbp"})
        self.enabled = bool(enabled and self.event_dir)
        self.max_events = max(0, int(max_events))
        self.hmac_key = hmac_key
        self.dropped = 0
        self.emitted = 0

    def _sign(self, event: dict[str, Any]) -> str:
        body = {key: value for key, value in event.items() if key != "hmac_sha256"}
        return hmac.new(
            self.hmac_key.encode("utf-8"), canonical_bytes(body), hashlib.sha256
        ).hexdigest()

    def emit(
        self,
        level: str,
        action: str,
        detail: dict[str, Any],
        *,
        evidence_hash: str | None = None,
    ) -> dict[str, Any] | None:
        """Append one event, or return None when disabled or rate-limited."""
        if not self.enabled or self.event_dir is None:
            return None
        head = _read_head(self.event_dir)
        seq = int(head["seq"]) + 1 if head else 1
        if self.max_events and seq > self.max_events:
            self.dropped += 1
            return None
        prev_hash = str(head["last_hash"]) if head else GENESIS
        event: dict[str, Any] = {
            "schema": "cbc-event/v1",
            "event_id": str(uuid.uuid4()),
            "timestamp": _timestamp(),
            "source": self.source,
            "level": level,
            "action": action,
            "detail": detail,
            "evidence_hash": evidence_hash or sha256_text(canonical_json(detail)),
            "prev_hash": prev_hash,
            "seq": seq,
        }
        if self.hmac_key:
            event["hmac_sha256"] = self._sign(event)
        event["event_hash"] = event_hash(prev_hash, event)
        self.event_dir.mkdir(parents=True, exist_ok=True)
        with (self.event_dir / EVENTS_NAME).open("a", encoding="utf-8", newline="\n") as handle:
            handle.write(json.dumps(event, ensure_ascii=False, separators=(",", ":")) + "\n")
        temporary = self.event_dir / (HEAD_NAME + ".tmp")
        temporary.write_text(json.dumps({"seq": seq, "last_hash": event["event_hash"]}), encoding="utf-8")
        os.replace(temporary, self.event_dir / HEAD_NAME)
        self.emitted += 1
        return event
