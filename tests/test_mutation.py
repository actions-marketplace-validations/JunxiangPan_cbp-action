"""Mutation gate: known mutants must all be detected (recall >= 0.95)."""
from __future__ import annotations

from pathlib import Path

from tests.mutation import run_mutations


def test_mutation_recall_meets_target(tmp_path: Path) -> None:
    result = run_mutations.run(tmp_path / "mutation-report.md")
    assert result["mutants"] >= 12
    assert result["recall"] >= 0.95
    assert all(row["detected"] for row in result["rows"])
