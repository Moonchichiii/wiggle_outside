"""The CONTRACTS section 3 POST table: 303, 409, 413, 415, 422, 429 and the honeypot.

Statuses the planner decides (the hosted quota codes) arrive on the GET, because POST
answers 303 as soon as the job reaches a terminal state (D43).
"""

from web_support import (
    ANSWERS,
    PROCESS_KEY,
    FixedPlanner,
    Harness,
    build_harness,
    one_idea,
    plan_result,
)

from wiggle_outside.planner.ports import Busy
from wiggle_outside.web import copy
from wiggle_outside.web.forms import canonical_form, fingerprint


def test_a_joined_submission_redirects_to_the_same_job(harness: Harness) -> None:
    tokens = harness.start()

    first = harness.post("/plan", harness.body(tokens))
    second = harness.post("/plan", harness.body(tokens))

    assert (first.status_code, second.status_code) == (303, 303)
    assert first.headers["location"] == second.headers["location"]


def test_the_same_key_with_different_answers_is_a_conflict(harness: Harness) -> None:
    tokens = harness.start()
    harness.post("/plan", harness.body(tokens))

    refused = harness.post("/plan", harness.body(tokens, place="Uppsala"))

    assert refused.status_code == 409
    # CONTRACTS section 3 calls this action "Start a new search"; WP8's approved copy
    # labels it RETURN_TO_FORM. Raised as a copy proposal; the recovery itself is here.
    assert f'href="/">{copy.RETURN_TO_FORM}' in refused.text


def test_the_same_key_with_different_interest_text_is_a_conflict(harness: Harness) -> None:
    tokens = harness.start()
    harness.post("/plan", harness.body(tokens, interests_text="birds"))

    refused = harness.post("/plan", harness.body(tokens, interests_text="birds, puddles"))

    assert refused.status_code == 409


def test_the_planners_own_conflict_is_also_a_409() -> None:
    for harness in build_harness(FixedPlanner(conflict=True)):
        refused = harness.plan()

        assert refused.status_code == 409
        break


def test_field_order_does_not_change_the_submission(harness: Harness) -> None:
    tokens = harness.start()
    forwards = harness.body(tokens)
    backwards = dict(reversed(list(forwards.items())))

    first = harness.post("/plan", forwards)
    second = harness.post("/plan", backwards)

    assert (first.status_code, second.status_code) == (303, 303)
    assert first.headers["location"] == second.headers["location"]


def test_the_fingerprint_is_the_hmac_over_the_canonical_form(harness: Harness) -> None:
    tokens = harness.start()
    body = harness.body(tokens)
    harness.post("/plan", body)

    session = next(iter(harness.sessions))
    expected = fingerprint(PROCESS_KEY, {name: [value] for name, value in body.items()})

    assert session.keys[tokens["idempotency_key"]] == expected
    # The canonical form is what is signed, and it excludes the three CONTRACTS 7 fields.
    assert b"csrf_token" not in canonical_form({name: [value] for name, value in body.items()})


def test_a_busy_planner_is_a_429_linking_to_the_active_result() -> None:
    planner = FixedPlanner(result=plan_result(ideas=(one_idea(),)))
    for harness in build_harness(planner):
        active = harness.plan().headers["location"]
        planner.busy = Busy(retry_after_s=7)

        refused = harness.plan()

        assert refused.status_code == 429
        assert refused.headers["retry-after"] == "7"
        assert active in refused.text
        break


def test_no_retry_after_is_invented_when_the_delay_is_unknown() -> None:
    for harness in build_harness(FixedPlanner(busy=Busy())):
        refused = harness.plan()

        assert refused.status_code == 429
        assert "retry-after" not in refused.headers
        break


def test_a_flood_of_new_submissions_is_refused_before_any_work() -> None:
    planner = FixedPlanner(result=plan_result(ideas=(one_idea(),)))
    for harness in build_harness(planner):
        statuses = [harness.plan().status_code for _ in range(8)]

        assert statuses[:6] == [303] * 6
        assert statuses[6:] == [429, 429]
        assert planner.calls.count("start_or_join") == 6
        break


# --- The honeypot (D49, DEPLOYMENT section 4) ---------------------------------------


def test_a_filled_honeypot_is_a_422_that_calls_nothing() -> None:
    planner = FixedPlanner()
    for harness in build_harness(planner):
        refused = harness.plan(hp_note="buy-cheap-pills")

        assert refused.status_code == 422
        assert planner.calls == []
        break


def test_the_honeypot_keeps_the_answers_and_clears_itself(harness: Harness) -> None:
    refused = harness.plan(hp_note="spam")

    assert "Bergby" in refused.text  # the answers are kept
    assert "spam" not in refused.text  # the honeypot is cleared, never echoed
    assert 'name="hp_note" value=""' in refused.text


def test_whitespace_in_the_honeypot_is_still_empty(harness: Harness) -> None:
    accepted = harness.plan(hp_note="   ")

    assert accepted.status_code == 303


def test_the_honeypot_does_not_change_the_submission(harness: Harness) -> None:
    tokens = harness.start()

    first = harness.post("/plan", harness.body(tokens))
    second = harness.post("/plan", harness.body(tokens, hp_note=""))

    assert first.headers["location"] == second.headers["location"]


def test_a_post_never_answers_404(harness: Harness) -> None:
    # Location candidates are form values scoped to the session (CONTRACTS section 3).
    answered = harness.post("/location-choice", {"candidate_id": "nope", **dict(ANSWERS)})

    assert answered.status_code != 404
