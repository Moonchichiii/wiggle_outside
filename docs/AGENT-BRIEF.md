# Agent brief — Wiggle Outside

You are building one work package of Wiggle Outside. This page tells you where the rules
are; it does not repeat them. At bootstrap the integration owner may place it in the
repository as `AGENTS.md`; that file is then a protected input (BUILD-PACKAGES §2.1),
and Mats reviews any change to it.

Who does what (BUILD-PACKAGES §2, TC-003): **Claude Code integrates and runs the gates,
Codex reviews, Mats approves and commits.** There is no build orchestrator.

## Read before editing

1. **PLAN.md §0**: the one current decision register. "Accepted" (or "decided") is
   binding; "deferred", "declined", "inactive", "superseded", "removed" and "not in v1"
   mean don't build it; "blocked" names a prerequisite in PLAN §0.1, so build only what
   does not depend on it. *Starting value* marks an accepted limit: build it as written
   and report measurements; never change it silently.
   **The primary build path is the independently hosted product** (D48: Fly.io →
   OpenRouter → the pinned model provider; ARCHITECTURE §2 and §2.1), so the hosted
   rules (D49, DEPLOYMENT §2–§3) apply. A local Ollama is optional for development and
   gates nothing. Spending and deployment still need Mats's separate approval.
2. **BUILD-PACKAGES.md**: your package, the paths you own, what you wait for, and your
   acceptance checks.
3. **CONTRACTS.md**: the shared types, routes, statuses, forms, view models and model
   schema.
4. The owning document for your area: BACKEND-CONTRACT, ERROR-HANDLING, ARCHITECTURE,
   DESIGN-SPEC or PRODUCT-FIT. Where documents differ, the owning document wins.
5. **WALKTHROUGH.md**: the fixture journey your work must support.

SIMPLICITY-REVIEW's historical section and earlier review files are background only,
not instructions.

## Rules

- Edit only the paths assigned to your package. Shared contracts, manifests, lockfiles
  and gates belong to the integration owner.
- Add no dependency, feature, route or framework without an approved change
  (CONTRACTS §10).
- Never weaken a gate, test or check, and never fabricate evidence, measurements or
  results.
- If something is ambiguous or contradictory, write it down as a question or a
  contract-change proposal. Carry on only with work the ambiguity doesn't affect.
- No application code before Mats's "kör".

## Finish with a short report

- The paths you changed.
- The checks you actually ran, with their real output. Say "not run" when you didn't
  run one.
- Remaining limitations, open questions and contract-change proposals.
