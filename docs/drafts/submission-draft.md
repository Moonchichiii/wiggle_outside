# Submission draft — Wiggle Outside (DEV, Hacktoberfest Open-Source AI Challenge, Week 1)

Status: outline only, 10 October 2026. Every bracketed item is evidence still to be
produced; nothing in brackets may be published as a claim until it exists. Follow the
official submission template; this outline only fixes the order and the honest claims
(PRODUCT-FIT §5.5).

## What it does (lead with the problem)

Wiggle Outside brings nearby places, the weather forecast and family activity ideas into
one quick search, so parents spend less time planning and more time outside.

Today a parent checks the weather, looks for somewhere nearby and tries to think of
something suitable for the children, then turns all of that into a plan. Wiggle Outside
does the combining: answer a few questions, get up to three practical ideas with
estimated travel time and the things we could not check, then put the phone away.

## How the open model is used

- The backend finds places (OpenStreetMap) and checks the forecast (Open-Meteo).
- Reviewed rules filter the activity list by ages, time, energy and access preferences.
- Gemma reads the optional "What are they into?" text and chooses among the eligible
  combinations; it never writes the instructions parents see.
- [One recorded example: the eligible pairs Gemma was given, its reading of the
  interests, its picks, and the cards the parent saw.]
- [Blinded comparison with the rules-only ranking, whatever it shows.]

## Demo and repository

- [Demo URL of the deployed planner, D48] · [repository link]
- [Short video of a real journey, including one failure and recovery]

## Why open innovation matters here

[Limited to what is shown: an inspectable, pinned open model behind one adapter; the
prompt, schema and activity list in the repository; who processes the answers in the
deployed version: our server, OpenRouter and the chosen model provider.]

## How it went outside

[A real outing using a suggestion: what we chose, what happened, a photo with no
identifiable children.]

## How it was built

[Honest note: AI tools helped explore the visual direction and plan and build the code;
what was reviewed by hand.]

## After the deadline

[README note on any commits after the submission time, as the rules require.]
