"""Property-based evaluation harness for the Researcher member's contribution."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def evaluate_research_properties() -> None:
    """Execute the Researcher property-based tests."""
    exit_code = pytest.main(["-q", "Member_2_Researcher/test_research_property.py"])
    if exit_code != 0:
        raise SystemExit(exit_code)
    print("Researcher property-based evaluation passed.")


if __name__ == "__main__":
    evaluate_research_properties()
