"""Live read-only smoke tests for the canonical CLI grammar."""

from __future__ import annotations

import pytest
import yaml
from click.testing import CliRunner

from twitter_cli.cli import cli

smoke = pytest.mark.smoke
runner = CliRunner()


def _invoke(*args: str):
    result = runner.invoke(cli, list(args))
    return result, yaml.safe_load(result.output) if result.output else None


@smoke
class TestReadOnly:
    def test_current_user(self):
        result, payload = _invoke("user")
        assert result.exit_code == 0, result.output
        assert payload["data"]["username"]
        assert payload["data"]["id"]

    def test_user(self):
        result, payload = _invoke("user", "elonmusk")
        assert result.exit_code == 0, result.output
        assert payload["data"]["username"]

    def test_search(self):
        result, payload = _invoke("search", "python", "--max", "3")
        assert result.exit_code == 0, result.output
        assert 1 <= len(payload["data"]) <= 3

    def test_user_posts(self):
        result, payload = _invoke("user", "elonmusk", "posts", "--max", "3")
        assert result.exit_code == 0, result.output
        assert len(payload["data"]) <= 3

    def test_feed(self):
        result, payload = _invoke("feed", "--max", "3")
        assert result.exit_code == 0, result.output
        assert 1 <= len(payload["data"]) <= 3

    def test_bookmarks(self):
        result, payload = _invoke("bookmarks", "--max", "3")
        assert result.exit_code == 0, result.output
        assert isinstance(payload["data"], list)
        assert len(payload["data"]) <= 3
