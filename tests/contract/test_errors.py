"""ErrorCode must equal the ERROR-HANDLING section 2 table (CONTRACTS section 3).

The table is the authority. This test parses it rather than restating it, so editing the
document without editing the enum fails, and the reverse.
"""

import re
from pathlib import Path
from typing import Final

import pytest

from wiggle_outside.core.errors import NOT_IN_V1, ErrorCode, NoticeId

pytestmark = pytest.mark.contract

# A row's first cell starts with the CODE, optionally followed by a parenthesised note.
ROW: Final = re.compile(r"^\|\s*([A-Z][A-Z0-9_]+)\s*(\([^)]*\))?\s*\|")
# ERROR-HANDLING marks a row that v1 never returns in that same note.
NOT_V1_MARKERS: Final = ("not in v1", "inactive", "not reached in v1")


def _table_rows(docs_dir: Path) -> dict[str, str]:
    """Map each code in the section 2 table to its parenthesised note (may be empty)."""
    text = (docs_dir / "ERROR-HANDLING.md").read_text(encoding="utf-8")
    start = text.index("## 2. Failure and recovery matrix")
    end = text.index("## 3. Backend responsibilities")
    rows: dict[str, str] = {}
    for line in text[start:end].splitlines():
        match = ROW.match(line)
        if match:
            rows[match.group(1)] = (match.group(2) or "").lower()
    return rows


def test_enum_members_equal_the_table(docs_dir: Path) -> None:
    assert set(_table_rows(docs_dir)) == {code.value for code in ErrorCode}


def test_enum_order_follows_the_table(docs_dir: Path) -> None:
    assert list(_table_rows(docs_dir)) == [code.value for code in ErrorCode]


def test_not_in_v1_matches_the_table_markers(docs_dir: Path) -> None:
    from_docs = {
        code
        for code, note in _table_rows(docs_dir).items()
        if any(marker in note for marker in NOT_V1_MARKERS)
    }
    assert from_docs == {code.value for code in NOT_IN_V1}


def test_values_equal_names() -> None:
    # The wire value is the code itself, so logs and the table never disagree.
    for code in ErrorCode:
        assert code.value == code.name
    for notice in NoticeId:
        assert notice.value == notice.name


def test_notice_ids_are_not_error_codes() -> None:
    # CONTRACTS section 2: NoticeId holds notices that are *not* in the table.
    assert not {n.value for n in NoticeId} & {c.value for c in ErrorCode}
