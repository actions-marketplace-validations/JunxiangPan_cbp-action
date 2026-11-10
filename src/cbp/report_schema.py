"""CONTRACT v1.7 gate statuses, exit codes, and manifest fields.

This module is the single place where CBP encodes the frozen exit-code table
(CONTRACT §1), the gate-status enum (§3), and the quality-manifest minimum
fields (§5). Anything that reports a verdict must go through it so a status and
an exit code cannot drift apart.
"""
from __future__ import annotations

import re
from enum import Enum
from typing import Any

CONTRACT_VERSION = "v1.7"

#: quality-manifest schema_version accepted by this build. D1: stays "1"; the
#: v1.7.1 amendment adds producer_id without a structural bump.
SUPPORTED_SCHEMA_VERSIONS = ("1",)
MANIFEST_SCHEMA_VERSION = "1"
PACKAGE_ID = "cbp"
PRODUCER_ID = "cbp"

EXIT_PASS = 0
EXIT_INPUT = 2
EXIT_GATE = 3
EXIT_SKIP = 4

VALID_EXIT_CODES = (EXIT_PASS, EXIT_INPUT, EXIT_GATE, EXIT_SKIP)

#: F3: skip_ratio > 0.20 exits 4. Exactly 0.20 passes.
SKIP_RATIO_LIMIT = 0.20
SKIP_RATIO_EPSILON = 1e-9

#: §5.2: hashes are bare 64-character lowercase hex. A sha256: prefix is an
#: input error and must not be stripped.
HASH_PATTERN = re.compile(r"^[a-f0-9]{64}$")
VERSION_PATTERN = re.compile(r"^v?[0-9]+\.[0-9]+\.[0-9]+$")

#: F3 forced gates for package_type=cbp. They may never be SKIPPED.
FORCED_GATES = ("claims", "binary", "encoding", "docs", "custom")
ADAPTED_GATES = ("coverage", "dependency", "comments", "upgrade")
ALL_GATES = FORCED_GATES + ADAPTED_GATES


class GateStatus(str, Enum):
    """The six gate-status values in CONTRACT §3."""

    PASS = "PASS"
    FAIL = "FAIL"
    SKIPPED = "SKIPPED"
    SKIPPED_INFRA = "SKIPPED_INFRA"
    PRECONDITION_FAIL = "PRECONDITION_FAIL"
    NOT_UPLOADED = "NOT_UPLOADED"


class InfraError(RuntimeError):
    """A runner, network, or provider failure: exit 3 with SKIPPED_INFRA."""


GATE_STATUS_VALUES = frozenset(status.value for status in GateStatus)
#: Statuses allowed on a whole report / manifest.
REPORT_STATUS_VALUES = frozenset({"PASS", "FAIL", "SKIPPED_INFRA", "PRECONDITION_FAIL", "NOT_UPLOADED"})
#: Statuses allowed on a single gate entry.
GATE_ENTRY_STATUS_VALUES = frozenset({"PASS", "FAIL", "SKIPPED"})

_EXIT_CODES_BY_STATUS = {
    "PASS": frozenset({EXIT_PASS}),
    "FAIL": frozenset({EXIT_INPUT, EXIT_GATE, EXIT_SKIP}),
    "SKIPPED_INFRA": frozenset({EXIT_GATE}),
    "PRECONDITION_FAIL": frozenset({EXIT_INPUT, EXIT_GATE}),
    # Per-gate states never travel as a report status.
    "SKIPPED": frozenset(),
    "NOT_UPLOADED": frozenset({EXIT_PASS, EXIT_GATE}),
}


def hash_problem(value: Any, path: str) -> str:
    """Return why a hash field is invalid, or an empty string when it is valid."""
    if not isinstance(value, str) or not value:
        return f"{path}: a bare 64-character lowercase hex string is required"
    if value.startswith("sha256:"):
        return (
            f"{path}: hashes are bare 64-character lowercase hex; "
            "a sha256: prefix is an input error and is not stripped"
        )
    if not HASH_PATTERN.fullmatch(value):
        return f"{path}: must be 64 lowercase hex characters"
    return ""


def schema_version_problem(value: Any, path: str = "schema_version") -> str:
    """Return why a schema_version is unsupported, or an empty string."""
    if not isinstance(value, str) or not value:
        return f"{path}: a schema_version string is required"
    if value not in SUPPORTED_SCHEMA_VERSIONS:
        supported = ", ".join(SUPPORTED_SCHEMA_VERSIONS)
        return f"{path}: unsupported schema_version {value!r} (supported: {supported})"
    return ""


def exit_status_problems(
    exit_code: Any,
    gate_status: Any,
    *,
    source: str = "report",
) -> list[str]:
    """Validate an observed exit code against a gate status (CONTRACT §1)."""
    problems: list[str] = []
    if exit_code not in VALID_EXIT_CODES:
        problems.append(f"{source}: exit_code {exit_code!r} is not one of 0/2/3/4")
    if not isinstance(gate_status, str) or not gate_status:
        if exit_code == EXIT_GATE:
            problems.append(
                f"{source}: exit 3 requires a valid gate_status; "
                "a missing gate_status is an input error (exit 2)"
            )
        else:
            problems.append(f"{source}: gate_status is required")
        return problems
    if gate_status not in REPORT_STATUS_VALUES:
        problems.append(
            f"{source}: gate_status {gate_status!r} is not one of "
            + ", ".join(sorted(REPORT_STATUS_VALUES))
        )
        return problems
    allowed = _EXIT_CODES_BY_STATUS[gate_status]
    if exit_code in VALID_EXIT_CODES and exit_code not in allowed:
        problems.append(
            f"{source}: exit {exit_code} is inconsistent with gate_status {gate_status}"
        )
    return problems


def gate_entries_problems(entries: Any, *, path: str = "gates") -> list[str]:
    """Validate the per-gate array from CONTRACT §5."""
    if not isinstance(entries, list):
        return [f"{path}: must be an array of gate objects"]
    problems: list[str] = []
    seen: set[str] = set()
    allowed_keys = {"name", "status", "reason"}
    for index, entry in enumerate(entries):
        at = f"{path}[{index}]"
        if not isinstance(entry, dict):
            problems.append(f"{at}: must be an object")
            continue
        unknown = sorted(set(entry) - allowed_keys)
        if unknown:
            problems.append(f"{at}: unexpected key(s) {', '.join(unknown)}")
        name = entry.get("name")
        if not isinstance(name, str) or not name:
            problems.append(f"{at}.name: a non-empty string is required")
        elif name in seen:
            problems.append(f"{at}.name: duplicate gate {name!r}")
        else:
            seen.add(name)
        status = entry.get("status")
        if status not in GATE_ENTRY_STATUS_VALUES:
            problems.append(
                f"{at}.status: must be one of " + ", ".join(sorted(GATE_ENTRY_STATUS_VALUES))
            )
        reason = entry.get("reason", "")
        if reason is not None and not isinstance(reason, str):
            problems.append(f"{at}.reason: must be a string when present")
    return problems


def forced_skip_names(entries: Any) -> set[str]:
    """Return forced gates that are marked SKIPPED in a gate array."""
    if not isinstance(entries, list):
        return set()
    skipped: set[str] = set()
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        if entry.get("name") in FORCED_GATES and entry.get("status") == "SKIPPED":
            skipped.add(str(entry["name"]))
    return skipped


def ratio_problem(
    applicable_count: Any,
    skip_count: Any,
    skip_ratio: Any,
    *,
    fields: tuple[str, str, str] = ("applicable_gate_count", "skip_count", "skip_ratio"),
) -> str:
    """Validate the skip denominator and its derived ratio."""
    applicable_name, skip_name, ratio_name = fields
    if not isinstance(applicable_count, int) or isinstance(applicable_count, bool) or applicable_count < 0:
        return f"{applicable_name}: a non-negative integer is required"
    if not isinstance(skip_count, int) or isinstance(skip_count, bool) or skip_count < 0:
        return f"{skip_name}: a non-negative integer is required"
    if skip_count > applicable_count:
        return f"{skip_name}: {skip_count} is greater than {applicable_name} {applicable_count}"
    if not isinstance(skip_ratio, (int, float)) or isinstance(skip_ratio, bool):
        return f"{ratio_name}: a number is required"
    if skip_ratio < 0 or skip_ratio > 1:
        return f"{ratio_name}: must be between 0 and 1"
    if applicable_count == 0:
        if skip_count != 0 or abs(float(skip_ratio)) > SKIP_RATIO_EPSILON:
            return f"{ratio_name}: must be 0 when {applicable_name} is 0"
        return ""
    expected = skip_count / applicable_count
    if abs(float(skip_ratio) - expected) > SKIP_RATIO_EPSILON:
        return (
            f"{ratio_name}: {skip_ratio} does not equal {skip_name}/{applicable_name} "
            f"({expected:.6f})"
        )
    return ""


MANIFEST_REQUIRED_FIELDS = (
    "schema_version",
    "package_id",
    "version",
    "gate_status",
    "applicable_gate_count",
    "skip_count",
    "skip_ratio",
    "blocking_skip",
    "gates",
    "artifact_hashes",
    "release_body_hash",
    "evidence_sha256",
)

MANIFEST_ALLOWED_FIELDS = frozenset(MANIFEST_REQUIRED_FIELDS) | {
    "producer_id",
    # 1.2.0: body hashing scope and the repository that owns the artifacts.
    "body_hash_scope",
    "artifact_repository",
    # CONTRACT §4 publish preconditions bind the manifest to a CI run and a commit.
    "ci_run_id",
    "ci_commit_sha",
    "generated_at",
    "generated_by",
}

#: 1.2.0 supports only the base body hash. "full" is explicitly unsupported.
BODY_HASH_SCOPES = ("base",)


def body_hash_scope_problem(value: Any, path: str = "body_hash_scope") -> str:
    """Return why a body_hash_scope is unsupported, or an empty string."""
    if value in BODY_HASH_SCOPES:
        return ""
    return (
        f"{path}: unsupported value {value!r}; supported: "
        + ", ".join(BODY_HASH_SCOPES)
    )


def validate_manifest(
    manifest: Any,
    *,
    require_producer: bool = False,
    require_body_scope: bool = False,
    expected_repository: str = "",
    require_rc2: bool = False,
) -> list[str]:
    """Validate a CBP quality manifest against CONTRACT §5.

    Returns a list of problems with JSON-ish paths. An empty list means valid.
    Missing required fields are input errors (exit 2), not gate failures.
    """
    if not isinstance(manifest, dict):
        return ["manifest: must be a JSON object"]
    problems: list[str] = []
    unknown = sorted(set(manifest) - MANIFEST_ALLOWED_FIELDS)
    if unknown:
        problems.append("manifest: unexpected key(s) " + ", ".join(unknown))
    for field in MANIFEST_REQUIRED_FIELDS:
        if field not in manifest:
            problems.append(f"{field}: required field is missing")
    if require_producer and "producer_id" not in manifest:
        problems.append("producer_id: required field is missing")
    if "schema_version" in manifest:
        problem = schema_version_problem(manifest["schema_version"])
        if problem:
            problems.append(problem)
    package_id = manifest.get("package_id")
    if "package_id" in manifest and (not isinstance(package_id, str) or not package_id):
        problems.append("package_id: a non-empty string is required")
    producer_id = manifest.get("producer_id")
    if "producer_id" in manifest and (not isinstance(producer_id, str) or not producer_id):
        problems.append("producer_id: a non-empty string is required")
    version = manifest.get("version")
    if "version" in manifest and (not isinstance(version, str) or not VERSION_PATTERN.fullmatch(version)):
        problems.append("version: must look like vX.Y.Z")
    if "body_hash_scope" in manifest:
        problem = body_hash_scope_problem(manifest["body_hash_scope"])
        if problem:
            problems.append(problem)
    elif require_body_scope:
        problems.append("body_hash_scope: required field is missing")
    repository = manifest.get("artifact_repository")
    repository_name = ""
    if "artifact_repository" in manifest:
        if isinstance(repository, str):
            if not repository:
                problems.append("artifact_repository: a non-empty string is required")
            repository_name = repository
        elif isinstance(repository, dict):
            missing = {"repository", "run_id", "artifact_name"} - set(repository)
            if missing:
                problems.append(
                    "artifact_repository: missing " + ", ".join(sorted(missing))
                )
            for key in ("repository", "run_id", "artifact_name"):
                value = repository.get(key)
                if key in repository and (not isinstance(value, str) or not value):
                    problems.append(f"artifact_repository.{key}: a non-empty string is required")
            repository_name = str(repository.get("repository", "") or "")
        else:
            problems.append("artifact_repository: must be an object")
    elif require_rc2:
        problems.append("artifact_repository: required object is missing")
    if expected_repository and repository_name and repository_name != expected_repository:
        problems.append(
            f"artifact_repository.repository: {repository_name!r} != expected "
            f"{expected_repository!r} (cross-repository artifact)"
        )
    commit_sha = manifest.get("ci_commit_sha")
    if "ci_commit_sha" in manifest:
        if not isinstance(commit_sha, str) or not re.fullmatch(r"[0-9a-f]{40}", commit_sha):
            problems.append("ci_commit_sha: 40 lowercase hexadecimal characters required")
    elif require_rc2:
        problems.append("ci_commit_sha: required field is missing")
    if require_rc2:
        if not isinstance(manifest.get("artifact_repository"), dict):
            problems.append("artifact_repository: RC2 requires the object form")
    gate_status = manifest.get("gate_status")
    if "gate_status" in manifest and gate_status not in REPORT_STATUS_VALUES:
        problems.append(
            "gate_status: must be one of " + ", ".join(sorted(REPORT_STATUS_VALUES))
        )
    if "gates" in manifest:
        problems.extend(gate_entries_problems(manifest["gates"]))
    if all(name in manifest for name in ("applicable_gate_count", "skip_count", "skip_ratio")):
        problem = ratio_problem(
            manifest["applicable_gate_count"], manifest["skip_count"], manifest["skip_ratio"]
        )
        if problem:
            problems.append(problem)
    blocking_skip = manifest.get("blocking_skip")
    if "blocking_skip" in manifest and not isinstance(blocking_skip, bool):
        problems.append("blocking_skip: must be a boolean")
    if isinstance(blocking_skip, bool) and package_id == PACKAGE_ID and "gates" in manifest:
        forced = forced_skip_names(manifest["gates"])
        if forced and not blocking_skip:
            problems.append(
                "blocking_skip: must be true when forced gate(s) are SKIPPED: "
                + ", ".join(sorted(forced))
            )
        if blocking_skip and not forced:
            problems.append("blocking_skip: is true but no forced gate is SKIPPED")
    artifact_hashes = manifest.get("artifact_hashes")
    if "artifact_hashes" in manifest:
        if not isinstance(artifact_hashes, dict):
            problems.append("artifact_hashes: must be an object")
        else:
            for name, digest in artifact_hashes.items():
                problem = hash_problem(digest, f"artifact_hashes.{name}")
                if problem:
                    problems.append(problem)
    for name in ("release_body_hash", "evidence_sha256"):
        if name in manifest:
            problem = hash_problem(manifest[name], name)
            if problem:
                problems.append(problem)
    return problems


def report_exit_code(
    *,
    blocking_skip: bool,
    failed: bool,
    skip_ratio: float,
) -> tuple[int, str]:
    """Map gate outcomes to the CONTRACT §1 exit code and report status."""
    if blocking_skip or failed:
        return EXIT_GATE, "FAIL"
    if skip_ratio > SKIP_RATIO_LIMIT:
        return EXIT_SKIP, "FAIL"
    return EXIT_PASS, "PASS"
