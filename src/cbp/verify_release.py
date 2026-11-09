"""Post-release audit: compare a published GitHub Release body with the repo."""
from __future__ import annotations

import hashlib
import json
import os
import urllib.error
import urllib.request
from pathlib import Path


def _canonical(data: str) -> bytes:
    return data.replace("\r\n", "\n").replace("\r", "\n").encode("utf-8")


def _sha(data: str) -> str:
    return hashlib.sha256(_canonical(data)).hexdigest()


from . import report_schema


def _api_error(status: int, repository: str, tag: str) -> Exception:
    """Classify an HTTP status: 5xx is infrastructure, 4xx is an input/gate error."""
    message = f"GitHub API HTTP {status} for {repository}@{tag}"
    if status >= 500:
        return report_schema.InfraError(message)
    return RuntimeError(message)


def fetch_release_body(repository: str, tag: str, token: str | None = None) -> str:
    """Fetch a release body from the GitHub REST API."""
    url = f"https://api.github.com/repos/{repository}/releases/tags/{tag}"
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "cbp-verify-release",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    if token:
        headers["Authorization"] = "Bearer " + token
    try:
        import certifi
        import requests

        response = requests.get(url, headers=headers, timeout=30, verify=certifi.where())
        if response.status_code >= 400:
            raise _api_error(response.status_code, repository, tag)
        payload = response.json()
    except (RuntimeError, report_schema.InfraError):
        raise
    except ImportError:
        import ssl
        context = ssl.create_default_context()
        try:
            import certifi
            context.load_verify_locations(certifi.where())
        except ImportError:
            pass
        request = urllib.request.Request(url, headers=headers)
        try:
            with urllib.request.urlopen(request, timeout=30, context=context) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            raise _api_error(exc.code, repository, tag) from exc
        except urllib.error.URLError as exc:
            raise report_schema.InfraError(f"GitHub API unavailable: {exc.reason}") from exc
    except Exception as exc:
        raise report_schema.InfraError(f"GitHub API unavailable: {exc}") from exc
    body = payload.get("body")
    if not isinstance(body, str):
        raise RuntimeError("GitHub release body is missing or is not a string")
    return body


def verify(repository: str, tag: str, local_body: Path, token: str | None = None) -> tuple[bool, str]:
    """Return a result and an ERRATA message when the body no longer matches."""
    if not local_body.is_file():
        return False, f"ERRATA local release body missing: {local_body}"
    local = local_body.read_text(encoding="utf-8")
    try:
        remote = fetch_release_body(repository, tag, token)
    except report_schema.InfraError:
        raise
    except RuntimeError as exc:
        return False, f"ERRATA cannot fetch release: {exc}"
    local_sha = _sha(local)
    remote_sha = _sha(remote)
    if local_sha != remote_sha:
        return False, (
            f"ERRATA release body mismatch for {repository}@{tag}: "
            f"local={local_sha} remote={remote_sha}; "
            "if this edit is intentional, update docs/RELEASE_BODY.md, rerun CI, and publish a new tag"
        )
    return True, f"RELEASE_BODY_OK sha256={local_sha}"


def token_from_env() -> str:
    """Read a GitHub token without printing it."""
    return os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN") or ""
