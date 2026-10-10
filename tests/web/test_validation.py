"""Invalid or incomplete answers are 422 with the answers kept (CONTRACTS section 7).

Unknown field names, repeated scalar fields and values outside the listed set are all
refused, and none of them reaches the planner.
"""

import pytest
from web_support import FixedPlanner, Harness, build_harness

CASES = (
    pytest.param({"who": ""}, id="who missing"),
    pytest.param({"who": "everyone"}, id="who not a listed value"),
    pytest.param({"time": ""}, id="time missing"),
    pytest.param({"time": "45"}, id="time not a listed value"),
    pytest.param({"energy": "frantic"}, id="energy not a listed value"),
    pytest.param({"age_band": ""}, id="kids with no age band"),
    pytest.param({"age_band": "13-17"}, id="age band not a listed value"),
    pytest.param({"place": "B"}, id="place too short"),
    pytest.param({"place": "x" * 81}, id="place too long"),
    pytest.param({"place": ""}, id="place missing with typed"),
    pytest.param({"location_mode": "elsewhere"}, id="location mode not listed"),
    pytest.param({"stroller": "yes"}, id="stroller not the literal 1"),
    pytest.param({"step_free": "true"}, id="step_free not the literal 1"),
    pytest.param({"interests_text": "x" * 121}, id="interests too long"),
    pytest.param({"idempotency_key": ""}, id="idempotency key missing"),
    pytest.param({"surprise": "1"}, id="unknown field"),
)


@pytest.mark.parametrize("overrides", CASES)
def test_an_invalid_submission_is_a_422_form_page(
    harness: Harness, overrides: dict[str, str]
) -> None:
    refused = harness.plan(**overrides)

    assert refused.status_code == 422
    assert 'action="/plan"' in refused.text


@pytest.mark.parametrize("overrides", CASES)
def test_an_invalid_submission_reaches_no_planner(overrides: dict[str, str]) -> None:
    planner = FixedPlanner()
    for harness in build_harness(planner):
        harness.plan(**overrides)

        assert planner.calls == []
        break


def test_a_repeated_scalar_field_is_refused(harness: Harness) -> None:
    tokens = harness.start()
    body = harness.body(tokens)

    refused = harness.client.post(
        "/plan",
        content="&".join([*(f"{name}={value}" for name, value in body.items()), "who=solo"]),
        headers={
            "Origin": "https://testserver",
            "Content-Type": "application/x-www-form-urlencoded",
        },
        follow_redirects=False,
    )

    assert refused.status_code == 422


def test_a_repeated_age_band_is_allowed_but_a_duplicate_is_not(harness: Harness) -> None:
    tokens = harness.start()
    base = "&".join(f"{name}={value}" for name, value in harness.body(tokens).items())
    headers = {
        "Origin": "https://testserver",
        "Content-Type": "application/x-www-form-urlencoded",
    }

    two = harness.client.post(
        "/plan", content=f"{base}&age_band=6-9", headers=headers, follow_redirects=False
    )
    duplicate = harness.client.post(
        "/plan", content=f"{base}&age_band=3-5", headers=headers, follow_redirects=False
    )

    assert two.status_code == 303
    assert duplicate.status_code == 422


def test_an_invalid_submission_keeps_what_was_typed(harness: Harness) -> None:
    refused = harness.plan(time="45", place="Bergsjon")

    assert refused.status_code == 422
    assert "Bergsjon" in refused.text


def test_an_unparseable_coordinate_is_a_422(harness: Harness) -> None:
    refused = harness.plan(location_mode="coords", lat="nope", lon="17.9", place="")

    assert refused.status_code == 422


def test_an_out_of_range_coordinate_is_a_422(harness: Harness) -> None:
    refused = harness.plan(location_mode="coords", lat="120.0", lon="17.9", place="")

    assert refused.status_code == 422


def test_an_age_band_is_ignored_when_solo(harness: Harness) -> None:
    accepted = harness.plan(who="solo", age_band="3-5")

    assert accepted.status_code == 303


def test_the_interests_field_is_unknown_when_d39_is_off() -> None:
    from web_support import harness_settings  # noqa: PLC0415  one case needs other settings

    for harness in build_harness(FixedPlanner(), harness_settings(d39_enabled=False)):
        refused = harness.plan(interests_text="birds")

        assert refused.status_code == 422
        break


def test_hostile_text_is_escaped_once_on_the_error_page(harness: Harness) -> None:
    refused = harness.plan(time="45", place="Oak & Elm <b>")

    assert "Oak &amp; Elm &lt;b&gt;" in refused.text
    assert "&amp;amp;" not in refused.text
    assert "<b>" not in refused.text
