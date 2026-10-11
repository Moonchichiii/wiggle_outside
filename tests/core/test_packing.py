"""The "Before you go" rules (TC-012 part E): every rule, the union of ages, the cap."""

import dataclasses
from typing import Final

import pytest

from wiggle_outside.core.packing import (
    MAX_ITEMS,
    PackingInputs,
    PackingItem,
    Snack,
    packing_list,
)
from wiggle_outside.core.types import AgeBand, TimeBudget, WeatherCondition, Who

MILD: Final = PackingInputs(
    who=Who.KIDS,
    age_bands=frozenset({AgeBand.B3_5}),
    stroller=False,
    time_budget=TimeBudget.H1,
    condition=WeatherCondition.CLOUDY,
    temp_min_c=12,
    temp_max_c=14,
    precip_probability=10,
    wind_kmh=10,
)


def with_(**changes: object) -> PackingInputs:
    return dataclasses.replace(MILD, **changes)  # type: ignore[arg-type]


# --- The weather group ------------------------------------------------------------------------


def test_a_mild_dry_day_needs_nothing_for_the_weather() -> None:
    assert packing_list(MILD).weather == ()


@pytest.mark.parametrize(
    ("changes", "expected"),
    [
        ({"precip_probability": 40}, (PackingItem.WATERPROOF_JACKETS, PackingItem.WELLIES)),
        (
            {"condition": WeatherCondition.RAIN_LIKELY},
            (PackingItem.WATERPROOF_JACKETS, PackingItem.WELLIES),
        ),
        (
            {"condition": WeatherCondition.SNOW},
            (PackingItem.WATERPROOF_JACKETS, PackingItem.WELLIES),
        ),
        ({"temp_min_c": 9}, (PackingItem.WARM_LAYER,)),
        ({"temp_min_c": 4}, (PackingItem.WARM_LAYER, PackingItem.HATS_AND_GLOVES)),
        ({"wind_kmh": 25}, (PackingItem.WINDPROOF,)),
        (
            {"temp_max_c": 20, "condition": WeatherCondition.CLEAR},
            (PackingItem.SUN_HATS_AND_CREAM,),
        ),
        ({"temp_max_c": 20}, ()),  # warm but not clear: no sun items
        ({"temp_max_c": 24}, (PackingItem.EXTRA_WATER,)),
        (
            {"temp_max_c": 24, "condition": WeatherCondition.CLEAR},
            (PackingItem.SUN_HATS_AND_CREAM, PackingItem.EXTRA_WATER),
        ),
        (
            {"temp_min_c": 4, "temp_max_c": 24, "condition": WeatherCondition.CLEAR},
            (PackingItem.WARM_LAYER, PackingItem.HATS_AND_GLOVES, PackingItem.EXTRA_WATER),
        ),  # one hat item
    ],
)
def test_each_weather_rule(changes: dict[str, object], expected: tuple[PackingItem, ...]) -> None:
    assert packing_list(with_(**changes)).weather == expected


def test_the_weather_group_is_ordered_wet_cold_wind_sun() -> None:
    stormy = with_(precip_probability=80, temp_min_c=2, wind_kmh=40)
    # Windproof is equivalent to the waterproof jackets already listed, so it is not repeated.
    assert packing_list(stormy).weather == (
        PackingItem.WATERPROOF_JACKETS,
        PackingItem.WELLIES,
        PackingItem.WARM_LAYER,
        PackingItem.HATS_AND_GLOVES,
    )
    dry_and_windy = with_(temp_min_c=2, wind_kmh=40)
    assert packing_list(dry_and_windy).weather == (
        PackingItem.WARM_LAYER,
        PackingItem.HATS_AND_GLOVES,
        PackingItem.WINDPROOF,
    )


# --- The little ones ----------------------------------------------------------------------------


def test_the_union_of_ages_youngest_first_and_deduplicated() -> None:
    both_older = with_(age_bands=frozenset({AgeBand.B6_9, AgeBand.B10_12}))
    assert packing_list(both_older).little_ones == (
        PackingItem.OWN_BACKPACK,
        PackingItem.WATER_BOTTLE_EACH,
        PackingItem.HAND_SANITISER,
    )
    mixed = with_(age_bands=frozenset({AgeBand.B10_12, AgeBand.B0_2}))
    # Essentials first, the optional extra (the toy) last; no food item for the youngest.
    assert packing_list(mixed).little_ones == (
        PackingItem.NAPPIES,
        PackingItem.CHANGE_OF_CLOTHES,
        PackingItem.MUSLIN,
        PackingItem.OWN_BACKPACK,
        PackingItem.WATER_BOTTLE_EACH,
        PackingItem.HAND_SANITISER,
        PackingItem.SMALL_TOY,
    )


def test_equivalent_items_are_deduplicated_not_just_identical_strings() -> None:
    # Nappies include wipes; a 0-2 and a 3-5 together list nappies, never wipes as well.
    both = with_(age_bands=frozenset({AgeBand.B0_2, AgeBand.B3_5}))
    little = packing_list(both).little_ones
    assert PackingItem.NAPPIES in little
    assert PackingItem.WIPES not in little
    # Extra water and a water bottle each are one need: the weather group's wins.
    hot_older = with_(age_bands=frozenset({AgeBand.B6_9}), temp_max_c=26)
    built = packing_list(hot_older)
    assert PackingItem.EXTRA_WATER in built.weather
    assert PackingItem.WATER_BOTTLE_EACH not in built.little_ones
    # A catalogue item equivalent to a listed one is dropped too.
    with_bag = with_(idea_items=("a small bag for fallen leaves", "a stick"))
    assert packing_list(with_bag).ideas == ("a stick",)  # the treasure bag is already there
    # The catalogue's wellies against the weather group's wellies (seen on a fixture page).
    rainy_puddles = with_(
        precip_probability=60, idea_items=("wellies (or shoes that may get wet)", "a towel")
    )
    assert packing_list(rainy_puddles).ideas == ("a towel",)


def test_three_to_five_essentials_then_the_treasure_bag() -> None:
    assert packing_list(MILD).little_ones == (
        PackingItem.WIPES,
        PackingItem.SPARE_TROUSERS,
        PackingItem.HAND_SANITISER,
        PackingItem.TREASURE_BAG,
    )


def test_the_pushchair_cover_only_with_rain_and_the_sunshade_only_warm_and_clear() -> None:
    assert PackingItem.PUSHCHAIR_RAIN_COVER not in packing_list(with_(stroller=True)).little_ones
    rainy = with_(stroller=True, precip_probability=50)
    assert PackingItem.PUSHCHAIR_RAIN_COVER in packing_list(rainy).little_ones
    sunny = with_(stroller=True, temp_max_c=22, condition=WeatherCondition.CLEAR)
    assert PackingItem.PUSHCHAIR_SUNSHADE in packing_list(sunny).little_ones
    assert PackingItem.PUSHCHAIR_SUNSHADE not in packing_list(with_(temp_max_c=22)).little_ones
    assert (
        PackingItem.PUSHCHAIR_RAIN_COVER
        not in packing_list(with_(precip_probability=50)).little_ones
    )


def test_hand_sanitiser_closes_the_essentials_before_any_extra() -> None:
    for inputs in (MILD, with_(age_bands=frozenset({AgeBand.B0_2})), with_(stroller=True)):
        little = packing_list(inputs).little_ones
        essentials = [
            item for item in little if item not in {PackingItem.SMALL_TOY, PackingItem.TREASURE_BAG}
        ]
        assert essentials[-1] is PackingItem.HAND_SANITISER


# --- The ideas' items and the cap ---------------------------------------------------------------


def test_the_chosen_ideas_items_pass_through_deduplicated_in_order() -> None:
    inputs = with_(idea_items=("a small bag", "the printed card", "A small bag", "  ", "a stick"))
    # "a small bag" is equivalent to the treasure bag a 3-5 already has, so it goes.
    assert packing_list(inputs).ideas == ("the printed card", "a stick")


def test_at_most_ten_items_weather_first_then_the_little_ones_then_the_ideas() -> None:
    inputs = with_(
        age_bands=frozenset({AgeBand.B0_2, AgeBand.B3_5, AgeBand.B6_9}),
        stroller=True,
        precip_probability=90,
        temp_min_c=1,
        wind_kmh=30,
        idea_items=("a bag", "a card", "a stick"),
    )
    built = packing_list(inputs)
    assert built.count == MAX_ITEMS
    # jackets, wellies, warm layer, hats and gloves, windproof: windproof is equivalent to
    # the jackets, so four stay.
    assert built.weather == (
        PackingItem.WATERPROOF_JACKETS,
        PackingItem.WELLIES,
        PackingItem.WARM_LAYER,
        PackingItem.HATS_AND_GLOVES,
    )
    assert len(built.little_ones) == 6
    assert built.little_ones[0] is PackingItem.NAPPIES
    assert built.ideas == ()


# --- Snacks ------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("changes", "snack"),
    [
        ({}, Snack.MILD),
        ({"temp_min_c": 7}, Snack.COLD),
        ({"temp_max_c": 20}, Snack.WARM),
        ({"precip_probability": 60}, Snack.RAIN),
        ({"precip_probability": 60, "temp_max_c": 25}, Snack.RAIN),  # rain wins
        ({"who": Who.SOLO, "age_bands": frozenset()}, Snack.SOLO),
        ({"age_bands": frozenset({AgeBand.B0_2, AgeBand.B6_9}), "temp_max_c": 25}, Snack.YOUNGEST),
    ],
)
def test_the_snack_idea(changes: dict[str, object], snack: Snack) -> None:
    assert packing_list(with_(**changes)).snack is snack


def test_two_hours_or_more_adds_a_sandwich_unless_the_youngest_is_coming() -> None:
    assert packing_list(MILD).sandwich is False
    assert packing_list(with_(time_budget=TimeBudget.H2)).sandwich is True
    assert packing_list(with_(time_budget=TimeBudget.HALF_DAY)).sandwich is True
    youngest = with_(age_bands=frozenset({AgeBand.B0_2}), time_budget=TimeBudget.HALF_DAY)
    assert packing_list(youngest).sandwich is False


# --- Solo --------------------------------------------------------------------------------------


def test_solo_gets_only_the_weather_group_and_a_charged_phone() -> None:
    solo = with_(who=Who.SOLO, age_bands=frozenset(), stroller=True, precip_probability=70)
    built = packing_list(solo)
    assert built.little_ones == ()
    assert built.weather == (
        PackingItem.WATERPROOF_JACKETS,
        PackingItem.WELLIES,
        PackingItem.CHARGED_PHONE,
    )
    assert built.snack is Snack.SOLO
    assert built.sandwich is False
