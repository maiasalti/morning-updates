"""Tests for _clean_json, the helper that turns Claude's reply into parseable JSON."""
import json
import os
import sys

# digest.py reads its secrets from the environment at import time.
for _key in ("ANTHROPIC_API_KEY", "NEWS_API_KEY", "EMAIL_SENDER",
             "EMAIL_PASSWORD", "EMAIL_RECIPIENT"):
    os.environ.setdefault(_key, "test-placeholder")

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "digest"))

from digest import _clean_json  # noqa: E402


def test_empty_list_followed_by_explanation_parses_as_empty_list():
    # Exact shape that broke the 2026-09-24 run: "[]", newline, prose.
    raw = "[]\nNone of the articles describe a model that was actually released."
    assert json.loads(_clean_json(raw)) == []


def test_array_with_prose_before_and_after_is_extracted():
    raw = ('Here are the stories:\n'
           '[{"title": "A", "summary": "s", "url": "u", "source": "x"}]\n'
           'Note: I skipped two funding rounds [see above].')
    assert json.loads(_clean_json(raw)) == [
        {"title": "A", "summary": "s", "url": "u", "source": "x"}
    ]


def test_markdown_fenced_array_still_parses():
    raw = '```json\n[{"title": "A"}]\n```'
    assert json.loads(_clean_json(raw)) == [{"title": "A"}]


def test_bare_valid_array_is_unchanged():
    raw = '[{"title": "A"}]'
    assert _clean_json(raw) == raw
