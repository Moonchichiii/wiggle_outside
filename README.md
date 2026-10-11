# Wiggle Outside

Find a realistic outdoor activity near you, for the next hour or two, then put the phone
away.

Answer five short questions — who is coming, how long you have, how much energy, where you
are, anything to account for — and Wiggle Outside offers up to three grounded ideas, each
one a nearby place from OpenStreetMap paired with a reviewed activity that suits the
forecast, the daylight and the ages you named. If nothing suitable exists right now, it
says so rather than padding the list.

An open model (Gemma 4 26B A4B, reached through OpenRouter) ranks activity–place pairs
that the application has already validated, and picks one reviewed story hook and up to
two reason codes per idea. It writes none of the text you read, and it never invents a
place. When the model is unavailable the application falls back to its own deterministic
ranking and labels the result as such. The model prompt goes through OpenRouter to one
of the approved providers it selects; the approved list rests on OpenRouter's published
data policy per provider (no training, no prompt retention), not on an independent
review of each provider's terms (TC-010).

Built for the Hacktoberfest Open-Source AI Challenge, Week 1 ("Touch Grass").

## Status

**Specification and bootstrap.** The accepted build specification is in [`docs/`](docs/) —
start with [`docs/PLAN.md`](docs/PLAN.md) §0 for the decision register and
[`docs/BUILD-PACKAGES.md`](docs/BUILD-PACKAGES.md) for what each package delivers. Changes
after the frozen baseline are tracked changes in
[`docs/decisions/tracked-changes/`](docs/decisions/tracked-changes/).

Nothing here is deployed, and no measurement or accessibility claim in the documents has
been verified yet. Per TC-006, the quality gates currently enforced are ruff, mypy,
import-linter, pytest and the contract tests; the rest arrive with WP9b, and until then
nothing is released or described as supply-chain verified.

## Development

Requires [uv](https://docs.astral.sh/uv/), [bun](https://bun.sh/) and PowerShell 7.

The two headline fonts (Cabinet Grotesk and Switzer, both from
[fontshare.com](https://www.fontshare.com/)) are **not in this repository**: the
Fontshare Font Licence 2.0 allows self-hosting them but not redistributing the files
publicly. See [`frontend/fonts/README.md`](frontend/fonts/README.md). The app renders
correctly without them, on the metric-matched system-font fallback.

```powershell
uv sync --all-groups
./scripts/check.ps1
```

`check.ps1` is the one gate script: CI runs the same file on Linux with `shell: pwsh`.

## Licence and credits

Apache-2.0 — see [LICENSE](LICENSE). Place data © OpenStreetMap contributors (ODbL);
weather from [Open-Meteo](https://open-meteo.com/); geocoding by
[Nominatim](https://nominatim.org/) and places by [Overpass](https://overpass-api.de/).
Security policy: [SECURITY.md](SECURITY.md).
