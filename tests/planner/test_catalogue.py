"""The reviewed catalogue loads, and a drifted file is refused by entry name.

The acceptance list is CATALOGUE-REVIEW section 0: 26 entries, every kids' entry
daylight-only, no wind limit higher than the 8.19 review copy with `tree-twins` at 25,
the baby-eligible entries at 5 C or more, and the two removed entries absent. The rest of
the file is one broken fixture per validation rule, built as TOML strings here so the
reviewed files stay untouched.
"""

from pathlib import Path
from typing import TYPE_CHECKING, Final

import pytest

from wiggle_outside.core.types import CARD_ITEMS, AgeBand, Who
from wiggle_outside.planner.catalogue import (
    ACTIVITIES_FILE,
    HOOKS_FILE,
    CatalogueError,
    TomlCatalogue,
    load_catalogue,
    parse_catalogue,
)

if TYPE_CHECKING:
    from wiggle_outside.planner.ports import Catalogue

# --- Fixtures -----------------------------------------------------------------------

VALID_ACTIVITY: Final = """\
[[activity]]
id = "test-walk"
title = "Test walk"
who = "kids"
ages = ["3-5"]
energy = ["gentle"]
places = ["park"]
generic_ok = false
interests = ["colours"]
minutes = [15, 30]
rain_ok = true
max_rain_pct = 50
min_temp_c = 0
max_wind_kmh = 30
daylight = true
activity_suits_stroller = true
seasons = ["autumn"]
optional = []
steps = ["Walk to the park."]
adapt = "Listen instead of looking."
ask = "What did you see?"
safety = "Stay on paths."
"""

VALID_HOOKS: Final = """\
[[hook]]
id = "test-hook"
for = ["kids", "solo"]
needs_destination = true
text = "Today's mission is waiting for you there."

[[reason]]
id = "close_by"
when = "straight-line distance is 1 km or less"
text = "It's close by."
"""

NINE_ITEM_CARD: Final = (
    'card = ["one", "two", "three", "four", "five", "six", "seven", "eight", "nine"]\n'
)

# CATALOGUE-REVIEW section 2, W1: the limits as the 8.19 review copy had them. W1 is a
# cap that can only lower, so each entry must now be min(reviewed, 30).
REVIEW_WIND_LIMITS: Final[dict[str, int]] = {
    "leaf-colour-hunt": 40,
    "nature-bingo": 40,
    "track-detective": 40,
    "stick-houses": 35,
    "minibeast-safari": 35,
    "i-spy-far": 35,
    "brisk-loop": 45,
    "leaf-study-solo": 40,
    "tree-twins": 25,
    "sound-map": 30,
    "bark-rubbing": 30,
    "sit-spot": 30,
    "quick-sketch": 30,
}
W1_CAP: Final = 30
TREE_PLACE_KINDS: Final = frozenset({"forest", "nature_reserve"})
BABY_MIN_TEMP_C: Final = 5
BABY_ENTRIES: Final = 6
ENTRY_COUNT: Final = 26
KIDS_ENTRIES: Final = 19
SOLO_ENTRIES: Final = 7
HOOK_COUNT: Final = 8
REASON_COUNT: Final = 7


@pytest.fixture(scope="module")
def catalogue() -> TomlCatalogue:
    return load_catalogue()


def _swap(source: str, old: str, new: str) -> str:
    assert old in source, f"fixture does not contain {old!r}"
    return source.replace(old, new)


def _rejects(message: str, *, activities: str = VALID_ACTIVITY, hooks: str = VALID_HOOKS) -> None:
    """Every rejection has to name the entry as well as the rule."""
    with pytest.raises(CatalogueError, match=message):
        parse_catalogue(activities, hooks)


# --- The reviewed files (CATALOGUE-REVIEW section 0) --------------------------------


def test_the_reviewed_files_load(catalogue: TomlCatalogue) -> None:
    activities = catalogue.activities()
    assert len(activities) == ENTRY_COUNT
    assert sum(1 for entry in activities if entry.who is Who.KIDS) == KIDS_ENTRIES
    assert sum(1 for entry in activities if entry.who is Who.SOLO) == SOLO_ENTRIES
    assert len(catalogue.hooks()) == HOOK_COUNT
    assert len(catalogue.reasons()) == REASON_COUNT


def test_the_loader_satisfies_the_catalogue_port() -> None:
    port: Catalogue = load_catalogue()
    assert port.activities()
    assert port.hooks()
    assert port.reasons()


def test_the_packaged_files_are_the_reviewed_drafts(
    repo_root: Path, docs_dir: Path, catalogue: TomlCatalogue
) -> None:
    """The TOML files are protected inputs (D14): the package copy is byte-identical."""
    assert catalogue.activities(), "nothing loaded, so the comparison would prove nothing"
    package = repo_root / "src" / "wiggle_outside" / "planner"
    for name in (ACTIVITIES_FILE, HOOKS_FILE):
        shipped = (package / name).read_bytes()
        reviewed = (docs_dir / "drafts" / name).read_bytes()
        assert shipped == reviewed, f"{name} differs from the reviewed draft"


def test_every_kids_entry_is_daylight_only(catalogue: TomlCatalogue) -> None:
    """W4: daylight only for every kids' entry; a night run gets the fixed copy."""
    after_dark = [
        entry.activity_id
        for entry in catalogue.activities()
        if entry.who is Who.KIDS and not entry.daylight_only
    ]
    assert not after_dark


def test_no_wind_limit_is_higher_than_the_review_copy(catalogue: TomlCatalogue) -> None:
    limits = {entry.activity_id: entry.max_wind_kmh for entry in catalogue.activities()}
    for activity_id, reviewed in REVIEW_WIND_LIMITS.items():
        assert limits[activity_id] == min(reviewed, W1_CAP), activity_id


def test_tree_twins_stays_at_twenty_five(catalogue: TomlCatalogue) -> None:
    limits = {entry.activity_id: entry.max_wind_kmh for entry in catalogue.activities()}
    assert limits["tree-twins"] == 25


def test_every_forest_entry_caps_wind_at_thirty(catalogue: TomlCatalogue) -> None:
    too_high = [
        entry.activity_id
        for entry in catalogue.activities()
        if entry.place_kinds & TREE_PLACE_KINDS and entry.max_wind_kmh > W1_CAP
    ]
    assert not too_high


def test_baby_eligible_entries_need_five_degrees(catalogue: TomlCatalogue) -> None:
    """A1 x W3: option (b). Six entries list 0-2, and none goes below 5 C."""
    babies = [entry for entry in catalogue.activities() if AgeBand.B0_2 in entry.ages]
    assert len(babies) == BABY_ENTRIES
    assert all(entry.min_temp_c >= BABY_MIN_TEMP_C for entry in babies)


def test_the_removed_entries_are_absent(catalogue: TomlCatalogue) -> None:
    """W2: `shadow-play` and `cloud-stories` need a sky condition nothing reports."""
    ids = {entry.activity_id for entry in catalogue.activities()}
    assert "shadow-play" not in ids
    assert "cloud-stories" not in ids


def test_a1_babies_join_colour_match_and_nature_bingo(catalogue: TomlCatalogue) -> None:
    entries = {entry.activity_id: entry for entry in catalogue.activities()}
    for activity_id in ("colour-match", "nature-bingo"):
        entry = entries[activity_id]
        assert AgeBand.B0_2 in entry.ages
        assert "With a baby, the adult" in entry.safety


def test_a2_animal_walk_is_still_three_to_five_only(catalogue: TomlCatalogue) -> None:
    entries = {entry.activity_id: entry for entry in catalogue.activities()}
    assert entries["animal-walk"].ages == frozenset({AgeBand.B3_5})


def test_w4_five_senses_lost_its_after_dark_line(catalogue: TomlCatalogue) -> None:
    entries = {entry.activity_id: entry for entry in catalogue.activities()}
    five_senses = entries["five-senses"]
    assert five_senses.daylight_only
    assert "lit path" not in five_senses.safety


def test_x1_statues_adapts_for_mobility(catalogue: TomlCatalogue) -> None:
    entries = {entry.activity_id: entry for entry in catalogue.activities()}
    assert "any way of stopping counts" in entries["statues"].adapt


def test_h1_the_solo_hook_has_the_new_wording(catalogue: TomlCatalogue) -> None:
    hooks = {hook.hook_id: hook for hook in catalogue.hooks()}
    assert hooks["quick-escape"].text == "A small escape for right now."


def test_t1_quick_sketch_third_step_is_reworded(catalogue: TomlCatalogue) -> None:
    entries = {entry.activity_id: entry for entry in catalogue.activities()}
    assert entries["quick-sketch"].steps[2] == "Make three sketches of three different things."


# --- One broken fixture per validation rule -----------------------------------------


def test_the_fixtures_themselves_are_valid() -> None:
    parsed = parse_catalogue(VALID_ACTIVITY, VALID_HOOKS)
    assert parsed.activities()[0].activity_id == "test-walk"
    assert parsed.activities()[0].card == ()
    assert parsed.hooks()[0].hook_id == "test-hook"
    assert parsed.reasons()[0].reason_id == "close_by"


def test_an_unknown_activity_key_is_rejected() -> None:
    _rejects(
        "activity 'test-walk': unknown keys: cost",
        activities=_swap(VALID_ACTIVITY, 'title = "Test walk"', 'title = "Test walk"\ncost = 3'),
    )


def test_an_unknown_hook_key_is_rejected() -> None:
    _rejects(
        "hook 'test-hook': unknown keys: places",
        hooks=_swap(VALID_HOOKS, 'for = ["kids", "solo"]', 'for = ["kids", "solo"]\nplaces = []'),
    )


def test_an_unknown_top_level_table_is_rejected() -> None:
    _rejects(
        "hooks.toml: unknown top-level tables: tagline",
        hooks=VALID_HOOKS + '\n[[tagline]]\nid = "x"\ntext = "y"\n',
    )


def test_a_missing_key_is_rejected() -> None:
    _rejects(
        "activity 'test-walk': missing keys: safety",
        activities=_swap(VALID_ACTIVITY, 'safety = "Stay on paths."\n', ""),
    )


@pytest.mark.parametrize(
    ("old", "new", "message"),
    [
        ('ages = ["3-5"]', 'ages = ["13-15"]', "ages has unknown value '13-15'"),
        ('energy = ["gentle"]', 'energy = ["extreme"]', "energy has unknown value 'extreme'"),
        (
            'interests = ["colours"]',
            'interests = ["dinosaurs"]',
            "interests has unknown value 'dinosaurs'",
        ),
        ('seasons = ["autumn"]', 'seasons = ["monsoon"]', "seasons has unknown value 'monsoon'"),
        ('who = "kids"', 'who = "grownups"', "who has unknown value 'grownups'"),
    ],
)
def test_a_value_outside_an_enum_is_rejected(old: str, new: str, message: str) -> None:
    _rejects(f"activity 'test-walk': {message}", activities=_swap(VALID_ACTIVITY, old, new))


def test_a_max_energy_outside_the_enum_is_rejected() -> None:
    _rejects(
        "hook 'test-hook': max_energy has unknown value 'calm'",
        hooks=_swap(
            VALID_HOOKS, 'for = ["kids", "solo"]', 'for = ["kids", "solo"]\nmax_energy = "calm"'
        ),
    )


@pytest.mark.parametrize("tags", ["[]", '["colours", "trees", "sky", "quiet"]'])
def test_interests_outside_one_to_three_tags_are_rejected(tags: str) -> None:
    _rejects(
        "activity 'test-walk': interests must be 1-3 tags",
        activities=_swap(VALID_ACTIVITY, 'interests = ["colours"]', f"interests = {tags}"),
    )


def test_a_repeated_interest_tag_is_rejected() -> None:
    _rejects(
        "activity 'test-walk': interests repeats a tag",
        activities=_swap(
            VALID_ACTIVITY, 'interests = ["colours"]', 'interests = ["colours", "colours"]'
        ),
    )


def test_a_card_that_is_not_nine_items_is_rejected() -> None:
    eight = 'card = ["one", "two", "three", "four", "five", "six", "seven", "eight"]\n'
    _rejects(
        f"activity 'test-walk': card must be absent or exactly {CARD_ITEMS} items, got 8",
        activities=VALID_ACTIVITY + eight,
    )


def test_a_nine_item_card_is_accepted() -> None:
    parsed = parse_catalogue(VALID_ACTIVITY + NINE_ITEM_CARD, VALID_HOOKS)
    assert len(parsed.activities()[0].card) == CARD_ITEMS


@pytest.mark.parametrize(
    "text",
    [
        "A mission at {place} is waiting.",
        "A mission at %s is waiting.",
        "A mission at $place is waiting.",
    ],
)
def test_a_hook_with_a_placeholder_is_rejected(text: str) -> None:
    _rejects(
        "hook 'test-hook': a hook is a fixed sentence",
        hooks=_swap(VALID_HOOKS, "Today's mission is waiting for you there.", text),
    )


def test_generic_ok_without_any_places_is_rejected() -> None:
    _rejects(
        "activity 'test-walk': generic_ok = true needs places = \\[\"any\"\\]",
        activities=_swap(VALID_ACTIVITY, "generic_ok = false", "generic_ok = true"),
    )


def test_a_hook_that_both_needs_and_forbids_a_destination_is_rejected() -> None:
    _rejects(
        "hook 'test-hook': needs_destination and generic_only cannot both be true",
        hooks=_swap(
            VALID_HOOKS, "needs_destination = true", "needs_destination = true\ngeneric_only = true"
        ),
    )


def test_a_hook_that_declares_no_destination_stance_is_rejected() -> None:
    _rejects(
        "hook 'test-hook': set needs_destination or generic_only",
        hooks=_swap(VALID_HOOKS, "needs_destination = true\n", ""),
    )


@pytest.mark.parametrize("kind", ["beach", "viewpoint"])
def test_a_place_kind_outside_v1_is_rejected(kind: str) -> None:
    _rejects(
        f"activity 'test-walk': places outside v1: {kind}",
        activities=_swap(VALID_ACTIVITY, 'places = ["park"]', f'places = ["{kind}"]'),
    )


def test_any_mixed_with_a_specific_place_kind_is_rejected() -> None:
    _rejects(
        "activity 'test-walk': places mixes \"any\" with a specific kind",
        activities=_swap(VALID_ACTIVITY, 'places = ["park"]', 'places = ["any", "park"]'),
    )


def test_a_duplicate_activity_id_is_rejected() -> None:
    _rejects("activity 'test-walk': duplicate id", activities=VALID_ACTIVITY * 2)


def test_a_duplicate_hook_id_is_rejected() -> None:
    _rejects("hook 'test-hook': duplicate id", hooks=VALID_HOOKS + VALID_HOOKS.split("\n\n")[0])


def test_a_duplicate_reason_id_is_rejected() -> None:
    _rejects("reason 'close_by': duplicate id", hooks=VALID_HOOKS + VALID_HOOKS.split("\n\n")[1])


@pytest.mark.parametrize(
    ("minutes", "message"),
    [
        ("[15]", r"minutes must be \[min, max\], got 1 value"),
        ("[15, 20, 25]", r"minutes must be \[min, max\], got 3 value"),
        ("[30, 15]", r"minutes must ascend, got \[30, 15\]"),
        ("[0, 30]", "minutes must be positive, got 0"),
    ],
)
def test_minutes_that_is_not_an_ascending_pair_is_rejected(minutes: str, message: str) -> None:
    _rejects(
        f"activity 'test-walk': {message}",
        activities=_swap(VALID_ACTIVITY, "minutes = [15, 30]", f"minutes = {minutes}"),
    )


@pytest.mark.parametrize(
    ("old", "new", "message"),
    [
        ('energy = ["gentle"]', "energy = []", "energy must list at least one level"),
        ('places = ["park"]', "places = []", "places must name at least one kind"),
    ],
)
def test_an_empty_list_where_one_value_is_needed_is_rejected(
    old: str, new: str, message: str
) -> None:
    _rejects(f"activity 'test-walk': {message}", activities=_swap(VALID_ACTIVITY, old, new))


@pytest.mark.parametrize(
    ("old", "new", "message"),
    [
        ('for = ["kids", "solo"]', "for = []", "for must name at least one audience"),
        ("Today's mission is waiting for you there.", "   ", "text must not be blank"),
    ],
)
def test_an_empty_hook_field_is_rejected(old: str, new: str, message: str) -> None:
    _rejects(f"hook 'test-hook': {message}", hooks=_swap(VALID_HOOKS, old, new))


@pytest.mark.parametrize(
    ("document", "message"),
    [
        ('activity = "test-walk"', "activity: must be a list of tables"),
        ('activity = ["test-walk"]', "activity #1: must be a table"),
    ],
)
def test_an_entry_list_that_holds_no_tables_is_rejected(document: str, message: str) -> None:
    _rejects(message, activities=document)


@pytest.mark.parametrize(
    ("old", "new"),
    [
        ('who = "kids"\nages = ["3-5"]', 'who = "solo"\nages = ["3-5"]'),
        ('ages = ["3-5"]', "ages = []"),
    ],
)
def test_who_and_ages_must_agree(old: str, new: str) -> None:
    _rejects(
        "activity 'test-walk': a kids entry lists age bands and a solo entry lists none",
        activities=_swap(VALID_ACTIVITY, old, new),
    )


def test_a_solo_entry_with_a_kids_question_is_rejected() -> None:
    solo = _swap(VALID_ACTIVITY, 'who = "kids"\nages = ["3-5"]', 'who = "solo"\nages = []')
    _rejects("activity 'test-walk': ask is for kids entries only", activities=solo)


def test_blank_text_the_card_renders_is_rejected() -> None:
    _rejects(
        "activity 'test-walk': text rendered verbatim must not be blank: title",
        activities=_swap(VALID_ACTIVITY, 'title = "Test walk"', 'title = "  "'),
    )


def test_an_entry_with_no_steps_is_rejected() -> None:
    _rejects(
        "activity 'test-walk': steps must not be empty",
        activities=_swap(VALID_ACTIVITY, 'steps = ["Walk to the park."]', "steps = []"),
    )


def test_a_blank_id_is_rejected_and_the_entry_named_by_position() -> None:
    _rejects(
        "activity #1: id must not be blank",
        activities=_swap(VALID_ACTIVITY, 'id = "test-walk"', 'id = ""'),
    )


@pytest.mark.parametrize(
    ("old", "new", "message"),
    [
        ("max_wind_kmh = 30", 'max_wind_kmh = "thirty"', "max_wind_kmh must be a whole number"),
        ("max_wind_kmh = 30", "max_wind_kmh = true", "max_wind_kmh must be a whole number"),
        ("rain_ok = true", 'rain_ok = "yes"', "rain_ok must be true or false"),
        ('steps = ["Walk to the park."]', 'steps = "Walk."', "steps must be a list"),
        ('adapt = "Listen instead of looking."', "adapt = 3", "adapt must be a string"),
        ("minutes = [15, 30]", 'minutes = ["15", "30"]', r"minutes\[0\] must be a whole number"),
        ("optional = []", "optional = [3]", r"optional\[0\] must be a string"),
    ],
)
def test_a_value_of_the_wrong_type_is_rejected(old: str, new: str, message: str) -> None:
    _rejects(f"activity 'test-walk': {message}", activities=_swap(VALID_ACTIVITY, old, new))


def test_a_file_that_is_not_toml_is_rejected() -> None:
    _rejects(f"{ACTIVITIES_FILE}: is not valid TOML", activities="[[activity]\nid = 'x'\n")


def test_a_file_with_no_entries_is_rejected() -> None:
    _rejects("activity: the file has no entries", activities="")
