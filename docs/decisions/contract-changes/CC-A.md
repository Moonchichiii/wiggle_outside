# CC-A…CC-G — `present_form` takes one `FormContext`

| Field | Value |
|---|---|
| Raised by | WP8 (form page), in its hand-off report, as seven separate proposals |
| Change | `present_form(context: FormContext) -> FormPage`. `FormContext` is a new frozen dataclass in `web/views.py` (WP0). |
| Status | **accepted** by the integration owner; CC-E and CC-F noted, not closed |

Five of the seven were the same defect seen from different angles: the signature could
not carry what the page needs. One carrier fixes all five at once and removes three
`# noqa` codes.

## CC-A — a partly filled form, and a typed place, were unrepresentable

`values: AnswersSummary | None` admitted exactly two states: every answer present **and**
geocoded, or nothing. Two required behaviours were therefore unreachable:

- A 422 re-render must keep the answers the person did give (ERROR-HANDLING §2 "retain
  valid values", DESIGN-SPEC §12 "answers kept"). With only `AnswersSummary` it could keep
  all of them or none.
- A typed town that failed to geocode (LOCATION_NOT_FOUND, LOCATION_AMBIGUOUS,
  GEOCODER_UNAVAILABLE) could not be echoed back, so `FormPage.place` was always `""`.

`FormContext.submitted: Mapping[str, str]` carries the raw submission and wins field by
field over `answers`. An illegal value is **not** preselected — it is what made the
request a 422 — but it is echoed in the text inputs so it can be corrected.

## CC-B — no way to pass the asset manifest

`PageMeta.assets` is required, `present_form` had no manifest parameter, and "no globals"
rightly forbids reaching for one. WP8 worked around it with `with_assets(page, assets)`.
`FormContext.assets` closes it; `with_assets` stays for a caller that builds a page before
it knows its manifest.

## CC-C — the D39 prefill was unreachable

CONTRACTS §7 and DESIGN-SPEC §9 say "Change answers" prefills `interests_text` with the
recognised tag labels, but `AnswersSummary` has no tags — `Interests` hangs off
`PlanResult`. `FormContext.interests` closes it, and `copy.INTEREST_TAG_LABELS` supplies
the labels. Never the original free text: the labels are what we actually understood.

## CC-D — candidate expiry had no timezone

CONTRACTS §8 says times render in the planned location's timezone.
`FormContext.candidates_tz` supplies it; with no timezone the moment renders in whatever
it carries, and the caller is told to pass one rather than the presenter guessing.

## CC-G — the gate config and the contract signature conflicted

`ruff.toml` sets `max-args = 5`; the old signature had six parameters and a positional
boolean, so PLR0913, PLR0917 and FBT001 all fired and WP8 left three `# noqa` codes
citing the contract. One parameter means neither the gate nor the contract bends.

## Not closed

- **CC-E — `tests/fixtures/` does not exist.** CONTRACTS §8 says WP0 creates fixture
  instances of every view model there. It has not; WP8 keeps its own in
  `tests/templates/fixtures.py`. Still owed by WP0.
- **CC-F — nothing owns `render`.** CONTRACTS §8 says "WP7 routes … pass the view to
  `render`", but no file in the BUILD-PACKAGES §3 table owns it. WP8 put
  `build_environment()` and `render_form()` in `presenters.py`, a path it owns. WP7 must
  either use those or an owner must be named.

## Tests that change

WP8's `present_form` call sites (`tests/templates/`), updated by the integration owner as
§10.3 requires. New tests cover what the change unblocked: a partial submission echoed on
re-render, an illegal value not preselected, a typed place echoed, and the D39 tag prefill.
