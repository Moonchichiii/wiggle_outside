"""Build the one model request a run sends (CONTRACTS section 6).

Only the planner builds it. The user message carries three delimited data blocks: the
eligible pairs as a JSON list, the D39 tag vocabulary, and the family text. The pairs
block holds pair and activity IDs, the activity title, the place *kind* (our vocabulary,
or `none`), a distance band, the activity's energy levels and interests, and the hook
and reason IDs the pair allows. Place names, coordinates, OSM free text, the typed town,
session or network data are never part of it; the test suite asserts that on the
serialised request.

Everything is internal enum values, never display labels (TC-001): energy reaches the
model as `energetic`, not "High".
"""

import json
from typing import TYPE_CHECKING, Final

from wiggle_outside.core.types import InterestTag
from wiggle_outside.planner.ports import ModelRequest

if TYPE_CHECKING:
    from wiggle_outside.core.types import Activity, Pair
    from wiggle_outside.planner.ports import Catalogue

PROMPT_V1: Final = "select.v1"
PROMPT_V2: Final = "select.v2"
SCHEMA_V1: Final = "selection.v1"
SCHEMA_V2: Final = "selection.v2"

GENERIC_PLACE: Final = "none"
# Straight-line distance bands: coarse on purpose, so no coordinate can be inferred.
BAND_LIMITS_M: Final[tuple[tuple[int, str], ...]] = (
    (500, "under_500m"),
    (1000, "500m_to_1km"),
    (2000, "1km_to_2km"),
)
BAND_FAR: Final = "over_2km"
BAND_NONE: Final = "none"

# The family text is a single printable line of at most 120 characters (web/forms). The
# angle brackets are dropped so the text can never close or open a data block.
BLOCK_BREAKERS: Final = str.maketrans("", "", "<>")


def build_request(
    pairs: tuple[Pair, ...],
    catalogue: Catalogue,
    family_text: str | None,
    *,
    d39_enabled: bool,
) -> ModelRequest:
    """Build the request for these pairs; v2 with interests when D39 is on, else v1."""
    by_id = {activity.activity_id: activity for activity in catalogue.activities()}
    entries = [_entry(pair, by_id[pair.activity_id]) for pair in pairs]
    text = (family_text or "").translate(BLOCK_BREAKERS).strip() if d39_enabled else ""
    return ModelRequest(
        prompt_version=PROMPT_V2 if d39_enabled else PROMPT_V1,
        schema_version=SCHEMA_V2 if d39_enabled else SCHEMA_V1,
        pairs_block=json.dumps(entries, separators=(",", ":"), ensure_ascii=False),
        vocabulary_block=", ".join(tag.value for tag in InterestTag) if d39_enabled else "",
        family_text_block=text,
    )


def user_message(request: ModelRequest) -> str:
    """Lay the three blocks out as the user message the adapter sends."""
    return (
        f"<pairs>\n{request.pairs_block}\n</pairs>\n"
        f"<vocabulary>\n{request.vocabulary_block}\n</vocabulary>\n"
        f"<family_text>\n{request.family_text_block}\n</family_text>"
    )


def distance_band(distance_m: int | None) -> str:
    if distance_m is None:
        return BAND_NONE
    for limit, band in BAND_LIMITS_M:
        if distance_m <= limit:
            return band
    return BAND_FAR


def _entry(pair: Pair, activity: Activity) -> dict[str, object]:
    return {
        "pair_id": pair.pair_id,
        "activity_id": pair.activity_id,
        "title": activity.title,
        "place_kind": pair.place.kind if pair.place is not None else GENERIC_PLACE,
        "distance_band": distance_band(pair.distance_m),
        "energy": sorted(level.value for level in activity.energy),
        "interests": [tag.value for tag in activity.interests],
        "allowed_hook_ids": sorted(pair.allowed_hook_ids),
        "allowed_reason_ids": sorted(pair.allowed_reason_ids),
    }
