"""Every hostile corpus entry must be rejected; >=50 cases."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from cbp import hostile_input

CORPUS = Path(__file__).parent / "hostile" / "corpus.json"
CASES = json.loads(CORPUS.read_text(encoding="utf-8"))


def _reject(case: dict) -> None:
    target = case["target"]
    payload = case["payload"]
    if target == "strict_json":
        with pytest.raises((ValueError, json.JSONDecodeError)):
            hostile_input.strict_json(payload, duplicate_keys=True)
    else:
        with pytest.raises(hostile_input.HostileInput):
            getattr(hostile_input, target)(payload)


def test_corpus_has_at_least_50_cases() -> None:
    assert len(CASES) >= 50
    assert {case["expect"] for case in CASES} == {"FAIL"}


@pytest.mark.parametrize("case", CASES, ids=[case["id"] for case in CASES])
def test_each_hostile_case_is_rejected(case: dict) -> None:
    _reject(case)
