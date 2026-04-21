"""Standalone evaluation harness for the Researcher member's contribution."""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from Member_2_Researcher.attraction_tool import AttractionResult, DestinationContext
from Member_2_Researcher.research_agent import AttractionRecommendation, ResearchOutput


def evaluate_research_models() -> None:
    """Run deterministic checks on Researcher-side structured models."""
    context = DestinationContext(
        destination="Kandy",
        display_name="Kandy, Sri Lanka",
        latitude=7.2906,
        longitude=80.6337,
        country="Sri Lanka",
    )
    attraction = AttractionResult(
        name="Temple of the Tooth",
        description="Historic religious site in Kandy.",
        estimated_time_hours=2.0,
        interest_match="culture",
        source="https://example.com",
    )
    output = ResearchOutput(
        destination_summary="Kandy is known for cultural heritage and scenic surroundings.",
        attractions=[AttractionRecommendation(**attraction.model_dump())],
    )

    assert context.destination == "Kandy"
    assert context.country == "Sri Lanka"
    assert output.destination_summary
    assert len(output.attractions) == 1
    assert output.attractions[0].name == "Temple of the Tooth"
    print("Researcher evaluation passed.")


if __name__ == "__main__":
    evaluate_research_models()
