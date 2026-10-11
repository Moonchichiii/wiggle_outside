# Hosted model smoke (PLAN section 15 step 3)

Run on 2026-10-11 12:12 UTC with `scripts/model_smoke.py`. Model `google/gemma-4-26b-a4b-it` through OpenRouter, routing `provider.only` = ['nextbit', 'deepinfra', 'coreweave'], `require_parameters` true, fallbacks within the list, `max_tokens` 256, reasoning effort none, strict `json_schema` `selection.v2`, prompt `select.v2`. Controlled input: fixture places and a fixed interest text; no visitor data. The key is never written.

### Typical request (WALKTHROUGH family, 4 places)

Controlled interest text: `birds and puddles`

Pairs offered (exactly what the model saw, plus the straight-line distance for the reader):

| pair | activity | place kind | distance m | allowed hooks | allowed reasons |
|---|---|---|---|---|---|
| p1 | leaf-colour-hunt | park | 0 | expedition, explorer-club, pocket-adventure, secret-spot, todays-idea | all_ages, close_by, fits_time, matches_energy |
| p2 | shape-safari | playground | 0 | expedition, explorer-club, pocket-adventure, secret-spot, todays-idea | all_ages, close_by, fits_time, matches_energy |
| p3 | sound-map | nature_reserve | 1112 | expedition, explorer-club, pocket-adventure, secret-spot, todays-idea | all_ages, fits_time |
| p4 | sound-map | park | 1236 | expedition, explorer-club, pocket-adventure, secret-spot, todays-idea | all_ages, fits_time |
| p5 | nature-bingo | park | 0 | expedition, explorer-club, pocket-adventure, secret-spot, todays-idea | all_ages, close_by, fits_time, matches_energy |
| p6 | puddle-jumping | playground | 0 | expedition, explorer-club, pocket-adventure, secret-spot, todays-idea | all_ages, close_by, fits_time, matches_energy |
| p7 | colour-match | nature_reserve | 1112 | expedition, explorer-club, pocket-adventure, secret-spot, todays-idea | all_ages, fits_time, matches_energy |
| p8 | shape-safari | park | 0 | expedition, explorer-club, pocket-adventure, secret-spot, todays-idea | all_ages, close_by, fits_time, matches_energy |
| p9 | colour-match | playground | 0 | expedition, explorer-club, pocket-adventure, secret-spot, todays-idea | all_ages, close_by, fits_time, matches_energy |
| p10 | five-senses | nature_reserve | 1112 | expedition, explorer-club, pocket-adventure, secret-spot, todays-idea | all_ages, fits_time |
| p11 | sound-map | park | 0 | expedition, explorer-club, pocket-adventure, secret-spot, todays-idea | all_ages, close_by, fits_time |
| p12 | five-senses | playground | 0 | expedition, explorer-club, pocket-adventure, secret-spot, todays-idea | all_ages, close_by, fits_time |

Request size: 7468 bytes (cap 10000).
Adapter outcome: `Ok` in 1.68 s (no queue: direct call).

| served by | model | prompt tokens | completion tokens | reasoning tokens | finish | adapter latency |
|---|---|---|---|---|---|---|
| DeepInfra | google/gemma-4-26b-a4b-it | 1598 | 93 | 0 | stop | 1.68 s |

Raw answer (schema-constrained JSON):

```json
{"interests": ["birds", "puddles"], "interest_status": "matched", "picks": [{"pair_id": "p5", "hook_id": "pocket-adventure", "reason_ids": ["all_ages", "close_by"]}, {"pair_id": "p6", "hook_id": "todays-idea", "reason_ids": ["all_ages", "close_by"]}]}
```

Validation: 2 pick(s) kept, 0 dropped; interests matched ['birds', 'puddles']

| pick | pair | activity | hook | reasons |
|---|---|---|---|---|
| 1 | p5 | nature-bingo | pocket-adventure | all_ages, close_by |
| 2 | p6 | puddle-jumping | todays-idea | all_ages, close_by |
