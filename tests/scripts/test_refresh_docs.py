"""
Phase 2 (tasks.md): refresh_docs.py fetches Anthropic reference docs into
references/anthropic-docs/*.md.

Covers:
- Happy path: given a mocked fetch layer, one file per doc is written with a
  `fetched_at:` header line followed by the verbatim mocked content.
- Partial failure: one mocked fetch fails, the others still succeed and are
  written, and the failure is reported in the returned summary without an
  unhandled exception.
"""

import os

import pytest

from scripts import refresh_docs


def test_refresh_docs_writes_one_file_per_doc_with_fetched_at_header(tmp_path):
    def fake_fetch(url):
        return f"mock content for {url}"

    results = refresh_docs.refresh_docs(output_dir=tmp_path, fetch=fake_fetch)

    assert len(results) == len(refresh_docs.DOCS)
    for name, url in refresh_docs.DOCS:
        path = tmp_path / f"{name}.md"
        assert path.is_file(), f"expected {path} to be written"

        text = path.read_text(encoding="utf-8")
        lines = text.splitlines()
        assert lines[0].startswith("fetched_at: ")
        remainder = "\n".join(lines[1:])
        assert remainder == f"mock content for {url}"

    assert all(r["status"] == "ok" for r in results)


def test_refresh_docs_reports_partial_failure_without_raising(tmp_path):
    failing_name = refresh_docs.DOCS[0][0]

    def flaky_fetch(url):
        for name, doc_url in refresh_docs.DOCS:
            if doc_url == url and name == failing_name:
                raise RuntimeError("simulated fetch failure")
        return f"mock content for {url}"

    results = refresh_docs.refresh_docs(output_dir=tmp_path, fetch=flaky_fetch)

    assert len(results) == len(refresh_docs.DOCS)

    failing_result = next(r for r in results if r["name"] == failing_name)
    assert failing_result["status"] == "error"
    assert "simulated fetch failure" in failing_result["error"]
    assert not (tmp_path / f"{failing_name}.md").exists()

    succeeding_results = [r for r in results if r["name"] != failing_name]
    assert all(r["status"] == "ok" for r in succeeding_results)
    for name, _ in refresh_docs.DOCS:
        if name == failing_name:
            continue
        assert (tmp_path / f"{name}.md").is_file()
