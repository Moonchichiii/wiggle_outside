"""Check the static mocks and write screenshots plus a JSON report.

Usage:
  python3 check_mocks.py <mocks-dir> <path-to-axe.min.js>
Requires: Python Playwright with Chromium; axe-core 4.10.2 (bun add axe-core@4.10.2).
Writes <mocks-dir>/screens/*.png and <mocks-dir>/reports/check-report.json.
These checks cover static pages only; they do not establish accessibility.
"""
import json
import re
import sys
from importlib.metadata import version
from pathlib import Path

from playwright.sync_api import sync_playwright

d = Path(sys.argv[1]).resolve()
axe_src = Path(sys.argv[2]).read_text()
axe_version = re.search(r"axe v([0-9.]+)", axe_src[:500])
shots = d / "screens"
reports = d / "reports"
shots.mkdir(exist_ok=True)
reports.mkdir(exist_ok=True)
pages = sorted(p.stem for p in d.glob("*.html"))
report: dict = {"tools": {"playwright": version("playwright"),
                          "axe-core": axe_version.group(1) if axe_version else "unknown"},
                "rules": ["wcag2a", "wcag2aa", "wcag21aa", "wcag22aa"], "pages": {}}

static = {}
for n in pages:
    html = (d / f"{n}.html").read_text()
    static[n] = {"inline_style_attributes": html.count(" style="),
                 "script_elements": html.count("<script")}

with sync_playwright() as p:
    b = p.chromium.launch()
    report["tools"]["chromium"] = b.version
    for w in (320, 390, 1440):
        pg = b.new_page(viewport={"width": w, "height": 900}, reduced_motion="reduce")
        for n in pages:
            pg.goto((d / f"{n}.html").as_uri())
            pg.wait_for_load_state("networkidle")
            pg.evaluate("document.fonts.ready")
            r = report["pages"].setdefault(n, dict(static[n]))
            r[f"scroll_width_{w}"] = pg.evaluate("document.documentElement.scrollWidth")
            # smallest interactive target (visible controls only)
            r[f"min_target_px_{w}"] = pg.evaluate("""Math.round(Math.min(...[...document.querySelectorAll(
              'button, a, summary, label.tile, input[type=text]')].filter(e => e.offsetParent)
              .map(e => e.getBoundingClientRect().height)))""")
            # tile labels that wrap onto a second line
            r[f"wrapped_tile_labels_{w}"] = pg.evaluate("""[...document.querySelectorAll('.tile-label')]
              .filter(e => e.offsetParent && e.getBoundingClientRect().height > 1.6 * parseFloat(getComputedStyle(e).lineHeight))
              .map(e => e.textContent)""")
            if w in (390, 1440):
                pg.screenshot(path=str(shots / f"{n}-{w}.png"), full_page=True)
            if w == 390:
                pg.add_script_tag(content=axe_src)
                r["axe_violations_390"] = pg.evaluate(
                    "axe.run(document,{runOnly:%s}).then(x=>x.violations.map(v=>({id:v.id,nodes:v.nodes.length})))"
                    % json.dumps(report["rules"]))
        pg.close()
    for n in [p for p in pages if p.startswith("04")]:
        pg = b.new_page(viewport={"width": 800, "height": 1100})
        pg.goto((d / f"{n}.html").as_uri())
        pg.emulate_media(media="print")
        pg.screenshot(path=str(shots / f"{n}-print.png"), full_page=True)
        report["pages"][n]["print_context_visible"] = pg.is_visible(".print-context")
        pg.close()
    b.close()

(reports / "check-report.json").write_text(json.dumps(report, indent=1, ensure_ascii=False))
print(json.dumps(report, indent=1, ensure_ascii=False))
