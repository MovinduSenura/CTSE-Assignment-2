"""Property-based evaluation harness for the Planner member's contribution."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def evaluate_planner_properties() -> None:
    """Execute the planner property-based tests as a standalone evaluation step."""
    exit_code = pytest.main(["-q", "Member_1_Planner/test_planner_property.py"])
    if exit_code != 0:
        raise SystemExit(exit_code)
    print("Planner property-based evaluation passed.")


if __name__ == "__main__":
    evaluate_planner_properties()
