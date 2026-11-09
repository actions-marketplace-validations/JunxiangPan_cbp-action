"""Strict UTF-8 no-BOM gate for tracked text files.

Legacy Windows PowerShell 5.1 needs a BOM to read non-ASCII (for example CJK)
script content. Such files can be exempted only by an explicit, per-path entry
with a reason; there are no wildcards and every entry is reported.
"""
from __future__ import annotations

import codecs
import subprocess
from pathlib import Path

from .config import GateConfig

TEXT_SUFFIXES = {
    ".md", ".yml", ".yaml", ".py", ".json", ".toml", ".txt", ".csv",
    ".ps1", ".cs", ".csproj", ".xml", ".sh", ".cfg", ".ini", ".html",
    ".css", ".js", ".ts", ".tsx", ".jsx",
}
SKIP_PARTS = {".git", ".venv", "site-packages", "node_modules", "__pycache__", "dist", "build"}


def _tracked(root: Path) -> list[Path]:
    try:
        completed = subprocess.run(
            ["git", "-C", str(root), "ls-files", "-z"],
            capture_output=True,
            timeout=20,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        completed = None
    if completed and completed.returncode == 0 and completed.stdout:
        names = [item for item in completed.stdout.decode("utf-8", "replace").split("\x00") if item]
        return [root / name for name in names if not (set(Path(name).parts) & SKIP_PARTS)]
    return [
        path for path in root.rglob("*")
        if path.is_file() and not (set(path.parts) & SKIP_PARTS)
    ]


def _text_files(root: Path) -> list[Path]:
    return sorted(
        path for path in _tracked(root)
        if path.is_file() and path.suffix.lower() in TEXT_SUFFIXES
    )


def _normalize(path: str) -> str:
    value = path.replace("\\", "/")
    while value.startswith("./"):
        value = value[2:]
    return value


def _allowlist(cfg: GateConfig) -> tuple[dict[str, str], str]:
    """Return {relative path: reason} or a configuration error string."""
    entries = getattr(cfg, "encoding_allowlist", ()) or ()
    if not isinstance(entries, (list, tuple)):
        return {}, "encoding_allowlist must be an array"
    allowed: dict[str, str] = {}
    for index, entry in enumerate(entries):
        at = f"encoding_allowlist[{index}]"
        if not isinstance(entry, dict):
            return {}, f"{at}: must be an object"
        unknown = sorted(set(entry) - {"path", "reason"})
        if unknown:
            return {}, f"{at}: unexpected key(s) {', '.join(unknown)}"
        path = entry.get("path")
        reason = entry.get("reason")
        if not isinstance(path, str) or not path.strip():
            return {}, f"{at}.path: a relative path is required"
        if Path(path).is_absolute() or path.startswith(("/", "\\")):
            return {}, f"{at}.path: an absolute path is not allowed"
        if any(character in path for character in "*?["):
            return {}, f"{at}.path: wildcards are not allowed"
        if not isinstance(reason, str) or not reason.strip():
            return {}, f"{at}.reason: a non-empty reason is required"
        normalized = _normalize(path.strip())
        if normalized in allowed:
            return {}, f"{at}.path: duplicate allowlist entry {normalized}"
        allowed[normalized] = reason.strip()
    return allowed, ""


def run(cfg: GateConfig) -> tuple[bool, str]:
    """Reject BOM-prefixed or non-UTF-8 tracked text files."""
    allowed, problem = _allowlist(cfg)
    if problem:
        return False, problem
    bad: list[str] = []
    allowlisted: list[str] = []
    unused: list[str] = []
    seen: set[str] = set()
    files = _text_files(cfg.root)
    for path in files:
        relative = path.relative_to(cfg.root).as_posix()
        seen.add(relative)
        try:
            data = path.read_bytes()
        except OSError as exc:
            bad.append(f"{relative}: read error: {exc}")
            continue
        has_bom = data.startswith(codecs.BOM_UTF8) or data.startswith(codecs.BOM_UTF16_LE) or data.startswith(codecs.BOM_UTF16_BE)
        if has_bom:
            if relative in allowed:
                allowlisted.append(relative)
                continue
            kind = "UTF-8 BOM" if data.startswith(codecs.BOM_UTF8) else "UTF-16 BOM"
            bad.append(f"{relative}: {kind}")
            continue
        if relative in allowed:
            unused.append(relative)
        try:
            data.decode("utf-8", "strict")
        except UnicodeDecodeError as exc:
            bad.append(f"{relative}: invalid UTF-8: {exc}")
    missing = sorted(set(allowed) - seen)
    if missing:
        bad.append("encoding_allowlist entry matches no tracked text file: " + ", ".join(missing))
    if bad:
        return False, "\n".join(bad[:80]) + f"\nfindings={len(bad)}"
    detail = f"encoding={len(files)} UTF-8 files without BOM"
    if allowlisted:
        detail += f" allowlisted={len(allowlisted)} ({', '.join(sorted(allowlisted)[:5])})"
    if unused:
        detail += f" allowlist_unused={len(unused)}"
    return True, detail
