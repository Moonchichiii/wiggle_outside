"""The "Before you go" list (TC-012 part E): pure rules, keys only.

Built from the actual window's forecast, the ages, the time and the chosen ideas. This
module decides *which* items; the reviewed wording lives in `web/copy.py`, keyed by
`PackingItem` and `Snack`. The chosen ideas' optional items are catalogue text and pass
through as they are. At most `MAX_ITEMS` items in all, the most important first in each
group. No health, allergy or safety claims are made here.
"""

import re
from dataclasses import dataclass
from enum import StrEnum
from typing import Final

from wiggle_outside.core.types import AgeBand, TimeBudget, WeatherCondition, Who

MAX_ITEMS: Final = 10
RAIN_PROBABILITY_PCT: Final = 40
COLD_C: Final = 10
VERY_COLD_C: Final = 5
WINDY_KMH: Final = 25
WARM_C: Final = 20
HOT_C: Final = 24
COCOA_BELOW_C: Final = 8
SANDWICH_FROM_MIN: Final = TimeBudget.H2.value
OLDER_BANDS: Final[frozenset[AgeBand]] = frozenset({AgeBand.B6_9, AgeBand.B10_12})


class PackingItem(StrEnum):
    NAPPIES = "nappies"
    CHANGE_OF_CLOTHES = "change_of_clothes"
    MUSLIN = "muslin"
    SMALL_TOY = "small_toy"
    WIPES = "wipes"
    SPARE_TROUSERS = "spare_trousers"
    TREASURE_BAG = "treasure_bag"
    OWN_BACKPACK = "own_backpack"
    WATER_BOTTLE_EACH = "water_bottle_each"
    PUSHCHAIR_RAIN_COVER = "pushchair_rain_cover"
    PUSHCHAIR_SUNSHADE = "pushchair_sunshade"
    HAND_SANITISER = "hand_sanitiser"
    WATERPROOF_JACKETS = "waterproof_jackets"
    WELLIES = "wellies"
    WARM_LAYER = "warm_layer"
    HATS_AND_GLOVES = "hats_and_gloves"
    WINDPROOF = "windproof"
    SUN_HATS_AND_CREAM = "sun_hats_and_cream"
    EXTRA_WATER = "extra_water"
    CHARGED_PHONE = "charged_phone"


class Snack(StrEnum):
    COLD = "cold"
    MILD = "mild"
    WARM = "warm"
    RAIN = "rain"
    SOLO = "solo"
    # A 0-2 is coming: only the neutral line, never a food suggestion for the youngest.
    YOUNGEST = "youngest"


# Optional extras come after the essentials (TC-012 clarification).
EXTRAS: Final[frozenset[PackingItem]] = frozenset({PackingItem.SMALL_TOY, PackingItem.TREASURE_BAG})
# Equivalent items are deduplicated, not just identical strings: one of each key stays.
EQUIVALENCE: Final[dict[PackingItem, str]] = {
    PackingItem.NAPPIES: "wipes",
    PackingItem.WIPES: "wipes",
    PackingItem.WATER_BOTTLE_EACH: "water",
    PackingItem.EXTRA_WATER: "water",
    PackingItem.TREASURE_BAG: "bag",
    PackingItem.HATS_AND_GLOVES: "hat",
    PackingItem.SUN_HATS_AND_CREAM: "hat",
    PackingItem.WATERPROOF_JACKETS: "jacket",
    PackingItem.WINDPROOF: "jacket",
    PackingItem.WELLIES: "wellies",
}
# The same keys, found in a catalogue item's text.
EQUIVALENCE_WORDS: Final[dict[str, str]] = {
    "wipes": "wipes",
    "water": "water",
    "bag": "bag",
    "bags": "bag",
    "hat": "hat",
    "hats": "hat",
    "jacket": "jacket",
    "jackets": "jacket",
    "coat": "jacket",
    "coats": "jacket",
    "wellies": "wellies",
    "welly": "wellies",
    "boots": "wellies",
}
_WORD: Final = re.compile(r"[a-z]+")


BY_BAND: Final[dict[AgeBand, tuple[PackingItem, ...]]] = {
    AgeBand.B0_2: (
        PackingItem.NAPPIES,
        PackingItem.CHANGE_OF_CLOTHES,
        PackingItem.MUSLIN,
        PackingItem.SMALL_TOY,
    ),
    AgeBand.B3_5: (PackingItem.WIPES, PackingItem.SPARE_TROUSERS, PackingItem.TREASURE_BAG),
    AgeBand.B6_9: (PackingItem.OWN_BACKPACK, PackingItem.WATER_BOTTLE_EACH),
    AgeBand.B10_12: (PackingItem.OWN_BACKPACK, PackingItem.WATER_BOTTLE_EACH),
}


@dataclass(frozen=True, slots=True)
class PackingInputs:
    """What the rules read: the answers and the forecast of the window actually planned."""

    who: Who
    age_bands: frozenset[AgeBand]
    stroller: bool
    time_budget: TimeBudget
    condition: WeatherCondition
    temp_min_c: int  # the window's lowest temperature stands in for "feels like"
    temp_max_c: int
    precip_probability: int
    wind_kmh: int
    # The chosen ideas' catalogue `optional` items, in idea order.
    idea_items: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class PackingList:
    little_ones: tuple[PackingItem, ...]
    weather: tuple[PackingItem, ...]
    ideas: tuple[str, ...]
    snack: Snack
    sandwich: bool  # two hours or more, no 0-2: a proper sandwich each

    @property
    def count(self) -> int:
        return len(self.little_ones) + len(self.weather) + len(self.ideas)


def is_rainy(inputs: PackingInputs) -> bool:
    return inputs.precip_probability >= RAIN_PROBABILITY_PCT or inputs.condition in {
        WeatherCondition.RAIN_LIKELY,
        WeatherCondition.SNOW,
    }


def is_warm_and_clear(inputs: PackingInputs) -> bool:
    return inputs.temp_max_c >= WARM_C and inputs.condition is WeatherCondition.CLEAR


def weather_items(inputs: PackingInputs) -> tuple[PackingItem, ...]:
    """Build the weather group, most important first: wet, cold, wind, sun, heat."""
    rules: tuple[tuple[bool, tuple[PackingItem, ...]], ...] = (
        (is_rainy(inputs), (PackingItem.WATERPROOF_JACKETS, PackingItem.WELLIES)),
        (inputs.temp_min_c < COLD_C, (PackingItem.WARM_LAYER,)),
        (inputs.temp_min_c < VERY_COLD_C, (PackingItem.HATS_AND_GLOVES,)),
        (inputs.wind_kmh >= WINDY_KMH, (PackingItem.WINDPROOF,)),
        (is_warm_and_clear(inputs), (PackingItem.SUN_HATS_AND_CREAM,)),
        (inputs.temp_max_c >= HOT_C, (PackingItem.EXTRA_WATER,)),
        (inputs.who is Who.SOLO, (PackingItem.CHARGED_PHONE,)),
    )
    return tuple(item for applies, items in rules if applies for item in items)


def little_ones_items(inputs: PackingInputs) -> tuple[PackingItem, ...]:
    """Collect the union of the selected ages, youngest first: essentials, then extras."""
    if inputs.who is not Who.KIDS:
        return ()
    items: list[PackingItem] = []
    for band in AgeBand:
        if band in inputs.age_bands:
            items += [item for item in BY_BAND[band] if item not in items]
    if inputs.stroller and is_rainy(inputs):
        items.append(PackingItem.PUSHCHAIR_RAIN_COVER)
    elif inputs.stroller and is_warm_and_clear(inputs):
        items.append(PackingItem.PUSHCHAIR_SUNSHADE)
    items.append(PackingItem.HAND_SANITISER)
    essentials = [item for item in items if item not in EXTRAS]
    extras = [item for item in items if item in EXTRAS]
    return tuple(_distinct_items(essentials + extras))


def _distinct_items(items: list[PackingItem]) -> list[PackingItem]:
    """Keep the first of each equivalence key (nappies include wipes, and so on)."""
    kept: list[PackingItem] = []
    keys: set[str] = set()
    for item in items:
        key = EQUIVALENCE.get(item, item.value)
        if key in keys:
            continue
        keys.add(key)
        kept.append(item)
    return kept


def snack_for(inputs: PackingInputs) -> Snack:
    if inputs.who is Who.SOLO:
        return Snack.SOLO
    if AgeBand.B0_2 in inputs.age_bands:
        return Snack.YOUNGEST
    if is_rainy(inputs):
        return Snack.RAIN
    if inputs.temp_min_c < COCOA_BELOW_C:
        return Snack.COLD
    if inputs.temp_max_c >= WARM_C:
        return Snack.WARM
    return Snack.MILD


def packing_list(inputs: PackingInputs) -> PackingList:
    """Build the list: weather first, then the little ones, then the ideas, capped at 10."""
    all_weather = _distinct_items(list(weather_items(inputs)))
    weather_keys = {EQUIVALENCE.get(item, item.value) for item in all_weather}
    little = tuple(
        item
        for item in little_ones_items(inputs)
        if EQUIVALENCE.get(item, item.value) not in weather_keys
    )
    taken = {EQUIVALENCE.get(item, item.value) for item in (*all_weather, *little)}
    ideas = _distinct_texts(inputs.idea_items, taken)
    room = MAX_ITEMS
    weather = tuple(all_weather[:room])
    room -= len(weather)
    little = little[:room]
    room -= len(little)
    ideas = ideas[:room]
    youngest = AgeBand.B0_2 in inputs.age_bands
    return PackingList(
        little_ones=little,
        weather=weather,
        ideas=ideas,
        snack=snack_for(inputs),
        sandwich=(
            inputs.who is Who.KIDS
            and not youngest
            and inputs.time_budget.value >= SANDWICH_FROM_MIN
        ),
    )


def _equivalence_key(text: str) -> str:
    """Key a catalogue item by the first whole word that names a listed need."""
    words: list[str] = _WORD.findall(text.casefold())
    for word in words:
        key = EQUIVALENCE_WORDS.get(word)
        if key is not None:
            return key
    return text.casefold()


def _distinct_texts(items: tuple[str, ...], taken: set[str]) -> tuple[str, ...]:
    """Keep catalogue items that are not equivalent to one already listed, in order."""
    kept: list[str] = []
    keys = set(taken)
    for item in items:
        text = item.strip()
        if not text:
            continue
        key = _equivalence_key(text)
        if key in keys:
            continue
        keys.add(key)
        kept.append(text)
    return tuple(kept)
