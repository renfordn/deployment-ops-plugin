#!/usr/bin/env python3
"""
Fetch a fixed list of Anthropic reference doc URLs into
references/anthropic-docs/*.md.

Each output file is prefixed with a `fetched_at: <ISO date>` header line
followed by the verbatim fetched content (no extra framing).

Run manually:

    python3 scripts/refresh_docs.py

This script is intentionally not imported by scripts/validate_plugin.py (or
anything else) -- it is a standalone, manually-triggered refresh utility.
"""

import datetime
import os
import sys

import requests

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DEFAULT_OUTPUT_DIR = os.path.join(REPO_ROOT, "references", "anthropic-docs")

# Fixed URL list, per design.md's Architecture `references/anthropic-docs/` listing.
DOCS = [
    ("sub-agents", "https://code.claude.com/docs/en/sub-agents"),
    ("plugins", "https://code.claude.com/docs/en/plugins"),
    ("plugins-reference", "https://code.claude.com/docs/en/plugins-reference"),
    ("skills", "https://code.claude.com/docs/en/skills"),
    ("hooks", "https://code.claude.com/docs/en/hooks"),
    ("plugin-evals", "https://code.claude.com/docs/en/plugin-evals"),
    ("best-practices", "https://code.claude.com/docs/en/best-practices"),
    ("agent-sdk-subagents", "https://code.claude.com/docs/en/agent-sdk/subagents"),
    ("agent-sdk-skills", "https://code.claude.com/docs/en/agent-sdk/skills"),
    ("python-sdk", "https://platform.claude.com/docs/en/cli-sdks-libraries/sdks/python"),
    ("middleware", "https://platform.claude.com/docs/en/cli-sdks-libraries/middleware"),
]


def fetch_doc(url):
    """Default fetch implementation: HTTP GET via `requests`, raising on error."""
    response = requests.get(url, timeout=30)
    response.raise_for_status()
    return response.text


def refresh_docs(output_dir=DEFAULT_OUTPUT_DIR, fetch=fetch_doc):
    """Fetch every doc in DOCS and write it to `<output_dir>/<name>.md`.

    A failure fetching one doc is caught and reported in the returned summary
    without discarding docs that fetched successfully in the same run.

    Returns a list of dicts: {"name": str, "status": "ok" | "error", "error": str?}
    """
    os.makedirs(output_dir, exist_ok=True)
    results = []

    for name, url in DOCS:
        try:
            content = fetch(url)
        except Exception as exc:  # noqa: BLE001 - report, don't crash the run
            results.append({"name": name, "status": "error", "error": str(exc)})
            continue

        fetched_at = datetime.datetime.now(datetime.timezone.utc).isoformat()
        path = os.path.join(output_dir, f"{name}.md")
        with open(path, "w", encoding="utf-8") as f:
            f.write(f"fetched_at: {fetched_at}\n{content}")

        results.append({"name": name, "status": "ok"})

    return results


def main():
    results = refresh_docs()

    failures = [r for r in results if r["status"] == "error"]
    for r in results:
        if r["status"] == "ok":
            print(f"[ok] {r['name']}")
        else:
            print(f"[error] {r['name']}: {r['error']}", file=sys.stderr)

    if failures:
        print(
            f"\n{len(failures)} of {len(results)} doc(s) failed to fetch.",
            file=sys.stderr,
        )
        return 1

    print(f"\nAll {len(results)} doc(s) fetched successfully.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
