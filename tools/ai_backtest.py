"""Shadow-mode AI audit backtest: precision/recall only, never a guarantee."""
from __future__ import annotations

import json
from pathlib import Path


def metrics(rows: list[dict]) -> dict:
    tp = sum(1 for row in rows if row["label"] == "incident" and row["flagged"])
    fn = sum(1 for row in rows if row["label"] == "incident" and not row["flagged"])
    fp = sum(1 for row in rows if row["label"] == "clean" and row["flagged"])
    tn = sum(1 for row in rows if row["label"] == "clean" and not row["flagged"])
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    return {"tp": tp, "fp": fp, "fn": fn, "tn": tn,
            "precision": precision, "recall": recall, "blocking": False}


if __name__ == "__main__":
    import sys
    path = Path(sys.argv[1] if len(sys.argv) > 1 else "tests/ai/incidents.json")
    print(json.dumps(metrics(json.loads(path.read_text(encoding="utf-8"))), indent=2))
