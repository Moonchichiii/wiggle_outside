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

from wiggle_outside.core.errors import ErrorCode, NoticeId
from wiggle_outside.core.types import (
    AgeBand,
    DeploymentMode,
    Energy,
    InterestTag,
    TimeBudget,
    WeatherCondition,
    Who,
)

if TYPE_CHECKING:
    from collections.abc import Mapping

# Written as code points: a literal en dash reads as a hyphen to the linter and to a
# reviewer, and the age ranges in DESIGN-SPEC section 9 are en dashes, not hyphens.
EN_DASH: Final = chr(0x2013)
ELLIPSIS: Final = chr(0x2026)
MIDDLE_DOT: Final = chr(0x00B7)
DEGREE: Final = chr(0x00B0)
COPYRIGHT_SIGN: Final = chr(0x00A9)

# --- Page chrome (section 9) -------------------------------------------------------

PAGE_TITLE: Final = "Wiggle Outside"  # D40
FORM_PAGE_TITLE: Final = PAGE_TITLE
# The approved concept board (docs/mocks/reference/visual-direction-v2.png) puts the
# product name small in a masthead and this question as the page heading.
FORM_HEADING: Final = "A little fresh air?"
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
# The 14 tags as display labels (D39). "Change answers" prefills the interests field
# with these, never with the original free text, because these are what we recognised
# (CONTRACTS section 7, CC-C). Lower case: they read as a list, not as proper nouns.
# Activity illustrations for the result cards: the three pictures cut from the approved
# concept board (docs/design-kit/board/card-*.png, TC-008), keyed by catalogue activity
# id. Trees for the tree activities, the magnifier for anything that looks closely, and
# the sun and cloud for the rest; the name is chosen by code, never by the model.
ACTIVITY_ILLUSTRATIONS: Final[Mapping[str, str]] = MappingProxyType(
    {
        "tree-twins": "card-trees",
        "bark-rubbing": "card-trees",
        "stick-houses": "card-trees",
        "nature-bingo": "card-magnifier",
        "minibeast-safari": "card-magnifier",
        "i-spy-far": "card-magnifier",
        "shape-safari": "card-magnifier",
        "track-detective": "card-magnifier",
        "colour-match": "card-magnifier",
        "leaf-study-solo": "card-magnifier",
    }
)
DEFAULT_ILLUSTRATION: Final = "card-sun-cloud"

INTEREST_TAG_LABELS: Final[Mapping[InterestTag, str]] = MappingProxyType(
    {
        InterestTag.ANIMALS: "animals",
        InterestTag.BIRDS: "birds",
        InterestTag.BUGS: "bugs",
        InterestTag.TREES: "trees",
        InterestTag.COLOURS: "colours",
        InterestTag.SHAPES: "shapes",
        InterestTag.STORIES: "stories",
        InterestTag.RUNNING: "running",
        InterestTag.BUILDING: "building",
        InterestTag.SOUNDS: "sounds",
        InterestTag.DRAWING: "drawing",
        InterestTag.SKY: "sky",
        InterestTag.QUIET: "quiet",
        InterestTag.PUDDLES: "puddles",
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

# --- The results page (section 9) ----------------------------------------------------

# The answers summary reads "Me and the kids (3-5, 6-9) - 1 hour - Moderate - near Bergby",
# with the middle dot as the separator and the ages only when there are any.
ANSWERS_WITH_AGES: Final = "{who} ({ages})"
ANSWERS_NEAR: Final = "near {label}"
ANSWERS_JOIN: Final = f" {MIDDLE_DOT} "
AGES_JOIN: Final = ", "

PLAN_AGAIN: Final = "Plan again"
HISTORICAL: Final = (
    f"This information is no longer current. Planned for {{date}}, {{start}}{EN_DASH}{{end}}, "
    f"weather checked at {{time}}. Plan again for fresh ideas."
)

# --- The shared weather line, shown once above the ideas ------------------------------

# Fixture data is labelled exactly as the approved board labels it (TC-008). Shown only
# when the result carries NoticeId.REPLAY, which only fixture planners set.
EXAMPLE_FORECAST: Final = "Example forecast"
EXAMPLE_NOTE: Final = "Illustrative places and weather"
WEATHER_LINE: Final = "Weather for {window}, checked at {time}: {summary}"
WEATHER_WINDOW: Final = f"{{start}}{EN_DASH}{{end}}"
WEATHER_SUMMARY: Final = "{condition}{rain}, {temperature}, wind up to {wind} km/h."
WEATHER_RAIN: Final = " (up to {percent} %)"
WEATHER_TEMPERATURE_RANGE: Final = f"{{low}}{EN_DASH}{{high}} {DEGREE}C"
WEATHER_TEMPERATURE_ONE: Final = f"{{value}} {DEGREE}C"

# The forecast in words. The condition is the worst instant in the window, so
# "cloudy with showers possible" keeps the cloud in the sentence rather than promising rain.
WEATHER_CONDITIONS: Final[Mapping[WeatherCondition, str]] = MappingProxyType(
    {
        WeatherCondition.CLEAR: "clear",
        WeatherCondition.CLOUDY: "cloudy",
        WeatherCondition.SHOWERS_POSSIBLE: "cloudy with showers possible",
        WeatherCondition.RAIN_LIKELY: "rain likely",
        WeatherCondition.FOG: "fog",
        WeatherCondition.SNOW: "snow",
    }
)

# DESIGN-SPEC section 5 names six weather glyphs: sun, cloud, rain, wind, sunset and
# thermometer. There is no snow or fog glyph, so both take the cloud; the text, never the
# icon, states the weather, and every icon is decorative and aria-hidden.
WEATHER_ICONS: Final[Mapping[WeatherCondition, str]] = MappingProxyType(
    {
        WeatherCondition.CLEAR: "sun",
        WeatherCondition.CLOUDY: "cloud",
        WeatherCondition.SHOWERS_POSSIBLE: "rain",
        WeatherCondition.RAIN_LIKELY: "rain",
        WeatherCondition.FOG: "cloud",
        WeatherCondition.SNOW: "cloud",
    }
)

# --- Interest labels (D39, D46): plain text, never controls --------------------------

INTERESTS_HEADING_BY_WHO: Final[Mapping[Who, str]] = MappingProxyType(
    {
        Who.SOLO: "We think you're into:",
        Who.KIDS: "We think they're into:",
    }
)
INTERESTS_LIST_JOIN: Final = ", "
INTERESTS_LIST_END: Final = "."
# The legend named here is the one the interests field actually carries, so the
# instruction points at a control the person can find under "Change answers".
INTERESTS_NOTE: Final = 'To change these, edit "{legend}" under Change answers.'

# hooks.toml's derived reason `matches_interest`, rendered from validated tags only.
INTEREST_MATCH: Final = "Matches the interests: {tags}."

# --- Idea cards (section 9, tightened in 8.12) ---------------------------------------

CARD_LINK: Final = "Read the full activity"
# A visually hidden suffix, so three identical link texts still name their own card.
CARD_LINK_CONTEXT: Final = ": {title}"
PRACTICAL_JOIN: Final = f" {MIDDLE_DOT} "
DISTANCE: Final = "about {km} km away"
# The detail page says where the number comes from; the card keeps the line short and the
# detail page carries the qualification (DESIGN-SPEC section 9).
DISTANCE_STRAIGHT_LINE_SUFFIX: Final = " in a straight line"
TIMES: Final = f"{{travel}} min there and back {MIDDLE_DOT} {{duration}} min activity"
DETAIL_TIMES: Final = "About {times} (estimates)"

# OSM place kinds as words. A kind that is not listed falls back to the tag with its
# underscores replaced, because the kind is provider data, not our vocabulary.
PLACE_KIND_LABELS: Final[Mapping[str, str]] = MappingProxyType(
    {
        "park": "park",
        "forest": "forest",
        "nature_reserve": "nature area",
        "picnic_site": "picnic site",
        "playground": "playground",
    }
)
# A generic pair carries an explicit absent destination (PLAN section 3).
PLACE_KIND_GENERIC: Final = "near you"

# Uncertainty labels (D37, D42 P, BACKEND-CONTRACT section 8). Only the ones that apply.
FEE_UNKNOWN: Final = "Admission not verified"
FEE_REPORTED_FREE: Final = "Reported free admission"
STEP_FREE_UNKNOWN: Final = "Step-free access not verified"
STEP_FREE_REPORTED: Final = "OpenStreetMap reports step-free access"

# --- The detail and print views (sections 6, 9 and 10) -------------------------------

DETAIL_WHY: Final = "Why this idea"
DETAIL_STEPS: Final = "What to do"
DETAIL_OPTIONAL: Final = "Nice to have"
DETAIL_ADAPT: Final = "Another way to play"
DETAIL_SAFETY: Final = "Safety"
DETAIL_ASK: Final = "Ask on the way home"
BINGO_HEADING: Final = "Your bingo card"
BACK_TO_RESULTS: Final = "Back to results"
PRINT_LABEL: Final = "Print this card"
# The plain-browser route, named in words so the page never depends on a script to print.
PRINT_HELP: Final = ERROR_MESSAGES[ErrorCode.PRINT_HELP]

PRINT_CONTEXT: Final = (
    f"Planned for {{date}}, {{start}}{EN_DASH}{{end}} ({{tz}}), near {{location}}."
)
PRINT_WEATHER: Final = "Weather checked at {time} on {date}; times are estimates."
PRINT_SOURCE: Final = (
    f"Place data {COPYRIGHT_SIGN} OpenStreetMap contributors; weather from Open-Meteo."
)
PRINT_NOTE: Final = "Check the weather again before you go if plans change."

# --- Notices that are not rows of the ERROR-HANDLING table ---------------------------

# NoticeId.REPLAY is deliberately absent: the replay demo is inactive (D24 superseded by
# D48), so there is no reviewed copy for it and the presenter renders nothing for it.
NOTICE_MESSAGES: Final[Mapping[NoticeId, str]] = MappingProxyType(
    {
        NoticeId.GENTLER_THAN_ASKED: (
            "These suggestions are gentler than the energy level you selected."
        ),
        NoticeId.INTEREST_NO_MATCH: (
            "We couldn't match that to our activity list, so these ideas aren't sorted by "
            "interests."
        ),
        NoticeId.INTEREST_UNCLEAR: (
            "We weren't sure what that meant, so these ideas aren't sorted by interests."
        ),
        NoticeId.INTEREST_NOT_APPLIED: (
            "We couldn't read the interests this time, so these ideas aren't sorted by them."
        ),
        NoticeId.INTERESTS_USED_BY_FALLBACK: (
            "These picks are sorted by our activity list using the interests above."
        ),
    }
)

# --- The error page ------------------------------------------------------------------

# ERROR-HANDLING section 5 wants a specific action label, and REQUEST_TOO_LARGE's own copy
# already says "Return to the form", so that is the wording for the one action an error
# page can always offer.
RETURN_TO_FORM: Final = "Return to the form"

# D49, DEPLOYMENT section 2.3: the daily allowance rolls over at 00:00 UTC and nothing
# else resets it, so SERVICE_LIMIT_REACHED's reset time is this constant rather than a
# value a presenter has to be told.
SERVICE_RESET_TIME: Final = "00:00 UTC"

# The short weekday and month names, so a rendered date never depends on the process
# locale. CONTRACTS section 8 fixes the shape: "Sat 10 Oct 2026".
WEEKDAYS: Final[tuple[str, ...]] = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")
MONTHS: Final[tuple[str, ...]] = (
    "Jan",
    "Feb",
    "Mar",
    "Apr",
    "May",
    "Jun",
    "Jul",
    "Aug",
    "Sep",
    "Oct",
    "Nov",
    "Dec",
)
