# Touchgrass error handling and recovery — baseline 8.20

Status: DRAFT planning contract, 9 October 2026. Requested by Mats. No application code or runtime verification is implied.
Read with [PLAN.md](PLAN.md), [ARCHITECTURE.md](ARCHITECTURE.md) and [COMPETITION.md](COMPETITION.md). ([HERMES-P0.md](HERMES-P0.md) is a superseded appendix, TC-003.)

## 1. Experience contract

Every failure has a stable internal code, an owning layer, a truthful user message, a recovery action when one exists, a terminal or continuing state, and an acceptance check. The user can understand what happened and what to do next without understanding the infrastructure.

Keep messages short, specific and calm. State the consequence, then the next action. Do not blame the user, invent a cause or estimated recovery time, promise saved answers unless they remain available, or use playful wording where a security or weather failure needs clarity. Progress text reflects work actually happening; no fake percentages, spinning forever or fictional provider activity in a replay demo.

A notice names an edit as a remedy only for a limit the run actually evaluated. Where a check ended the run early, so later checks never ran, the copy says the answers will be checked again, not that a particular edit will work (TC-002). This generalises the NO_MATCHES rule in §2.

Expected empty results, cancellation and successful deterministic fallback are explicit outcomes, not generic crashes. Fault tolerance never bypasses weather, age, place, model-output or security rules. All error copy comes from reviewed application text, never from Gemma or raw provider responses.

## 2. Failure and recovery matrix

Copy below is a reviewed-draft starting point. Actions must be enabled only when they can work. Preserve current form values where safe and actually available; never persist them merely to make a message true.

| Code / condition | Message | Recovery and behaviour |
|---|---|---|
| INPUT_INVALID | “Check the highlighted answers before we find an outing.” | Inline field explanations plus linked error summary; retain valid values; no provider/model call |
| LOCATION_DENIED | “Location access wasn’t allowed. Enter a town or area instead.” | Focus/manual-location option; do not repeatedly trigger the permission prompt |
| LOCATION_UNAVAILABLE | “We couldn’t get your location. Enter a town or area, or try again.” | Manual alternative; do not claim permission was denied when the cause is unknown |
| LOCATION_AMBIGUOUS | “Which place did you mean?” | At most five distinguishable matches, with region/country labels; no silent first-match selection; choosing one starts a new attempt without geocoding again (BACKEND-CONTRACT §3) |
| LOCATION_CHOICE_EXPIRED | “That list of places has expired. Enter the town or area again.” | Manual-entry form with other answers retained; forged and expired choices are treated alike |
| LOCATION_NOT_FOUND | “We couldn’t find that place. Try a nearby town or add the country.” | Edit location; retain other answers |
| GEOCODER_UNAVAILABLE | “Place search isn’t available right now. Try again, or use your location.” | Geolocation offered only when supported and permitted; bounded retry |
| WEATHER_UNAVAILABLE | “We couldn’t check the weather, so we haven’t suggested an outing. Try again.” | No model or generic recommendations; explicit retry, same form values if retained |
| WEATHER_RESTRICTED | “The forecast is outside this activity list’s weather limits. No outing suggested.” | Edit/retry later; no “safe later” claim and no inferred universal danger claim |
| PLACES_CACHED | “Live place information is unavailable. These places were last checked {age} ago.” | Show only cache entries permitted by freshness/eligibility rules; show uncertainty |
| PLACES_UNAVAILABLE | “We couldn’t load nearby places.” | Only explicitly eligible generic activities if weather and all other rules pass; otherwise retry; never invent a destination |
| DAYLIGHT_NIGHT (family path, Mats 8.20) | “**The adventures can wait till morning.** Time to put the phone down and get some rest. The outdoors will still be there tomorrow.” | 200, evaluated; answers summary and “Change answers” kept; no model call; takes precedence over WEATHER_RESTRICTED and NO_MATCHES (BACKEND-CONTRACT §1); solo path unchanged |
| DAYLIGHT_TOO_SHORT (family path, Mats 8.20; copy TC-002) | “**Not enough daylight for this one.** The outing would end after sunset. Change your answers and we’ll check the daylight and the weather again, or leave the adventure for tomorrow.” | As DAYLIGHT_NIGHT; shown when the outing would start in daylight but end after sunset. The weather limits were never evaluated on this run, so the copy promises a re-check and never offers a shorter outing as the fix (§1, TC-002) |
| NO_MATCHES | “No activities in our list match these answers right now.” | Offer relevant edits only; a longer outing must not be presented as a fix for missing weather |
| FEWER_MATCHES | “We found {count} matching ideas.” | Render one or two honestly; never pad to three |
| MODEL_FALLBACK | “AI selection isn’t available right now. These picks come from our activity list.” | Successful degraded result using the same eligible pairs; no automatic regenerate loop |
| SERVICE_LIMIT_REACHED (hosted live mode only, D49) | “Wiggle Outside has reached today’s limit. Please try again after {reset_time}.” | 503 with `Retry-After` until 00:00 UTC; only when the daily allowance is used up; answers kept; no provider or model call |
| SERVICE_UNAVAILABLE (hosted live mode only, D49) | “Wiggle Outside can’t take new searches right now. Your answers are kept; please try again in a few minutes.” | 503 with `Retry-After: 60`; quota storage failed, so the run is refused (fails closed); operator log; never mentions midnight |
| REQUEST_BUSY | “The planner is busy. Try again shortly.” | Bounded admission and submission rate limits (BACKEND-CONTRACT §4); optional server-provided retry delay, never a fabricated countdown; a second tab links to the active result |
| PROGRESS_DISCONNECTED (not in v1, D43) | “We’ve lost contact with the planner. Checking for your result…” | Reconnect to the same owned job within bounded attempts; do not restart generation |
| CONNECTION_FAILED | “We couldn’t reach the planner. Check your connection, then try again.” | Treat the cause as unknown; preserve client-visible input; reconcile an existing job before resubmission |
| JOB_CANCEL_REQUESTED (not in v1, D43) | “Stopping this request…” | No “stopped” claim until cancellation is confirmed; retained model slot follows architecture cleanup rules |
| JOB_CANCELLED (not in v1, D43) | “This request was cancelled.” | Explicit new submission with a new key; no hidden restart |
| RESULT_EXPIRED (not reached in v1: retained results show a historical view, removed ones 404) | “This result is no longer available. Submit your answers again to plan an outing.” | Restore only values still present; no guarantee after a restart or refresh |
| REQUEST_CONFLICT | “Your answers changed during this request. Submit them again to start a new search.” | Reject reuse of the old key with different input |
| SESSION_INVALID | “This page needs refreshing before we can continue.” | Reject the request; refresh/re-establish the session and require explicit resubmission; no automatic CSRF bypass |
| REQUEST_TOO_LARGE | “That submission is too large. Return to the form and try again.” | Reject before expensive processing; no reflection of raw body contents |
| UNEXPECTED_FAILURE | “We couldn’t finish that request. Please try again. Reference: {reference}.” | Generic safe error; opaque correlation reference; no traceback/provider response to the browser |
| PRINT_HELP | “Use your browser’s print menu to print or save this card.” | Plain-browser alternative when scripted print fails; do not claim printing succeeded |
| REPLAY_FIXTURE_MISSING (**inactive**: replay superseded by D48; not in v1) | “This example isn’t available. Choose another example.” | No substitution of fabricated live output; clearly preserve replay-demo label |

Placeholders are bounded plain-text application values, escaped once by template autoescape (BACKEND-CONTRACT §7). A correlation reference is not a result-access token. Record developer-specific causes privately as safe codes, not extra implementation details in the user message.

## 3. Backend responsibilities

- Adapters translate known transport, timeout, malformed-response and provider-status failures into narrow typed outcomes. Core owns domain outcomes; web owns HTTP and presentation. Do not catch every exception and pretend it was “no matching activities.”
- Unexpected programming faults reach one top-level handler that returns a safe failure and emits a redacted diagnostic record. Task cancellation and shutdown propagate through cleanup; they are not converted into ordinary provider errors.
- Release resources in all paths: HTTP responses, SQLite work, request records and generation slots. A response timeout may return an eligible fallback while cancellation drains, but cannot admit overlapping inference.
- HTTP status reflects the operation: validation 422; malformed request 400; session/CSRF refusal 403; key conflict 409; oversized body 413; admission throttling 429; unavailable required service 503; unexpected fault 500. An authorized expired result can return 410; unknown or unowned IDs use indistinguishable 404 responses. Successful empty/fallback results remain successful outcomes with explicit labels. Canonical code-by-code mapping (round 8.8): CONTRACTS.md §3. In short: weather unavailable or expired, geocoder unavailable, and places unavailable with no eligible generic idea are 503 (nothing could be evaluated); NO_MATCHES, WEATHER_RESTRICTED, DAYLIGHT_NIGHT and DAYLIGHT_TOO_SHORT are 200 (evaluated, nothing qualified).
- Plain form and enhanced requests use the same error mapping and approved copy. HTML routes return full HTML pages, including error pages; htmx selects the region to swap from them (CONTRACTS §5). If JSON endpoints are used, use RFC 9457 problem details with stable type/code, HTTP status and opaque reference; no extra framework is required. Do not return raw validation inputs, tracebacks, SQL, paths, prompt text or secrets in details.
- There is no progress stream in v1 (D43). A POST whose response is lost is recovered by resubmitting the same form, which joins the existing job; it never starts a new one.
- Support a minimal fallback error page independent of the database, model and complex templates. Keep security headers on failures generated by both app and proxy. Failure of a progress channel must not remove the plain-form recovery path.
- Cache write failure may bypass caching and finish an otherwise valid result. Required weather failure may not. Readiness, liveness and model readiness stay distinct; model unavailability does not make working deterministic functionality a crash.

## 4. Retry and duplicate policy

Retries have a single owner per operation. Provider retries must fit the absolute request deadline and respect rate limits. The browser must not retry a POST under a new key after an uncertain response; it first checks or rejoins the original owned request.

Use bounded backoff for transient provider failures where permitted (one retry, in the provider wrapper); no package is added solely for a tiny retry policy. Do not retry validation, CSRF, unknown ownership or deterministic schema failures indefinitely. There is no model repair attempt (D44). User-requested retry of a terminal result is a new explicit operation; resubmitting the same form after a lost response joins the existing job.

If recovery is exhausted, replace the busy state with an actionable terminal state. Ignore repeated submits while a request is pending; the answers stay keyboard-editable and the busy state never traps focus (there is no user-facing cancellation, D43). Restore usable controls on all terminal paths. A stale response from an older request must never overwrite newer answers/results.

## 5. Frontend and accessible recovery

- Keep form answers during validation failures and transient network errors where they still exist in the current page/session. Do not clear the whole form on one invalid field. Do not add localStorage persistence of family answers by default.
- Identify each invalid field with text, associate its explanation with the control, and expose its invalid state programmatically. On explicit failed submission, focus a linked error summary once; do not move focus on every keystroke or progress event.
- Use polite status announcements for progress and successful fallback. Use an alert only for a meaningful blocking dynamic error where appropriate. Avoid duplicated announcements from simultaneously moving focus and announcing the same content.
- Errors remain visible until resolved or dismissed where dismissal is appropriate; never rely on a transient toast, colour, icon, sound or animation alone. Actions have specific labels such as “Edit location” or “Try again.”
- Correct busy states and button text on success, empty, fallback, failure, timeout and cancellation. No infinite spinner or broken disabled form. Respect reduced motion and zoom/reflow.
- Configure the enhanced transport to render intended non-2xx validation/error responses. Verify the actual htmx behaviour rather than assuming a 422 page will swap automatically. Unsupported or malformed responses trigger a controlled error state, not silent disappearance of the form.
- Test with JavaScript disabled, script-load failure and a response lost after submission. Retrying must preserve security checks. Do not weaken CSP to add inline recovery handlers.
- Critical guidance is plain language. Keep playful copy for successful exploration; never obscure a weather restriction, privacy event or failure with an unexplained joke.

## 6. Diagnostics and security

Use existing structured logging, not a new telemetry service. Allowlist: reference ID, stable error code, stage, timestamp, outcome, duration, retry count and exception class where safe. Sanitize exception messages and stack reports; exclude locals, raw request bodies, coordinates, family answers, provider payloads and credentials. Access/proxy/model logs follow the same policy.

Record a failure once at its owning boundary and correlate related events without duplicate traceback floods. Bound/rotate diagnostic storage and repeated-error reporting. An opaque reference helps local diagnosis; no public endpoint reveals logs from a reference. Security failures reveal no extra account/job existence information.

## 7. Verification and release gate

Every matrix row maps to an acceptance scenario with code, expected state/status, rendered copy, available actions, input retention, focus/announcement behaviour, side effects and diagnostic redaction. Automated copy checks ensure required meaning and actions, not brittle snapshots of every decorative word.

Required scenarios include:
- Provider 429/timeout/malformed or oversized body, missing interval coverage and cache expiry.
- Model unavailable, invalid selection (straight to fallback, D44), timeout and unconfirmed internal cancellation.
- Duplicate POST, response lost after acceptance (resubmission joins), stale response racing a new submission, full queue and process restart.
- Invalid form, CSRF refusal, unowned/expired result, database unavailable/full and template/asset failure.
- Plain HTML and enhanced versions of the same failures; keyboard/screen-reader review, 400% zoom, reduced motion and narrow viewport.
- A failed retry never displays an earlier result as if it belonged to the new request: earlier results are replaced or visibly marked before the new request starts.
- Proxy-generated error pages, unexpected HTML and network failures in the enhanced path produce the CONNECTION_FAILED or UNEXPECTED_FAILURE state, never a blank or half-swapped page.
- Every failure path respects the request budget in ARCHITECTURE section 14: no recovery action triggers duplicate inference.
- No unexpected CSP violations on valid journeys; intentional negative tests expect blocking and remain distinct from the zero-violation positive suite.
- Failure-page headers after the proxy, no sensitive data in returned content/log fixtures, correct rollback of a failed candidate.

No release passes while a known blocking path leaves an endless spinner, clears recoverable input, exposes sensitive diagnostics, repeats side effects, bypasses eligibility or offers a recovery action that does not work. Implementation remains pending until these checks run.

## 8. Competition alignment

This contract improves the existing Touch Grass project; it adds no sponsor technology or unrelated feature. Keep the official rules in COMPETITION.md authoritative and preserve the entry window, new-project requirement, single submission and required repository/demo/open-innovation explanation.

The hosted product labels deterministic fallback truthfully (replay is inactive, D48). Record development runs on a local model separately from hosted measurements; do not disguise errors or fallback as live Gemma success. Publish only redacted evidence and legitimately reusable fixtures. Describe error handling as tested only after the mapped checks pass; no “perfect security,” “zero failures” or unverified accessibility claims. Track post-deadline changes under the existing competition contract. Compliance is checked at submission, not inferred from this document.

References: [RFC 9457](https://www.rfc-editor.org/rfc/rfc9457.html) for optional JSON error responses; [W3C status messages](https://www.w3.org/WAI/WCAG22/Understanding/status-messages.html) for accessible dynamic feedback. These inform implementation; they are not evidence that the future app conforms.
