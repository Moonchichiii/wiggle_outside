# Claude deep architecture review — round 8

Mats's instruction: dig deeply into the complete planning set before any application build. Keep the implementation lean, readable and secure. Review every important detail without expanding the product or treating extra tools as evidence of engineering quality.

## Delivery rule — required by Mats, 9 October 2026

Deliver each revision as one complete, versioned ZIP only. Include all current
planning documents, catalogues, review results and SHA256SUMS.txt inside it.
Do not attach individual documents, sidecar files or partial update bundles.
The ZIP is the authoritative handoff; provide one download link and a short
change summary. Verify its checksums before delivery. Keep reviews focused on
changed requirements, conflicts and outstanding proof; do not reopen settled
decisions without new evidence. This delivery change grants no build approval.

## Input and authority

Read PLAN.md, ARCHITECTURE.md, ERROR-HANDLING.md, HERMES-P0.md, COMPETITION.md, drafts/activities.toml and drafts/hooks.toml in full. Use the round 8 set, with the unchanged competition contract and catalogues supplied alongside it. Previous downloads are reference material, not competing masters.

No application code, deployment, publishing, commits or build permission follows from this review. Do not replace unresolved decisions with claims that Mats approved them. Distinguish a design review pass from a demonstrated security control. Explain any inability to inspect the actual Workbench governance or runtime rather than assuming the scoped P0 supersedes it.

## Required method

1. Trace the primary journey, every fallback and every terminal state across prose, diagrams, schemas, catalogues and planned checks.
2. Identify an exact failure or contradiction for each finding. Include the document section, consequence, smallest viable fix, verification method and whether it blocks planning approval, bootstrap or release.
3. Check current primary documentation for version-sensitive claims. Record URL, date and applicable version. Do not certify a tool setting merely because it sounds plausible.
4. Follow up existing findings before adding speculative scope. Consolidate duplicate rules instead of copying more prose into PLAN.
5. Return a bounded closure report and revised documents. Do not mark a finding resolved until its text is consistent everywhere; do not mark implementation verified before evidence exists.

## Review tracks

### Product and domain
- Replay toddler/default-energy and mixed-age cases through eligibility, ranking and capping.
- Validate generic suggestions: absent destination must not bypass place, daylight, weather, age or equipment constraints. Mark which activities actually permit a generic destination.
- Resolve energy arrays versus maximum-effort semantics; check hooks use the selected activity variant consistently.
- Verify all text predicates and placeholders, including approximate distance, time, access, daylight, season and rain. Decide geographic scope and hemisphere handling.
- Ensure reviewed steps remain immutable and model output contains only validated IDs. Treat provider labels as external data.
- Review provisional weather limits and infant adaptations explicitly; do not certify them as universally safe.

### Runtime and concurrency
- Trace deadline consumption from form acceptance through geocoding, providers, queue, model, repair, fallback and render. Pick provider budgets and explain their sum/concurrency.
- Verify one-worker deployment and bounded request/HTTP/database queues. Test duplicate submissions, reconnect, cancellation/completion races and restart.
- Show who owns each task and resource, who cancels it, and when the model slot can safely be reused. Verify cancellation at the runtime, not just the client socket.
- Specify SSE/htmx flow, session ownership, CSRF, expired results and no-JavaScript behaviour without multiplying application workflows.
- Review cache key versioning, capacity, expiry, journal growth, cleanup and corruption/disk-full behaviour.
- Distinguish memory-only retention from persistence; inspect server logs, model logs, traces and exception messages for privacy leaks.

### Error handling and user recovery — required round 8.1 review
- Audit every row of ERROR-HANDLING.md against the state machine, transport and plain-form flow.
- For every failure, verify truthful wording, meaningful action, retained safe input, usable controls,
  HTTP/event outcome, ownership, retry budget, screen-reader announcement and safe diagnostics.
- Check non-2xx htmx rendering, SSE terminal failures, stale response races, uncertain POST recovery,
  cancellation confirmation, script/template failures and restart/expiry. No endless spinner.
- Verify security refusals do not expose job ownership, raw errors or family data and never retry by
  weakening CSRF/CSP. No unavailable weather path produces an outing.
- Verify fallback/replay labels and error demonstrations do not misrepresent live open-model use.
- Map each error scenario to evidence and a blocking phase; do not call it state of the art or
  compliant solely because the contract exists. Confirm competition requirements remain intact.

### Deployment and security
- Resolve public demo replay versus live model, fixed inputs, model location and disclosure. No visitor location collection by accident.
- Resolve same-machine local access versus phone access, HTTPS, cookie prefix requirements and CSRF. Include cookie Path=/ and omitted Domain where __Host- is used; make the token transport work with HttpOnly and plain forms.
- Check CSP against actual htmx/Alpine features and default injected styles, not just handwritten HTML. Verify positive journeys and intentional negative tests separately.
- Prove runner isolation with pinned tool versions; test wrapper argument handling and immutable effective permissions. Confirm default capabilities are appropriately removed, not merely that no extra capabilities were added.
- Snapshot review: protect against symlink/path escapes, undeclared files, changing inputs during capture and Git filters affecting comparison. Preserve .env.example while excluding secrets. Identify exactly which source bytes/modes the commit comparison covers.
- Confirm supply-chain coverage for runtime, dev, analysis, optional extras if present, transitive and platform-specific dependencies. Audits must not resolve/build project code. Check whether export includes editable local project entries and how these are excluded without hiding third-party packages.
- Reconcile scanner package identities within each ecosystem/scope. Counts alone cannot prove completeness, and counts from OS packages and Python packages are not interchangeable. Unknown/skipped/unsupported packages cannot silently pass.
- Check required database sources for Trivy and other scanners, freshness/provenance, pre-provisioned tools and image archives. The audit runner has no container socket and cannot fetch arbitrary registries.
- Check current Dependabot support for chosen uv/Bun formats. Keep pins updateable through reviewed PRs; no false claim that pinning guarantees security.
- Distinguish merge, container-image audit and release gates so no workflow waits on an artifact that cannot exist yet. Test actual public host after promotion, including errors; define rollback.
- Verify CodeQL findings enforcement, not merely successful analysis upload. Check GitHub repository-plan capabilities, ruleset enforcement, solo-author review constraints, expected status names and protection against untrusted PR execution with secrets.
- Observatory 145/A+ remains the target. Assess hostname/preload feasibility early; do not fake a score or weaken product requirements to obtain one.

### Lean implementation and performance
- Confirm the six proposed runtime dependencies and every direct import; justify additions. Keep analysis, scanners, browser tools and asset builders out of the runtime image.
- Check the eight-dependency policy against the documented exception process. Never replace vetted security functionality with custom code just to keep a count down.
- Freeze Python and compatible runtime/tool versions during bootstrap; do not leave “3.14 or 3.13” as an implemented pin.
- Prefer pure functions and a small number of genuine resource-owning classes. No generic Protocols without a type relationship, gratuitous wrappers or pattern demonstrations.
- Preserve short one-line purposeful comments, licence notices and longer explanations in docs. Do not replace readable code with compressed clever code to pass size budgets.
- Review all import-linter contracts and required test exemptions. Reconcile the claimed number of contracts with concrete configuration.
- Quantization: compare supported variants on the same task, schema, model and scenarios. Confirm actual GPU use, memory headroom and cold/warm behaviour. Record resource contention separately.
- Validate startup catalogue parsing, build asset availability and the precise offline-card promise.

### Evidence, accessibility and competition
- Trace each mandatory requirement to a check or named human review, a blocking phase and an evidence location.
- Review the four diagrams against code responsibilities; keep diagrams explanatory rather than turning every diagram box into a module.
- Test keyboard, screen reader, zoom/reflow, touch, motion preferences and plain-form flow. Do not infer AAA from contrast/axe alone.
- Keep contest facts in COMPETITION.md. Distinguish rules, chosen project policies and recommendations. Check repository creation window and final submitted artifact provenance.
- Assess whether model ranking materially improves the experience. Report blinded comparisons including ties/losses; do not tune against all evaluation scenarios and call the result independent validation.
- Preserve a real user trial and time for the write-up. Further workbench machinery needs a concrete risk justification, not a prestige argument.

## Return format

Return:
1. A short verdict: design ready, ready with named conditions, or blocked.
2. Findings table: ID, severity, exact location, failing scenario, minimum fix, evidence/check, owner, status and blocking phase.
3. Explicit answers to each proposed round 8 decision: accept, revise with reason, or needs Mats's choice. Supply a recommendation for genuine choices.
4. Changed documents with a concise cross-file change log; preserve accepted scope and catalogue provenance.
5. Residual risks, unverified assumptions and the exact first-build proof tasks.

Do not promise ZERO GAPS. The target is zero known unresolved blockers at the relevant phase, explicit ownership of uncertainty and tests capable of exposing wrong assumptions. Stop planning churn when the contracts are coherent and the remaining questions are empirical bootstrap checks; do not label those checks passed prematurely.
