from Member_2_Researcher import attraction_tool
from Member_2_Researcher.attraction_tool import AttractionResult, DestinationContext
from Member_2_Researcher.attraction_tool import (
    _build_interest_search_queries,
    _is_excluded_place,
    _is_excluded_summary,
    _is_destination_related,
    _pick_interest,
    _select_ranked_attractions,
    search_attractions,
)
from Member_2_Researcher.research_agent import AttractionRecommendation, ResearchOutput, _sanitize_research_output


def test_research_models_hold_expected_values() -> None:
    recommendation = AttractionRecommendation(
        name="Senso-ji",
        description="Historic Buddhist temple.",
        estimated_time_hours=2.5,
        interest_match="culture",
        source="https://example.com",
    )
    output = ResearchOutput(destination_summary="Tokyo is a large city.", attractions=[recommendation])
    assert output.destination_summary
    assert output.attractions[0].interest_match == "culture"


def test_destination_context_model_holds_expected_values() -> None:
    context = DestinationContext(
        destination="Kandy",
        display_name="Kandy, Sri Lanka",
        latitude=7.2906,
        longitude=80.6337,
        country="Sri Lanka",
    )
    assert context.destination == "Kandy"
    assert context.country == "Sri Lanka"


def test_attraction_result_model_requires_positive_time() -> None:
    result = AttractionResult(
        name="Temple of the Tooth",
        description="Historic religious site.",
        estimated_time_hours=2.0,
        interest_match="culture",
        source="https://example.com",
        distance_meters=350,
        relevance_score=4.5,
    )
    assert result.estimated_time_hours > 0
    assert result.distance_meters == 350
    assert result.relevance_score > 0


def test_research_tool_excludes_low_value_places() -> None:
    assert _is_excluded_place("Kandy Airport") is True
    assert _is_excluded_place("Colombo Fort Railway Station") is True
    assert _is_excluded_place("Kandy Administrative District") is True
    assert _is_excluded_place("Temple of the Tooth") is False


def test_summary_filter_allows_valid_kandy_context_words() -> None:
    assert _is_excluded_summary("Kandy is a major city in the Central Province of Sri Lanka.") is False
    assert _is_excluded_summary("The complex was built by a local company and is near the temple.") is False
    assert _is_excluded_summary("This is a railway station used for commuter transport.") is True


def test_interest_matching_uses_summary_keywords() -> None:
    interest = _pick_interest(
        title="Royal Botanical Gardens",
        summary="A scenic natural garden with rare trees and walking paths.",
        interests=["culture", "nature"],
    )
    assert interest == "nature"


def test_interest_matching_supports_buddhism_and_gems() -> None:
    assert _pick_interest("Maha Saman Devalaya", "A Buddhist shrine in Ratnapura.", ["buddhism", "gems"]) == "buddhism"
    assert _pick_interest("Gem Museum", "A museum about sapphire and gemstone mining.", ["buddhism", "gems"]) == "gems"


def test_interest_search_queries_include_domain_terms() -> None:
    queries = _build_interest_search_queries("Ratnapura", ["buddhism", "gems"])

    assert "Ratnapura devalaya Sri Lanka" in queries
    assert "Ratnapura Saman Devalaya Sri Lanka" in queries
    assert "Ratnapura gem museum Sri Lanka" in queries


def test_ranked_selection_prefers_different_landmark_types() -> None:
    attractions = [
        AttractionResult(
            name="First Raja Maha Vihara",
            description="Ancient Buddhist vihara.",
            estimated_time_hours=2.5,
            interest_match="buddhism",
            source="https://example.com/first",
            relevance_score=6.4,
        ),
        AttractionResult(
            name="Second Raja Maha Vihara",
            description="Another Buddhist vihara.",
            estimated_time_hours=2.5,
            interest_match="buddhism",
            source="https://example.com/second",
            relevance_score=5.9,
        ),
        AttractionResult(
            name="Local Saman Devalaya",
            description="A Buddhist devalaya and shrine.",
            estimated_time_hours=2.5,
            interest_match="buddhism",
            source="https://example.com/devalaya",
            relevance_score=5.8,
        ),
    ]

    selected = _select_ranked_attractions(attractions, ["buddhism"], limit=2)

    assert [item.name for item in selected] == ["First Raja Maha Vihara", "Local Saman Devalaya"]


def test_text_search_results_must_be_destination_related() -> None:
    context = DestinationContext(
        destination="Ratnapura",
        display_name="Ratnapura District, Sabaragamuwa Province, Sri Lanka",
        latitude=6.6828,
        longitude=80.3992,
        country="Sri Lanka",
    )

    assert _is_destination_related(context, "Maha Saman Devalaya", "A shrine situated in Ratnapura.") is True
    assert _is_destination_related(context, "Temple of the Tooth", "A Buddhist temple in Kandy.") is False


def test_sanitize_research_output_removes_unsupported_llm_attractions() -> None:
    context = DestinationContext(
        destination="Kandy",
        display_name="Kandy, Sri Lanka",
        latitude=7.2906,
        longitude=80.6337,
        country="Sri Lanka",
    )
    supported = AttractionResult(
        name="Temple of the Tooth",
        description="Historic Buddhist temple in Kandy.",
        estimated_time_hours=2.5,
        interest_match="culture",
        source="https://example.com/tooth",
        distance_meters=400,
        relevance_score=5.0,
    )
    llm_output = ResearchOutput(
        destination_summary="Kandy has strong cultural attractions.",
        attractions=[
            AttractionRecommendation(
                name="Made Up Place",
                description="Unsupported attraction invented by the LLM.",
                estimated_time_hours=2.0,
                interest_match="culture",
                source="https://example.com/fake",
            ),
            AttractionRecommendation(**supported.model_dump()),
        ],
    )

    sanitized = _sanitize_research_output(llm_output, context, [supported])

    assert [item.name for item in sanitized.attractions] == ["Temple of the Tooth"]
    assert sanitized.attractions[0].distance_meters == 400
    assert sanitized.attractions[0].relevance_score == 5.0


def test_search_attractions_expands_radius_when_nearby_results_are_thin(monkeypatch) -> None:
    context = DestinationContext(
        destination="Kandy",
        display_name="Kandy, Sri Lanka",
        latitude=7.2906,
        longitude=80.6337,
        country="Sri Lanka",
    )
    calls: list[int] = []

    def fake_search_with_radius(
        context: DestinationContext,
        interests: list[str],
        limit: int,
        timeout: int,
        radius: int,
    ) -> list[AttractionResult]:
        calls.append(radius)
        if radius == 10000:
            return [
                AttractionResult(
                    name="Nearby Temple",
                    description="Historic temple.",
                    estimated_time_hours=2.5,
                    interest_match="culture",
                    source="https://example.com/nearby",
                    distance_meters=500,
                    relevance_score=4.0,
                )
            ]
        return [
            AttractionResult(
                name="Far Museum",
                description="Historic museum with cultural exhibits.",
                estimated_time_hours=2.5,
                interest_match="culture",
                source="https://example.com/far",
                distance_meters=12000,
                relevance_score=5.0,
            )
        ]

    monkeypatch.setattr(attraction_tool, "_search_attractions_with_radius", fake_search_with_radius)
    monkeypatch.setattr(attraction_tool, "_search_attractions_by_text", lambda *args, **kwargs: [])

    results = search_attractions(context, ["culture"], limit=4)

    assert calls == [10000, 25000]
    assert results[0].name == "Far Museum"
