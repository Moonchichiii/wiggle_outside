// Enhancement only (DESIGN-SPEC section 6, PLAN section 5): the form is complete without
// this file. "Use my location" is rendered `hidden`, because a button that cannot work must
// not be offered; this unhides it once a real script is running in a browser that has the
// geolocation API. One browser prompt on click. The rounded coordinates go into the form's
// own hidden fields and travel with the ordinary POST /plan when the person submits:
// nothing is sent from here, and no server endpoint exists for it.
//
// No inline script and no inline handler anywhere, so the canonical CSP (PLAN section 9)
// needs no unsafe-inline. Loaded with `defer`, hashed and SRI-pinned by the build.
"use strict";

// Two decimals, about a kilometre (PLAN section 5). The server rounds again.
const PRECISION = 100;
const OPTIONS = { enableHighAccuracy: false, timeout: 10000, maximumAge: 300000 };

function rounded(value) {
  return (Math.round(value * PRECISION) / PRECISION).toFixed(2);
}

function hiddenField(form, name) {
  const existing = form.elements.namedItem(name);
  if (existing instanceof HTMLInputElement && existing.type === "hidden") {
    return existing;
  }
  const input = document.createElement("input");
  input.type = "hidden";
  input.name = name;
  form.prepend(input);
  return input;
}

// The status line takes the place hint's slot while it shows, so the form does not grow
// (the desktop form fits one screen, TC-011).
function say(status, hint, key) {
  status.textContent = status.dataset[key] || "";
  status.hidden = false;
  if (hint) {
    hint.hidden = true;
  }
}

function quiet(status, hint) {
  status.hidden = true;
  status.textContent = "";
  if (hint) {
    hint.hidden = false;
  }
}

function enhance(button) {
  const form = button.form;
  const status = form ? form.querySelector("[data-wo-locate-status]") : null;
  const place = form ? form.elements.namedItem("place") : null;
  if (!form || !status || !(place instanceof HTMLInputElement)) {
    return;
  }
  const hint = form.querySelector("#place-hint");
  let asking = false;

  button.hidden = false;
  button.addEventListener("click", () => {
    if (asking) {
      return;
    }
    asking = true;
    button.setAttribute("aria-busy", "true");
    say(status, hint, "asking");
    navigator.geolocation.getCurrentPosition(
      (position) => {
        hiddenField(form, "lat").value = rounded(position.coords.latitude);
        hiddenField(form, "lon").value = rounded(position.coords.longitude);
        hiddenField(form, "location_mode").value = "coords";
        hiddenField(form, "location_label").value = "";
        place.value = "";
        say(status, hint, "using");
        asking = false;
        button.removeAttribute("aria-busy");
      },
      (error) => {
        say(status, hint, error.code === error.PERMISSION_DENIED ? "denied" : "failed");
        asking = false;
        button.removeAttribute("aria-busy");
      },
      OPTIONS,
    );
  });

  // Typing a town again means the typed town, not the coordinates from before.
  place.addEventListener("input", () => {
    if (place.value.trim() === "") {
      return;
    }
    hiddenField(form, "location_mode").value = "typed";
    quiet(status, hint);
  });
}

// The loader (TC-011): shown only while an explicitly submitted search is pending, never
// on page load. The browser's navigation clears it with the page on success, a 422 or a
// network error; `pageshow` clears it when the page comes back from the back-forward
// cache; and a safety timer clears it when nothing answered within the server's own
// deadline plus a margin, so it can never be left showing. No polling, no requests.
const LOADER_SAFETY_MS = 30000;

function pending(form) {
  const loader = form.querySelector("[data-wo-loader]");
  const status = loader ? loader.querySelector("[data-wo-loader-status]") : null;
  if (!loader || !status) {
    return;
  }
  const actions = form.querySelector(".wo-actions");
  let timer = 0;

  function clear() {
    loader.hidden = true;
    if (actions) {
      actions.hidden = false;
    }
    status.textContent = "";
    for (const button of form.querySelectorAll('button[type="submit"]')) {
      button.removeAttribute("aria-busy");
    }
    if (timer) {
      window.clearTimeout(timer);
      timer = 0;
    }
  }

  form.addEventListener("submit", () => {
    loader.hidden = false;
    // The loader takes the button's place, so it is always where the click was.
    if (actions) {
      actions.hidden = true;
    }
    status.textContent = status.dataset.message || "";
    for (const button of form.querySelectorAll('button[type="submit"]')) {
      button.setAttribute("aria-busy", "true");
    }
    timer = window.setTimeout(clear, LOADER_SAFETY_MS);
  });
  window.addEventListener("pageshow", clear);
  window.addEventListener("pagehide", clear);
}

for (const form of document.querySelectorAll("form[data-wo-pending]")) {
  pending(form);
}

if ("geolocation" in navigator && window.isSecureContext) {
  for (const button of document.querySelectorAll("[data-wo-locate]")) {
    enhance(button);
  }
}
