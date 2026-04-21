from hypothesis import given, strategies as st

from Member_2_Researcher.attraction_tool import AttractionResult, DestinationContext


@given(
    destination=st.text(
        alphabet=st.characters(whitelist_categories=("Lu", "Ll", "Zs")),
        min_size=1,
        max_size=20,
    ).map(str.strip).filter(bool),
    latitude=st.floats(min_value=-90, max_value=90, allow_nan=False, allow_infinity=False),
    longitude=st.floats(min_value=-180, max_value=180, allow_nan=False, allow_infinity=False),
)
def test_destination_context_properties(destination: str, latitude: float, longitude: float) -> None:
    context = DestinationContext(
        destination=destination,
        display_name=f"{destination}, Test Country",
        latitude=latitude,
        longitude=longitude,
        country="Test Country",
    )
    assert context.destination
    assert -90 <= context.latitude <= 90
    assert -180 <= context.longitude <= 180


@given(
    name=st.text(min_size=1, max_size=30),
    description=st.text(min_size=1, max_size=120),
    estimated_time=st.floats(min_value=0.5, max_value=8, allow_nan=False, allow_infinity=False),
)
def test_attraction_result_properties(name: str, description: str, estimated_time: float) -> None:
    result = AttractionResult(
        name=name,
        description=description,
        estimated_time_hours=estimated_time,
        interest_match="culture",
        source="https://example.com",
    )
    assert result.name
    assert result.description
    assert result.estimated_time_hours > 0
