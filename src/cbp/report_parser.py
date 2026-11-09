"""CONTRACT v1.7 report parser.

Reads structured JSON only. This module never greps stdout, logs, or a step
summary: a verdict that cannot be read from the report document is an input
error (exit 2), never a guess.

Parsed kinds:

* ``cbe-report``      — CONTRACT §5, CBE report (``producer_id`` = ``cbe``)
* ``cbp-manifest``    — CONTRACT §5, CBP quality manifest
* ``cbp-gate-report`` — the CLI's own gate report (same fields minus artifact
  hashes, which belong to the release manifest)
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from . import report_schema as schema


class ReportError(ValueError):
    """An input or format error. The process must exit with code 2."""

    exit_code = schema.EXIT_INPUT


CBE_REQUIRED_FIELDS = (
    "schema_version",
    "package_id",
    "producer_id",
    "version",
    "tag",
    "gate_status",
    "exit_code",
    "applicable_count",
    "skip_count",
    "skip_ratio",
    "blocking_skip",
    "warn_count",
    "rules_manifest_hash",
    "sarif_paths",
    "evidence_sha256",
)
CBE_ALLOWED_FIELDS = frozenset(CBE_REQUIRED_FIELDS)
CBE_PACKAGE_IDS = frozenset({"cbs", "cbe", "cbp", "cbm", "cbc", "cbg"})

GATE_REPORT_REQUIRED_FIELDS = (
    "schema_version",
    "package_id",
    "producer_id",
    "version",
    "gate_status",
    "exit_code",
    "applicable_gate_count",
    "skip_count",
    "skip_ratio",
    "blocking_skip",
    "gates",
)
GATE_REPORT_ALLOWED_FIELDS = frozenset(GATE_REPORT_REQUIRED_FIELDS)


@dataclass(frozen=True)
class ParsedReport:
    """A validated report reduced to the fields consumers act on."""

    kind: str
    source: str
    schema_version: str
    package_id: str
    producer_id: str
    version: str
    gate_status: str
    exit_code: int | None
    applicable_count: int
    skip_count: int
    skip_ratio: float
    blocking_skip: bool
    tag: str = ""
    gates: tuple[dict[str, Any], ...] = field(default_factory=tuple)

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-ready projection of the report."""
        return {
            "kind": self.kind,
            "schema_version": self.schema_version,
            "package_id": self.package_id,
            "producer_id": self.producer_id,
            "version": self.version,
            "tag": self.tag,
            "gate_status": self.gate_status,
            "exit_code": self.exit_code,
            "applicable_count": self.applicable_count,
            "skip_count": self.skip_count,
            "skip_ratio": self.skip_ratio,
            "blocking_skip": self.blocking_skip,
            "gates": list(self.gates),
        }


def parse_report(path: Path, *, observed_exit_code: int | None = None) -> ParsedReport:
    """Read and validate one report file. Raises ``ReportError`` on failure."""
    try:
        raw = path.read_text(encoding="utf-8")
    except FileNotFoundError as exc:
        raise ReportError(f"report missing: {path}") from exc
    except OSError as exc:
        raise ReportError(f"report is unreadable: {path}: {exc}") from exc
    try:
        data = json.loads(raw)
    except ValueError as exc:
        raise ReportError(f"report is not valid JSON: {path}: {exc}") from exc
    return parse_report_data(data, source=str(path), observed_exit_code=observed_exit_code)


def parse_report_data(
    data: Any,
    *,
    source: str = "<memory>",
    observed_exit_code: int | None = None,
) -> ParsedReport:
    """Validate an already-decoded report object."""
    if not isinstance(data, dict):
        raise ReportError(f"{source}: report must be a JSON object")
    kind = _detect_kind(data, source)
    if kind == "cbe-report":
        return _parse_cbe(data, source, observed_exit_code)
    if kind == "cbp-gate-report":
        return _parse_gate_report(data, source, observed_exit_code)
    return _parse_manifest(data, source, observed_exit_code)


def _detect_kind(data: dict[str, Any], source: str) -> str:
    producer = data.get("producer_id")
    if producer == "cbe":
        return "cbe-report"
    if "artifact_hashes" in data or "release_body_hash" in data or "evidence_sha256" in data:
        return "cbp-manifest"
    if producer == "cbp" and "exit_code" in data:
        return "cbp-gate-report"
    if "applicable_count" in data and "rules_manifest_hash" in data:
        return "cbe-report"
    if "gates" in data and isinstance(data.get("gates"), list):
        return "cbp-gate-report"
    if isinstance(producer, str) and producer:
        raise ReportError(f"{source}: unknown producer_id {producer!r}")
    raise ReportError(
        f"{source}: cannot determine the report kind; producer_id is required"
    )


def _require_fields(data: dict[str, Any], required: tuple[str, ...], allowed: frozenset[str], source: str) -> None:
    missing = [name for name in required if name not in data]
    if missing:
        raise ReportError(f"{source}: missing required field(s): " + ", ".join(missing))
    unknown = sorted(set(data) - allowed)
    if unknown:
        raise ReportError(f"{source}: unexpected field(s): " + ", ".join(unknown))


def _precheck_exit(data: dict[str, Any], source: str, observed: int | None) -> None:
    """F1: exit 3 without a valid gate_status is an input error, not a FAIL."""
    code = observed if observed is not None else data.get("exit_code")
    status = data.get("gate_status")
    if code == schema.EXIT_GATE and status not in schema.REPORT_STATUS_VALUES:
        raise ReportError(
            f"{source}: exit 3 without a valid gate_status is an input error (exit 2)"
        )


def _required_status(data: dict[str, Any], source: str, exit_code: int | None) -> str:
    status = data.get("gate_status")
    if not isinstance(status, str) or not status or status not in schema.REPORT_STATUS_VALUES:
        if exit_code == schema.EXIT_GATE:
            raise ReportError(
                f"{source}: exit 3 without a valid gate_status is an input error (exit 2)"
            )
        raise ReportError(
            f"{source}: gate_status is required and must be one of "
            + ", ".join(sorted(schema.REPORT_STATUS_VALUES))
        )
    return status


def _check_exit(data: dict[str, Any], status: str, source: str, observed: int | None) -> int | None:
    embedded = data.get("exit_code")
    if embedded is not None and (not isinstance(embedded, int) or isinstance(embedded, bool)):
        raise ReportError(f"{source}: exit_code must be an integer")
    if embedded is not None and embedded not in schema.VALID_EXIT_CODES:
        raise ReportError(f"{source}: exit_code {embedded} is not one of 0/2/3/4")
    if embedded is not None and observed is not None and embedded != observed:
        raise ReportError(
            f"{source}: exit_code {embedded} in the report does not match the observed exit {observed}"
        )
    exit_code = embedded if embedded is not None else observed
    if exit_code is None:
        return None
    problems = schema.exit_status_problems(exit_code, status, source=source)
    if problems:
        raise ReportError("; ".join(problems))
    return exit_code


def _require_ratio(data: dict[str, Any], source: str, fields: tuple[str, str, str]) -> tuple[int, int, float]:
    applicable = data.get(fields[0])
    skip = data.get(fields[1])
    ratio = data.get(fields[2])
    problem = schema.ratio_problem(applicable, skip, ratio, fields=fields)
    if problem:
        raise ReportError(f"{source}: {problem}")
    return int(applicable), int(skip), float(ratio)


def _parse_cbe(data: dict[str, Any], source: str, observed: int | None) -> ParsedReport:
    _precheck_exit(data, source, observed)
    _require_fields(data, CBE_REQUIRED_FIELDS, CBE_ALLOWED_FIELDS, source)
    problem = schema.schema_version_problem(data["schema_version"])
    if problem:
        raise ReportError(f"{source}: {problem}")
    if data["package_id"] not in CBE_PACKAGE_IDS:
        raise ReportError(f"{source}: package_id {data['package_id']!r} is not a known package")
    if data["producer_id"] != "cbe":
        raise ReportError(f"{source}: producer_id must be 'cbe' for a CBE report")
    for name in ("version", "tag"):
        if not isinstance(data[name], str) or not schema.VERSION_PATTERN.fullmatch(data[name]) or not data[name].startswith("v"):
            raise ReportError(f"{source}: {name} must look like vX.Y.Z")
    status = _required_status(data, source, data.get("exit_code"))
    exit_code = _check_exit(data, status, source, observed)
    applicable, skip, ratio = _require_ratio(
        data, source, ("applicable_count", "skip_count", "skip_ratio")
    )
    for name in ("warn_count",):
        if not isinstance(data[name], int) or isinstance(data[name], bool) or data[name] < 0:
            raise ReportError(f"{source}: {name} must be a non-negative integer")
    for name in ("rules_manifest_hash", "evidence_sha256"):
        problem = schema.hash_problem(data[name], name)
        if problem:
            raise ReportError(f"{source}: {problem}")
    sarif_paths = data["sarif_paths"]
    if not isinstance(sarif_paths, list) or any(not isinstance(item, str) or not item for item in sarif_paths):
        raise ReportError(f"{source}: sarif_paths must be an array of non-empty strings")
    if not isinstance(data["blocking_skip"], bool):
        raise ReportError(f"{source}: blocking_skip must be a boolean")
    return ParsedReport(
        kind="cbe-report",
        source=source,
        schema_version=data["schema_version"],
        package_id=data["package_id"],
        producer_id=data["producer_id"],
        version=data["version"],
        tag=data["tag"],
        gate_status=status,
        exit_code=exit_code,
        applicable_count=applicable,
        skip_count=skip,
        skip_ratio=ratio,
        blocking_skip=data["blocking_skip"],
    )


def _parse_gate_report(data: dict[str, Any], source: str, observed: int | None) -> ParsedReport:
    _precheck_exit(data, source, observed)
    _require_fields(data, GATE_REPORT_REQUIRED_FIELDS, GATE_REPORT_ALLOWED_FIELDS, source)
    problem = schema.schema_version_problem(data["schema_version"])
    if problem:
        raise ReportError(f"{source}: {problem}")
    if data["producer_id"] != schema.PRODUCER_ID:
        raise ReportError(f"{source}: producer_id must be {schema.PRODUCER_ID!r}")
    if not isinstance(data["version"], str) or not schema.VERSION_PATTERN.fullmatch(data["version"]):
        raise ReportError(f"{source}: version must look like vX.Y.Z")
    status = _required_status(data, source, data.get("exit_code"))
    exit_code = _check_exit(data, status, source, observed)
    applicable, skip, ratio = _require_ratio(
        data, source, ("applicable_gate_count", "skip_count", "skip_ratio")
    )
    if not isinstance(data["blocking_skip"], bool):
        raise ReportError(f"{source}: blocking_skip must be a boolean")
    problems = schema.gate_entries_problems(data["gates"])
    if problems:
        raise ReportError(f"{source}: " + "; ".join(problems))
    forced = schema.forced_skip_names(data["gates"])
    if forced and not data["blocking_skip"]:
        raise ReportError(
            f"{source}: blocking_skip must be true when forced gate(s) are SKIPPED: "
            + ", ".join(sorted(forced))
        )
    if data["blocking_skip"] and not forced:
        raise ReportError(f"{source}: blocking_skip is true but no forced gate is SKIPPED")
    return ParsedReport(
        kind="cbp-gate-report",
        source=source,
        schema_version=data["schema_version"],
        package_id=data["package_id"],
        producer_id=data["producer_id"],
        version=data["version"],
        gate_status=status,
        exit_code=exit_code,
        applicable_count=applicable,
        skip_count=skip,
        skip_ratio=ratio,
        blocking_skip=data["blocking_skip"],
        gates=tuple(dict(entry) for entry in data["gates"]),
    )


def _parse_manifest(data: dict[str, Any], source: str, observed: int | None) -> ParsedReport:
    _precheck_exit(data, source, observed)
    problems = schema.validate_manifest(data, require_producer=False)
    if problems:
        raise ReportError(f"{source}: " + "; ".join(problems))
    status = _required_status(data, source, observed)
    exit_code = _check_exit(data, status, source, observed)
    return ParsedReport(
        kind="cbp-manifest",
        source=source,
        schema_version=data["schema_version"],
        package_id=data["package_id"],
        producer_id=str(data.get("producer_id", schema.PRODUCER_ID)),
        version=data["version"],
        gate_status=status,
        exit_code=exit_code,
        applicable_count=int(data["applicable_gate_count"]),
        skip_count=int(data["skip_count"]),
        skip_ratio=float(data["skip_ratio"]),
        blocking_skip=bool(data["blocking_skip"]),
        gates=tuple(dict(entry) for entry in data["gates"]),
    )
