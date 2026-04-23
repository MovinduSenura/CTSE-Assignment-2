"""Attraction research tool using public endpoints."""

from __future__ import annotations

from typing import Any

import requests
from pydantic import BaseModel, Field
from requests.utils import quote


USER_AGENT = "ai-travel-planner/0.1 (student assignment project)"
SRI_LANKA_COUNTRY_CODE = "lk"
EXCLUDED_KEYWORDS = {
    "airport",
    "station",
    "library",
    "office",
    "building",
    "bank",
    "hospital",
    "school",
    "college",
    "university",
    "road",
    "street",
    "district",
    "province",
    "company",
    "club",
    "railway",
    "bus stop",
    "junction",
    "secretariat",
}
SUMMARY_EXCLUDED_KEYWORDS = {
    "airport",
    "railway station",
    "bus station",
    "hospital",
    "school",
    "college",
    "university",
    "bank",
}

INTEREST_KEYWORDS = {
    "buddhism": {"buddhism", "buddhist", "vihara", "temple", "devalaya", "saman", "stupa"},
    "culture": {"culture", "cultural", "temple", "buddhist", "hindu", "mosque", "church", "festival"},
    "history": {"history", "historic", "ancient", "colonial", "kingdom", "fort", "palace", "museum"},
    "nature": {"nature", "natural", "park", "garden", "lake", "river", "waterfall", "forest", "mountain"},
    "food": {"food", "market", "cuisine", "restaurant", "tea", "spice", "cafe"},
    "gems": {"gem", "gems", "gemstone", "sapphire", "ruby", "museum", "mine", "mining"},
    "adventure": {"hiking", "trek", "trail", "climb", "safari", "surf", "diving", "adventure"},
    "relaxation": {"beach", "spa", "resort", "garden", "lake", "scenic", "view"},
}
INTEREST_SEARCH_TERMS = {
    "buddhism": ["Buddhist temple", "devalaya", "Saman Devalaya", "vihara"],
    "gems": ["gem museum", "gemstone", "sapphire"],
    "nature": ["park", "waterfall", "forest"],
}


class DestinationContext(BaseModel):
    """Resolved destination information used by the Researcher Agent."""

    destination: str
    display_name: str
    latitude: float
    longitude: float
    country: str


class AttractionResult(BaseModel):
    """Structured attraction data returned by the research tool."""

    name: str
    description: str
    estimated_time_hours: float = Field(gt=0)
    interest_match: str
    source: str
    distance_meters: int | None = None
    relevance_score: float = Field(default=0.0, ge=0)


def resolve_destination(destination: str, timeout: int = 15) -> DestinationContext:
    """Resolve a destination into coordinates and country data.

    Args:
        destination: User-requested destination.
        timeout: Maximum request timeout in seconds.

    Returns:
        Structured destination metadata from Nominatim.

    Raises:
        ValueError: If the destination is empty or no result is found.
        requests.RequestException: If the API request fails.
    """
    normalized_destination = destination.strip()
    if not normalized_destination:
        raise ValueError("Destination is required for research.")

    query = normalized_destination
    if "sri lanka" not in normalized_destination.lower():
        query = f"{normalized_destination}, Sri Lanka"

    response = requests.get(
        "https://nominatim.openstreetmap.org/search",
        params={
            "q": query,
            "format": "jsonv2",
            "limit": 1,
            "addressdetails": 1,
            "accept-language": "en",
            "countrycodes": SRI_LANKA_COUNTRY_CODE,
        },
        headers={"User-Agent": USER_AGENT},
        timeout=timeout,
    )
    response.raise_for_status()
    payload = response.json()
    if not payload:
        raise ValueError(f"Could not resolve destination '{normalized_destination}'.")

    first = payload[0]
    address = first.get("address", {})
    country = address.get("country", "Unknown")
    if country != "Sri Lanka":
        raise ValueError(f"Destination '{normalized_destination}' is outside Sri Lanka.")

    return DestinationContext(
        destination=normalized_destination,
        display_name=first["display_name"],
        latitude=float(first["lat"]),
        longitude=float(first["lon"]),
        country=country,
    )


def search_attractions(
    context: DestinationContext,
    interests: list[str],
    limit: int = 8,
    timeout: int = 15,
) -> list[AttractionResult]:
    """Find nearby attractions using Wikimedia geosearch and summaries.

    Args:
        context: Destination metadata from `resolve_destination`.
        interests: User interests used for simple attraction matching.
        limit: Maximum number of attractions to return.
        timeout: Maximum request timeout in seconds.

    Returns:
        A list of structured attraction recommendations.

    Raises:
        ValueError: If no attractions can be found.
        requests.RequestException: If the API request fails.
    """
    if limit <= 0:
        raise ValueError("Attraction search limit must be greater than zero.")

    recommendations_by_name: dict[str, AttractionResult] = {}
    for radius in (10000, 25000):
        radius_results = _search_attractions_with_radius(context, interests, limit, timeout, radius)
        for result in radius_results:
            recommendations_by_name.setdefault(result.name, result)
        recommendations = list(recommendations_by_name.values())
        if (
            len(recommendations_by_name) >= min(limit, 4)
            and _has_interest_coverage(recommendations, interests)
        ) or radius == 25000:
            break

    if len(recommendations_by_name) < limit or not _has_interest_coverage(list(recommendations_by_name.values()), interests):
        text_results = _search_attractions_by_text(context, interests, limit, timeout)
        for result in text_results:
            recommendations_by_name.setdefault(result.name, result)

    recommendations = list(recommendations_by_name.values())
    if not recommendations:
        raise ValueError(f"No attraction data found for '{context.destination}'.")

    recommendations.sort(key=lambda item: (-item.relevance_score, item.distance_meters or 999999, item.name))
    return _select_ranked_attractions(recommendations, interests, limit)


def _search_attractions_with_radius(
    context: DestinationContext,
    interests: list[str],
    limit: int,
    timeout: int,
    radius: int,
) -> list[AttractionResult]:
    """Find and score nearby attractions within a specific search radius."""
    response = requests.get(
        "https://en.wikipedia.org/w/api.php",
        params={
            "action": "query",
            "list": "geosearch",
            "gscoord": f"{context.latitude}|{context.longitude}",
            "gsradius": radius,
            "gslimit": max(limit * 4, 20),
            "format": "json",
        },
        headers={"User-Agent": USER_AGENT},
        timeout=timeout,
    )
    response.raise_for_status()
    places: list[dict[str, Any]] = response.json().get("query", {}).get("geosearch", [])

    recommendations: list[AttractionResult] = []
    for place in places:
        if len(recommendations) >= max(limit * 3, 12):
            break
        title = place.get("title", "")
        if title.casefold() == context.destination.casefold():
            continue
        if _is_excluded_place(title):
            continue
        summary = _fetch_summary(title, timeout)
        if not summary:
            continue
        if _is_excluded_summary(summary):
            continue
        interest_match = _pick_interest(title, summary, interests)
        distance = _safe_int(place.get("dist"))
        recommendations.append(
            AttractionResult(
                name=title,
                description=summary,
                estimated_time_hours=_estimate_visit_time(summary),
                interest_match=interest_match,
                source=f"https://en.wikipedia.org/wiki/{title.replace(' ', '_')}",
                distance_meters=distance,
                relevance_score=_calculate_relevance_score(title, summary, interest_match, interests, distance),
            )
        )

    return recommendations


def _search_attractions_by_text(
    context: DestinationContext,
    interests: list[str],
    limit: int,
    timeout: int,
) -> list[AttractionResult]:
    """Find destination-specific attractions that Wikipedia geosearch may miss."""
    recommendations: list[AttractionResult] = []
    seen_titles: set[str] = set()

    for query in _build_interest_search_queries(context.destination, interests):
        response = requests.get(
            "https://en.wikipedia.org/w/api.php",
            params={
                "action": "query",
                "list": "search",
                "srsearch": query,
                "srlimit": 5,
                "format": "json",
            },
            headers={"User-Agent": USER_AGENT},
            timeout=timeout,
        )
        response.raise_for_status()
        for item in response.json().get("query", {}).get("search", []):
            if len(recommendations) >= max(limit * 2, 8):
                return recommendations
            title = item.get("title", "")
            if not title or title in seen_titles:
                continue
            seen_titles.add(title)
            if title.casefold() == context.destination.casefold() or _is_excluded_place(title):
                continue
            summary = _fetch_summary(title, timeout)
            if not summary or _is_excluded_summary(summary):
                continue
            if not _is_destination_related(context, title, summary):
                continue
            interest_match = _pick_interest(title, summary, interests)
            recommendations.append(
                AttractionResult(
                    name=title,
                    description=summary,
                    estimated_time_hours=_estimate_visit_time(summary),
                    interest_match=interest_match,
                    source=f"https://en.wikipedia.org/wiki/{title.replace(' ', '_')}",
                    relevance_score=_calculate_relevance_score(title, summary, interest_match, interests, None),
                )
            )

    return recommendations


def _fetch_summary(title: str, timeout: int) -> str:
    """Fetch a short summary for a Wikipedia page title."""
    response = requests.get(
        f"https://en.wikipedia.org/api/rest_v1/page/summary/{quote(title, safe='')}",
        headers={"User-Agent": USER_AGENT},
        timeout=timeout,
    )
    if response.status_code != 200:
        return ""
    return str(response.json().get("extract", "")).strip()


def _pick_interest(title: str, summary: str, interests: list[str]) -> str:
    """Pick the best matching user interest using title and summary keywords."""
    lowered = f"{title} {summary}".lower()
    for interest in interests:
        normalized_interest = interest.lower()
        keywords = INTEREST_KEYWORDS.get(normalized_interest, {normalized_interest})
        if normalized_interest in lowered or any(keyword in lowered for keyword in keywords):
            return interest
    return interests[0] if interests else "general sightseeing"


def _estimate_visit_time(summary: str) -> float:
    """Estimate attraction visit time using simple category heuristics."""
    lowered = summary.lower()
    if "museum" in lowered or "park" in lowered or "temple" in lowered or "palace" in lowered:
        return 2.5
    if "tower" in lowered or "market" in lowered or "viewpoint" in lowered:
        return 1.5
    return 2.0


def _is_excluded_place(text: str) -> bool:
    """Return True for generic infrastructure or low-value tourism results."""
    lowered = text.lower()
    return any(keyword in lowered for keyword in EXCLUDED_KEYWORDS)


def _is_excluded_summary(text: str) -> bool:
    """Use a safer summary filter so valid attractions are not removed by context words."""
    lowered = text.lower()
    return any(keyword in lowered for keyword in SUMMARY_EXCLUDED_KEYWORDS)


def _is_destination_related(context: DestinationContext, title: str, summary: str) -> bool:
    """Keep text-search results tied to the requested destination."""
    haystack = f"{title} {summary}".lower()
    destination_terms = {
        context.destination.lower(),
        *[part.strip().lower() for part in context.display_name.split(",") if part.strip()],
    }
    broad_terms = {context.country.lower(), "sri lanka"}
    return any(term in haystack for term in destination_terms if len(term) >= 4 and term not in broad_terms)


def _calculate_relevance_score(
    title: str,
    summary: str,
    interest_match: str,
    interests: list[str],
    distance_meters: int | None,
) -> float:
    """Score attractions so stronger, closer, interest-aligned places rank first."""
    lowered = f"{title} {summary}".lower()
    score = 1.0

    if interest_match in interests:
        score += 2.0

    if len(summary) >= 120:
        score += 1.0

    tourism_keywords = {
        "temple",
        "museum",
        "park",
        "fort",
        "palace",
        "garden",
        "beach",
        "lake",
        "waterfall",
        "market",
        "historic",
        "ancient",
        "devalaya",
        "vihara",
        "shrine",
        "falls",
        "gem",
        "sapphire",
    }
    score += sum(0.3 for keyword in tourism_keywords if keyword in lowered)
    landmark_keywords = {"devalaya", "vihara", "museum", "falls", "waterfall", "temple", "fort", "palace"}
    if any(keyword in lowered for keyword in landmark_keywords):
        score += 1.0

    if distance_meters is not None:
        if distance_meters <= 3000:
            score += 1.0
        elif distance_meters <= 10000:
            score += 0.5

    return round(score, 2)


def _safe_int(value: Any) -> int | None:
    """Convert optional API distance values without failing the whole search."""
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _has_interest_coverage(attractions: list[AttractionResult], interests: list[str]) -> bool:
    """Return True when enough requested interests are represented in results."""
    if not interests:
        return True
    matched = {item.interest_match.lower() for item in attractions}
    requested = {interest.lower() for interest in interests}
    return bool(matched & requested) and (len(requested) == 1 or len(matched & requested) >= 2)


def _build_interest_search_queries(destination: str, interests: list[str]) -> list[str]:
    """Build focused Wikipedia search queries from destination and requested interests."""
    queries: list[str] = []
    for interest in interests:
        terms = INTEREST_SEARCH_TERMS.get(interest.lower(), [interest])
        for term in terms:
            queries.append(f"{destination} {term} Sri Lanka")
    queries.append(f"{destination} attractions Sri Lanka")
    return queries


def _select_ranked_attractions(
    attractions: list[AttractionResult],
    interests: list[str],
    limit: int,
) -> list[AttractionResult]:
    """Preserve ranking while representing multiple requested interests when possible."""
    selected: list[AttractionResult] = []
    selected_names: set[str] = set()
    selected_types: set[str] = set()

    for interest in interests:
        match = next(
            (item for item in attractions if item.interest_match.lower() == interest.lower() and item.name not in selected_names),
            None,
        )
        if match:
            selected.append(match)
            selected_names.add(match.name)
            selected_types.add(_classify_attraction_type(match))

    for attraction in attractions:
        if len(selected) >= limit:
            break
        attraction_type = _classify_attraction_type(attraction)
        if attraction.name not in selected_names and attraction_type not in selected_types:
            selected.append(attraction)
            selected_names.add(attraction.name)
            selected_types.add(attraction_type)

    for attraction in attractions:
        if len(selected) >= limit:
            break
        if attraction.name not in selected_names:
            selected.append(attraction)
            selected_names.add(attraction.name)

    selected.sort(key=lambda item: (-item.relevance_score, item.distance_meters or 999999, item.name))
    return selected[:limit]


def _classify_attraction_type(attraction: AttractionResult) -> str:
    """Classify broad attraction type to avoid repetitive recommendations."""
    lowered = f"{attraction.name} {attraction.description}".lower()
    for keyword in ("devalaya", "vihara", "temple", "museum", "falls", "waterfall", "park", "fort", "palace"):
        if keyword in lowered:
            return keyword
    return attraction.interest_match.lower()
