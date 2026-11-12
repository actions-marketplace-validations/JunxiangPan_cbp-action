"""CBP 1.5 gates stay independent of CBE."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_no_cbe_import_in_source_or_tools() -> None:
    for directory in ("src", "tools"):
        for path in (ROOT / directory).rglob("*.py"):
            text = path.read_text(encoding="utf-8", errors="replace")
            assert "import cbe" not in text, path
            assert "from cbe" not in text, path


def test_import_cbp_does_not_load_cbe() -> None:
    code = "import sys, cbp; assert not any(m == 'cbe' or m.startswith('cbe.') for m in sys.modules); print('OK')"
    result = subprocess.run([sys.executable, "-I", "-c", code], cwd=ROOT, capture_output=True, text=True, check=False)
    assert result.returncode == 0, result.stderr
