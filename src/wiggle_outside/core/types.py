"""Shared domain values (CONTRACTS section 2).

Frozen dataclasses whose nested values are immutable too (D17). No I/O, no framework.
"""

import json
import math
from dataclasses import dataclass, field
from datetime import datetime
from enum import IntEnum, StrEnum
from typing import Final, Literal, Self, cast

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
    # CC-004: the display label a "Change answers" form carries with its coordinates (the
    # earlier geocode label), so the resubmission keeps it. None with a typed place, or
    # for device coordinates ("Your location"). Validated by the form reader (<= 80,
    # printable); never a lookup input.
    location_label: str | None = None


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
        fields = _fields(payload)
        fee = _text(fields, "fee")
        access = _text(fields, "osm_access")
        if fee not in {"no", "yes", "unknown"} or access not in {"yes", "limited", "no", "unknown"}:
            msg = "not a cached place"
            raise ValueError(msg)
        return cls(
            place_id=_text(fields, "place_id"),
            name=_text(fields, "name"),
            kind=_text(fields, "kind"),
            coords=Coordinates(lat=_number(fields, "lat"), lon=_number(fields, "lon")),
            fee=cast("Literal['no', 'yes', 'unknown']", fee),
            osm_access=cast("Literal['yes', 'limited', 'no', 'unknown']", access),
        )


@dataclass(frozen=True, slots=True)
class GeocodeHit:
    label: str
    coords: Coordinates


@dataclass(frozen=True, slots=True)
class GeocodeHits:
    hits: tuple[GeocodeHit, ...]  # at most MAX_CANDIDATES

    def to_cache(self) -> bytes:
        # The label and the rounded coordinates only: never the typed query
        # (BACKEND-CONTRACT section 9).
        hits: list[dict[str, str | float]] = [
            {"label": hit.label, "lat": hit.coords.lat, "lon": hit.coords.lon} for hit in self.hits
        ]
        return _dump({"hits": hits})

    @classmethod
    def from_cache(cls, payload: bytes) -> Self:
        hits: list[GeocodeHit] = []
        for raw in _items(_fields(payload), "hits")[:MAX_CANDIDATES]:
            fields = _mapping(raw)
            hits.append(
                GeocodeHit(
                    label=_text(fields, "label"),
                    coords=Coordinates(lat=_number(fields, "lat"), lon=_number(fields, "lon")),
                )
            )
        return cls(hits=tuple(hits))


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
        return _dump(
            {
                "start": self.start.isoformat(),
                "end": self.end.isoformat(),
                "fetched_at": self.fetched_at.isoformat(),
                "tz": self.tz,
                "times": [moment.isoformat() for moment in self.times],
                "temp_c": list(self.temp_c),
                "apparent_temp_c": list(self.apparent_temp_c),
                "precip_probability": list(self.precip_probability),
                "precipitation_mm": list(self.precipitation_mm),
                "wind_kmh": list(self.wind_kmh),
                "weather_code": list(self.weather_code),
                "sunrise": self.sunrise.isoformat(),
                "sunset": self.sunset.isoformat(),
            }
        )

    @classmethod
    def from_cache(cls, payload: bytes) -> Self:
        fields = _fields(payload)
        return cls(
            start=_moment(fields, "start"),
            end=_moment(fields, "end"),
            fetched_at=_moment(fields, "fetched_at"),
            tz=_text(fields, "tz"),
            times=tuple(_parse_moment(raw) for raw in _items(fields, "times")),
            temp_c=tuple(_real(raw) for raw in _items(fields, "temp_c")),
            apparent_temp_c=tuple(_real(raw) for raw in _items(fields, "apparent_temp_c")),
            precip_probability=tuple(_whole(raw) for raw in _items(fields, "precip_probability")),
            precipitation_mm=tuple(_real(raw) for raw in _items(fields, "precipitation_mm")),
            wind_kmh=tuple(_real(raw) for raw in _items(fields, "wind_kmh")),
            weather_code=tuple(_whole(raw) for raw in _items(fields, "weather_code")),
            sunrise=_moment(fields, "sunrise"),
            sunset=_moment(fields, "sunset"),
        )


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


# --- Cache codecs --------------------------------------------------------------------
# Compact JSON, decoded without trusting its shape: every field is checked, and a payload
# that is not what we wrote raises TypeError or ValueError, which the cache wrapper counts
# as a miss (storage.wrapper.CODEC_ERRORS).


def _dump(fields: dict[str, object]) -> bytes:
    return json.dumps(fields, separators=(",", ":"), sort_keys=True).encode()


def _fields(payload: bytes) -> dict[str, object]:
    try:
        decoded: object = json.loads(payload)
    except UnicodeDecodeError as exc:
        msg = "not a cached value"
        raise ValueError(msg) from exc
    return _mapping(decoded)


def _mapping(raw: object) -> dict[str, object]:
    if not isinstance(raw, dict):
        msg = "not an object"
        raise TypeError(msg)
    return {str(key): value for key, value in cast("dict[object, object]", raw).items()}


def _items(fields: dict[str, object], name: str) -> list[object]:
    raw = fields.get(name)
    if not isinstance(raw, list):
        msg = f"{name} is not a list"
        raise TypeError(msg)
    return list(cast("list[object]", raw))


def _text(fields: dict[str, object], name: str) -> str:
    raw = fields.get(name)
    if not isinstance(raw, str):
        msg = f"{name} is not text"
        raise TypeError(msg)
    return raw


def _real(raw: object) -> float:
    if isinstance(raw, bool) or not isinstance(raw, int | float) or not math.isfinite(raw):
        msg = "not a finite number"
        raise ValueError(msg)
    return float(raw)


def _whole(raw: object) -> int:
    if isinstance(raw, bool) or not isinstance(raw, int):
        msg = "not a whole number"
        raise TypeError(msg)
    return raw


def _number(fields: dict[str, object], name: str) -> float:
    return _real(fields.get(name))


def _parse_moment(raw: object) -> datetime:
    if not isinstance(raw, str):
        msg = "not a timestamp"
        raise TypeError(msg)
    moment = datetime.fromisoformat(raw)
    if moment.tzinfo is None:
        msg = "a cached timestamp must be aware"
        raise ValueError(msg)
    return moment


def _moment(fields: dict[str, object], name: str) -> datetime:
    return _parse_moment(fields.get(name))
