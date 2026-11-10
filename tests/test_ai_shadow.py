"""AI audit stays shadow-mode and reports metrics, not a safety guarantee."""
from __future__ import annotations

import json
from pathlib import Path

from tools import ai_backtest


def test_shadow_backtest_metrics() -> None:
    rows = json.loads((Path(__file__).parent / "ai" / "incidents.json").read_text(encoding="utf-8"))
    result = ai_backtest.metrics(rows)
    assert result["tp"] == 5 and result["fn"] == 1
    assert result["fp"] == 1 and result["tn"] == 3
    assert abs(result["precision"] - 5 / 6) < 1e-9
    assert abs(result["recall"] - 5 / 6) < 1e-9
    assert result["blocking"] is False
