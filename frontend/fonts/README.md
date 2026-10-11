# Fonts

Two variable WOFF2 faces, used per DESIGN-SPEC §1.2 (D41):

| File | Family | Role |
|---|---|---|
| `CabinetGrotesk-Variable.woff2` | Cabinet Grotesk Variable (`wght` 100–900) | headings and activity titles, weight 800 |
| `Switzer-Variable.woff2` | Switzer Variable (`wght` 100–900) | body 400, labels 500, buttons and emphasis 600 |

Both are from **[fontshare.com](https://www.fontshare.com/)**, the Indian Type Foundry's
free font service, and are used unmodified.

## The Fontshare files are deliberately not in this repository

They are licensed under the **Fontshare Font Licence (FFL) 2.0**, which permits
self-hosting them on our own site but **forbids redistributing the font files in a public
repository** (TC-007, prerequisite P1 resolved).

So `.gitignore` excludes `*.woff2` here, and this README is the only tracked file in the
directory. To work on the design locally, put the two files in this folder; to deploy,
supply them from private storage at image-build time — `Dockerfile` copies
`frontend/fonts/` when it is present and simply omits the fonts when it is not.

Nothing breaks without them. `frontend/css/tokens.css` declares `font-display: swap` and a
metric-matched fallback, so the system-font stack renders instead, at the same size and in
the same line box.

## Checking them

```powershell
uv run python scripts/check_fonts.py
```

Reports the character map against the DESIGN-SPEC §1.2 set (English, Swedish, French and
the typographic marks the copy deck uses) and the metrics the fallback overrides are
derived from. Both faces currently cover the whole set.
