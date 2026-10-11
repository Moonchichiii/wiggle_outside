# Hosted model smoke (PLAN section 15 step 3)

Run on 2026-10-11 17:31 UTC with `scripts/model_smoke.py`. Model `google/gemma-4-26b-a4b-it` through OpenRouter, routing `provider.only` = ['nextbit', 'deepinfra', 'coreweave'], `require_parameters` true, fallbacks within the list, `max_tokens` 256, reasoning effort none, strict `json_schema` `selection.v2`, prompt `select.v2`. Controlled input: fixture places and a fixed interest text; no visitor data. The key is never written.

### Generic-only request (places unavailable: no place in any pair)

Controlled interest text: `birds and puddles`

Pairs offered (exactly what the model saw, plus the straight-line distance for the reader):

| pair | activity | place kind | distance m | allowed hooks | allowed reasons |
|---|---|---|---|---|---|
| p1 | shape-safari | none | - | no-destination | all_ages, fits_time, matches_energy |
| p2 | colour-match | none | - | no-destination | all_ages, fits_time, matches_energy |
| p3 | five-senses | none | - | no-destination | all_ages, fits_time |

Request size: 3991 bytes (cap 10000).
Adapter outcome: `Ok` in 1.42 s (no queue: direct call).

| served by | model | prompt tokens | completion tokens | reasoning tokens | finish | adapter latency |
|---|---|---|---|---|---|---|
| CoreWeave | google/gemma-4-26b-a4b-it | 735 | 103 | 0 | stop | 1.42 s |

Raw answer (schema-constrained JSON):

```json
{"interests": ["birds", "puddles"], "interest_status": "no_match", "picks": [{"pair_id": "p1", "hook_id": "no-destination", "reason_ids": []}, {"pair_id": "p2", "hook_id": "no-destination", "reason_ids": []}, {"pair_id": "p3", "hook_id": "no-destination", "reason_ids": []}]}
```

Validation: 3 pick(s) kept, 0 dropped; interests no_match []

| pick | pair | activity | hook | reasons |
|---|---|---|---|---|
| 1 | p1 | shape-safari | no-destination |  |
| 2 | p2 | colour-match | no-destination |  |
| 3 | p3 | five-senses | no-destination |  |

### The call before this one (same evening, first wording)

The first attempt at the rule only added that a `place_kind "none"` pair is a valid pick
and that the model should still pick up to 3 when every pair is generic. With that
wording the same three pairs got the same answer as the two live Back Bay runs: served
by DeepInfra, 699 / 27 / 0 tokens, 1.28 s, `{"interests": ["birds", "puddles"],
"interest_status": "no_match", "picks": []}`. The model read "choose none only when no
pair is acceptable" together with an interest mismatch as a reason to pick nothing. The
second wording (above) says that every offered pair has already passed the rules and is
acceptable, that an interest mismatch only affects the order, and that fewer than three
picks are for fewer than three pairs. With it the model picked all three; through
`plan_outing` three validated picks are `source=MODEL`, state `complete`, with the
`PLACES_UNAVAILABLE` notice first (covered by
`tests/planner/test_plan_outing.py::test_with_places_down_the_model_is_asked_to_choose_among_the_generic_pairs`).
Two live calls were used for this, as approved.

