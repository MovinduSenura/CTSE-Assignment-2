"""Property-based evaluation harness for the Reviewer member's contribution."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def evaluate_reviewer_properties() -> None:
    """Execute the Reviewer property-based tests as a standalone evaluation step."""
    exit_code = pytest.main(["-q", "Member_4_Reviewer/test_reviewer_property.py"])
    if exit_code != 0:
        raise SystemExit(exit_code)
    print("Reviewer property-based evaluation passed.")


if __name__ == "__main__":
    evaluate_reviewer_properties()
