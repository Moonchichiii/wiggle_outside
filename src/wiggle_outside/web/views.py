"""Template context (CONTRACTS section 8).

Templates receive only these view models, never domain objects, raw provider data or
exceptions. Strings are plain text; escaping happens once, by Jinja autoescape.
WP8 builds them in presenters.py; WP0 owns the shapes.
"""

from collections.abc import Mapping
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Literal

from wiggle_outside.core.errors import ErrorCode
from wiggle_outside.core.types import (
    AnswersSummary,
    DeploymentMode,
    Interests,
    LocationCandidates,
)

IdeaVariant = Literal["sage", "peach", "butter"]
NoticeKind = Literal["info", "success", "alert"]
HttpMethod = Literal["get", "post"]


@dataclass(frozen=True, slots=True)
class AssetRef:
    url: str
    integrity: str


@dataclass(frozen=True, slots=True)
class PageMeta:
    title: str
    assets: Mapping[str, AssetRef]
    demo_mode: bool


@dataclass(frozen=True, slots=True)
class SessionView:
    csrf_token: str
    idempotency_key: str | None  # present only on pages with a plan form


@dataclass(frozen=True, slots=True)
class FieldError:
    field: str
    anchor: str
    message: str


@dataclass(frozen=True, slots=True)
class Option:
    value: str  # the enum value, e.g. "energetic"
    label: str  # the display label, e.g. "High" (TC-001)
    icon: str | None
    checked: bool


@dataclass(frozen=True, slots=True)
class ActionView:
    label: str
    url: str
    method: HttpMethod
    csrf_token: str | None


@dataclass(frozen=True, slots=True)
class NoticeView:
    kind: NoticeKind
    heading: str | None
    body: str
    actions: tuple[ActionView, ...]


@dataclass(frozen=True, slots=True)
class FormPage:
    meta: PageMeta
    session: SessionView
    intro: str
    who: tuple[Option, ...]
    ages: tuple[Option, ...]
    time: tuple[Option, ...]
    energy: tuple[Option, ...]
    location_mode: str
    place: str
    coords: tuple[str, str] | None  # rounded; device, or carried from a result (D46)
    location_label: str | None
    place_hint: str  # copy by DeploymentMode
    stroller: bool
    step_free: bool
    interests_text: str | None  # None = D39 off; prefilled only with tag labels
    field_errors: Mapping[str, FieldError]
    summary: tuple[FieldError, ...]
    candidates: tuple[Option, ...]
    candidates_expire_at: str | None


_NO_ERRORS: Mapping[str, ErrorCode] = MappingProxyType({})
_NO_ASSETS: Mapping[str, AssetRef] = MappingProxyType({})


@dataclass(frozen=True, slots=True)
class FormContext:
    """Everything `present_form` needs, in one carrier (CC-A, CC-B, CC-C, CC-D).

    The original signature took six positional parameters and could represent only two
    states: every answer present and geocoded, or nothing. That made three required
    behaviours unreachable — a 422 re-render keeping the answers someone did give
    (ERROR-HANDLING §2), echoing back a typed town that failed to geocode, and the D46
    interests prefill — and it collided with the 5-argument limit in `ruff.toml`.

    Every value is still explicit: no globals, no hidden catalogue or settings lookups.
    """

    session: SessionView
    mode: DeploymentMode
    d39_enabled: bool

    # The build manifest, which the caller knows and a presenter must not reach for.
    assets: Mapping[str, AssetRef] = _NO_ASSETS

    # A carried result's answers: complete and geocoded (D46, "Change answers").
    answers: AnswersSummary | None = None

    # What the person actually submitted, which may be incomplete or ungeocodable. This
    # is what a 422 re-render echoes back, and it wins over `answers` field by field.
    submitted: Mapping[str, str] = field(default_factory=dict)

    errors: Mapping[str, ErrorCode] = _NO_ERRORS
    candidates: LocationCandidates | None = None

    # IANA name for rendering candidate expiry; times are never shown in server time
    # (CONTRACTS §8).
    candidates_tz: str | None = None

    # The validated tags of a previous result, so "Change answers" can prefill the
    # interests field with their labels rather than the original free text (D46).
    interests: Interests | None = None


@dataclass(frozen=True, slots=True)
class InterestsView:
    heading: str
    labels: tuple[str, ...]  # plain labels, not controls
    note: str


@dataclass(frozen=True, slots=True)
class WeatherView:
    icon: str
    line: str
    checked_at: str
    window: str


@dataclass(frozen=True, slots=True)
class AnswersView:
    lines: tuple[str, ...]
    change_label: str


@dataclass(frozen=True, slots=True)
class PlaceView:
    name: str | None  # None = generic
    kind_label: str
    distance: str | None
    uncertainty: tuple[str, ...]  # fee and access labels, always "as reported"


@dataclass(frozen=True, slots=True)
class IdeaView:
    idea_id: str
    variant: IdeaVariant
    title: str
    intro: str  # Hook.text verbatim, no placeholders
    reasons: tuple[str, ...]  # detail page only
    interest_match: str | None
    place: PlaceView
    times: str
    detail_url: str
    # The card's activity illustration, as a decor asset stem (visual direction, TC-008).
    # Empty means the generic leaf; the name never comes from the model.
    illustration: str = ""


@dataclass(frozen=True, slots=True)
class ResultPage:
    meta: PageMeta
    session: SessionView
    heading: str
    answers: AnswersView
    edit_form: FormPage  # prefilled, inside "Change answers"
    weather: WeatherView | None
    ideas: tuple[IdeaView, ...]  # 0-3, no padding
    notices: tuple[NoticeView, ...]
    interests: InterestsView | None
    source_label: str | None
    is_historical: bool
    historical_text: str | None
    plan_again: ActionView


@dataclass(frozen=True, slots=True)
class BingoView:
    heading: str
    items: tuple[str, ...]  # 9 items, 3x3


@dataclass(frozen=True, slots=True)
class ActivityView:
    steps: tuple[str, ...]
    optional: tuple[str, ...]
    adapt: str
    ask: str | None
    safety: str
    card: BingoView | None


@dataclass(frozen=True, slots=True)
class PrintView:
    context_line: str
    weather_line: str
    source_line: str
    note: str


@dataclass(frozen=True, slots=True)
class DetailPage:
    meta: PageMeta
    idea: IdeaView
    activity: ActivityView
    weather: WeatherView
    print: PrintView
    notices: tuple[NoticeView, ...]
    is_historical: bool
    back_url: str
    print_label: str


@dataclass(frozen=True, slots=True)
class ErrorPage:
    meta: PageMeta
    notice: NoticeView
    reference: str | None
    form: FormPage | None  # a 422 re-render keeps the answers
