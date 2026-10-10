"""Ownership, forged and expired IDs, and that no GET starts work.

An unowned job, an unknown job and a removed job are one 404 with one body, so nothing
about another session is revealed (BACKEND-CONTRACT section 5).
"""

from web_support import ANSWERS, FixedPlanner, Harness, build_harness, one_idea, plan_result

from wiggle_outside.core.types import JobState

FORGED = (
    "job-1",
    "../../etc/passwd",
    "a" * 300,
    "' OR 1=1 --",
)


def test_an_unknown_job_id_is_a_404(harness: Harness) -> None:
    answered = harness.client.get("/results/not-a-job")

    assert answered.status_code == 404


def test_a_forged_job_id_is_the_same_404(harness: Harness) -> None:
    harness.client.get("/")
    bodies = {
        harness.client.get(f"/results/{forged}").text for forged in FORGED if "/" not in forged
    }

    assert bodies == {""}


def test_another_sessions_job_is_indistinguishable_from_an_unknown_one() -> None:
    for harness in build_harness(FixedPlanner(result=plan_result(ideas=(one_idea(),)))):
        mine = harness.plan()
        owned = harness.client.get(mine.headers["location"])
        assert owned.status_code == 200

        harness.client.cookies.clear()
        harness.client.get("/")  # a second session, which owns nothing
        theirs = harness.client.get(mine.headers["location"])
        unknown = harness.client.get("/results/no-such-job")

        assert theirs.status_code == unknown.status_code == 404
        assert theirs.text == unknown.text
        assert theirs.headers.get("content-length") == unknown.headers.get("content-length")
        break


def test_a_request_with_no_session_at_all_is_a_404(harness: Harness) -> None:
    answered = harness.client.get("/results/job-1")

    assert answered.status_code == 404


def test_an_expired_result_is_the_same_404() -> None:
    for harness in build_harness(FixedPlanner(result=plan_result(state=JobState.EXPIRED))):
        shown = harness.client.get(harness.plan().headers["location"])

        assert shown.status_code == 404
        assert shown.text == ""
        break


def test_an_idea_id_not_in_the_result_is_a_404() -> None:
    for harness in build_harness(FixedPlanner(result=plan_result(ideas=(one_idea("known"),)))):
        base = harness.plan().headers["location"]

        assert harness.client.get(f"{base}/ideas/known").status_code == 200
        assert harness.client.get(f"{base}/ideas/unknown").status_code == 404
        break


def test_a_detail_url_on_an_unowned_job_is_a_404(harness: Harness) -> None:
    harness.client.get("/")

    answered = harness.client.get("/results/someone-elses/ideas/anything")

    assert answered.status_code == 404


def test_no_get_starts_work() -> None:
    planner = FixedPlanner(result=plan_result(ideas=(one_idea(),)))
    for harness in build_harness(planner):
        harness.client.get("/")
        harness.client.get("/results/job-1")
        harness.client.get("/results/job-1/ideas/idea-1")
        harness.client.get("/healthz")
        harness.client.get("/readyz")
        harness.client.get("/static/app.css")

        assert planner.calls == []
        break


def test_waiting_on_an_owned_running_job_is_not_starting_work() -> None:
    planner = FixedPlanner(
        result=plan_result(state=JobState.RUNNING, ideas=(one_idea(),)),
    )
    for harness in build_harness(planner):
        posted = harness.plan()
        planner.calls.clear()

        harness.client.get(posted.headers["location"])

        assert planner.calls == ["wait"]
        break


def test_the_answers_are_never_in_a_url(harness: Harness) -> None:
    posted = harness.plan()

    location = posted.headers["location"]

    for answer in ANSWERS.values():
        assert answer not in location
