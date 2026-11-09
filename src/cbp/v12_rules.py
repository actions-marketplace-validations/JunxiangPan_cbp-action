"""CBP 1.2.0 detection rules.

The engine is deliberately small: every rule returns findings that start with a
repository-relative path, so a waiver can bind one rule to one exact path. A
waiver must carry a reason and an expiry; an expired waiver is not applied and
is reported. Warning rules may use a baseline with the same shape, so a warning
can be accepted only until a date.

Exit codes are decided by the CLI:
* blocking rule failure -> 3
* warning-only failure  -> 0 (visible WARN; 1.2.1 turns it into 3)
* malformed waiver/baseline -> 2
"""
from __future__ import annotations

import ast
import json
import re
import subprocess
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any, Callable

SKIP_PARTS = {".git", ".venv", "node_modules", "__pycache__", "dist", "build", ".tmp-sessions"}
VERSION_RE = re.compile(r"(?m)^version\s*=\s*[\"']([^\"']+)[\"']")
HEADING_RE = re.compile(r"(?m)^#{1,2}\s+v?(\d+\.\d+\.\d+)\s*$")
TOTAL_RE = re.compile(r"(?i)\b(total|count|rows?)\s*[:=]\s*(\d+)")
COVERED_ZERO_RE = re.compile(r"(?i)\bcovered\s*[:=]\s*0\b")
PERCENT_RE = re.compile(r"\b\d+(?:\.\d+)?%")
SCRIPT_RE = re.compile(r"(?:tools|scripts|installer|build)/[A-Za-z0-9_./-]+\.(?:ps1|py|sh|cmd|bat)")
DEBT_RE = re.compile(r"\b(FIXED|NOT_FIXED)\b")
PATH_TOKEN_RE = re.compile(r"[A-Za-z0-9_./-]+\.(?:py|ps1|sh|md|json|ya?ml|cs|ts|js|toml)")
NUMBER_RE = re.compile(r"\b\d+\b")


class RuleConfigError(ValueError):
    """Raised for a malformed waiver or baseline (CLI exit 2)."""


@dataclass(frozen=True)
class Waiver:
    rule: str
    path: str
    reason: str
    expires: str

    def active(self, today: date) -> bool:
        try:
            return date.fromisoformat(self.expires) >= today
        except ValueError:
            return False


@dataclass
class RuleResult:
    rule_id: str
    name: str
    severity: str
    findings: list[str] = field(default_factory=list)
    waived: list[str] = field(default_factory=list)
    baselined: list[str] = field(default_factory=list)

    @property
    def status(self) -> str:
        if self.findings:
            return "FAIL" if self.severity == "blocking" else "WARN"
        return "PASS"


@dataclass
class RuleContext:
    root: Path
    initial_worktree: str = ""
    waivers: list[Waiver] = field(default_factory=list)
    baseline: list[Waiver] = field(default_factory=list)
    today: date = field(default_factory=date.today)


def _ignored(path: Path, root: Path) -> bool:
    return any(
        part in SKIP_PARTS or part.startswith(".tmp-")
        for part in path.relative_to(root).parts
    )


def _iter_markdown(root: Path) -> list[Path]:
    return sorted(
        path for path in root.rglob("*.md")
        if path.is_file() and not _ignored(path, root)
    )


def _run_blocks(workflow: Path) -> list[str]:
    """Extract run commands (block or inline) without YAML comments."""
    lines = workflow.read_text(encoding="utf-8", errors="replace").splitlines()
    blocks: list[str] = []
    current: list[str] = []
    in_run = False
    indent = 0
    for line in lines:
        stripped = line.strip()
        match = re.search(r"\brun:\s*([|>])?\s*(.*)", stripped)
        if match and not in_run:
            if match.group(1):
                in_run = True
                indent = len(line) - len(line.lstrip())
                current = []
            elif match.group(2).strip():
                blocks.append(match.group(2).strip())
            continue
        if in_run:
            current_indent = len(line) - len(line.lstrip())
            if stripped and current_indent <= indent:
                in_run = False
                blocks.append("\n".join(current))
            elif not stripped.startswith("#"):
                current.append(line)
    if in_run:
        blocks.append("\n".join(current))
    return blocks


def _workflows(root: Path) -> list[Path]:
    directory = root / ".github" / "workflows"
    if not directory.is_dir():
        return []
    return sorted(
        path for path in directory.iterdir()
        if path.is_file() and path.suffix.lower() in {".yml", ".yaml"}
    )


def _git(root: Path, *args: str) -> tuple[int, str]:
    try:
        completed = subprocess.run(
            ["git", "-C", str(root), *args],
            capture_output=True, encoding="utf-8", errors="replace", timeout=30, check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return 1, f"git unavailable: {exc}"
    # A failed decode used to leave stdout=None on Windows (locale codec);
    # the unit separator output can contain non-UTF-8 file names.
    return completed.returncode, completed.stdout or ""


def _test_roots(root: Path) -> list[Path]:
    ignored = {"examples", "fixtures", "vendor", "third_party", "node_modules", "tests-fixtures"}
    roots = []
    for candidate in root.rglob("tests"):
        if not candidate.is_dir() or _ignored(candidate, root):
            continue
        parts = candidate.relative_to(root).parts
        if set(parts) & ignored:
            continue
        if parts and len(parts) > 3:
            continue
        if any(candidate.glob("test_*.py")):
            roots.append(candidate)
    return sorted(set(roots))


def rule_ci_001(ctx: RuleContext) -> list[str]:
    """CBP-CI-001: every test root must be executed by some workflow."""
    workflows = _workflows(ctx.root)
    if not workflows:
        return [".[github/workflows]: no CI workflow found"]
    commands = "\n".join("\n".join(_run_blocks(path)) for path in workflows).replace("\\", "/")
    roots = _test_roots(ctx.root)
    root_names = [root.relative_to(ctx.root).as_posix() for root in roots]
    bare_pytest = any(
        "pytest" in line and not any(name in line for name in root_names)
        for line in commands.splitlines()
    )
    if bare_pytest:
        return []
    findings = []
    for relative in root_names:
        if relative not in commands:
            findings.append(f"{relative}: test root is not executed by any workflow")
    return findings


def _version_sources(root: Path) -> dict[str, str]:
    sources: dict[str, str] = {}
    version_file = root / "VERSION"
    if version_file.is_file():
        value = version_file.read_text(encoding="utf-8", errors="replace").strip()
        if value:
            sources["VERSION"] = value.lstrip("vV")
    pyproject = root / "pyproject.toml"
    if pyproject.is_file():
        match = VERSION_RE.search(pyproject.read_text(encoding="utf-8", errors="replace"))
        if match:
            sources["pyproject.toml"] = match.group(1).lstrip("vV")
    config = root / "cbp.json"
    if config.is_file():
        try:
            data = json.loads(config.read_text(encoding="utf-8"))
            value = str(data.get("release_version", "") or "").lstrip("vV")
            if value:
                sources["cbp.json"] = value
        except (OSError, ValueError):
            sources["cbp.json"] = ""
    changelog = root / "CHANGELOG.md"
    if changelog.is_file():
        match = HEADING_RE.search(changelog.read_text(encoding="utf-8", errors="replace"))
        if match:
            sources["CHANGELOG.md"] = match.group(1)
    return sources


def rule_ver_001(ctx: RuleContext) -> list[str]:
    """CBP-VER-001: VERSION, pyproject, config and the newest CHANGELOG agree."""
    sources = _version_sources(ctx.root)
    if len(sources) < 2:
        return []
    canonical = sources.get("VERSION") or next(iter(sources.values()))
    findings = [
        f"{name}: version {value or '<missing>'} != {canonical}"
        for name, value in sorted(sources.items())
        if value != canonical
    ]
    return findings


def _qa_files(root: Path) -> list[Path]:
    candidates = [root / "FINAL_QA_REPORT.md"]
    candidates.extend(root.glob("*QA*REPORT*.md"))
    candidates.extend((root / "docs").glob("*QA*REPORT*.md"))
    return sorted({path for path in candidates if path.is_file()})


def rule_qa_001(ctx: RuleContext) -> list[str]:
    """CBP-QA-001: declared QA counts equal the table rows; Covered:0 is real."""
    findings: list[str] = []
    for qa in _qa_files(ctx.root):
        text = qa.read_text(encoding="utf-8", errors="replace")
        relative = qa.relative_to(ctx.root).as_posix()
        rows = 0
        in_table = False
        status_column = None
        for line in text.splitlines():
            stripped = line.strip()
            if not stripped.startswith("|"):
                in_table = False
                continue
            cells = [cell.strip() for cell in stripped.strip("|").split("|")]
            if not in_table:
                if any(cell.lower() == "status" for cell in cells):
                    in_table = True
                    status_column = [cell.lower() for cell in cells].index("status")
                continue
            if all(set(cell) <= set("-: ") for cell in cells):
                continue
            rows += 1
            if status_column is not None and status_column < len(cells):
                status = cells[status_column].upper()
                if status not in {"PASS", "PASSED", "FAIL", "FAILED", "SKIP", "SKIPPED", "WARN", "WARNING", "PARTIAL"}:
                    findings.append(f"{relative}: unknown QA row status {status!r}")
        if rows:
            match = TOTAL_RE.search(text)
            if match and int(match.group(2)) != rows:
                findings.append(f"{relative}: declared total {match.group(2)} != {rows} rows")
        if COVERED_ZERO_RE.search(text) and any(float(p.rstrip("%")) > 0 for p in PERCENT_RE.findall(text)):
            findings.append(f"{relative}: Covered: 0 contradicts disclosed coverage")
    return findings


def rule_debt_001(ctx: RuleContext) -> list[str]:
    """CBP-DEBT-001: every FIXED / NOT_FIXED entry cites a file or a number."""
    findings = []
    for path in _iter_markdown(ctx.root):
        relative = path.relative_to(ctx.root).as_posix()
        for number, line in enumerate(path.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
            if not DEBT_RE.search(line):
                continue
            if PATH_TOKEN_RE.search(line) or NUMBER_RE.search(line):
                continue
            findings.append(f"{relative}:{number}: {DEBT_RE.search(line).group(1)} without file or number")
    return findings


def rule_sign_001(ctx: RuleContext) -> list[str]:
    """CBP-SIGN-001: sign workflow scripts must exist in the tag tree."""
    findings = []
    for workflow in _workflows(ctx.root):
        if "sign" not in workflow.name.lower():
            continue
        relative_workflow = workflow.relative_to(ctx.root).as_posix()
        for block in _run_blocks(workflow):
            for script in SCRIPT_RE.findall(block):
                if not (ctx.root / script).is_file():
                    findings.append(f"{relative_workflow}: script missing from the tree: {script}")
    return findings


CONFLICT_START = "<<<<<<<"
CONFLICT_END = ">>>>>>>"
CONFLICT_BASE = "|||||||"
CONFLICT_SEPARATOR = "======="


def _tracked_files(root: Path) -> list[str] | None:
    code, output = _git(root, "ls-files", "-z")
    if code != 0:
        return None
    return [item for item in output.split("\0") if item]


def _conflict_marker_findings(root: Path) -> list[str]:
    """CBP-WT-001: tracked text files must not contain conflict markers."""
    files = _tracked_files(root)
    if files is None:
        return [".: git unavailable: cannot scan tracked files for conflict markers"]
    findings: list[str] = []
    for relative in files:
        path = root / relative
        try:
            if path.stat().st_size > 2_000_000:
                continue
            data = path.read_bytes()
        except OSError:
            continue
        if b"\0" in data[:4096]:
            continue
        in_conflict = False
        for number, line in enumerate(data.decode("utf-8", "replace").splitlines(), 1):
            stripped = line.rstrip()
            if stripped.startswith(CONFLICT_START):
                in_conflict = True
                findings.append(f"{relative}:{number}: conflict marker: {stripped[:60]}")
            elif stripped.startswith(CONFLICT_END):
                in_conflict = False
                findings.append(f"{relative}:{number}: conflict marker: {stripped[:60]}")
            elif stripped.startswith(CONFLICT_BASE):
                findings.append(f"{relative}:{number}: conflict marker: {stripped[:60]}")
            elif in_conflict and stripped == CONFLICT_SEPARATOR:
                findings.append(f"{relative}:{number}: conflict marker: {stripped[:60]}")
    return findings


def rule_wt_001(ctx: RuleContext) -> list[str]:
    """CBP-WT-001: no leftover conflict markers, no tracked changes after gates."""
    findings = _conflict_marker_findings(ctx.root)
    code, current = _git(ctx.root, "status", "--porcelain", "--untracked-files=no")
    if code != 0:
        findings.append(f".: {current}")
        return findings
    if current != ctx.initial_worktree:
        before = set(ctx.initial_worktree.splitlines())
        changed = []
        for line in current.splitlines():
            if line not in before:
                path = line[3:].strip() if len(line) > 3 else line
                changed.append(f"{path}: tracked file changed while gates ran")
        findings.extend(changed or [".: tracked worktree changed while gates ran"])
    return findings


def _pe_has_signature(path: Path) -> bool:
    """Return True when the PE certificate table is non-empty (presence only)."""
    data = path.read_bytes()
    if len(data) < 0x40 or data[:2] != b"MZ":
        return False
    offset = int.from_bytes(data[0x3C:0x40], "little")
    if offset + 24 > len(data) or data[offset:offset + 4] != b"PE\0\0":
        return False
    optional = offset + 24
    magic = int.from_bytes(data[optional:optional + 2], "little")
    directory = optional + (112 if magic == 0x20B else 96)
    entry = directory + 4 * 8
    if entry + 8 > len(data):
        return False
    size = int.from_bytes(data[entry + 4:entry + 8], "little")
    return size > 0


def rule_bin_001(ctx: RuleContext) -> list[str]:
    """CBP-BIN-001: installer executables carry an Authenticode blob."""
    findings = []
    for path in sorted(ctx.root.rglob("*.exe")):
        if _ignored(path, ctx.root):
            continue
        if "install" not in path.name.lower():
            continue
        if not _pe_has_signature(path):
            findings.append(f"{path.relative_to(ctx.root).as_posix()}: no Authenticode signature blob")
    return findings


DOC_PATH_RE = re.compile(
    r"[A-Za-z0-9_][A-Za-z0-9_./-]*\.(?:py|ps1|sh|md|json|ya?ml|cs|ts|js|toml)"
)
INLINE_CODE_RE = re.compile(r"`([^`]+)`")
LINK_TARGET_RE = re.compile(r"\[[^\]]*\]\(([^)]+)\)")


def _doc_paths(line: str) -> list[str]:
    candidates = INLINE_CODE_RE.findall(line) + LINK_TARGET_RE.findall(line)
    paths = []
    for candidate in candidates:
        value = candidate.split("#", 1)[0].strip().strip("\"'")
        if not value or value.startswith(("http://", "https://", "/")):
            continue
        if any(character in value for character in "<>*?{}") or "..." in value or " " in value:
            continue
        if value.startswith("../"):
            continue
        if not DOC_PATH_RE.fullmatch(value):
            continue
        paths.append(value[2:] if value.startswith("./") else value)
    return paths


CROSS_REPO_PREFIXES = (
    "public-release/", "cbe/", "cbm/", "cbc-event/", "cbp-action-release/",
    # The v1.7 contract namespace is owned by CBS.
    "docs/v1.7/", "schemas/v1.7/",
)
DOC_SOFT_RE = re.compile(r"(?i)\b(pending|planned|not yet|future|todo)\b")


def _doc_reference_exists(root: Path, reference: str) -> bool:
    """Resolve a doc reference; bare filenames and cross-repo paths are skipped."""
    if "/" not in reference:
        # A bare filename is too weak to fail on; the fixture uses a path.
        return True
    if reference.startswith(CROSS_REPO_PREFIXES) or reference.startswith("baseline/"):
        return True
    if (root / reference).exists():
        return True
    # A path quoted relative to a subdirectory still resolves by suffix.
    return any(
        path.is_file() and not _ignored(path, root)
        and path.as_posix().endswith("/" + reference)
        for path in root.rglob(reference.rsplit("/", 1)[-1])
    )


def rule_doc_001(ctx: RuleContext) -> list[str]:
    """CBP-DOC-001: backticked / linked repository paths exist."""
    findings = []
    for path in _iter_markdown(ctx.root):
        relative = path.relative_to(ctx.root).as_posix()
        for number, line in enumerate(path.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
            if DOC_SOFT_RE.search(line):
                continue
            for reference in _doc_paths(line):
                if not _doc_reference_exists(ctx.root, reference):
                    findings.append(f"{relative}:{number}: referenced path missing: {reference}")
    return findings


CLAIM_RE = re.compile(
    r"(?i)\b(prevents?|guarantees?|blocks?|enforces?)\b[^.\n]{0,60}"
    r"\b(escalation|bypass|injection|tamper|unauthori[sz]ed|privilege|secret|leak|replay|forgery|spoof|isolation)\b"
)
CLAIM_EVIDENCE_RE = re.compile(r"(test_|tests/|\bCBP-[A-Z]+-\d{3}\b|CBP-EXT-|origin_rule|\.py\b|\.ps1\b)")
CLAIM_SOFT_RE = re.compile(
    r"(?i)(audit-only|proposal|planned|partial|not yet|todo|cannot|does not|do not|isn't|claim this)"
)


def rule_claim_001(ctx: RuleContext) -> list[str]:
    """CBP-CLAIM-001: capability claims cite evidence or are audit-only."""
    findings = []
    for path in _iter_markdown(ctx.root):
        relative = path.relative_to(ctx.root).as_posix()
        in_code = False
        for number, line in enumerate(path.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
            stripped = line.lstrip()
            if stripped.startswith("```"):
                in_code = not in_code
                continue
            if in_code or stripped.startswith("#"):
                continue
            prose = re.sub(r"`[^`]*`", "", line)
            if not CLAIM_RE.search(prose) or CLAIM_SOFT_RE.search(prose):
                continue
            if CLAIM_EVIDENCE_RE.search(line):
                continue
            if " --" in line or line.strip().startswith(("python", "pip", "mode:", "cbe ")):
                continue
            findings.append(f"{relative}:{number}: capability claim without implementation or audit-only marker")
    return findings


def rule_cov_001(ctx: RuleContext) -> list[str]:
    """CBP-COV-001: the coverage gate is not downgraded to a warning."""
    findings = []
    pyproject = ctx.root / "pyproject.toml"
    if pyproject.is_file():
        text = pyproject.read_text(encoding="utf-8", errors="replace")
        for match in re.finditer(r"(?m)^\s*fail_under\s*=\s*(\d+)", text):
            if int(match.group(1)) < 50:
                findings.append(f"pyproject.toml: fail_under {match.group(1)} is below 50")
    for workflow in _workflows(ctx.root):
        text = workflow.read_text(encoding="utf-8", errors="replace")
        relative = workflow.relative_to(ctx.root).as_posix()
        lines = text.splitlines()
        for number, line in enumerate(lines):
            if "coverage" not in line.lower():
                continue
            window = "\n".join(lines[number:number + 10])
            if "continue-on-error: true" in window or "|| true" in window:
                findings.append(f"{relative}:{number + 1}: coverage step allows failure")
    return findings


PROOF_MARKERS = {
    "scm": re.compile(r"(?i)\b(commit|tag|branch|sha)\b"),
    "acl": re.compile(r"(?i)\b(acl|access control|permission)\b"),
    "service_account": re.compile(r"(?i)\b(service account|svc[-_ ]?account|服务账户)\b"),
}


def rule_proof_001(ctx: RuleContext) -> list[str]:
    """CBP-PROOF-001: high-tier proofs name SCM, ACL and service account."""
    proofs = sorted(
        path for path in [*ctx.root.glob("*PROOF*.md"), *ctx.root.glob("*proof*.md"),
                          *ctx.root.glob("*PROOF*.json"), *ctx.root.glob("*proof*.json"),
                          *ctx.root.glob("docs/*PROOF*.md"), *ctx.root.glob("docs/*proof*.md")]
        if path.is_file()
    )
    findings = []
    for proof in proofs:
        text = proof.read_text(encoding="utf-8", errors="replace")
        missing = [name for name, pattern in PROOF_MARKERS.items() if not pattern.search(text)]
        if missing:
            findings.append(f"{proof.relative_to(ctx.root).as_posix()}: missing markers: {', '.join(missing)}")
    return findings


SLOP_RE = re.compile(
    r"(?i)^(todo|no description|return the result|initialize the object|constructor|placeholder|implementation)\.?$"
)


def rule_slop_001(ctx: RuleContext) -> list[str]:
    """CBP-SLOP-001: template docstrings above the threshold."""
    threshold = 3
    occurrences: list[str] = []
    for path in sorted(ctx.root.rglob("*.py")):
        if _ignored(path, ctx.root):
            continue
        try:
            tree = ast.parse(path.read_text(encoding="utf-8", errors="replace"))
        except SyntaxError:
            continue
        relative = path.relative_to(ctx.root).as_posix()
        for node in ast.walk(tree):
            if not isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            docstring = ast.get_docstring(node, clean=True)
            if docstring and SLOP_RE.match(docstring.strip()):
                occurrences.append(f"{relative}:{getattr(node, 'lineno', 1)}: template docstring: {docstring.strip()!r}")
    return occurrences if len(occurrences) > threshold else []


RULES: list[tuple[str, str, str, Callable[[RuleContext], list[str]]]] = [
    ("CBP-CI-001", "TEST_ROOTS_IN_CI", "blocking", rule_ci_001),
    ("CBP-VER-001", "VERSION_SYNC", "blocking", rule_ver_001),
    ("CBP-QA-001", "QA_COUNTS_CONSISTENT", "blocking", rule_qa_001),
    ("CBP-DEBT-001", "DEBT_EVIDENCE", "blocking", rule_debt_001),
    ("CBP-SIGN-001", "SIGN_TOOLS_IN_TAG", "blocking", rule_sign_001),
    ("CBP-WT-001", "WORKTREE_CLEAN_AFTER_GATES", "blocking", rule_wt_001),
    ("CBP-BIN-001", "BINARY_AUTHENTICODE", "warning", rule_bin_001),
    ("CBP-DOC-001", "DOC_REFERENCES_EXIST", "warning", rule_doc_001),
    ("CBP-CLAIM-001", "CAPABILITY_CLAIMS", "warning", rule_claim_001),
    ("CBP-COV-001", "COVERAGE_HARD", "warning", rule_cov_001),
    ("CBP-PROOF-001", "PROOF_HIGH_TIER", "warning", rule_proof_001),
    ("CBP-SLOP-001", "DOCSTRING_SLOP", "warning", rule_slop_001),
]


def load_entries(path: Path | str | None, *, label: str) -> list[Waiver]:
    """Load and validate waivers or a baseline file."""
    if not path:
        return []
    target = Path(path)
    try:
        data = json.loads(target.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise RuleConfigError(f"{label} missing: {target}") from exc
    except (OSError, ValueError) as exc:
        raise RuleConfigError(f"{label} unreadable: {target}: {exc}") from exc
    entries = data.get(label) if isinstance(data, dict) else data
    if not isinstance(entries, list):
        raise RuleConfigError(f"{label} must be an array")
    parsed: list[Waiver] = []
    for index, entry in enumerate(entries):
        at = f"{label}[{index}]"
        if not isinstance(entry, dict):
            raise RuleConfigError(f"{at}: must be an object")
        unknown = sorted(set(entry) - {"rule", "path", "reason", "expires"})
        if unknown:
            raise RuleConfigError(f"{at}: unexpected key(s) {', '.join(unknown)}")
        rule = entry.get("rule")
        path_value = entry.get("path")
        reason = entry.get("reason")
        expires = entry.get("expires")
        if not isinstance(rule, str) or not rule:
            raise RuleConfigError(f"{at}.rule: required")
        if not isinstance(path_value, str) or not path_value:
            raise RuleConfigError(f"{at}.path: required")
        if not isinstance(reason, str) or not reason.strip():
            raise RuleConfigError(f"{at}.reason: required")
        if not isinstance(expires, str):
            raise RuleConfigError(f"{at}.expires: required (YYYY-MM-DD)")
        try:
            date.fromisoformat(expires)
        except ValueError as exc:
            raise RuleConfigError(f"{at}.expires: invalid date {expires!r}") from exc
        parsed.append(Waiver(rule=rule, path=path_value, reason=reason.strip(), expires=expires))
    return parsed


def _apply(entries: list[Waiver], rule_id: str, findings: list[str], today: date) -> tuple[list[str], list[str], list[str]]:
    remaining: list[str] = []
    accepted: list[str] = []
    expired: list[str] = []
    for finding in findings:
        path = finding.split(":", 1)[0]
        match = None
        for entry in entries:
            if entry.rule != rule_id:
                continue
            if entry.path not in {path, "*"}:
                continue
            if entry.active(today):
                match = entry
                break
            expired.append(f"{rule_id}: waiver for {path} expired on {entry.expires}")
        if match is None:
            remaining.append(finding)
        else:
            accepted.append(f"{path} (waiver {match.expires}: {match.reason})")
    return remaining, accepted, expired


def run_rules(
    root: Path,
    *,
    only: set[str] | None = None,
    waivers_path: Path | str | None = None,
    baseline_path: Path | str | None = None,
    today: date | None = None,
) -> tuple[list[RuleResult], list[str]]:
    """Run the selected rules and return results plus expired-waiver notices."""
    root = root.resolve()
    waivers = load_entries(waivers_path, label="waivers")
    baseline = load_entries(baseline_path, label="baseline")
    used_today = today or date.today()
    code, initial = _git(root, "status", "--porcelain", "--untracked-files=no")
    ctx = RuleContext(
        root=root,
        initial_worktree=initial if code == 0 else "",
        waivers=waivers,
        baseline=baseline,
        today=used_today,
    )
    results: list[RuleResult] = []
    expired: list[str] = []
    for rule_id, name, severity, function in RULES:
        if only and rule_id not in only:
            continue
        try:
            findings = function(ctx)
        except Exception as exc:  # a crashing rule is a failure, never a pass
            findings = [f".: rule crashed: {type(exc).__name__}: {exc}"]
        remaining, waived, expired_here = _apply(waivers, rule_id, findings, used_today)
        expired.extend(expired_here)
        result = RuleResult(rule_id=rule_id, name=name, severity=severity, waived=waived)
        if severity == "warning" and remaining:
            remaining, baselined, expired_base = _apply(baseline, rule_id, remaining, used_today)
            expired.extend(expired_base)
            result.baselined = baselined
        result.findings = remaining
        results.append(result)
    return results, expired


def report(results: list[RuleResult], expired: list[str]) -> dict[str, Any]:
    counts = {"PASS": 0, "FAIL": 0, "WARN": 0}
    for result in results:
        counts[result.status] += 1
    return {
        "schema": "cbp-v12-rule-report/v1",
        "rules": [
            {
                "id": result.rule_id,
                "name": result.name,
                "severity": result.severity,
                "status": result.status,
                "findings": result.findings,
                "waived": result.waived,
                "baselined": result.baselined,
            }
            for result in results
        ],
        "summary": {
            **counts,
            "blocking_failed": any(r.severity == "blocking" and r.status == "FAIL" for r in results),
            "warning_failed": any(r.severity == "warning" and r.status == "WARN" for r in results),
        },
        "expired_entries": expired,
    }
