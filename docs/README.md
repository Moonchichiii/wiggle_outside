# docs/

What is specification and what is record. The specification is the baseline of 8.20
(commit `8b734cc`) plus the tracked changes; everything else here is kept for the record
and is not updated.

## The living specification (read in this order)

| File | What it fixes |
|---|---|
| [PLAN.md](PLAN.md) | the product: decisions D1–D49, the five questions, the budget, the rules |
| [ARCHITECTURE.md](ARCHITECTURE.md) | one process, one deadline, the caches, the deployment shape |
| [CONTRACTS.md](CONTRACTS.md) | types, routes, form fields, the model schema, the tracked-change table (§10) |
| [BACKEND-CONTRACT.md](BACKEND-CONTRACT.md) | the planning workflow rule by rule, in evaluation order |
| [DESIGN-SPEC.md](DESIGN-SPEC.md) | the board, the copy table, interaction and accessibility |
| [ERROR-HANDLING.md](ERROR-HANDLING.md) | every outcome, its status and its copy |
| [DEPLOYMENT.md](DEPLOYMENT.md) | Fly, secrets, the release runbook and its checks |
| [COMPETITION.md](COMPETITION.md) | what the challenge asks and how the submission answers it |
| [PRODUCT-FIT.md](PRODUCT-FIT.md) | what the model is for, and what it is not |
| [WALKTHROUGH.md](WALKTHROUGH.md) | one family's evening, request by request |

## Decisions after the baseline

- [decisions/tracked-changes/](decisions/tracked-changes/) — TC-001 to TC-012, one file
  each: the change, the reason, the approver, the files. The latest two matter most for
  reading the app as it runs today: [TC-011](decisions/tracked-changes/TC-011.md) (the
  night rule and the morning plan) and [TC-012](decisions/tracked-changes/TC-012.md) (the
  results page; its part B, a model-written note, was withdrawn).
- [decisions/contract-changes/](decisions/contract-changes/) — CC-001 to CC-006 and CC-A,
  raised by the packages while building.

## Evidence

[evidence/](evidence/): the model smoke tests, the live journeys with the model-call
ledger, and the release record. Fixture runs are labelled as such, never presented as
live performance.

## Review artefacts and drafts (record only)

[AGENT-BRIEF.md](AGENT-BRIEF.md), [BUILD-PACKAGES.md](BUILD-PACKAGES.md),
[CLAUDE-REVIEW.md](CLAUDE-REVIEW.md), [BACKEND-REVIEW.md](BACKEND-REVIEW.md),
[CATALOGUE-REVIEW.md](CATALOGUE-REVIEW.md), [SIMPLICITY-REVIEW.md](SIMPLICITY-REVIEW.md),
[REVIEW-RESULT.md](REVIEW-RESULT.md) and [HERMES-P0.md](HERMES-P0.md) (superseded, TC-003)
are the planning rounds and reviews that produced the baseline. [drafts/](drafts/) holds
the catalogue drafts and the submission draft; the reviewed catalogue lives in
`src/wiggle_outside/planner/`. [mocks/](mocks/) and [design-kit/](design-kit/) are the
approved visual direction and its artwork.

Where a record and the specification disagree, the specification wins; where the
specification and the code disagree, that is a finding, and the tracked-change table in
CONTRACTS §10 says what was decided.

## Known follow-ups, after the deadline

- The web session keeps an ambiguous-town candidate set, answers included, until the next
  such search or the session's end (up to two hours), past its ten-minute expiry.
- `htmx.org` is listed in `package.json` but no page loads it; the enhanced path was never
  built (marked "not built" throughout).
- HEAD on GET routes and the uniform 404/405 handler are not in the CONTRACTS §5 table;
  the Fly-Client-IP obligation in ARCHITECTURE §2.1 is unused.
- Test support duplicates a complete answer set and a weather-window builder in several
  modules; two long wiring functions (`main.build_resources`, `presenters.present_result`).
