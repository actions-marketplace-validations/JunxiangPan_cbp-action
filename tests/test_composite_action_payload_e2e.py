"""Static contract for the 15-case composite-action payload workflow."""
from pathlib import Path


def test_composite_payload_matrix_is_complete() -> None:
    text = Path(".github/workflows/e2e-payload.yml").read_text(encoding="utf-8")
    assert "root:" in text and "coverage-json:" in text and "config:" in text
    assert "$(touch /tmp/pwned)" in text
    assert "`touch /tmp/pwned`" in text
    assert "PAYLOAD NOT EXECUTED" in text
    assert "continue-on-error: true" in text
