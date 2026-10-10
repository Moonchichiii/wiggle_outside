# Security policy

## Reporting a vulnerability

Open a [private security advisory](https://github.com/Moonchichiii/wiggle_outside/security/advisories/new)
on this repository. Please do not open a public issue for a vulnerability.

Include what you did, what happened, and what you expected. A proof of concept helps but
is not required. You will get an acknowledgement within a few days; this is a solo
project, so please be patient with the timeline.

## Scope

This repository and the deployed planner. The planner holds no accounts and no personal
data beyond an opaque session, so the interesting areas are the session and CSRF handling,
the request limits, the content security policy, and the handling of untrusted input from
users, providers and the model.

## Out of scope

Reports produced only by an automated scanner with no demonstrated impact; missing headers
on endpoints that serve no content; and findings in the upstream providers themselves
(OpenStreetMap, Open-Meteo, OpenRouter) — report those to them.

## What this project does with untrusted input

Free text from the form goes to the model only, never to the place or weather providers,
and is never logged or cached. Place names and provider fields are treated as data and
escaped once at render. Model output is re-validated against the application's own
allowed IDs before anything is shown.
