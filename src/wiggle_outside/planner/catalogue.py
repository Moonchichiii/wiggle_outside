"""Loads and strictly validates the two reviewed catalogue files.

`activities.toml` and `hooks.toml` are protected inputs: Mats reviewed them line by line
(D14, CATALOGUE-REVIEW section 0) and this module never alters their text. It refuses to
load a file that has drifted from the shape CONTRACTS section 2 states, and every
rejection names the entry it is about. Importing the module has no side effects; reading
the files happens in `load_catalogue`.
"""

import re
import tomllib
from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from functools import cache
from importlib import resources
from typing import Final, NoReturn

from wiggle_outside.core.places import ANY_PLACE_KIND
from wiggle_outside.core.types import (
    CARD_ITEMS,
    MAX_TAGS,
    Activity,
    AgeBand,
    Energy,
    Hook,
    InterestTag,
    Reason,
    Season,
    Who,
)

PACKAGE: Final = "wiggle_outside.planner"
ACTIVITIES_FILE: Final = "activities.toml"
HOOKS_FILE: Final = "hooks.toml"

# PLAN section 3: the five OSM kinds v1 asks Overpass for, plus "any". Viewpoints and
# beaches are out of v1 (heights and water edges), so an entry naming one is a mistake.
PLACE_KINDS: Final = frozenset(
    {"park", "playground", "nature_reserve", "forest", "picnic_site", ANY_PLACE_KIND}
)

MIN_INTERESTS: Final = 1
MINUTES_LEN: Final = 2

ACTIVITY_REQUIRED: Final = frozenset(
    {
        "id",
        "title",
        "who",
        "ages",
        "energy",
        "places",
        "generic_ok",
        "interests",
        "minutes",
        "rain_ok",
        "max_rain_pct",
        "min_temp_c",
        "max_wind_kmh",
        "daylight",
        "activity_suits_stroller",
        "seasons",
        "optional",
        "steps",
        "adapt",
        "ask",
        "safety",
    }
)
ACTIVITY_OPTIONAL: Final = frozenset({"card", "max_temp_c"})
HOOK_REQUIRED: Final = frozenset({"id", "for", "text"})
HOOK_OPTIONAL: Final = frozenset({"needs_destination", "generic_only", "max_energy"})
REASON_REQUIRED: Final = frozenset({"id", "when", "text"})
NOTICE_REQUIRED: Final = frozenset({"id", "text"})
ACTIVITY_TABLES: Final = frozenset({"activity"})
HOOK_TABLES: Final = frozenset({"hook", "reason", "derived_reason", "notice"})

# Hooks are fixed sentences (8.12), so no brace, printf or shell-style placeholder.
PLACEHOLDER: Final = re.compile(r"[{}]|%[A-Za-z]|\$")


class CatalogueError(ValueError):
    """A catalogue file does not match the contract. The message names the entry."""


@dataclass(frozen=True, slots=True)
class TomlCatalogue:
    """The reviewed catalogue, parsed and validated once. Satisfies the Catalogue port."""

    activity_entries: tuple[Activity, ...]
    hook_entries: tuple[Hook, ...]
    reason_entries: tuple[Reason, ...]

    def activities(self) -> tuple[Activity, ...]:
        return self.activity_entries

    def hooks(self) -> tuple[Hook, ...]:
        return self.hook_entries

    def reasons(self) -> tuple[Reason, ...]:
        return self.reason_entries


def parse_catalogue(activities_toml: str, hooks_toml: str) -> TomlCatalogue:
    """Validate both files from their text and return the catalogue, or raise."""
    activities_doc = _document(activities_toml, ACTIVITIES_FILE)
    _check_tables(activities_doc, ACTIVITY_TABLES, ACTIVITIES_FILE)
    hooks_doc = _document(hooks_toml, HOOKS_FILE)
    _check_tables(hooks_doc, HOOK_TABLES, HOOKS_FILE)
    _check_unexposed_tables(hooks_doc)
    return TomlCatalogue(
        activity_entries=_parse_activities(activities_doc),
        hook_entries=_parse_hooks(hooks_doc),
        reason_entries=_parse_reasons(hooks_doc),
    )


@cache
def load_catalogue() -> TomlCatalogue:
    """Load the files shipped beside this module. They never change while running."""
    files = resources.files(PACKAGE)
    return parse_catalogue(
        files.joinpath(ACTIVITIES_FILE).read_text(encoding="utf-8"),
        files.joinpath(HOOKS_FILE).read_text(encoding="utf-8"),
    )


def _fail(where: str, detail: str) -> NoReturn:
    msg = f"{where}: {detail}"
    raise CatalogueError(msg)


@dataclass(frozen=True, slots=True)
class _Reader:
    """Reads one TOML table, refusing any value that is not the declared type."""

    where: str
    data: Mapping[str, object]

    def text(self, key: str) -> str:
        value = self.data.get(key)
        if not isinstance(value, str):
            _fail(self.where, f"{key} must be a string")
        return value

    def flag(self, key: str, *, default: bool | None = None) -> bool:
        value = self.data.get(key, default)
        if not isinstance(value, bool):
            _fail(self.where, f"{key} must be true or false")
        return value

    def whole(self, key: str) -> int:
        return _whole(self.where, key, self.data.get(key))

    def optional_whole(self, key: str) -> int | None:
        return self.whole(key) if key in self.data else None

    def texts(self, key: str) -> tuple[str, ...]:
        return tuple(
            _item_text(self.where, key, index, item) for index, item in enumerate(self._items(key))
        )

    def wholes(self, key: str) -> tuple[int, ...]:
        return tuple(
            _whole(self.where, f"{key}[{index}]", item)
            for index, item in enumerate(self._items(key))
        )

    def _items(self, key: str) -> tuple[object, ...]:
        value = self.data.get(key)
        if not isinstance(value, list):
            _fail(self.where, f"{key} must be a list")
        return tuple(value)


def _document(text: str, name: str) -> Mapping[str, object]:
    try:
        document: dict[str, object] = tomllib.loads(text)
    except tomllib.TOMLDecodeError as error:
        _fail(name, f"is not valid TOML: {error}")
    return document


def _check_tables(doc: Mapping[str, object], known: frozenset[str], name: str) -> None:
    unknown = sorted(set(doc) - known)
    if unknown:
        _fail(name, f"unknown top-level tables: {', '.join(unknown)}")


def _tables(
    doc: Mapping[str, object], key: str, *, required: bool = True
) -> tuple[Mapping[str, object], ...]:
    value = doc.get(key)
    if value is None:
        if required:
            _fail(key, "the file has no entries")
        return ()
    if not isinstance(value, list):
        _fail(key, "must be a list of tables")
    return tuple(_table(key, index, item) for index, item in enumerate(value))


def _table(key: str, index: int, item: object) -> Mapping[str, object]:
    if not isinstance(item, dict):
        _fail(f"{key} #{index + 1}", "must be a table")
    return item


def _label(kind: str, index: int, table: Mapping[str, object]) -> str:
    """Name the entry by its id when it has one, otherwise by its position."""
    value = table.get("id")
    if isinstance(value, str) and value:
        return f"{kind} {value!r}"
    return f"{kind} #{index + 1}"


def _readers(doc: Mapping[str, object], kind: str) -> tuple[_Reader, ...]:
    return tuple(
        _Reader(_label(kind, index, table), table) for index, table in enumerate(_tables(doc, kind))
    )


def _whole(where: str, key: str, value: object) -> int:
    # TOML booleans arrive as Python ints, so a flag in a number's place must be refused.
    if isinstance(value, bool) or not isinstance(value, int):
        _fail(where, f"{key} must be a whole number")
    return value


def _item_text(where: str, key: str, index: int, item: object) -> str:
    if not isinstance(item, str):
        _fail(where, f"{key}[{index}] must be a string")
    return item


def _as_enum[E: StrEnum](enum: type[E], value: str, where: str, key: str) -> E:
    members = tuple(enum)
    for member in members:
        if member.value == value:
            return member
    allowed = ", ".join(member.value for member in members)
    _fail(where, f"{key} has unknown value {value!r}; allowed: {allowed}")


def _check_keys(reader: _Reader, required: frozenset[str], optional: frozenset[str]) -> None:
    unknown = sorted(set(reader.data) - required - optional)
    if unknown:
        _fail(reader.where, f"unknown keys: {', '.join(unknown)}")
    missing = sorted(required - set(reader.data))
    if missing:
        _fail(reader.where, f"missing keys: {', '.join(missing)}")


def _check_unique(kind: str, ids: tuple[str, ...]) -> None:
    seen: set[str] = set()
    for value in ids:
        if value in seen:
            _fail(f"{kind} {value!r}", "duplicate id")
        seen.add(value)


def _identifier(reader: _Reader) -> str:
    value = reader.text("id")
    if not value.strip():
        _fail(reader.where, "id must not be blank")
    return value


def _parse_activities(doc: Mapping[str, object]) -> tuple[Activity, ...]:
    entries = tuple(_activity(reader) for reader in _readers(doc, "activity"))
    _check_unique("activity", tuple(entry.activity_id for entry in entries))
    return entries


def _activity(reader: _Reader) -> Activity:
    _check_keys(reader, ACTIVITY_REQUIRED, ACTIVITY_OPTIONAL)
    who = _as_enum(Who, reader.text("who"), reader.where, "who")
    minutes_min, minutes_max = _minutes(reader)
    activity = Activity(
        activity_id=_identifier(reader),
        title=reader.text("title"),
        who=who,
        ages=_ages(reader, who),
        energy=_energy(reader),
        place_kinds=_places(reader),
        generic_ok=reader.flag("generic_ok"),
        interests=_interests(reader),
        minutes_min=minutes_min,
        minutes_max=minutes_max,
        rain_ok=reader.flag("rain_ok"),
        max_rain_pct=reader.whole("max_rain_pct"),
        min_temp_c=reader.whole("min_temp_c"),
        max_wind_kmh=reader.whole("max_wind_kmh"),
        max_temp_c=reader.optional_whole("max_temp_c"),
        daylight_only=reader.flag("daylight"),
        activity_suits_stroller=reader.flag("activity_suits_stroller"),
        seasons=_seasons(reader),
        optional=reader.texts("optional"),
        steps=reader.texts("steps"),
        adapt=reader.text("adapt"),
        ask=_ask(reader, who),
        safety=reader.text("safety"),
        card=_card(reader),
    )
    _check_activity(activity, reader.where)
    return activity


def _minutes(reader: _Reader) -> tuple[int, int]:
    values = reader.wholes("minutes")
    if len(values) != MINUTES_LEN:
        _fail(reader.where, f"minutes must be [min, max], got {len(values)} value(s)")
    low, high = values
    if low <= 0:
        _fail(reader.where, f"minutes must be positive, got {low}")
    if low > high:
        _fail(reader.where, f"minutes must ascend, got [{low}, {high}]")
    return low, high


def _ages(reader: _Reader, who: Who) -> frozenset[AgeBand]:
    bands = frozenset(
        _as_enum(AgeBand, value, reader.where, "ages") for value in reader.texts("ages")
    )
    if (who is Who.KIDS) != bool(bands):
        _fail(reader.where, "a kids entry lists age bands and a solo entry lists none")
    return bands


def _energy(reader: _Reader) -> frozenset[Energy]:
    levels = frozenset(
        _as_enum(Energy, value, reader.where, "energy") for value in reader.texts("energy")
    )
    if not levels:
        _fail(reader.where, "energy must list at least one level")
    return levels


def _seasons(reader: _Reader) -> frozenset[Season]:
    # An empty list is the all-year case (D30), so only the values are checked.
    return frozenset(
        _as_enum(Season, value, reader.where, "seasons") for value in reader.texts("seasons")
    )


def _places(reader: _Reader) -> frozenset[str]:
    kinds = reader.texts("places")
    if not kinds:
        _fail(reader.where, "places must name at least one kind")
    outside = sorted(set(kinds) - PLACE_KINDS)
    if outside:
        allowed = ", ".join(sorted(PLACE_KINDS))
        _fail(reader.where, f"places outside v1: {', '.join(outside)}; allowed: {allowed}")
    if ANY_PLACE_KIND in kinds and len(set(kinds)) > 1:
        _fail(reader.where, f'places mixes "{ANY_PLACE_KIND}" with a specific kind')
    return frozenset(kinds)


def _interests(reader: _Reader) -> tuple[InterestTag, ...]:
    values = reader.texts("interests")
    if not MIN_INTERESTS <= len(values) <= MAX_TAGS:
        _fail(
            reader.where,
            f"interests must be {MIN_INTERESTS}-{MAX_TAGS} tags, got {len(values)}",
        )
    tags = tuple(_as_enum(InterestTag, value, reader.where, "interests") for value in values)
    if len(set(tags)) != len(tags):
        _fail(reader.where, "interests repeats a tag")
    return tags


def _ask(reader: _Reader, who: Who) -> str | None:
    text = reader.text("ask")
    if who is Who.SOLO and text:
        _fail(reader.where, "ask is for kids entries only")
    return text or None


def _card(reader: _Reader) -> tuple[str, ...]:
    items = reader.texts("card") if "card" in reader.data else ()
    if items and len(items) != CARD_ITEMS:
        _fail(reader.where, f"card must be absent or exactly {CARD_ITEMS} items, got {len(items)}")
    return items


def _check_activity(activity: Activity, where: str) -> None:
    """Rules that read more than one field of the finished entry."""
    if activity.generic_ok and ANY_PLACE_KIND not in activity.place_kinds:
        _fail(where, f'generic_ok = true needs places = ["{ANY_PLACE_KIND}"]')
    blank = tuple(
        name
        for name, value in (
            ("title", activity.title),
            ("adapt", activity.adapt),
            ("safety", activity.safety),
        )
        if not value.strip()
    )
    if blank:
        _fail(where, f"text rendered verbatim must not be blank: {', '.join(blank)}")
    if not activity.steps:
        _fail(where, "steps must not be empty")


def _parse_hooks(doc: Mapping[str, object]) -> tuple[Hook, ...]:
    hooks = tuple(_hook(reader) for reader in _readers(doc, "hook"))
    _check_unique("hook", tuple(hook.hook_id for hook in hooks))
    return hooks


def _hook(reader: _Reader) -> Hook:
    _check_keys(reader, HOOK_REQUIRED, HOOK_OPTIONAL)
    hook = Hook(
        hook_id=_identifier(reader),
        text=_hook_text(reader),
        for_who=_who_set(reader),
        needs_destination=reader.flag("needs_destination", default=False),
        generic_only=reader.flag("generic_only", default=False),
        max_energy=_max_energy(reader),
    )
    _check_hook(hook, reader.where)
    return hook


def _hook_text(reader: _Reader) -> str:
    text = reader.text("text")
    if not text.strip():
        _fail(reader.where, "text must not be blank")
    found = PLACEHOLDER.search(text)
    if found is not None:
        _fail(reader.where, f"a hook is a fixed sentence; text holds {found.group()!r}")
    return text


def _who_set(reader: _Reader) -> frozenset[Who]:
    values = reader.texts("for")
    if not values:
        _fail(reader.where, "for must name at least one audience")
    return frozenset(_as_enum(Who, value, reader.where, "for") for value in values)


def _max_energy(reader: _Reader) -> Energy | None:
    if "max_energy" not in reader.data:
        return None
    return _as_enum(Energy, reader.text("max_energy"), reader.where, "max_energy")


def _check_hook(hook: Hook, where: str) -> None:
    """Every hook states one destination stance, so a pair can gate it (CC-003)."""
    if hook.needs_destination and hook.generic_only:
        _fail(where, "needs_destination and generic_only cannot both be true")
    if not (hook.needs_destination or hook.generic_only):
        _fail(where, "set needs_destination or generic_only: a hook declares one")


def _parse_reasons(doc: Mapping[str, object]) -> tuple[Reason, ...]:
    reasons = tuple(_reason(reader) for reader in _readers(doc, "reason"))
    _check_unique("reason", tuple(reason.reason_id for reason in reasons))
    return reasons


def _reason(reader: _Reader) -> Reason:
    _check_keys(reader, REASON_REQUIRED, frozenset())
    return Reason(
        reason_id=_identifier(reader),
        when=reader.text("when"),
        text=reader.text("text"),
    )


def _check_unexposed_tables(doc: Mapping[str, object]) -> None:
    """`derived_reason` and `notice` are code's own copy, so only validate them here."""
    for kind, required in (("derived_reason", REASON_REQUIRED), ("notice", NOTICE_REQUIRED)):
        tables = _tables(doc, kind, required=False)
        readers = tuple(
            _Reader(_label(kind, index, table), table) for index, table in enumerate(tables)
        )
        for reader in readers:
            _check_keys(reader, required, frozenset())
            _identifier(reader)
            reader.text("text")
        _check_unique(kind, tuple(_identifier(reader) for reader in readers))
