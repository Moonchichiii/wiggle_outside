"""The model output schemas (CONTRACTS section 6): valid and invalid fixtures.

core.ideas re-validates everything anyway, so these tests check the schema is the one the
document specifies, not that the model behaves.
"""

import json
from pathlib import Path
from typing import Any, Final

import pytest
from jsonschema import Draft202012Validator
from jsonschema.exceptions import ValidationError

from wiggle_outside.core.types import MAX_IDEAS, MAX_REASONS, MAX_TAGS, InterestTag

pytestmark = pytest.mark.contract

SCHEMA_DIR: Final = (
    Path(__file__).resolve().parents[2] / "src" / "wiggle_outside" / "planner" / "schema"
)


def _schema(name: str) -> dict[str, Any]:
    data: dict[str, Any] = json.loads((SCHEMA_DIR / name).read_text(encoding="utf-8"))
    return data


@pytest.fixture(scope="module")
def v1() -> Draft202012Validator:
    schema = _schema("selection.v1.json")
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema)


@pytest.fixture(scope="module")
def v2() -> Draft202012Validator:
    schema = _schema("selection.v2.json")
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema)


PICK: Final[dict[str, Any]] = {
    "pair_id": "p3",
    "hook_id": "leaf-hunt",
    "reason_ids": ["fits_time", "matches_energy"],
}


def test_v1_accepts_picks_only(v1: Draft202012Validator) -> None:
    v1.validate({"picks": [PICK]})


def test_v1_rejects_v2_fields(v1: Draft202012Validator) -> None:
    # v1 is the D39-declined shape: interests are not part of it.
    with pytest.raises(ValidationError):
        v1.validate({"picks": [PICK], "interests": ["birds"]})


def test_v2_accepts_a_matched_selection(v2: Draft202012Validator) -> None:
    v2.validate(
        {
            "interests": ["birds", "puddles"],
            "interest_status": "matched",
            "picks": [PICK],
        }
    )


def test_v2_accepts_an_empty_selection(v2: Draft202012Validator) -> None:
    # No valid pick is a legitimate answer; the planner then falls back (D44).
    v2.validate({"interests": [], "interest_status": "no_match", "picks": []})


@pytest.mark.parametrize(
    "document",
    [
        pytest.param({"interest_status": "matched", "picks": []}, id="interests-missing"),
        pytest.param({"interests": [], "picks": []}, id="status-missing"),
        pytest.param({"interests": [], "interest_status": "matched"}, id="picks-missing"),
        pytest.param(
            {"interests": ["dinosaurs"], "interest_status": "matched", "picks": []},
            id="tag-outside-vocabulary",
        ),
        pytest.param(
            {"interests": ["birds", "birds"], "interest_status": "matched", "picks": []},
            id="duplicate-tags",
        ),
        pytest.param(
            {
                "interests": ["birds", "bugs", "sky", "trees"],
                "interest_status": "matched",
                "picks": [],
            },
            id="too-many-tags",
        ),
        pytest.param(
            {"interests": [], "interest_status": "maybe", "picks": []},
            id="status-outside-enum",
        ),
        pytest.param(
            {"interests": [], "interest_status": "matched", "picks": [PICK] * 4},
            id="too-many-picks",
        ),
        pytest.param(
            {
                "interests": [],
                "interest_status": "matched",
                "picks": [PICK | {"matches_interest": True}],
            },
            id="model-supplied-matches-interest",
        ),
        pytest.param(
            {
                "interests": [],
                "interest_status": "matched",
                "picks": [PICK | {"reason_ids": ["a", "b", "c"]}],
            },
            id="too-many-reasons",
        ),
        pytest.param(
            {"interests": [], "interest_status": "matched", "picks": [PICK], "note": "x"},
            id="extra-top-level-field",
        ),
    ],
)
def test_v2_rejects(v2: Draft202012Validator, document: dict[str, Any]) -> None:
    with pytest.raises(ValidationError):
        v2.validate(document)


def test_v2_vocabulary_equals_the_interest_tag_enum() -> None:
    schema = _schema("selection.v2.json")
    in_schema = schema["properties"]["interests"]["items"]["enum"]
    assert in_schema == [tag.value for tag in InterestTag]


def test_v2_limits_match_the_domain_constants() -> None:
    schema = _schema("selection.v2.json")
    picks = schema["properties"]["picks"]
    assert schema["properties"]["interests"]["maxItems"] == MAX_TAGS
    assert picks["maxItems"] == MAX_IDEAS
    assert picks["items"]["properties"]["reason_ids"]["maxItems"] == MAX_REASONS


def test_schemas_forbid_unknown_fields_everywhere() -> None:
    # "No model output can introduce an unsupplied field" (ARCHITECTURE section 10).
    for name in ("selection.v1.json", "selection.v2.json"):
        schema = _schema(name)
        assert schema["additionalProperties"] is False
        assert schema["properties"]["picks"]["items"]["additionalProperties"] is False
