"""Turn a urlencoded body into validated answers, or into field errors.

CONTRACTS section 7 and BACKEND-CONTRACT section 7: the fields are enumerated, unknown
names and repeated scalars are refused, and values outside the listed set are refused.
Nothing here guesses: a value that is not legal becomes an error on its own field, so a
422 can keep the rest.
"""

import unicodedata
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Final
from urllib.parse import parse_qsl

from wiggle_outside.core.errors import ErrorCode
from wiggle_outside.core.types import (
    INTEREST_TEXT_MAX,
    PLACE_TEXT_MAX,
    AgeBand,
    Answers,
    Coordinates,
    Energy,
    Location,
    TimeBudget,
    TypedPlace,
    Who,
)
from wiggle_outside.web.forms import (
    DEFAULT_ENERGY,
    DEFAULT_LOCATION_MODE,
    LOCATION_CHOICE_FIELDS,
    PLAN_FIELDS,
    PLAN_FORM_FIELDS,
    REPEATABLE_FIELDS,
)

# Anchor for a problem that belongs to the submission rather than to one answer, so a
# client-chosen field name is never reflected into the page.
FORM_ANCHOR: Final = "form"
INVALID: Final = ErrorCode.INPUT_INVALID
COORD_MODE: Final = "coords"


def parse_body(body: bytes) -> dict[str, list[str]] | None:
    """Parse a urlencoded body, or None when it cannot be parsed (400)."""
    try:
        text = body.decode("utf-8")
    except UnicodeDecodeError:
        return None
    try:
        pairs = parse_qsl(text, keep_blank_values=True, strict_parsing=bool(text))
    except ValueError:
        return None
    values: dict[str, list[str]] = {}
    for name, value in pairs:
        values.setdefault(name, []).append(value)
    return values


def shape_errors(
    values: Mapping[str, Sequence[str]],
    allowed: frozenset[str],
    repeatable: frozenset[str] = frozenset(),
) -> dict[str, ErrorCode]:
    """Unknown field names and repeated scalar fields (CONTRACTS section 7)."""
    errors: dict[str, ErrorCode] = {}
    for name, items in values.items():
        if name not in allowed:
            errors[FORM_ANCHOR] = INVALID
        elif len(items) > 1 and name not in repeatable:
            errors[name] = INVALID
    return errors


def _normalise(raw: str) -> str:
    return unicodedata.normalize("NFC", raw).strip()


@dataclass(slots=True)
class _Reader:
    """Reads one plan submission, collecting an error per field it cannot accept."""

    values: Mapping[str, Sequence[str]]
    errors: dict[str, ErrorCode] = field(default_factory=dict)

    def text(self, name: str) -> str:
        items = self.values.get(name, ())
        return _normalise(items[0]) if items else ""

    def fail(self, name: str) -> None:
        self.errors[name] = INVALID

    def who(self) -> Who | None:
        try:
            return Who(self.text("who"))
        except ValueError:
            self.fail("who")
            return None

    def ages(self, who: Who | None) -> frozenset[AgeBand]:
        raw = [_normalise(item) for item in self.values.get("age_band", ())]
        if who is not Who.KIDS:
            return frozenset()  # Ignored when solo (CONTRACTS section 7).
        try:
            bands = [AgeBand(item) for item in raw]
        except ValueError:
            self.fail("age_band")
            return frozenset()
        if not bands or len(set(bands)) != len(bands):
            self.fail("age_band")
            return frozenset()
        return frozenset(bands)

    def time_budget(self) -> TimeBudget | None:
        raw = self.text("time")
        try:
            return TimeBudget(int(raw))
        except ValueError:
            self.fail("time")
            return None

    def energy(self) -> Energy:
        raw = self.text("energy")
        if not raw:
            return DEFAULT_ENERGY  # D18: Moderate unless something else is chosen.
        try:
            return Energy(raw)
        except ValueError:
            self.fail("energy")
            return DEFAULT_ENERGY

    def location(self) -> Location | None:
        mode = self.text("location_mode") or DEFAULT_LOCATION_MODE
        if mode == COORD_MODE:
            return self._coordinates()
        if mode != DEFAULT_LOCATION_MODE:
            self.fail(FORM_ANCHOR)
            return None
        return self._typed_place()

    def _coordinates(self) -> Coordinates | None:
        try:
            return Coordinates(lat=float(self.text("lat")), lon=float(self.text("lon")))
        except ValueError:
            self.fail("place")
            return None

    def _typed_place(self) -> TypedPlace | None:
        try:
            return TypedPlace(text=self.text("place"))
        except ValueError:
            self.fail("place")
            return None

    def label(self) -> str | None:
        raw = self.text("location_label")
        if not raw:
            return None
        if len(raw) > PLACE_TEXT_MAX or not raw.isprintable():
            self.fail("place")
            return None
        return raw

    def flag(self, name: str) -> bool:
        items = self.values.get(name, ())
        if not items:
            return False
        if _normalise(items[0]) != "1":
            self.fail(name)
            return False
        return True

    def interests(self, *, enabled: bool) -> str | None:
        if "interests_text" not in self.values:
            return None
        if not enabled:
            # D39 off, so this is an unknown field (CONTRACTS section 7).
            self.fail(FORM_ANCHOR)
            return None
        raw = self.text("interests_text")
        if not raw:
            return None
        if len(raw) > INTEREST_TEXT_MAX or not raw.isprintable():
            self.fail("interests_text")
            return None
        return raw


@dataclass(frozen=True, slots=True)
class PlanParse:
    """The outcome of reading a plan form: answers, or the errors that stopped them."""

    answers: Answers | None
    errors: Mapping[str, ErrorCode]
    key: str
    label: str | None


def read_plan(values: Mapping[str, Sequence[str]], *, d39_enabled: bool) -> PlanParse:
    """Validate a plan submission (CONTRACTS section 7)."""
    reader = _Reader(
        values=values, errors=shape_errors(values, PLAN_FORM_FIELDS, REPEATABLE_FIELDS)
    )
    who = reader.who()
    ages = reader.ages(who)
    budget = reader.time_budget()
    energy = reader.energy()
    location = reader.location()
    label = reader.label()
    interests = reader.interests(enabled=d39_enabled)
    stroller = reader.flag("stroller")
    step_free = reader.flag("step_free")
    key = reader.text("idempotency_key")
    if not key:
        reader.fail(FORM_ANCHOR)
    if reader.errors or who is None or budget is None or location is None:
        return PlanParse(answers=None, errors=reader.errors, key=key, label=label)
    return PlanParse(
        answers=Answers(
            who=who,
            age_bands=ages,
            time_budget=budget,
            energy=energy,
            location=location,
            stroller=stroller,
            step_free=step_free,
            interest_text=interests,
        ),
        errors={},
        key=key,
        label=label,
    )


def read_choice(values: Mapping[str, Sequence[str]]) -> str | None:
    """Read the `candidate_id` of a location choice, or None when the body is not one."""
    if shape_errors(values, frozenset(LOCATION_CHOICE_FIELDS)):
        return None
    items = values.get("candidate_id", ())
    return _normalise(items[0]) if items else None


def submitted_fields(values: Mapping[str, Sequence[str]]) -> dict[str, str]:
    """Collect what was typed, for a 422 re-render (CONTRACTS section 8, CC-A).

    Only the answer fields: never `csrf_token`, `idempotency_key` or the honeypot, which
    the form page renders fresh and empty.
    """
    sent: dict[str, str] = {}
    for name in PLAN_FIELDS:
        items = values.get(name)
        if items is None:
            continue
        sent[name] = ",".join(items) if name in REPEATABLE_FIELDS else items[0]
    return sent


def fields_from_answers(answers: Answers) -> dict[str, str]:
    """Render stored answers back as form values, so a 422 can keep them."""
    sent = {
        "who": answers.who.value,
        "time": str(int(answers.time_budget)),
        "energy": answers.energy.value,
        "stroller": "1" if answers.stroller else "",
        "step_free": "1" if answers.step_free else "",
    }
    if answers.age_bands:
        sent["age_band"] = ",".join(band.value for band in sorted(answers.age_bands))
    location = answers.location
    if isinstance(location, TypedPlace):
        sent["location_mode"] = DEFAULT_LOCATION_MODE
        sent["place"] = location.text
    else:
        sent["location_mode"] = COORD_MODE
        sent["lat"] = f"{location.lat}"
        sent["lon"] = f"{location.lon}"
    return sent
