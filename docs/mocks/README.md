# Static mock screens — baseline 8.20

These are design artefacts for Mats's review (PLAN §15 step 1). They are not application
code, and approving them does not start the build. The data comes from the fixture
journey in `../WALKTHROUGH.md`: place Bergby, Uppsala län; window 10:31–11:31
Europe/Stockholm; interests "birds and puddles"; deployment mode `hosted_live`, so the town and interests
hints use the hosted privacy wording. All decisions shown are accepted (step-free is the
preference, D42 P). Only the fonts are open: they are a disclosed system-font
placeholder until prerequisite P1 (D41).

| Screen | Files | Shows |
|---|---|---|
| 1. Form | `01-form.html`, `01b-form-error.html` | The compact form (8.19, toward the approved concept board): smaller question headings, tighter spacing, ages four across and energy three across on phones with the control above the label, stroller and step-free as plain checkbox rows. Every plan form now contains the honeypot field (D49), hidden from keyboard and screen readers; axe still reports no violations. The optional panel splits stroller and step-free (D42). The error version has a summary first, then inline errors |
| 2. Waiting | `02-waiting.html` | The static busy state (D43): "Finding outings…" and "This can take up to 20 seconds." No Stop button, no stage messages |
| 5. Night (family path) | `05-night.html` | The fixed DAYLIGHT_NIGHT copy (Mats 8.20) with the answers summary and "Change answers"; a mock note gives the DAYLIGHT_TOO_SHORT wording. No cards, no model call |
| 3. Results and card | `03-results.html`, `04-detail-bingo.html` | One column: the answers summary with "Change answers" (prefilled form with the carried location and the tag labels in the interests field, D46), the weather once, the inferred interests as plain labels, then three tightened cards (title, one playful sentence, one practical line, labels, link). The detail page adds "Why this idea", the bingo grid and a dated print context. "Change answers" labels the prefilled interests as recognised tags |

**Fonts (8.19):** Shantell Sans is removed. The mocks use a **disclosed system-font
placeholder** (headings at weight 800 standing in for Cabinet Grotesk ExtraBold). They
will be regenerated with Cabinet Grotesk and Switzer once the WOFF2 files are in the
package (D41), together with the glyph-coverage and layout-shift checks. The passing
report below applies to these placeholder-font screens only, not to the concept board
or the final typography.

Screenshots are in `screens/`, at 390 px and 1440 px, plus `04-detail-bingo-print.png`.
Removed in 8.11: the long-wait and "not in current list" screens (D43, D46).

## Reproduce the checks

From `docs/mocks/`:

```
bun add axe-core@4.10.2                                  # in any scratch folder; npm registry via Bun
python3 tools/build_mocks.py .                           # regenerates the .html files
python3 tools/check_mocks.py . <path>/node_modules/axe-core/axe.min.js
```

`check_mocks.py` needs Python Playwright with Chromium. It writes `screens/*.png` and
`reports/check-report.json`, which records the tool versions (Playwright 1.56.0,
Chromium 141.0.7390.37, axe-core 4.10.2) and, for each page:

- inline `style` attributes and `<script>` elements (both 0);
- horizontal scroll width at 320, 390 and 1440 px (no overflow);
- the smallest visible interactive target (44 px or more on every page);
- tile labels that wrap onto a second line (wrapping is allowed; "10–12" never wraps);
- axe violations at 390 px for the wcag2a, wcag2aa, wcag21aa and wcag22aa rules (none);
- whether the print context is visible in print media (yes).

## Status of the claims

| Kind | What |
|---|---|
| Verified on these static mocks (report above) | No overflow at 320, 390 or 1440 px; targets of 44 px or more; no axe rule violations at 390 px; no inline styles or scripts; dated print context visible when printed |
| Documented only | Everything about behaviour: the busy state, focus movement, resubmission and the expiry views. The mocks show states; they don't run them |
| Not done | Keyboard and Orca walkthroughs, 400 % zoom, forced colours, real phones, printing on paper, and the application itself. None of this shows that the product is accessible |

## Questions for review

1. Does the night screen read as intended: playful, no claim that the children are
   asleep, no promise about tomorrow's weather?
