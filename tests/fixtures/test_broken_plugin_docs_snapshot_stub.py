"""
Phase 10c (tasks.md): fixture best-practice-doc snapshot stub sanity check.

Confirms `tests/fixtures/broken-plugin/references/anthropic-docs/sub-agents.md` exists,
mirrors Phase 2's `scripts/refresh_docs.py` snapshot format (`fetched_at: <ISO date>`
header line followed by content), and has non-empty best-practice content after the
header so Phase 10d's best-practice-doc-deviation check has something deterministic to
run against without live network access.
"""

import os

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
SNAPSHOT_PATH = os.path.join(
    REPO_ROOT,
    "tests",
    "fixtures",
    "broken-plugin",
    "references",
    "anthropic-docs",
    "sub-agents.md",
)


def test_docs_snapshot_stub_exists_with_fetched_at_header_and_content():
    assert os.path.isfile(SNAPSHOT_PATH), f"expected snapshot stub at {SNAPSHOT_PATH}"

    with open(SNAPSHOT_PATH, "r", encoding="utf-8") as f:
        lines = f.readlines()

    assert lines, "snapshot stub must not be empty"
    assert lines[0].startswith("fetched_at: "), (
        "snapshot stub must start with a `fetched_at: <ISO date>` header line, "
        "matching scripts/refresh_docs.py's real snapshot format"
    )

    header_date = lines[0][len("fetched_at: "):].strip()
    assert header_date, "fetched_at header must carry a non-empty ISO date value"

    body = "".join(lines[1:]).strip()
    assert body, "snapshot stub must have non-empty best-practice content after the header"
