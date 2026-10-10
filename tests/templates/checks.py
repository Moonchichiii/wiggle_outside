"""Structural checks every rendered page has to pass (DESIGN-SPEC sections 11 and 12).

Standard library only: WP8 adds no dependency (BUILD-PACKAGES section 2).

These are markup and structure checks. They are **not** an accessibility result: axe, the
contrast script and the keyboard, screen-reader, forced-colours and zoom walkthroughs are
WP9b's and have not run.
"""

import re
from collections import Counter
from typing import Final

from parse import read

# An inline event handler: on<name>= but not a legitimate attribute that merely starts
# with "on" (there is none in these templates).
INLINE_HANDLER: Final = re.compile(r"\son[a-z]+\s*=", re.IGNORECASE)
INLINE_STYLE: Final = re.compile(r"\sstyle\s*=", re.IGNORECASE)
SVG_TAG: Final = re.compile(r"<svg[^>]*>")


def assert_nothing_inline(name: str, html: str) -> None:
    """No inline script, style or event handler, and no javascript: URL (section 11)."""
    assert "<script" not in html.lower(), f"{name}: inline or unexpected script"
    assert not INLINE_STYLE.search(html), f"{name}: inline style"
    assert not INLINE_HANDLER.search(html), f"{name}: inline event handler"
    assert "javascript:" not in html.lower(), f"{name}: javascript: URL"


def assert_escaped_once(name: str, html: str) -> None:
    """Text is escaped exactly once, by Jinja autoescape (BACKEND-CONTRACT section 7)."""
    assert "&amp;amp;" not in html, f"{name}: text escaped twice"
    assert "&amp;lt;" not in html, f"{name}: text escaped twice"


def assert_ids_unique(name: str, html: str) -> None:
    doc = read(html)
    duplicates = [value for value, count in Counter(doc.ids).items() if count > 1]
    assert not duplicates, f"{name}: duplicate id {duplicates}"


def assert_references_resolve(name: str, html: str) -> None:
    """Every aria-describedby, aria-labelledby, label `for`, #fragment and <use> target."""
    doc = read(html)
    known = set(doc.ids)
    for kind, targets in (
        ("aria-describedby", doc.described_by),
        ("aria-labelledby", doc.labelled_by),
        ("label for", doc.label_targets),
        ("link #fragment", doc.fragment_links),
        ("svg use", doc.use_refs),
    ):
        for target in targets:
            assert target in known, f"{name}: {kind} points at a missing {target}"


def assert_controls_are_labelled(name: str, html: str) -> None:
    """Every visible control has a visible label, not a hidden one."""
    doc = read(html)
    for control in doc.controls:
        if control.tag == "button":
            assert "aria-label" not in control.attrs, f"{name}: a button hides its label"
            continue
        if control.tag != "input" or control.attrs.get("type") == "hidden":
            continue
        labelled = control.in_label or control.attrs.get("id") in doc.label_targets
        assert labelled, f"{name}: unlabelled input {control.attrs}"


def assert_svgs_are_sized(name: str, html: str) -> None:
    """Every inline svg carries width and height attributes (DESIGN-SPEC section 3).

    An svg with a viewBox and no intrinsic size falls back to 300 x 150, so the page has to
    stay usable when the stylesheet fails. That has already happened once.
    """
    svgs = SVG_TAG.findall(html)
    assert svgs, f"{name}: no inline svg found"
    missing = [tag for tag in svgs if "width=" not in tag or "height=" not in tag]
    assert not missing, f"{name}: svg without width/height: {missing}"


def assert_decorative_svgs_are_hidden(name: str, html: str) -> None:
    """Every icon is decorative: the text carries the meaning (DESIGN-SPEC section 5)."""
    svgs = SVG_TAG.findall(html)
    exposed = [tag for tag in svgs if 'aria-hidden="true"' not in tag]
    assert not exposed, f"{name}: svg not aria-hidden: {exposed}"


def assert_page_is_sound(name: str, html: str) -> None:
    """Run every structural check over one rendered page."""
    assert_nothing_inline(name, html)
    assert_escaped_once(name, html)
    assert_ids_unique(name, html)
    assert_references_resolve(name, html)
    assert_controls_are_labelled(name, html)
    assert_svgs_are_sized(name, html)
    assert_decorative_svgs_are_hidden(name, html)
