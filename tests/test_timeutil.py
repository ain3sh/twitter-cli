"""Tests for terminal-only time formatting."""

from __future__ import annotations

from twitter_cli.timeutil import format_local_time, format_relative_time

SAMPLE_TIMESTAMP = "Sat Mar 08 12:00:00 +0000 2026"


def test_format_local_time() -> None:
    result = format_local_time(SAMPLE_TIMESTAMP)

    assert result.startswith("2026-03-")
    assert ":" in result


def test_format_local_time_preserves_unparseable_values() -> None:
    assert format_local_time("") == ""
    assert format_local_time("not a date") == "not a date"


def test_format_relative_time() -> None:
    result = format_relative_time("Sat Jan 01 00:00:00 +0000 2020")

    assert result.endswith("ago")


def test_format_relative_time_preserves_unparseable_values() -> None:
    assert format_relative_time("") == ""
    assert format_relative_time("garbage") == "garbage"
