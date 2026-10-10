"""The reviewed copy table (DESIGN-SPEC section 9), as data.

Every user-facing string lives here, never in a template. Strings are plain text:
Jinja autoescape escapes them exactly once at the HTML boundary (BACKEND-CONTRACT
section 7). Importing this module has no side effects.

TC-001: the energy values stay `gentle` / `moderate` / `energetic`; the labels read
Gentle / Moderate / High. No string here spells the value with a capital letter, and a
test asserts it.

Characters that ruff reads as ASCII look-alikes (en dash, apostrophe) are written as
escapes so the gate stays quiet and the intent stays visible.
"""

from types import MappingProxyType
from typing import TYPE_CHECKING, Final

from wiggle_outside.core.errors import ErrorCode
from wiggle_outside.core.types import AgeBand, DeploymentMode, Energy, TimeBudget, Who

if TYPE_CHECKING:
    from collections.abc import Mapping

# Written as code points: a literal en dash reads as a hyphen to the linter and to a
# reviewer, and the age ranges in DESIGN-SPEC section 9 are en dashes, not hyphens.
EN_DASH: Final = chr(0x2013)
ELLIPSIS: Final = chr(0x2026)

# --- Page chrome (section 9) -------------------------------------------------------

PAGE_TITLE: Final = "Wiggle Outside"  # D40
FORM_PAGE_TITLE: Final = PAGE_TITLE
INTRO: Final = "A few details. Up to three outdoor ideas near you."

# --- Who ---------------------------------------------------------------------------

WHO_LEGEND: Final = "Who's coming?"
WHO_LABELS: Final[Mapping[Who, str]] = MappingProxyType(
    {
        Who.SOLO: "Just me",
        Who.KIDS: "Me and the kids",
    }
)
WHO_ICONS: Final[Mapping[Who, str]] = MappingProxyType(
    {
        Who.SOLO: "adult",
        Who.KIDS: "adult-with-child",
    }
)

# --- Ages --------------------------------------------------------------------------

AGES_LEGEND: Final = "Kids' ages"
AGES_HINT: Final = "Pick all that apply."
AGE_LABELS: Final[Mapping[AgeBand, str]] = MappingProxyType(
    {
        AgeBand.B0_2: f"0{EN_DASH}2",
        AgeBand.B3_5: f"3{EN_DASH}5",
        AgeBand.B6_9: f"6{EN_DASH}9",
        AgeBand.B10_12: f"10{EN_DASH}12",
    }
)

# --- Time --------------------------------------------------------------------------

TIME_LEGEND: Final = "Time, there and back"
TIME_LABELS: Final[Mapping[TimeBudget, str]] = MappingProxyType(
    {
        TimeBudget.M30: "30 min",
        TimeBudget.H1: "1 hour",
        TimeBudget.H2: "2 hours",
        TimeBudget.HALF_DAY: "Half day (4 h)",  # D35
    }
)
# DESIGN-SPEC section 5 names one clock symbol per time tile.
TIME_ICONS: Final[Mapping[TimeBudget, str]] = MappingProxyType(
    {
        TimeBudget.M30: "clock-30",
        TimeBudget.H1: "clock-1h",
        TimeBudget.H2: "clock-2h",
        TimeBudget.HALF_DAY: "clock-half-day",
    }
)

# --- Energy (TC-001) ----------------------------------------------------------------

ENERGY_LEGEND: Final = "How much energy today?"
ENERGY_HINT: Final = "We may suggest something gentler."
ENERGY_LABELS: Final[Mapping[Energy, str]] = MappingProxyType(
    {
        Energy.GENTLE: "Gentle",
        Energy.MODERATE: "Moderate",
        Energy.ENERGETIC: "High",  # TC-001: the label, never the stored value.
    }
)
ENERGY_ICONS: Final[Mapping[Energy, str]] = MappingProxyType(
    {
        Energy.GENTLE: "snail",
        Energy.MODERATE: "walker",
        Energy.ENERGETIC: "whirlwind",
    }
)

# --- Where ---------------------------------------------------------------------------

WHERE_LEGEND: Final = "Where are you?"
USE_MY_LOCATION: Final = "Use my location"
PLACE_LABEL: Final = "or type a town or area"
# BACKEND-CONTRACT section 9: local development may show the hosted note; it is not a
# product mode of its own, so every mode gets the same disclosed wording.
_PLACE_HINT: Final = (
    "Please don't type a street address. We look the town up with OpenStreetMap's "
    "search and keep the lookup on our server for up to 30 days to avoid repeat requests."
)
PLACE_HINT_BY_MODE: Final[Mapping[DeploymentMode, str]] = MappingProxyType(
    {
        DeploymentMode.HOSTED_LIVE: _PLACE_HINT,
        DeploymentMode.LOCAL: _PLACE_HINT,
        DeploymentMode.REPLAY: _PLACE_HINT,
    }
)
# D46: the location carried into a prefilled "Change answers" form.
CARRIED_LOCATION_SUFFIX: Final = " (kept from this search; no new place lookup)"
CARRIED_LOCATION_ALTERNATIVE: Final = "or type a different town or area"
LOCATION_CHOICE_LEGEND: Final = "Which place did you mean?"
LOCATION_CHOICE_EXPIRES: Final = "This list of places expires at {time}."

# --- Interests (D39) -----------------------------------------------------------------

INTERESTS_LEGEND_BY_WHO: Final[Mapping[Who, str]] = MappingProxyType(
    {
        Who.SOLO: "What are you into?",
        Who.KIDS: "What are they into?",
    }
)
INTERESTS_OPTIONAL: Final = "(optional)"
INTERESTS_HINT: Final = (
    "For example: birds, puddles, running. Optional. Don't include personal details. "
    "We send this to our AI model provider to choose ideas; we don't store it."
)
# D46: "Change answers" prefills the recognised tag labels, never the original text.
INTERESTS_PREFILLED_HINT: Final = (
    "These are the interests we recognised. Edit them for your next search."
)

# --- The optional panel (D42) ---------------------------------------------------------

OPTIONAL_SUMMARY: Final = "Anything to account for?"
STROLLER_LABEL: Final = "We're bringing a stroller"
STEP_FREE_LABEL: Final = "Prefer places reported as step-free"
STEP_FREE_HINT: Final = (
    "Places OpenStreetMap reports as step-free come first. We can't check this ourselves."
)

# --- Submit and the busy state (D43) ---------------------------------------------------

SUBMIT: Final = "Find outings"
BUSY_LABEL: Final = f"Finding outings{ELLIPSIS}"
BUSY_NOTE: Final = "This can take up to 20 seconds."

# --- Honeypot (D49, DEPLOYMENT section 4) ----------------------------------------------

HONEYPOT_LABEL: Final = "Leave this field empty"

# --- Errors ------------------------------------------------------------------------------

ERROR_SUMMARY_HEADING: Final = "Check these answers"

# The field name each error is anchored to, and how it is named in the summary.
FIELD_LABELS: Final[Mapping[str, str]] = MappingProxyType(
    {
        "who": WHO_LEGEND,
        "age_band": AGES_LEGEND,
        "time": TIME_LEGEND,
        "energy": ENERGY_LEGEND,
        "place": WHERE_LEGEND,
        "interests_text": INTERESTS_LEGEND_BY_WHO[Who.KIDS],
    }
)

# The id a summary link jumps to, per field.
FIELD_ANCHORS: Final[Mapping[str, str]] = MappingProxyType(
    {
        "who": "who-first",
        "age_band": "age-first",
        "time": "time-first",
        "energy": "energy-first",
        "place": "place",
        "interests_text": "interests",
    }
)

# INPUT_INVALID, inline under the field. The age and place lines are the wording Mats
# approved in docs/mocks/01b-form-error.html; the rest follow it.
FIELD_INVALID: Final[Mapping[str, str]] = MappingProxyType(
    {
        "who": "Choose who's coming.",
        "age_band": "Pick at least one age group.",
        "time": "Choose how long you have.",
        "energy": "Choose an energy level.",
        "place": "Use your location or type a town or area.",
        "interests_text": "Keep this to 120 characters of plain text.",
    }
)

# INPUT_INVALID, in the error summary list (same approved source).
FIELD_INVALID_SUMMARY: Final[Mapping[str, str]] = MappingProxyType(
    {
        "who": "Who's coming: choose one.",
        "age_band": "Kids' ages: pick at least one.",
        "time": "Time, there and back: choose one.",
        "energy": "How much energy today: choose one.",
        "place": "Where are you: use your location or type a town or area.",
        "interests_text": "What are they into: keep this to 120 characters of plain text.",
    }
)

# ERROR-HANDLING section 2, verbatim. Placeholders stay as named fields.
ERROR_MESSAGES: Final[Mapping[ErrorCode, str]] = MappingProxyType(
    {
        ErrorCode.INPUT_INVALID: "Check the highlighted answers before we find an outing.",
        ErrorCode.LOCATION_DENIED: (
            "Location access wasn't allowed. Enter a town or area instead."
        ),
        ErrorCode.LOCATION_UNAVAILABLE: (
            "We couldn't get your location. Enter a town or area, or try again."
        ),
        ErrorCode.LOCATION_AMBIGUOUS: "Which place did you mean?",
        ErrorCode.LOCATION_CHOICE_EXPIRED: (
            "That list of places has expired. Enter the town or area again."
        ),
        ErrorCode.LOCATION_NOT_FOUND: (
            "We couldn't find that place. Try a nearby town or add the country."
        ),
        ErrorCode.GEOCODER_UNAVAILABLE: (
            "Place search isn't available right now. Try again, or use your location."
        ),
        ErrorCode.WEATHER_UNAVAILABLE: (
            "We couldn't check the weather, so we haven't suggested an outing. Try again."
        ),
        ErrorCode.WEATHER_RESTRICTED: (
            "The forecast is outside this activity list's weather limits. No outing suggested."
        ),
        ErrorCode.PLACES_CACHED: (
            "Live place information is unavailable. These places were last checked {age} ago."
        ),
        ErrorCode.PLACES_UNAVAILABLE: "We couldn't load nearby places.",
        ErrorCode.DAYLIGHT_NIGHT: (
            "Time to put the phone down and get some rest. The outdoors will still be "
            "there tomorrow."
        ),
        ErrorCode.DAYLIGHT_TOO_SHORT: (
            "The outing would end after sunset. Change your answers and we'll check the "
            "daylight and the weather again, or leave the adventure for tomorrow."
        ),
        ErrorCode.NO_MATCHES: "No activities in our list match these answers right now.",
        ErrorCode.FEWER_MATCHES: "We found {count} matching ideas.",
        ErrorCode.MODEL_FALLBACK: (
            "AI selection isn't available right now. These picks come from our activity "
            "list and passed every normal check."
        ),
        ErrorCode.SERVICE_LIMIT_REACHED: (
            "Wiggle Outside has reached today's limit. Please try again after {reset_time}."
        ),
        ErrorCode.SERVICE_UNAVAILABLE: (
            "Wiggle Outside can't take new searches right now. Your answers are kept; "
            "please try again in a few minutes."
        ),
        ErrorCode.REQUEST_BUSY: "The planner is busy. Try again shortly.",
        ErrorCode.PROGRESS_DISCONNECTED: (
            f"We've lost contact with the planner. Checking for your result{ELLIPSIS}"
        ),
        ErrorCode.CONNECTION_FAILED: (
            "We couldn't reach the planner. Check your connection, then try again."
        ),
        ErrorCode.JOB_CANCEL_REQUESTED: f"Stopping this request{ELLIPSIS}",
        ErrorCode.JOB_CANCELLED: "This request was cancelled.",
        ErrorCode.RESULT_EXPIRED: (
            "This result is no longer available. Submit your answers again to plan an outing."
        ),
        ErrorCode.REQUEST_CONFLICT: (
            "Your answers changed during this request. Submit them again to start a new search."
        ),
        ErrorCode.SESSION_INVALID: "This page needs refreshing before we can continue.",
        ErrorCode.REQUEST_TOO_LARGE: (
            "That submission is too large. Return to the form and try again."
        ),
        ErrorCode.UNEXPECTED_FAILURE: (
            "We couldn't finish that request. Please try again. Reference: {reference}."
        ),
        ErrorCode.PRINT_HELP: ("Use your browser's print menu to print or save this card."),
        ErrorCode.REPLAY_FIXTURE_MISSING: ("This example isn't available. Choose another example."),
    }
)

# Headings that go with a code, where section 9 gives one.
ERROR_HEADINGS: Final[Mapping[ErrorCode, str]] = MappingProxyType(
    {
        ErrorCode.DAYLIGHT_NIGHT: "The adventures can wait till morning.",
        ErrorCode.DAYLIGHT_TOO_SHORT: "Not enough daylight for this one.",
        ErrorCode.INPUT_INVALID: ERROR_SUMMARY_HEADING,
    }
)

# --- Results-side copy the form page links to ----------------------------------------

CHANGE_ANSWERS: Final = "Change answers"
RESULTS_HEADING: Final = "Here's what we found"
