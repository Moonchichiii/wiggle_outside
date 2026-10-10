"""Shared domain values (CONTRACTS section 2).

Frozen dataclasses whose nested values are immutable too (D17). No I/O, no framework.
"""

import json
import math
from dataclasses import dataclass, field
from datetime import datetime
from enum import IntEnum, StrEnum
from typing import Final, Literal, Self

from wiggle_outside.core.errors import ErrorCode, NoticeId

LAT_MIN: Final = -90.0
LAT_MAX: Final = 90.0
LON_MIN: Final = -180.0
LON_MAX: Final = 180.0
COORD_DP: Final = 2
PLACE_TEXT_MIN: Final = 2
PLACE_TEXT_MAX: Final = 80
INTEREST_TEXT_MAX: Final = 120
MAX_IDEAS: Final = 3
MAX_TAGS: Final = 3
MAX_REASONS: Final = 2
MAX_CANDIDATES: Final = 5
MAX_PAIRS: Final = 12
MAX_PLACES: Final = 8
CARD_ITEMS: Final = 9


class Who(StrEnum):
    SOLO = "solo"
    KIDS = "kids"


class AgeBand(StrEnum):
    B0_2 = "0-2"
    B3_5 = "3-5"
    B6_9 = "6-9"
    B10_12 = "10-12"


class TimeBudget(IntEnum):
    M30 = 30
    H1 = 60
    H2 = 120
    HALF_DAY = 240  # D35: half a day means 4 hours.


class Energy(StrEnum):
    # Display labels: Gentle / Moderate / High (DESIGN-SPEC section 9, TC-001).
    # ENERGETIC is never shown to a user; "High" is never a stored value.
    GENTLE = "gentle"
    MODERATE = "moderate"
    ENERGETIC = "energetic"


class InterestTag(StrEnum):
    """The 14-tag vocabulary (PRODUCT-FIT section 3.2, D39). Order is the schema's."""

    ANIMALS = "animals"
    BIRDS = "birds"
    BUGS = "bugs"
    TREES = "trees"
    COLOURS = "colours"
    SHAPES = "shapes"
    STORIES = "stories"
    RUNNING = "running"
    BUILDING = "building"
    SOUNDS = "sounds"
    DRAWING = "drawing"
    SKY = "sky"
    QUIET = "quiet"
    PUDDLES = "puddles"


class InterestStatus(StrEnum):
    """What the model may report (model-facing)."""

    MATCHED = "matched"
    NO_MATCH = "no_match"
    UNCLEAR = "unclear"
    NOT_PROVIDED = "not_provided"


class InterestOutcome(StrEnum):
    """What code concludes. NOT_APPLIED = interpretation failed (PRODUCT-FIT 3.4)."""

    MATCHED = "matched"
    NO_MATCH = "no_match"
    UNCLEAR = "unclear"
    NOT_PROVIDED = "not_provided"
    NOT_APPLIED = "not_applied"


class Source(StrEnum):
    MODEL = "model"
    FALLBACK = "fallback"
    REPLAY = "replay"  # inactive (D24 superseded by D48); kept so the enum is stable.


class JobState(StrEnum):
    """One value per state in the ARCHITECTURE section 4 diagram."""

    RUNNING = "running"
    NEEDS_LOCATION_CHOICE = "needs_location_choice"
    WAITING = "waiting"
    GENERATING = "generating"
    CANCELLING = "cancelling"  # internal cleanup at deadline or shutdown only (D43).
    COMPLETE = "complete"
    FALLBACK = "fallback"
    UNAVAILABLE = "unavailable"
    FAILED = "failed"
    EXPIRED = "expired"


class Season(StrEnum):
    """Meteorological seasons from the date and hemisphere (D30).

    Equatorial locations (|lat| < 23.44 degrees) get no season-restricted activities, so
    an entry whose `seasons` is empty runs all year.
    """

    SPRING = "spring"
    SUMMER = "summer"
    AUTUMN = "autumn"
    WINTER = "winter"


class WeatherCondition(StrEnum):
    CLEAR = "clear"
    CLOUDY = "cloudy"
    SHOWERS_POSSIBLE = "showers_possible"
    RAIN_LIKELY = "rain_likely"
    FOG = "fog"
    SNOW = "snow"


class DeploymentMode(StrEnum):
    HOSTED_LIVE = "hosted_live"  # the product and primary build path (D48).
    LOCAL = "local"  # optional development.
    REPLAY = "replay"  # inactive (D24 superseded by D48).


@dataclass(frozen=True, slots=True)
class Coordinates:
    lat: float
    lon: float

    def __post_init__(self) -> None:
        for name, value, low, high in (
            ("lat", self.lat, LAT_MIN, LAT_MAX),
            ("lon", self.lon, LON_MIN, LON_MAX),
        ):
            if not math.isfinite(value):
                msg = f"{name} must be finite"
                raise ValueError(msg)
            if not low <= value <= high:
                msg = f"{name} out of range: {value}"
                raise ValueError(msg)
        object.__setattr__(self, "lat", round(self.lat, COORD_DP))
        object.__setattr__(self, "lon", round(self.lon, COORD_DP))


@dataclass(frozen=True, slots=True)
class TypedPlace:
    text: str

    def __post_init__(self) -> None:
        if not PLACE_TEXT_MIN <= len(self.text) <= PLACE_TEXT_MAX:
            msg = f"place text must be {PLACE_TEXT_MIN}-{PLACE_TEXT_MAX} characters"
            raise ValueError(msg)
        if not self.text.isprintable():
            msg = "place text must be printable"
            raise ValueError(msg)


type Location = Coordinates | TypedPlace


@dataclass(frozen=True, slots=True)
class Answers:
    who: Who
    age_bands: frozenset[AgeBand]  # empty if and only if solo
    time_budget: TimeBudget
    energy: Energy
    location: Location
    stroller: bool
    step_free: bool  # D42 P: a preference, never a filter
    # D39: memory only. Excluded from repr, hashing and comparison so it cannot leak.
    interest_text: str | None = field(default=None, repr=False, hash=False, compare=False)


@dataclass(frozen=True, slots=True)
class AnswersSummary:
    """Answers minus the free text, plus the label, kept with the result."""

    who: Who
    age_bands: frozenset[AgeBand]
    time_budget: TimeBudget
    energy: Energy
    location: Coordinates
    location_label: str  # geocode label, or "Your location" for device coordinates
    stroller: bool
    step_free: bool


@dataclass(frozen=True, slots=True)
class Activity:
    """A catalogue entry. One field per key in planner/activities.toml (CC-002).

    Text fields are rendered verbatim: no model text ever reaches a card.
    A contract test compares these field names with the real TOML, so the two cannot
    drift again.
    """

    activity_id: str  # TOML: id
    title: str
    who: Who
    ages: frozenset[AgeBand]
    energy: frozenset[Energy]
    place_kinds: frozenset[str]  # TOML: places
    generic_ok: bool
    interests: tuple[InterestTag, ...]  # 1-3 per entry
    # TOML: minutes = [min, max], on site, travel excluded.
    minutes_min: int
    minutes_max: int
    rain_ok: bool
    max_rain_pct: int
    min_temp_c: int
    max_wind_kmh: int
    max_temp_c: int | None  # optional; only when lower than the global heat rule
    daylight_only: bool  # TOML: daylight
    activity_suits_stroller: bool  # the activity only, never the route or place access
    seasons: frozenset[Season]  # empty = all year (D30)
    optional: tuple[str, ...]
    steps: tuple[str, ...]
    adapt: str  # alternatives for sight, hearing or mobility
    ask: str | None  # kids only
    safety: str
    card: tuple[str, ...]  # empty, or exactly CARD_ITEMS for a bingo-style card


@dataclass(frozen=True, slots=True)
class Hook:
    """One fixed, reviewed sentence. No placeholders (8.12); one field per TOML key.

    The three flags decide which pairs may offer it, so code can derive each pair's
    `allowed_hook_ids` without the model seeing the rule (CC-003).
    """

    hook_id: str  # TOML: id
    text: str
    for_who: frozenset[Who]  # TOML: for
    needs_destination: bool = False  # the sentence assumes a destination
    generic_only: bool = False  # only for generic pairs with no destination
    max_energy: Energy | None = None  # only when the activity's top level is at or below


@dataclass(frozen=True, slots=True)
class Reason:
    reason_id: str
    when: str
    text: str


@dataclass(frozen=True, slots=True)
class DerivedReason:
    """A reason code decides, never the model."""

    reason_id: str
    text: str


@dataclass(frozen=True, slots=True)
class Place:
    place_id: str  # opaque, internal
    name: str  # <= 60, plain text, escaped once at render
    kind: str
    coords: Coordinates
    fee: Literal["no", "yes", "unknown"]
    # OSM wheelchair tag: reported, never verified.
    osm_access: Literal["yes", "limited", "no", "unknown"]

    def to_cache(self) -> bytes:
        # Annotated locally: core forbids Any-typed expressions, and json.dumps takes Any.
        payload: dict[str, str | float] = {
            "place_id": self.place_id,
            "name": self.name,
            "kind": self.kind,
            "lat": self.coords.lat,
            "lon": self.coords.lon,
            "fee": self.fee,
            "osm_access": self.osm_access,
        }
        return json.dumps(payload, separators=(",", ":"), sort_keys=True).encode()

    @classmethod
    def from_cache(cls, payload: bytes) -> Self:
        raise NotImplementedError


@dataclass(frozen=True, slots=True)
class GeocodeHit:
    label: str
    coords: Coordinates


@dataclass(frozen=True, slots=True)
class GeocodeHits:
    hits: tuple[GeocodeHit, ...]  # at most MAX_CANDIDATES

    def to_cache(self) -> bytes:
        raise NotImplementedError

    @classmethod
    def from_cache(cls, payload: bytes) -> Self:
        raise NotImplementedError


@dataclass(frozen=True, slots=True)
class WeatherWindow:
    """Hourly arrays as received (BACKEND-CONTRACT 1). Input to core.weather."""

    start: datetime
    end: datetime
    fetched_at: datetime
    tz: str  # IANA name from the provider
    times: tuple[datetime, ...]
    temp_c: tuple[float, ...]
    apparent_temp_c: tuple[float, ...]
    precip_probability: tuple[int, ...]
    # Millimetres, the preceding-hour sum. BACKEND-CONTRACT section 1 requests
    # `precipitation` and two rules need it: `rain_ok = false` requires 0 mm, and the
    # `dry_window` reason requires 0 mm as well as probability <= 20 % (CC-001).
    precipitation_mm: tuple[float, ...]
    wind_kmh: tuple[float, ...]
    weather_code: tuple[int, ...]
    sunrise: datetime
    sunset: datetime

    def to_cache(self) -> bytes:
        raise NotImplementedError

    @classmethod
    def from_cache(cls, payload: bytes) -> Self:
        raise NotImplementedError


@dataclass(frozen=True, slots=True)
class WeatherSummary:
    """Derived from the samples used. This, not the arrays, is kept with the result."""

    fetched_at: datetime
    tz: str
    window_start: datetime
    window_end: datetime
    condition: WeatherCondition
    temp_min_c: int
    temp_max_c: int
    max_precip_probability: int
    max_wind_kmh: int


@dataclass(frozen=True, slots=True)
class Pair:
    pair_id: str  # p1..p12, model-facing, per request
    idea_id: str  # opaque token_urlsafe(16); never sent to the model
    activity_id: str
    place: Place | None  # None = generic
    distance_m: int | None
    travel_min: int
    duration_min: int
    allowed_hook_ids: frozenset[str]
    allowed_reason_ids: frozenset[str]


@dataclass(frozen=True, slots=True)
class Pick:
    pair_id: str
    hook_id: str
    reason_ids: tuple[str, ...]  # <= MAX_REASONS


@dataclass(frozen=True, slots=True)
class Interests:
    tags: tuple[InterestTag, ...]  # <= MAX_TAGS; empty unless MATCHED
    outcome: InterestOutcome


@dataclass(frozen=True, slots=True)
class Idea:
    """Interest matches are not stored; core.ideas.matched_interests computes them."""

    pair: Pair
    hook_id: str
    reason_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class PlanResult:
    """Immutable (D46). The whole object stays under 32 KiB."""

    job_id: str
    state: JobState
    source: Source
    ideas: tuple[Idea, ...]  # 0-MAX_IDEAS, display order
    notices: tuple[NoticeId | ErrorCode, ...]
    interests: Interests | None
    answers: AnswersSummary
    weather: WeatherSummary | None
    planned_start: datetime
    planned_end: datetime
    valid_until: datetime
    retain_until: datetime
    error: ErrorCode | None


@dataclass(frozen=True, slots=True)
class LocationCandidate:
    candidate_id: str
    label: str  # <= PLACE_TEXT_MAX
    coords: Coordinates
    job_id: str | None = None  # set once consumed


@dataclass(frozen=True, slots=True)
class LocationCandidates:
    candidates: tuple[LocationCandidate, ...]  # up to MAX_CANDIDATES
    answers: Answers  # includes the D39 text; memory only
    expires_at: datetime
