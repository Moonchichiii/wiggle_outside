"""`Activity` and `Hook` must cover every key the catalogue actually uses.

CONTRACTS section 2 used to say only "catalogue fields as in drafts/activities.toml",
and the types were written from that sentence instead of from the file. Six Activity
fields and three Hook fields were missing as a result (CC-002, CC-003). These tests parse
the real TOML, so prose can no longer stand in for the shape.

The drafts are the source Mats reviewed (D14). WP2 will load the same keys from
planner/activities.toml and planner/hooks.toml.
"""

import tomllib
from dataclasses import fields
from pathlib import Path
from typing import Any, Final

import pytest

from wiggle_outside.core.types import Activity, Hook, Reason

pytestmark = pytest.mark.contract

# TOML key -> the dataclass field that carries it, where the names differ on purpose.
ACTIVITY_ALIASES: Final[dict[str, str]] = {
    "id": "activity_id",
    "places": "place_kinds",
    "daylight": "daylight_only",
    # minutes = [min, max] becomes two int fields, so the clamp is expressible.
    "minutes": "minutes_min",
}
HOOK_ALIASES: Final[dict[str, str]] = {"id": "hook_id", "for": "for_who"}
REASON_ALIASES: Final[dict[str, str]] = {"id": "reason_id"}


def _load(docs_dir: Path, name: str) -> dict[str, Any]:
    with (docs_dir / "drafts" / name).open("rb") as handle:
        data: dict[str, Any] = tomllib.load(handle)
    return data


def _field_names(cls: type) -> set[str]:
    return {f.name for f in fields(cls)}


def _covered(keys: set[str], cls: type, aliases: dict[str, str]) -> set[str]:
    """Return the TOML keys that no field of `cls` carries."""
    names = _field_names(cls)
    return {key for key in keys if aliases.get(key, key) not in names}


def test_activity_covers_every_catalogue_key(docs_dir: Path) -> None:
    entries = _load(docs_dir, "activities.toml")["activity"]
    assert entries, "no activities parsed"
    keys = {key for entry in entries for key in entry}
    missing = _covered(keys, Activity, ACTIVITY_ALIASES)
    assert not missing, f"Activity is missing catalogue keys: {sorted(missing)}"


def test_activity_has_no_field_the_catalogue_never_sets(docs_dir: Path) -> None:
    entries = _load(docs_dir, "activities.toml")["activity"]
    keys = {key for entry in entries for key in entry}
    carried = {ACTIVITY_ALIASES.get(key, key) for key in keys}
    # minutes feeds two fields. card and max_temp_c are keys the catalogue header
    # documents as optional, and no entry in the reviewed draft happens to set
    # max_temp_c - the field still has to exist for the ones that will.
    carried |= {"minutes_max", "card", "max_temp_c"}
    extra = _field_names(Activity) - carried
    assert not extra, f"Activity has fields the catalogue never sets: {sorted(extra)}"


def test_hook_covers_every_hook_key(docs_dir: Path) -> None:
    hooks = _load(docs_dir, "hooks.toml")["hook"]
    assert hooks, "no hooks parsed"
    keys = {key for hook in hooks for key in hook}
    missing = _covered(keys, Hook, HOOK_ALIASES)
    assert not missing, f"Hook is missing keys: {sorted(missing)}"


def test_reason_covers_every_reason_key(docs_dir: Path) -> None:
    reasons = _load(docs_dir, "hooks.toml")["reason"]
    assert reasons, "no reasons parsed"
    keys = {key for reason in reasons for key in reason}
    missing = _covered(keys, Reason, REASON_ALIASES)
    assert not missing, f"Reason is missing keys: {sorted(missing)}"


def test_the_hook_flags_that_gate_a_pair_exist(docs_dir: Path) -> None:
    # PLAN section 3 needs all three to derive a pair's allowed_hook_ids.
    hooks = _load(docs_dir, "hooks.toml")["hook"]
    assert any(hook.get("needs_destination") for hook in hooks)
    assert {"needs_destination", "generic_only", "max_energy"} <= _field_names(Hook)


def test_minutes_is_a_two_element_range_everywhere(docs_dir: Path) -> None:
    # Activity.minutes_min / minutes_max only make sense if the TOML is always a pair.
    for entry in _load(docs_dir, "activities.toml")["activity"]:
        minutes = entry["minutes"]
        assert len(minutes) == 2, f"{entry['id']}: minutes is not [min, max]"
        assert minutes[0] <= minutes[1], f"{entry['id']}: minutes range is inverted"
