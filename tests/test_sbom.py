"""CBP self-SBOM: CycloneDX shape and full-SHA action pins."""
from __future__ import annotations

from tools import generate_sbom


def test_sbom_has_component_and_pinned_actions() -> None:
    data = generate_sbom.generate()
    assert data["bomFormat"] == "CycloneDX"
    assert data["metadata"]["component"]["name"] == "cbp-action"
    assert data["components"]
    for component in data["components"]:
        if component["name"].startswith("actions/"):
            assert len(component["version"]) == 40
