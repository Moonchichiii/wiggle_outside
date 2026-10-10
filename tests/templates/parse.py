"""A small HTML reader for the template tests.

Standard library only: WP8 adds no dependency (BUILD-PACKAGES section 2). It records
just enough structure to check labelling, ids, references and document order.
"""

from dataclasses import dataclass, field
from html.parser import HTMLParser

Attrs = dict[str, str]


@dataclass
class Control:
    tag: str
    attrs: Attrs
    in_label: bool


@dataclass
class Document:
    controls: list[Control] = field(default_factory=list)
    ids: list[str] = field(default_factory=list)
    label_targets: list[str] = field(default_factory=list)
    described_by: list[str] = field(default_factory=list)
    labelled_by: list[str] = field(default_factory=list)
    fragment_links: list[str] = field(default_factory=list)
    # Every <use href="#..."> in the page, so a missing sprite symbol is caught here
    # rather than by someone looking at a blank icon.
    use_refs: list[str] = field(default_factory=list)
    # (input value, the text of the label that wraps it), in document order.
    option_labels: list[tuple[str, str]] = field(default_factory=list)

    def named(self, name: str) -> list[Control]:
        return [c for c in self.controls if c.attrs.get("name") == name]


class Reader(HTMLParser):
    """Collects controls, ids and references, and the text of each wrapping label."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.doc = Document()
        self._label_depth = 0
        self._pending_value: str | None = None
        self._text: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values: Attrs = {k: (v if v is not None else "") for k, v in attrs}
        self._record_references(tag, values)
        if tag == "label":
            self._open_label(values)
        if tag in {"input", "select", "textarea", "button"}:
            self._open_control(tag, values)

    def _record_references(self, tag: str, values: Attrs) -> None:
        if "id" in values:
            self.doc.ids.append(values["id"])
        if "aria-describedby" in values:
            self.doc.described_by.extend(values["aria-describedby"].split())
        if "aria-labelledby" in values:
            self.doc.labelled_by.extend(values["aria-labelledby"].split())
        if tag == "a" and values.get("href", "").startswith("#"):
            self.doc.fragment_links.append(values["href"][1:])
        if tag == "use" and values.get("href", "").startswith("#"):
            self.doc.use_refs.append(values["href"][1:])

    def _open_label(self, values: Attrs) -> None:
        self._label_depth += 1
        self._text = []
        if "for" in values:
            self.doc.label_targets.append(values["for"])

    def _open_control(self, tag: str, values: Attrs) -> None:
        self.doc.controls.append(Control(tag, values, self._label_depth > 0))
        if tag == "input" and self._label_depth > 0 and "value" in values:
            self._pending_value = values["value"]

    def handle_endtag(self, tag: str) -> None:
        if tag != "label" or self._label_depth == 0:
            return
        self._label_depth -= 1
        if self._pending_value is not None:
            self.doc.option_labels.append((self._pending_value, "".join(self._text).strip()))
            self._pending_value = None

    def handle_data(self, data: str) -> None:
        if self._label_depth > 0:
            self._text.append(data)


def read(html: str) -> Document:
    reader = Reader()
    reader.feed(html)
    reader.close()
    return reader.doc
