// Enhancement only (DESIGN-SPEC section 11): the detail page is complete without this
// file. The print button is rendered `hidden`, because a button that cannot print must not
// be offered; this unhides it once a real script is running, and the printed-card note
// (PRINT_HELP) names the browser's own print menu either way.
//
// No inline script and no inline handler anywhere, so the canonical CSP (PLAN section 9)
// needs no unsafe-inline. Loaded with `defer`, hashed and SRI-pinned by the build.
"use strict";

for (const button of document.querySelectorAll("[data-wo-print]")) {
  button.hidden = false;
  button.addEventListener("click", () => {
    window.print();
  });
}
