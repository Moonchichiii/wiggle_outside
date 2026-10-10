"""Generate the Wiggle Outside static mock screens (baseline 8.20; design artefacts only).

Usage: python3 build_mocks.py <output-dir>   (writes the .html files next to mock.css)
Data follows docs/WALKTHROUGH.md; activity text is copied from docs/drafts/activities.toml.
"""
from pathlib import Path
import sys

OUT = Path(sys.argv[1])

S = 'fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"'
SYMBOLS = {
    "adult": f'<g {S}><circle cx="12" cy="5.5" r="2.6"/><path d="M8.2 21l1-6.8-1.6-.3.9-4.6c.3-1 1.1-1.6 2.1-1.6h2.6c1 0 1.8.7 2 1.6l.9 4.6-1.6.3 1 6.8"/></g>',
    "adult-with-child": f'<g {S}><circle cx="8.5" cy="5" r="2.3"/><path d="M5.6 21l.8-6-1.4-.3.8-4c.2-.9 1-1.5 1.9-1.5h2c.9 0 1.6.6 1.8 1.5l.7 3.6"/><circle cx="17" cy="10.5" r="1.9"/><path d="M14.6 21l.6-4.3-1-.2.6-2.4c.2-.7.8-1.1 1.5-1.1h1.4c.7 0 1.3.4 1.5 1.1l.6 2.4-1 .2.6 4.3"/></g>',
    "clock": f'<g {S}><path d="M12 3.2c5 .1 8.8 3.9 8.7 8.9-.1 4.9-4 8.7-8.9 8.6-4.9-.1-8.6-4-8.6-8.8.1-4.9 4-8.8 8.8-8.7z"/><path d="M12 7.5V12l3.2 2"/></g>',
    "snail": f'<g {S}><path d="M3 18.5h15.5c1.4 0 2.5-1.1 2.5-2.5V10"/><path d="M19.5 10l-.8-3.2M21.4 10.2l1-3"/><path d="M6 18.4c-1.8-1-2.7-3-2.2-5 .7-2.5 3.3-4.1 5.9-3.6 2.2.5 3.6 2.6 3.1 4.7-.4 1.7-2.1 2.8-3.8 2.4-1.3-.3-2-1.6-1.7-2.8"/></g>',
    "walker": f'<g {S}><circle cx="13" cy="4.6" r="2.2"/><path d="M8 21l3.2-6.2 2.8 2.6V21"/><path d="M11.2 14.8l.9-5.2-3.4 1.6-1.3 3"/><path d="M12.1 9.6l2.4 2.6 3 .8"/></g>',
    "whirlwind": f'<g {S}><path d="M3.5 6.5h13.2c2.3 0 3.6 2.6 1.4 3.9"/><path d="M5.5 11h10.3c2 0 3 2.3 1 3.4"/><path d="M8 15.5h5.6c1.6 0 2.2 2 .8 2.8"/><path d="M10.5 20h2"/></g>',
    "pin": f'<g {S}><path d="M12 21.2s-6.4-6.3-6.4-11.1c0-3.6 2.8-6.4 6.4-6.4s6.5 2.8 6.4 6.4c0 4.8-6.4 11.1-6.4 11.1z"/><circle cx="12" cy="10" r="2.3"/></g>',
    "check": f'<g {S}><path d="M4.5 12.8l4.6 4.4L19.6 6.6"/></g>',
    "alert": f'<g {S}><path d="M12 3.4L2.8 19.6c-.3.5.1 1.1.7 1.1h17c.6 0 1-.6.7-1.1z"/><path d="M12 9.5v4.6M12 17.2v.1"/></g>',
    "info": f'<g {S}><circle cx="12" cy="12" r="8.8"/><path d="M12 11v5.4M12 7.7v.1"/></g>',
    "x": f'<g {S}><path d="M6.5 6.8l11 10.6M17.3 6.6L6.7 17.2"/></g>',
    "cloud-rain": f'<g {S}><path d="M7 15.5h10.2c2.2 0 3.8-1.7 3.7-3.8-.1-2-1.8-3.5-3.8-3.4-.8-2.6-3.2-4.3-5.9-4.1-2.8.2-5 2.4-5.2 5.2-1.6.3-2.8 1.7-2.7 3.4.1 1.6 1.5 2.8 3.1 2.7z"/><path d="M8.5 18.4l-.8 2M12.4 18.4l-.8 2M16.3 18.4l-.8 2"/></g>',
    "spinner": f'<g {S}><path d="M12 3.5c4.7 0 8.5 3.8 8.5 8.5"/><path d="M5.2 7.2c-.8 1.3-1.4 2.8-1.6 4.4" opacity=".5"/><path d="M8.6 20.1c-2-.8-3.6-2.3-4.5-4.2" opacity=".3"/></g>',
    "print": f'<g {S}><path d="M7 9V3.8h10V9"/><rect x="3.6" y="9" width="16.8" height="7.6" rx="1.5"/><path d="M7 14.2h10v6H7z"/></g>',
}
SPRITE = '<svg class="vh" aria-hidden="true">' + "".join(
    f'<symbol id="i-{k}" viewBox="0 0 24 24">{v}</symbol>' for k, v in SYMBOLS.items()) + "</svg>"



def ic(name: str, cls: str = "icon") -> str:
    return f'<svg class="{cls}" aria-hidden="true" focusable="false"><use href="#i-{name}"/></svg>'


TAPE = ('<svg class="tape" viewBox="0 0 64 16" aria-hidden="true"><path d="M2 3.5l58-1.5 2 10.5-59 1.5z" '
        'fill="#FFFCF6" stroke="currentColor" stroke-width="2" stroke-linejoin="round"/></svg>')
DOODLES = ('<svg class="doodle leaf" viewBox="0 0 96 96" aria-hidden="true"><path d="M14 82C20 40 48 14 86 10c-2 38-26 66-66 70zM18 78L66 30" '
           'fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"/></svg>'
           '<svg class="doodle cloud" viewBox="0 0 96 64" aria-hidden="true"><path d="M20 52h52c10 0 18-8 17-18-1-9-9-15-18-14-4-11-15-17-27-15-11 2-19 11-20 22-8 1-13 8-12 15 1 6 3 10 8 10z" '
           'fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"/></svg>')

BANNER = ('<div class="mock-banner"><strong>Static mock, baseline 8.20.</strong> Design artefact, not application code. '
          'Sample data from WALKTHROUGH.md (places and weather are fixtures); copy for the hosted product. '
          '<strong>Fonts are a system-font placeholder</strong> until the Cabinet Grotesk and Switzer files and '
          'their licence are supplied (D41, prerequisite P1).</div>')


def page(title: str, body: str, main_cls: str = "") -> str:
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<link rel="stylesheet" href="mock.css">
</head>
<body>
{SPRITE}
{BANNER}
<div class="page">
{DOODLES}
<header class="masthead">
  <h1>Wiggle Outside</h1>
  <p class="soft m0">A few details. Up to three outdoor ideas near you.</p>
</header>
<main class="column {main_cls}">
{body}
</main>
</div>
</body>
</html>
"""


def tile(kind, name, value, label, icon=None, checked=False, extra=""):
    c = " checked" if checked else ""
    i = ic(icon) if icon else ""
    return (f'<label class="tile"><input type="{kind}" name="{name}" value="{value}"{c}{extra}>{i}'
            f'<span class="tile-label">{label}</span>{ic("check", "icon check")}</label>')


CARRIED = ('<input type="hidden" name="location_mode" value="coords"><input type="hidden" name="lat" value="60.12">'
           '<input type="hidden" name="lon" value="17.95"><input type="hidden" name="location_label" value="Bergby, Uppsala län, Sweden">'
           '<p class="carried m0"><strong>Bergby, Uppsala län, Sweden</strong> (kept from this search; no new place lookup)</p>')


def form(state: str, prog: str = "", inner: bool = False) -> str:
    """state: filled | error | busy"""
    err = state == "error"
    busy = state == "busy"
    summary = ""
    if err:
        summary = f"""<div class="notice alert" role="alert" tabindex="-1" id="error-summary">{ic('alert')}<div>
  <h2>Check these answers</h2>
  <ul><li><a href="#age-first">Kids' ages: pick at least one.</a></li>
  <li><a href="#place">Where are you: use your location or type a town or area.</a></li></ul></div></div>"""
    age_err = (f'<p class="field-error" id="ages-error">{ic("alert")}<span>Pick at least one age group.</span></p>'
               if err else "")
    place_err = (f'<p class="field-error" id="place-error">{ic("alert")}<span>Use your location or type a town or area.</span></p>'
                 if err else "")
    a_first = ' id="age-first" aria-describedby="ages-hint ages-error"' if err else ' aria-describedby="ages-hint"'
    ages = (tile("checkbox", "age_band", "0-2", "0–2", extra=a_first)
            + tile("checkbox", "age_band", "3-5", "3–5", checked=not err)
            + tile("checkbox", "age_band", "6-9", "6–9", checked=not err)
            + tile("checkbox", "age_band", "10-12", "10–12"))
    inv = (' aria-invalid="true" aria-describedby="place-hint place-error"' if err
           else ' aria-describedby="place-hint"')
    submit = ('<button class="btn btn-primary" type="submit" aria-busy="true">Finding outings…</button>'
              if busy else '<button class="btn btn-primary" type="submit">Find outings</button>')
    place_val = "" if (err or inner) else "Bergby"
    interests = "" if err else "birds, puddles" if inner else "birds and puddles"
    cls = "plan-form" if inner else "panel plan-form"
    return f"""<form class="{cls}" method="post" action="#plan" novalidate>
<input type="hidden" name="csrf_token" value="T1"><input type="hidden" name="idempotency_key" value="K-new">
<div class="vh" aria-hidden="true"><label for="hp{'-e' if inner else ''}">Leave this field empty</label><input type="text" id="hp{'-e' if inner else ''}" name="hp_note" value="" tabindex="-1" autocomplete="off"></div>
{summary}
<fieldset><legend class="q">Who's coming?</legend>
  <div class="tiles two">{tile("radio", "who", "solo", "Just me", "adult")}{tile("radio", "who", "kids", "Me and the kids", "adult-with-child", checked=True)}</div></fieldset>
<fieldset><legend class="q">Kids' ages</legend>
  <p class="hint" id="ages-hint">Pick all that apply.</p>
  <div class="tiles four{' invalid' if err else ''}">{ages}</div>{age_err}</fieldset>
<fieldset><legend class="q">Time, there and back</legend>
  <div class="tiles two">{tile("radio", "time", "30", "30 min", "clock")}{tile("radio", "time", "60", "1 hour", "clock", checked=not err)}{tile("radio", "time", "120", "2 hours", "clock")}{tile("radio", "time", "240", "Half day (4 h)", "clock")}</div></fieldset>
<fieldset><legend class="q">How much energy today?</legend>
  <p class="hint">We may suggest something gentler.</p>
  <div class="tiles three">{tile("radio", "energy", "gentle", "Gentle", "snail")}{tile("radio", "energy", "moderate", "Moderate", "walker", checked=True)}{tile("radio", "energy", "energetic", "High", "whirlwind")}</div></fieldset>
<fieldset><legend class="q">Where are you?</legend>
  {CARRIED if inner else ""}
  <button class="btn btn-secondary" type="button">{ic("pin")}Use my location</button>
  <label class="field" for="place{'-e' if inner else ''}">{"or type a different town or area" if inner else "or type a town or area"}</label>
  <p class="hint" id="place-hint">Please don't type a street address. We look the town up with OpenStreetMap's search and keep the lookup on our server for up to 30 days to avoid repeat requests.</p>
  <input type="text" id="place{'-e' if inner else ''}" name="place" value="{place_val}" autocomplete="address-level2"{inv}>{place_err}</fieldset>
<fieldset><legend class="q">What are they into? <span class="soft">(optional)</span></legend>
  <p class="hint" id="int-hint">{"These are the interests we recognised. Edit them for your next search." if inner else "For example: birds, puddles, running."} Optional. Don't include personal details. We send this to our AI model provider to choose ideas; we don't store it.</p>
  {"" if inner else "<p class=\"mock-note\">Mock note: EN/SV/FR are evaluation targets; no language claim in product copy until evaluated.</p>"}
  <label class="vh" for="interests{'-e' if inner else ''}">What are they into?</label>
  <input type="text" id="interests{'-e' if inner else ''}" name="interests_text" maxlength="120" value="{interests}" aria-describedby="int-hint"></fieldset>
<details class="more"><summary>Anything to account for?</summary>
  <label class="checkrow"><input type="checkbox" name="stroller" value="1"><span>We're bringing a stroller</span></label>
  <label class="checkrow"><input type="checkbox" name="step_free" value="1" aria-describedby="sf-hint"><span>Prefer places reported as step-free</span></label>
  <p class="hint" id="sf-hint">Places OpenStreetMap reports as step-free come first. We can't check this ourselves.</p>
</details>
<div class="actions">{submit}</div>
{prog}
</form>"""


IDEAS = {
    "i1": dict(v="sage", title="Puddle jumping championship",
               intro="A pocket-sized adventure for right now.",
               reasons=["It's close by.", "The activity list includes all your selected age groups."],
               place="Linden Park", kind="park", dist="0.6", travel=24, dur=36,
               labels=["Admission not verified", "Step-free access not verified"], interests={"puddles", "running"}),
    "i4": dict(v="peach", title="Nature bingo",
               intro="The explorer club meets here today.",
               reasons=["Estimated to fit your time, including travel.", "It matches the energy you asked for."],
               place="Birchwood Nature Area", kind="nature area", dist="0.9", travel=36, dur=24,
               labels=["Step-free access not verified"], interests={"animals", "birds", "trees"}),
    "i7": dict(v="butter", title="Leaf colour hunt",
               intro="Here's today's idea for getting outside.",
               reasons=["It's the right season for it.", "It's close by."],
               place="Oak Lane Park", kind="park", dist="0.4", travel=16, dur=44,
               labels=["Admission not verified", "OpenStreetMap reports step-free access"], interests={"colours", "trees"}),
}
WEATHER = "Weather for 10:31–11:31, checked at 10:31: cloudy with showers possible (up to 40 %), 11–12 °C, wind up to 18 km/h."
PRINT_CONTEXT = ("Planned for Sat 10 Oct 2026, 10:31–11:31 (Europe/Stockholm), near Bergby, Uppsala län, Sweden. "
                 "Weather checked at 10:31 on Sat 10 Oct 2026; times are estimates. "
                 "Check the weather again before you go if plans change.")
TAGS = ("birds", "puddles")


def card(key, variant):
    c = IDEAS[key]
    labels = "".join(f"<li>{x}</li>" for x in c["labels"])
    return f"""<article class="idea {variant}" aria-labelledby="t-{key}">{TAPE}
  <h3 id="t-{key}">{c['title']}</h3>
  <p class="intro">{c['intro']}</p>
  <p class="practical">{ic('pin', 'icon')}<span><strong>{c['place']}</strong> · {c['kind']} · about {c['dist']} km away · {c['travel']} min there and back · {c['dur']} min activity</span></p>
  <ul class="labels" aria-label="Not verified">{labels}</ul>
  <a class="more-link" href="04-detail-bingo.html">Read the full activity<span class="vh">: {c['title']}</span></a>
</article>"""


def results():
    return f"""<section class="results" aria-labelledby="results-heading">
<h2 id="results-heading" tabindex="-1">Here's what we found</h2>
<div class="answers">
  <p class="m0"><strong>Me and the kids (3–5, 6–9)</strong> · 1 hour · Moderate · near Bergby, Uppsala län, Sweden</p>
  <details class="change"><summary>Change answers</summary>{form("filled", inner=True)}</details>
</div>
<div class="weather-once">{ic('cloud-rain', 'icon icon-32')}<p class="m0">{WEATHER}</p></div>
<div class="interests-box"><p class="m0"><strong>We think they're into:</strong> {", ".join(TAGS)}.</p>
<p class="soft m0">To change these, edit "What are they into?" under Change answers.</p></div>
<div class="cards">{card("i1", "sage")}{card("i4", "peach")}{card("i7", "butter")}</div>
</section>"""


def night() -> str:
    return f"""<section class="results" aria-labelledby="night-heading">
<h2 id="night-heading" tabindex="-1">The adventures can wait till morning.</h2>
<p>Time to put the phone down and get some rest. The outdoors will still be there tomorrow.</p>
<div class="answers">
  <p class="m0"><strong>Me and the kids (3–5, 6–9)</strong> · 1 hour · Moderate · near Bergby, Uppsala län, Sweden</p>
  <details class="change"><summary>Change answers</summary>{form("filled", inner=True)}</details>
</div>
<p class="mock-note">Mock note: fixed copy chosen by code when a family outing would start after sunset or before sunrise (DAYLIGHT_NIGHT). When it would start in daylight but end after sunset, the heading is "Not enough daylight for this one." and the text "The outing would end after sunset. Change your answers and we’ll check the daylight and the weather again, or leave the adventure for tomorrow." (TC-002) No model call.</p>
</section>"""


def busy_note() -> str:
    return f"""<div class="notice progress-box" role="status" aria-live="polite"><div class="progress">{ic('spinner')}<p class="m0">This can take up to 20 seconds.</p></div></div>"""


BINGO = ["a bird", "a fallen feather", "something round", "a spiky leaf", "moss",
         "a dog on a walk", "a cloud shaped like an animal", "a bench", "something red"]


def detail(not_current: bool):
    key = "i1" if not_current else "i4"
    c = IDEAS[key]
    m = sorted(c["interests"] & {"birds"}) if not_current else sorted(c["interests"] & set(TAGS))
    note = ("""<div class="notice">""" + ic("info") +
            """<p class="m0">This idea is no longer in your current list. It's shown as it was first suggested.</p></div>"""
            if not_current else "")
    if not_current:
        body = """<section><h3>What to do</h3><ol>
<li>Find three puddles on the path.</li>
<li>Judge each jump: biggest splash, quietest landing, silliest jump.</li>
<li>Award points and crown a champion.</li></ol></section>
<section><h3>Nice to have</h3><ul>
<li>wellies (or shoes that may get wet)</li>
<li>a towel for the way home (or head straight home to change)</li></ul></section>
<section><h3>Another way to play</h3><p>Judge splashes by sound or by stepping instead of jumping.</p></section>
<section><h3>Safety</h3><p>Small, shallow puddles on paths only. Never near roads, ponds or streams.</p></section>
<section><h3>Ask on the way home</h3><p>Which puddle was the deepest, and how could you tell before jumping?</p></section>"""
    else:
        rows = "".join("<tr>" + "".join(f"<td>{BINGO[r * 3 + k]}</td>" for k in range(3)) + "</tr>" for r in range(3))
        body = f"""<section><h3>What to do</h3><ol>
<li>Look at the nine things on the card together.</li>
<li>Tick each one when someone spots it.</li>
<li>Three in a row wins. A full card wins everything.</li></ol></section>
<section><h3 id="bingo-h">Your bingo card</h3><table class="bingo" aria-labelledby="bingo-h"><tbody>{rows}</tbody></table></section>
<section><h3>Nice to have</h3><ul><li>the printed card (or read the list from the screen once before you go)</li></ul></section>
<section><h3>Another way to play</h3><p>Swap any item for one you can hear or touch, such as birdsong or rough bark.</p></section>
<section><h3>Safety</h3><p>Look and point, no need to touch or pick anything.</p></section>
<section><h3>Ask on the way home</h3><p>What did you spot that wasn't on the card?</p></section>"""
    match = f'<p class="match">{ic("check")} Matches the interests: {", ".join(m)}</p>' if m else ""
    return f"""<p class="no-print"><a class="back-link" href="03-results.html">Back to results</a></p>
{note}
<article class="panel detail" aria-labelledby="d-title">
<h2 id="d-title">{c['title']}</h2>
<p class="intro">{c['intro']}</p>
<section><h3>Why this idea</h3><ul class="reasons">{''.join(f'<li>{r}</li>' for r in c['reasons'])}</ul>{match}</section>
<p><strong>{c['place']}</strong> · {c['kind']} · about {c['dist']} km away in a straight line<br>
About {c['travel']} min there and back · {c['dur']} min activity (estimates)</p>
<ul class="labels">{''.join(f'<li>{x}</li>' for x in c['labels'])}</ul>
{body}
<div class="weather-once">{ic('cloud-rain', 'icon icon-32')}<p class="m0">{WEATHER}</p></div>
<p class="print-context">{PRINT_CONTEXT}</p>
<p class="soft source">Place data © OpenStreetMap contributors; weather from Open-Meteo.</p>
<div class="actions no-print"><button class="btn btn-primary" type="button">{ic('print')}Print this card</button>
<a class="btn btn-secondary" href="03-results.html">Back to results</a></div>
</article>"""


OUT.mkdir(parents=True, exist_ok=True)
files = {
    "01-form.html": page("Form · Wiggle Outside mock", form("filled")),
    "01b-form-error.html": page("Form with errors · Wiggle Outside mock", form("error")),
    "02-waiting.html": page("Waiting · Wiggle Outside mock", form("busy", busy_note())),
    "03-results.html": page("Results · Wiggle Outside mock", results()),
    "04-detail-bingo.html": page("Detail and print · Wiggle Outside mock", detail(False)),
    "05-night.html": page("Night · Wiggle Outside mock", night()),
}
for name, html in files.items():
    (OUT / name).write_text(html, encoding="utf-8")
print("\n".join(files))
