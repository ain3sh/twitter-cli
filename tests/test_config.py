from __future__ import annotations

from pathlib import Path

import pytest

from twitter_cli.config import DEFAULT_CONFIG, load_config
from twitter_cli.exceptions import InvalidInputError


def _write_config(root: Path, content: str) -> Path:
    path = root / "twitter-cli" / "config.yaml"
    path.parent.mkdir(parents=True)
    path.write_text(content, encoding="utf-8")
    return path


def test_load_config_reads_only_the_xdg_contract(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    _write_config(
        tmp_path,
        """fetch:
  count: 25
filter:
  lang: [en, zh]
  minScore: 10
  limit: 5
  weights:
    viewsLog: 2
""",
    )

    config = load_config()

    assert config["fetch"]["count"] == 25
    assert config["filter"]["lang"] == ["en", "zh"]
    assert config["filter"]["minScore"] == 10.0
    assert config["filter"]["limit"] == 5
    assert config["filter"]["weights"]["viewsLog"] == 2.0


def test_load_config_ignores_working_directory(monkeypatch, tmp_path: Path) -> None:
    working_dir = tmp_path / "work"
    working_dir.mkdir()
    (working_dir / "config.yaml").write_text("fetch:\n  count: 99\n", encoding="utf-8")
    config_home = tmp_path / "config"
    _write_config(config_home, "fetch:\n  count: 7\n")

    monkeypatch.chdir(working_dir)
    monkeypatch.setenv("XDG_CONFIG_HOME", str(config_home))

    assert load_config()["fetch"]["count"] == 7


def test_load_config_does_not_mutate_defaults(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))

    config = load_config()
    config["filter"]["weights"]["likes"] = 999

    assert DEFAULT_CONFIG["filter"]["weights"]["likes"] == 1.0


@pytest.mark.parametrize(
    ("content", "message"),
    [
        ("fetch: [", "Invalid YAML"),
        ("fetch:\n  count: -5\n", "fetch.count must be greater than 0"),
        ("filter:\n  lang: en\n", "filter.lang must be a list"),
        ("filter:\n  limit: 0\n", "filter.limit must be greater than 0"),
        ("filter:\n  weights:\n    likes: bad\n", "filter.weights.likes must be a number"),
        ("rateLimit:\n  maxRetries: bad\n", "rateLimit.maxRetries must be an integer"),
        ("unknown: true\n", "config has unknown keys"),
    ],
)
def test_load_config_rejects_malformed_current_contract(
    monkeypatch,
    tmp_path: Path,
    content: str,
    message: str,
) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    _write_config(tmp_path, content)

    with pytest.raises(InvalidInputError, match=message):
        load_config()
