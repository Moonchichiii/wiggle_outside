"""Fixture view models for the form page states (DESIGN-SPEC section 12).

CONTRACTS section 8 says the shared fixtures live in `tests/fixtures/`; WP0 has not
created them yet, so WP8 keeps its own here and will move to the shared ones when they
land. The data is the WALKTHROUGH.md journey: Bergby, Uppsala lan, Sweden.
"""

from dataclasses import replace
from datetime import UTC, datetime
from typing import Final

from wiggle_outside.core.errors import ErrorCode, NoticeId
from wiggle_outside.core.types import (
    Activity,
    AgeBand,
    Answers,
    AnswersSummary,
    Coordinates,
    Energy,
    Hook,
    Idea,
    InterestOutcome,
    Interests,
    InterestTag,
    JobState,
    LocationCandidate,
    LocationCandidates,
    Pair,
    Place,
    PlanResult,
    Reason,
    Season,
    Source,
    TimeBudget,
    TypedPlace,
    WeatherCondition,
    WeatherSummary,
    Who,
)
from wiggle_outside.web.views import AssetRef, SessionView

SESSION: Final = SessionView(
    csrf_token="csrf-fixture-token",  # noqa: S106 - a fixture token, not a credential.
    idempotency_key="idem-fixture-key",
)

# d39_enabled is a positional flag in the CONTRACTS section 8 signature; naming the two
# values keeps the calls readable.
D39_ON: Final = True
D39_OFF: Final = False

BERGBY: Final = Coordinates(lat=60.42, lon=17.31)

CARRIED_ANSWERS: Final = AnswersSummary(
    who=Who.KIDS,
    age_bands=frozenset({AgeBand.B3_5, AgeBand.B6_9}),
    time_budget=TimeBudget.H1,
    energy=Energy.MODERATE,
    location=BERGBY,
    location_label="Bergby, Uppsala lan, Sweden",
    stroller=False,
    step_free=True,
)

# The approved error mock: ages missing and no location given.
FORM_ERRORS: Final[dict[str, ErrorCode]] = {
    "age_band": ErrorCode.INPUT_INVALID,
    "place": ErrorCode.INPUT_INVALID,
}

_AMBIGUOUS_ANSWERS: Final = Answers(
    who=Who.KIDS,
    age_bands=frozenset({AgeBand.B3_5, AgeBand.B6_9}),
    time_budget=TimeBudget.H1,
    energy=Energy.MODERATE,
    location=TypedPlace(text="Bergby"),
    stroller=False,
    step_free=False,
)

CANDIDATES: Final = LocationCandidates(
    candidates=(
        LocationCandidate(
            candidate_id="c1",
            label="Bergby, Gavleborg, Sweden",
            coords=Coordinates(lat=60.72, lon=17.08),
        ),
        LocationCandidate(
            candidate_id="c2",
            label="Bergby, Uppsala lan, Sweden",
            coords=BERGBY,
        ),
        LocationCandidate(
            candidate_id="c3",
            label="Bergby, Aland, Finland",
            coords=Coordinates(lat=60.18, lon=20.37),
        ),
    ),
    answers=_AMBIGUOUS_ANSWERS,
    expires_at=datetime(2026, 10, 10, 10, 41, tzinfo=UTC),
)

# A stand-in build manifest: the real one arrives with the Bun build (WP9b).
STYLESHEET: Final[dict[str, AssetRef]] = {"app.css": AssetRef(url="/static/app.css", integrity="")}


# --- The catalogue (WALKTHROUGH.md; text copied from docs/drafts) ---------------------
#
# Three real entries, copied verbatim from docs/drafts/activities.toml and hooks.toml, so
# the tests prove the actual reviewed text renders (PLAN section 3: no model-written text
# is displayed). The catalogue loader is WP2's; this is the port, not the loader.

LEAF_COLOUR_HUNT: Final = Activity(
    activity_id="leaf-colour-hunt",
    title="Leaf colour hunt",
    who=Who.KIDS,
    ages=frozenset({AgeBand.B3_5, AgeBand.B6_9}),
    energy=frozenset({Energy.GENTLE, Energy.MODERATE}),
    place_kinds=frozenset({"park", "forest", "nature_reserve"}),
    generic_ok=False,
    interests=(InterestTag.COLOURS, InterestTag.TREES),
    minutes_min=20,
    minutes_max=45,
    rain_ok=True,
    max_rain_pct=70,
    min_temp_c=0,
    max_wind_kmh=30,
    max_temp_c=None,
    daylight_only=True,
    activity_suits_stroller=True,
    seasons=frozenset({Season.AUTUMN}),
    optional=("a small bag for fallen leaves (or just make the row on the ground)",),
    steps=(
        "Pick three colours together before you start: red, yellow, brown.",
        "Look for one fallen leaf of each colour.",
        "Lay them in a row from lightest to darkest.",
        "Leave them in a little pattern on the ground before you go home.",
    ),
    adapt="Compare leaves by feel instead: smooth, crinkly, soft.",
    ask="Which colour was the hardest to find, and why do you think that is?",
    safety="Fallen leaves only. Wash hands before snacks.",
    card=(),
)

NATURE_BINGO: Final = Activity(
    activity_id="nature-bingo",
    title="Nature bingo",
    who=Who.KIDS,
    ages=frozenset(AgeBand),
    energy=frozenset({Energy.GENTLE, Energy.MODERATE}),
    place_kinds=frozenset({"park", "forest", "nature_reserve", "picnic_site"}),
    generic_ok=False,
    interests=(InterestTag.ANIMALS, InterestTag.BIRDS, InterestTag.TREES),
    minutes_min=20,
    minutes_max=60,
    rain_ok=True,
    max_rain_pct=60,
    min_temp_c=5,
    max_wind_kmh=30,
    max_temp_c=None,
    daylight_only=True,
    activity_suits_stroller=True,
    seasons=frozenset(),
    optional=("the printed card (or read the list from the screen once before you go)",),
    steps=(
        "Look at the nine things on the card together.",
        "Tick each one when someone spots it.",
        "Three in a row wins. A full card wins everything.",
    ),
    adapt="Swap any item for one you can hear or touch, such as birdsong or rough bark.",
    ask="What did you spot that wasn't on the card?",
    safety="Look and point, no need to touch or pick anything.",
    card=(
        "a bird",
        "a fallen feather",
        "something round",
        "a spiky leaf",
        "moss",
        "a dog on a walk",
        "a cloud shaped like an animal",
        "a bench",
        "something red",
    ),
)

PUDDLE_JUMPING: Final = Activity(
    activity_id="puddle-jumping",
    title="Puddle jumping championship",
    who=Who.KIDS,
    ages=frozenset({AgeBand.B3_5, AgeBand.B6_9}),
    energy=frozenset({Energy.MODERATE, Energy.ENERGETIC}),
    place_kinds=frozenset({"park", "playground"}),
    generic_ok=False,
    interests=(InterestTag.PUDDLES, InterestTag.RUNNING),
    minutes_min=15,
    minutes_max=40,
    rain_ok=True,
    max_rain_pct=100,
    min_temp_c=4,
    max_wind_kmh=45,
    max_temp_c=None,
    daylight_only=True,
    activity_suits_stroller=False,
    seasons=frozenset(),
    optional=(
        "wellies (or shoes that may get wet)",
        "a towel for the way home (or head straight home to change)",
    ),
    steps=(
        "Find three puddles on the path.",
        "Judge each jump: biggest splash, quietest landing, silliest jump.",
        "Award points and crown a champion.",
    ),
    adapt="Judge splashes by sound or by stepping instead of jumping.",
    ask="Which puddle was the deepest, and how could you tell before jumping?",
    safety="Small, shallow puddles on paths only. Never near roads, ponds or streams.",
    card=(),
)

ACTIVITIES: Final[tuple[Activity, ...]] = (LEAF_COLOUR_HUNT, NATURE_BINGO, PUDDLE_JUMPING)

HOOKS: Final[tuple[Hook, ...]] = (
    Hook(
        hook_id="pocket-adventure",
        text="A pocket-sized adventure for right now.",
        for_who=frozenset({Who.KIDS}),
        needs_destination=True,
    ),
    Hook(
        hook_id="todays-idea",
        text="Here's today's idea for getting outside.",
        for_who=frozenset({Who.KIDS, Who.SOLO}),
        needs_destination=True,
    ),
    Hook(
        hook_id="explorer-club",
        text="The explorer club meets here today.",
        for_who=frozenset({Who.KIDS}),
        needs_destination=True,
    ),
    Hook(
        hook_id="no-destination",
        text="No particular place needed: start on the paths near you.",
        for_who=frozenset({Who.KIDS, Who.SOLO}),
        generic_only=True,
    ),
)

REASONS: Final[tuple[Reason, ...]] = (
    Reason(
        reason_id="close_by",
        when="straight-line distance is 1 km or less",
        text="It's close by.",
    ),
    Reason(
        reason_id="fits_time",
        when=(
            "estimated travel there and back plus the activity's minimum minutes fit the "
            "time budget"
        ),
        text="Estimated to fit your time, including travel.",
    ),
    Reason(
        reason_id="matches_energy",
        when="the activity lists the energy level that was asked for",
        text="It matches the energy you asked for.",
    ),
    Reason(
        reason_id="all_ages",
        when="two or more age bands were selected and the activity lists all of them",
        text="The activity list includes all your selected age groups.",
    ),
    Reason(
        reason_id="in_season",
        when="the activity lists the current season",
        text="It's the right season for it.",
    ),
)


class FakeCatalogue:
    """The CONTRACTS section 4 `Catalogue` port over the fixture entries above."""

    def activities(self) -> tuple[Activity, ...]:
        return ACTIVITIES

    def hooks(self) -> tuple[Hook, ...]:
        return HOOKS

    def reasons(self) -> tuple[Reason, ...]:
        return REASONS


CATALOGUE: Final = FakeCatalogue()


# --- Places, weather and times (WALKTHROUGH.md fixture data) -------------------------
#
# Local times are Europe/Stockholm (UTC+2) on Sat 10 Oct 2026: the outing runs 10:31-11:31
# local, which is 08:31-09:31 UTC, and the forecast was received at 10:31 local.

PLANNED_START: Final = datetime(2026, 10, 10, 8, 31, tzinfo=UTC)
PLANNED_END: Final = datetime(2026, 10, 10, 9, 31, tzinfo=UTC)
FETCHED_AT: Final = datetime(2026, 10, 10, 8, 31, 1, tzinfo=UTC)
VALID_UNTIL: Final = datetime(2026, 10, 10, 8, 36, 6, tzinfo=UTC)
RETAIN_UNTIL: Final = datetime(2026, 10, 10, 9, 36, 6, tzinfo=UTC)
# Before and after `valid_until`, for the current and the historical view.
NOW: Final = datetime(2026, 10, 10, 8, 31, 6, tzinfo=UTC)
LATER: Final = datetime(2026, 10, 10, 8, 36, 30, tzinfo=UTC)

LINDEN_PARK: Final = Place(
    place_id="linden",
    name="Linden Park",
    kind="park",
    coords=Coordinates(lat=60.42, lon=17.32),
    fee="unknown",
    osm_access="unknown",
)
BIRCHWOOD: Final = Place(
    place_id="birchwood",
    name="Birchwood Nature Area",
    kind="nature_reserve",
    coords=Coordinates(lat=60.43, lon=17.31),
    fee="no",
    osm_access="unknown",
)
OAK_LANE: Final = Place(
    place_id="oak-lane",
    name="Oak Lane Park",
    kind="park",
    coords=Coordinates(lat=60.42, lon=17.30),
    fee="unknown",
    osm_access="yes",
)
# WALKTHROUGH step 11: "Elm & Oak Playground" must reach the HTML escaped exactly once.
ELM_AND_OAK: Final = Place(
    place_id="elm-oak",
    name="Elm & Oak Playground",
    kind="playground",
    coords=Coordinates(lat=60.42, lon=17.31),
    fee="unknown",
    osm_access="limited",
)

WEATHER: Final = WeatherSummary(
    fetched_at=FETCHED_AT,
    tz="Europe/Stockholm",
    window_start=PLANNED_START,
    window_end=PLANNED_END,
    condition=WeatherCondition.SHOWERS_POSSIBLE,
    temp_min_c=11,
    temp_max_c=12,
    max_precip_probability=40,
    max_wind_kmh=18,
)


def _pair(pair_id: str, activity_id: str, place: Place | None, metres: int | None) -> Pair:
    """Build a pair with the BACKEND-CONTRACT section 8 times for a 1-hour kids' outing."""
    travel = {None: 0, 600: 24, 900: 36, 400: 16, 500: 20}[metres]
    return Pair(
        pair_id=pair_id,
        idea_id=f"i{pair_id[1:]}",
        activity_id=activity_id,
        place=place,
        distance_m=metres,
        travel_min=travel,
        duration_min=60 - travel,
        allowed_hook_ids=frozenset({"pocket-adventure", "todays-idea", "explorer-club"}),
        allowed_reason_ids=frozenset({"close_by", "all_ages", "fits_time", "matches_energy"}),
    )


IDEA_PUDDLES: Final = Idea(
    pair=_pair("p1", "puddle-jumping", LINDEN_PARK, 600),
    hook_id="pocket-adventure",
    reason_ids=("close_by", "all_ages"),
)
IDEA_BINGO: Final = Idea(
    pair=_pair("p4", "nature-bingo", BIRCHWOOD, 900),
    hook_id="explorer-club",
    reason_ids=("fits_time", "matches_energy"),
)
IDEA_LEAVES: Final = Idea(
    pair=_pair("p7", "leaf-colour-hunt", OAK_LANE, 400),
    hook_id="todays-idea",
    reason_ids=("in_season", "close_by"),
)
# The two states the card line has to cope with besides a named place: an ampersand in an
# OSM name, and a generic pair with no destination and no distance at all.
IDEA_AMPERSAND: Final = Idea(
    pair=_pair("p5", "leaf-colour-hunt", ELM_AND_OAK, 500),
    hook_id="todays-idea",
    reason_ids=("close_by",),
)
IDEA_GENERIC: Final = Idea(
    pair=_pair("p9", "nature-bingo", None, None),
    hook_id="no-destination",
    reason_ids=(),
)

MATCHED_INTERESTS: Final = Interests(
    tags=(InterestTag.BIRDS, InterestTag.PUDDLES), outcome=InterestOutcome.MATCHED
)


# --- Results (DESIGN-SPEC section 12 states) -----------------------------------------

RESULT: Final = PlanResult(
    job_id="J2",
    state=JobState.COMPLETE,
    source=Source.MODEL,
    ideas=(IDEA_PUDDLES, IDEA_BINGO, IDEA_LEAVES),
    notices=(),
    interests=MATCHED_INTERESTS,
    answers=CARRIED_ANSWERS,
    weather=WEATHER,
    planned_start=PLANNED_START,
    planned_end=PLANNED_END,
    valid_until=VALID_UNTIL,
    retain_until=RETAIN_UNTIL,
    error=None,
)

RESULT_TWO: Final = replace(
    RESULT, ideas=(IDEA_PUDDLES, IDEA_BINGO), notices=(ErrorCode.FEWER_MATCHES,)
)
RESULT_ONE: Final = replace(RESULT, ideas=(IDEA_PUDDLES,), notices=(ErrorCode.FEWER_MATCHES,))
RESULT_NONE: Final = replace(
    RESULT, ideas=(), notices=(), interests=None, error=ErrorCode.NO_MATCHES
)

# The labelled fallback (DESIGN-SPEC section 7, PRODUCT-FIT 3.4): catalogue picks after
# every normal check, with the interests still used for the ranking.
RESULT_FALLBACK: Final = replace(
    RESULT,
    state=JobState.FALLBACK,
    source=Source.FALLBACK,
    notices=(ErrorCode.MODEL_FALLBACK, NoticeId.INTERESTS_USED_BY_FALLBACK),
)
RESULT_GENTLER: Final = replace(RESULT, notices=(NoticeId.GENTLER_THAN_ASKED,))
RESULT_GENERIC: Final = replace(RESULT, ideas=(IDEA_GENERIC,), interests=None)
# WALKTHROUGH step 11 and BACKEND-CONTRACT section 7: provider text with an ampersand and
# angle brackets, in both an OSM place name and the carried location label, so the
# escaped-exactly-once rule is checked where the strings are actually assembled.
HOSTILE_ANSWERS: Final = replace(CARRIED_ANSWERS, location_label="Oak & Elm <b>")
RESULT_AMPERSAND: Final = replace(RESULT, ideas=(IDEA_AMPERSAND,), answers=HOSTILE_ANSWERS)

# D39 outcomes (PRODUCT-FIT 3.4): labels only when the interpretation was valid.
RESULT_NO_MATCH: Final = replace(
    RESULT,
    interests=Interests(tags=(), outcome=InterestOutcome.NO_MATCH),
    notices=(NoticeId.INTEREST_NO_MATCH,),
)
RESULT_UNCLEAR: Final = replace(
    RESULT,
    interests=Interests(tags=(), outcome=InterestOutcome.UNCLEAR),
    notices=(NoticeId.INTEREST_UNCLEAR,),
)
RESULT_NOT_APPLIED: Final = replace(
    RESULT,
    interests=Interests(tags=(), outcome=InterestOutcome.NOT_APPLIED),
    notices=(NoticeId.INTEREST_NOT_APPLIED,),
)

# The family daylight path (BACKEND-CONTRACT section 1, TC-002): evaluated, no model call,
# no cards, no weather promise, answers summary and "Change answers" kept.
RESULT_NIGHT: Final = replace(
    RESULT, ideas=(), notices=(), interests=None, error=ErrorCode.DAYLIGHT_NIGHT
)
RESULT_TOO_SHORT: Final = replace(
    RESULT, ideas=(), notices=(), interests=None, error=ErrorCode.DAYLIGHT_TOO_SHORT
)

# Weather unavailable: no weather summary at all, so no card of any kind (D16).
RESULT_NO_WEATHER: Final = replace(
    RESULT,
    state=JobState.UNAVAILABLE,
    ideas=(),
    notices=(),
    interests=None,
    weather=None,
    error=ErrorCode.WEATHER_UNAVAILABLE,
)
